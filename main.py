import uuid
import httpx
import logging
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from collections import deque
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from config import CONFIG

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 请求日志存储
request_logs = deque(maxlen=100)
stats = {"total": 0, "success": 0, "error": 0}
from converters import (
    anthropic_to_openai,
    openai_to_anthropic,
    make_anthropic_stream_events,
    StreamConverter,
)

app = FastAPI()
IFLOW_URL = CONFIG["base_url"]

def make_openai_error(status: int, message: str, err_type: str = "api_error"):
    return JSONResponse({"error": {"message": message, "type": err_type, "code": status}}, status_code=status)

def make_anthropic_error(status: int, message: str, err_type: str = "api_error"):
    return JSONResponse({"type": "error", "error": {"type": err_type, "message": message}}, status_code=status)

# 重试配置
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]

async def retry_request(client, method, url, **kwargs):
    """带重试的非流式请求"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = await getattr(client, method)(url, **kwargs)
            if resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                logger.warning(f"HTTP {resp.status_code}, 重试 {attempt+1}/{MAX_RETRIES}")
                await asyncio.sleep(RETRY_DELAYS[attempt])
                continue
            return resp
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"{type(e).__name__}, 重试 {attempt+1}/{MAX_RETRIES}")
                await asyncio.sleep(RETRY_DELAYS[attempt])
            else:
                raise

@asynccontextmanager
async def retry_stream(client, method, url, **kwargs):
    """带重试的流式请求"""
    for attempt in range(MAX_RETRIES):
        try:
            async with client.stream(method, url, **kwargs) as resp:
                if resp.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    logger.warning(f"HTTP {resp.status_code}, 重试 {attempt+1}/{MAX_RETRIES}")
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                yield resp
                return
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            if attempt >= MAX_RETRIES - 1:
                raise
            logger.warning(f"{type(e).__name__}, 重试 {attempt+1}/{MAX_RETRIES}")
            await asyncio.sleep(RETRY_DELAYS[attempt])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.now()
    headers = dict(request.headers) if not request.url.path.startswith("/admin") else {}
    body_for_log = None
    if request.method == "POST" and not request.url.path.startswith("/admin"):
        full_body = await request.body()
        body_for_log = full_body.decode("utf-8", errors="ignore")[:8000]
        # 保留完整请求体供后续处理
        async def receive():
            return {"type": "http.request", "body": full_body}
        request = Request(request.scope, receive)

    response = await call_next(request)
    if not request.url.path.startswith("/admin") and request.url.path not in ["/v1/chat/completions", "/v1/messages"]:
        stats["total"] += 1
        if response.status_code < 400:
            stats["success"] += 1
        else:
            stats["error"] += 1
        request_logs.appendleft({
            "time": start.strftime("%H:%M:%S"),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "headers": headers,
            "body": body_for_log
        })
    return response

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>iFlow2API 控制台</title>
    <style>
        :root {
            --bg-body: #0f172a;
            --bg-card: #1e293b;
            --bg-hover: #334155;
            --text-main: #f1f5f9;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --danger: #ef4444;
            --success: #22c55e;
            --warning: #f59e0b;
            --border: #334155;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background: var(--bg-body); color: var(--text-main); line-height: 1.5; font-size: 14px; }
        
        /* Layout */
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }
        h1 { font-size: 1.5rem; font-weight: 700; background: linear-gradient(to right, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        
        /* Stats Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .card { background: var(--bg-card); border-radius: 12px; padding: 20px; border: 1px solid var(--border); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); transition: transform 0.2s; }
        .card:hover { transform: translateY(-2px); }
        .stat-label { color: var(--text-muted); font-size: 0.875rem; margin-bottom: 8px; }
        .stat-value { font-size: 1.875rem; font-weight: 700; color: var(--text-main); }
        .stat-value.success { color: var(--success); }
        .stat-value.error { color: var(--danger); }
        
        /* Models Section */
        .models-container { margin-bottom: 24px; }
        .section-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
        .chip-container { display: flex; flex-wrap: wrap; gap: 8px; }
        .chip { background: var(--bg-hover); padding: 6px 12px; border-radius: 9999px; font-size: 0.85rem; color: var(--text-main); border: 1px solid var(--border); }
        
        /* Logs Toolbar */
        .toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
        input[type="text"] { background: var(--bg-card); border: 1px solid var(--border); color: var(--text-main); padding: 8px 12px; border-radius: 6px; width: 300px; outline: none; transition: border-color 0.2s; }
        input[type="text"]:focus { border-color: var(--primary); }
        .btn { padding: 8px 16px; border-radius: 6px; border: none; font-weight: 500; cursor: pointer; transition: background 0.2s; font-size: 0.875rem; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-danger { background: rgba(239, 68, 68, 0.1); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.2); }
        .btn-danger:hover { background: rgba(239, 68, 68, 0.2); }
        .btn-icon { padding: 8px; background: transparent; color: var(--text-muted); }
        .btn-icon:hover { color: var(--text-main); background: var(--bg-hover); }

        /* Logs List */
        .logs-wrapper { background: var(--bg-card); border-radius: 12px; border: 1px solid var(--border); overflow: hidden; }
        .log-item { border-bottom: 1px solid var(--border); transition: background 0.15s; }
        .log-item:last-child { border-bottom: none; }
        .log-header { padding: 12px 16px; display: grid; grid-template-columns: 80px 80px 1fr 80px 150px; align-items: center; gap: 12px; cursor: pointer; }
        .log-header:hover { background: var(--bg-hover); }
        
        .badge { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; text-align: center; }
        .badge-2xx { background: rgba(34, 197, 94, 0.15); color: var(--success); }
        .badge-4xx { background: rgba(245, 158, 11, 0.15); color: var(--warning); }
        .badge-5xx { background: rgba(239, 68, 68, 0.15); color: var(--danger); }
        
        .method { font-family: monospace; font-weight: 700; color: var(--text-muted); }
        .path { font-family: monospace; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .time { color: var(--text-muted); font-size: 0.85rem; }
        .model-tag { font-size: 0.8rem; color: var(--primary); background: rgba(59, 130, 246, 0.1); padding: 2px 6px; border-radius: 4px; justify-self: start;}

        /* Log Detail */
        .log-detail { display: none; padding: 16px; background: #0b1120; border-top: 1px solid var(--border); font-family: 'Fira Code', monospace; font-size: 0.85rem; }
        .log-detail.active { display: block; }
        .detail-section { margin-bottom: 16px; }
        .detail-title { color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; display: flex; justify-content: space-between; }
        .code-block { background: #1e293b; padding: 12px; border-radius: 6px; overflow-x: auto; color: #e2e8f0; white-space: pre-wrap; word-break: break-all; border: 1px solid #334155; }
        .copy-btn { font-size: 0.7rem; background: transparent; border: 1px solid var(--border); color: var(--text-muted); padding: 2px 6px; border-radius: 4px; cursor: pointer; }
        .copy-btn:hover { color: var(--text-main); border-color: var(--text-muted); }
        
        .empty-state { padding: 40px; text-align: center; color: var(--text-muted); }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-body); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 iFlow2API Dashboard</h1>
            <div style="display: flex; gap: 10px; align-items: center;">
                <span id="status-indicator" style="width: 8px; height: 8px; background: var(--success); border-radius: 50%; box-shadow: 0 0 8px var(--success);"></span>
                <span style="font-size: 0.9rem; color: var(--text-muted);">运行中</span>
            </div>
        </header>

        <div class="stats-grid">
            <div class="card">
                <div class="stat-label">总请求数</div>
                <div class="stat-value" id="total">0</div>
            </div>
            <div class="card">
                <div class="stat-label">成功</div>
                <div class="stat-value success" id="success">0</div>
            </div>
            <div class="card">
                <div class="stat-label">错误</div>
                <div class="stat-value error" id="error">0</div>
            </div>
            <div class="card">
                <div class="stat-label">成功率</div>
                <div class="stat-value" id="rate">-</div>
            </div>
        </div>

        <div class="models-container">
            <div class="section-title">📦 可用模型</div>
            <div class="card">
                <div id="models" class="chip-container">加载中...</div>
            </div>
        </div>

        <div class="section-title">
            📋 请求日志
            <div style="flex: 1"></div>
            <div class="toolbar" style="margin-bottom: 0;">
                <input type="text" id="filter" placeholder="🔍 搜索模型、路径..." oninput="filterLogs()">
                <button class="btn btn-danger" onclick="clearLogs()">清空日志</button>
                <button class="btn btn-primary" onclick="refresh()">刷新</button>
            </div>
        </div>

        <div class="logs-wrapper">
            <div id="logs"></div>
        </div>
    </div>

    <script>
        let allLogs = [];
        let isAutoRefresh = true;

        function toggle(index) {
            const detail = document.getElementById(`detail-${index}`);
            const isActive = detail.style.display === 'block';
            detail.style.display = isActive ? 'none' : 'block';
        }

        function getStatusClass(status) {
            if (status < 400) return 'badge-2xx';
            if (status < 500) return 'badge-4xx';
            return 'badge-5xx';
        }

        function formatJson(obj) {
            if (!obj) return '';
            try {
                if (typeof obj === 'string') return escapeHtml(obj);
                return JSON.stringify(obj, null, 2);
            } catch (e) { return escapeHtml(String(obj)); }
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                // simple feedback could be added here
            });
        }

        function renderLogs(logs) {
            const container = document.getElementById('logs');
            if (logs.length === 0) {
                container.innerHTML = '<div class="empty-state">暂无日志记录</div>';
                return;
            }

            container.innerHTML = logs.map((l, i) => {
                const statusClass = getStatusClass(l.status);
                
                // Details construction
                let detailsHtml = '';
                
                if (l.headers) {
                    const content = JSON.stringify(l.headers, null, 2);
                    detailsHtml += `
                        <div class="detail-section">
                            <div class="detail-title">Headers <button class="copy-btn" onclick="event.stopPropagation();copyToClipboard('${escapeJs(content)}')">Copy</button></div>
                            <div class="code-block">${escapeHtml(content)}</div>
                        </div>`;
                }
                
                if (l.body) {
                    const content = l.body; 
                    detailsHtml += `
                        <div class="detail-section">
                            <div class="detail-title">Request Body <button class="copy-btn" onclick="event.stopPropagation();copyToClipboard('${escapeJs(content)}')">Copy</button></div>
                            <div class="code-block">${escapeHtml(content)}</div>
                        </div>`;
                }

                if (l.reasoning) {
                     detailsHtml += `
                        <div class="detail-section">
                            <div class="detail-title" style="color:#a78bfa">🧠 Thinking Process</div>
                            <div class="code-block" style="border-color: #a78bfa33;">${escapeHtml(l.reasoning)}</div>
                        </div>`;
                }

                if (l.content) {
                     detailsHtml += `
                        <div class="detail-section">
                            <div class="detail-title" style="color:#34d399">💬 Response Content</div>
                            <div class="code-block" style="border-color: #34d39933;">${escapeHtml(l.content)}</div>
                        </div>`;
                }

                return `
                <div class="log-item">
                    <div class="log-header" onclick="toggle(${i})">
                        <span class="time">${l.time}</span>
                        <span class="method">${l.method}</span>
                        <span class="path" title="${l.path}">${l.path}</span>
                        <span class="badge ${statusClass}">${l.status}</span>
                        ${l.model ? `<span class="model-tag">${l.model}</span>` : '<span></span>'}
                    </div>
                    <div class="log-detail" id="detail-${i}">
                        ${detailsHtml || '<div style="color:var(--text-muted)">无详细信息</div>'}
                    </div>
                </div>`;
            }).join('');
        }

        function escapeHtml(text) {
            if (!text) return '';
            return text.replace(/&/g, "&amp;")
                       .replace(/</g, "&lt;")
                       .replace(/>/g, "&gt;")
                       .replace(/"/g, "&quot;")
                       .replace(/'/g, "&#039;");
        }
        
        function escapeJs(text) {
             if (!text) return '';
             return text.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'").replace(/"/g, '\\\\"').replace(/\\n/g, '\\\\n').replace(/\\r/g, '\\\\r');
        }

        function filterLogs() {
            const q = document.getElementById('filter').value.toLowerCase();
            const filtered = allLogs.filter(l => 
                (l.model || '').toLowerCase().includes(q) || 
                (l.path || '').toLowerCase().includes(q) ||
                (l.method || '').toLowerCase().includes(q)
            );
            renderLogs(filtered);
        }

        async function refresh() {
            try {
                const s = await (await fetch('/admin/stats')).json();
                document.getElementById('total').textContent = s.total;
                document.getElementById('success').textContent = s.success;
                document.getElementById('error').textContent = s.error;
                document.getElementById('rate').textContent = s.total > 0 ? Math.round(s.success / s.total * 100) + '%' : '-';
                
                allLogs = await (await fetch('/admin/logs')).json();
                filterLogs();
            } catch (e) {
                console.error("Failed to refresh stats", e);
            }
        }

        async function clearLogs() {
            if (confirm('确定清空所有日志?')) {
                await fetch('/admin/logs', { method: 'DELETE' });
                refresh();
            }
        }

        async function loadModels() {
            const container = document.getElementById('models');
            try {
                // container.innerHTML = '<span style="color:var(--text-muted)">加载中...</span>';
                const res = await fetch('/v1/models?t=' + Date.now());
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const m = await res.json();
                
                if (m.data && Array.isArray(m.data) && m.data.length) {
                    container.innerHTML = m.data.map(x => `<span class="chip">${x.id}</span>`).join('');
                } else {
                    container.innerHTML = '<span style="color:var(--text-muted)">无可用模型 (列表为空)</span>';
                    console.log('Models data empty:', m);
                }
            } catch (e) {
                console.error("Load models failed:", e);
                container.innerHTML = `<span style="color:var(--danger)">加载失败: ${e.message}</span>`;
            }
        }

        // Init
        refresh();
        loadModels();
        setInterval(refresh, 3000);
    </script>
</body>
</html>"""

@app.get("/admin/stats")
async def get_stats():
    return stats

@app.get("/admin/logs")
async def get_logs():
    return list(request_logs)

@app.delete("/admin/logs")
async def clear_logs():
    request_logs.clear()
    stats["total"] = stats["success"] = stats["error"] = 0
    return {"status": "ok"}

HEADERS = {
    "user-agent": "iFlow-Cli",
    "Content-Type": "application/json",
}

def get_auth_headers(request: Request):
    # 始终使用配置文件的 API key，忽略客户端传来的
    return {**HEADERS, "Authorization": f"Bearer {CONFIG['api_key']}"}

@app.get("/v1/models")
async def models(request: Request):
    # iFlow CLI 支持的模型列表 (硬编码，因为 API 不返回完整列表)
    model_list = [
        "glm-4.7", "iFlow-ROME-30BA3B", "deepseek-v3.2-chat", "qwen3-coder-plus",
        "kimi-k2-thinking", "minimax-m2.1", "kimi-k2-0905", "glm-4.6",
        "deepseek-r1", "deepseek-v3", "qwen3-max", "qwen3-235b"
    ]
    import time
    return {
        "object": "list",
        "data": [{"id": m, "object": "model", "created": int(time.time()), "owned_by": "iflow"} for m in model_list]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except:
        return make_openai_error(400, "Invalid JSON", "invalid_request_error")
    headers = get_auth_headers(request)
    model = body.get("model", "unknown")
    # 设置合理的 max_tokens 下限，但尊重客户端设置
    body["max_tokens"] = max(body.get("max_tokens", 4096), 1024)
    body["thinking"] = {"type": "enabled", "budget_tokens": body.get("max_tokens", 8000)}

    try:
        if body.get("stream"):
            import json as _json
            reasoning_parts = []
            content_parts = []
            async def stream():
                async with httpx.AsyncClient() as client:
                    async with retry_stream(client, "POST", f"{IFLOW_URL}/chat/completions", json=body, headers=headers, timeout=120) as resp:
                        async for line in resp.aiter_lines():
                            if line and line.startswith("data: ") and not line.endswith("[DONE]"):
                                try:
                                    chunk = _json.loads(line[6:])
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    if delta.get("reasoning_content"):
                                        reasoning_parts.append(delta["reasoning_content"])
                                    if delta.get("content"):
                                        content_parts.append(delta["content"])
                                except: pass
                            if line:
                                yield line + "\n\n"
                request_logs.appendleft({
                    "time": datetime.now().strftime("%H:%M:%S"), "method": "POST", "path": "/v1/chat/completions",
                    "status": 200, "model": model, "reasoning": "".join(reasoning_parts)[:3000], "content": "".join(content_parts)[:1000]
                })
                stats["total"] += 1; stats["success"] += 1
            return StreamingResponse(stream(), media_type="text/event-stream")

        async with httpx.AsyncClient() as client:
            resp = await retry_request(client, "post", f"{IFLOW_URL}/chat/completions", json=body, headers=headers, timeout=120)
            data = resp.json()
            reasoning = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            request_logs.appendleft({
                "time": datetime.now().strftime("%H:%M:%S"), "method": "POST", "path": "/v1/chat/completions",
                "status": resp.status_code, "model": model, "reasoning": reasoning[:3000], "content": content[:1000]
            })
            stats["total"] += 1
            stats["success" if resp.status_code < 400 else "error"] += 1
            return data
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        stats["total"] += 1; stats["error"] += 1
        return make_openai_error(503, f"Upstream service unavailable: {type(e).__name__}", "service_unavailable")
    except Exception as e:
        stats["total"] += 1; stats["error"] += 1
        return make_openai_error(500, str(e), "internal_error")

@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    try:
        body = await request.json()
    except:
        return make_anthropic_error(400, "Invalid JSON", "invalid_request_error")
    openai_req = anthropic_to_openai(body)
    headers = get_auth_headers(request)
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    model = body.get("model", "")
    # 设置合理的 max_tokens 下限，但尊重客户端设置
    openai_req["max_tokens"] = max(openai_req.get("max_tokens", 4096), 1024)
    openai_req["thinking"] = {"type": "enabled", "budget_tokens": openai_req.get("max_tokens", 8000)}

    try:
        if body.get("stream"):
            import json as _json
            reasoning_parts = []
            content_parts = []
            async def stream():
                for event in make_anthropic_stream_events(model, msg_id):
                    yield event
                converter = StreamConverter()
                async with httpx.AsyncClient() as client:
                    async with retry_stream(client, "POST", f"{IFLOW_URL}/chat/completions", json=openai_req, headers=headers, timeout=120) as resp:
                        async for line in resp.aiter_lines():
                            if line and line.startswith("data: ") and not line.endswith("[DONE]"):
                                try:
                                    chunk = _json.loads(line[6:])
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    if delta.get("reasoning_content"):
                                        reasoning_parts.append(delta["reasoning_content"])
                                    if delta.get("content"):
                                        content_parts.append(delta["content"])
                                except: pass
                            if line:
                                for event in converter.convert_chunk(line):
                                    yield event
                for event in converter.finish():
                    yield event
                request_logs.appendleft({
                    "time": datetime.now().strftime("%H:%M:%S"), "method": "POST", "path": "/v1/messages",
                    "status": 200, "model": model, "reasoning": "".join(reasoning_parts)[:3000], "content": "".join(content_parts)[:1000]
                })
                stats["total"] += 1; stats["success"] += 1
            return StreamingResponse(stream(), media_type="text/event-stream")

        async with httpx.AsyncClient() as client:
            resp = await retry_request(client, "post", f"{IFLOW_URL}/chat/completions", json=openai_req, headers=headers, timeout=120)
            data = resp.json()
            reasoning = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            request_logs.appendleft({
                "time": datetime.now().strftime("%H:%M:%S"), "method": "POST", "path": "/v1/messages",
                "status": resp.status_code, "model": model, "reasoning": reasoning[:3000], "content": content[:1000]
            })
            stats["total"] += 1
            stats["success" if resp.status_code < 400 else "error"] += 1
            return JSONResponse(openai_to_anthropic(data))
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        stats["total"] += 1; stats["error"] += 1
        return make_anthropic_error(503, f"Upstream service unavailable: {type(e).__name__}", "service_unavailable")
    except Exception as e:
        stats["total"] += 1; stats["error"] += 1
        return make_anthropic_error(500, str(e), "internal_error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
