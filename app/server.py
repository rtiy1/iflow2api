import uuid
import logging
import asyncio
import os
import time
import json
import platform
import psutil
import sys
import httpx
from typing import Any, Dict
from datetime import datetime
from contextlib import asynccontextmanager
from collections import deque
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from core.config import CONFIG
from proxy.proxy import get_proxy

start_time = time.time()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# 请求日志存储（提高容量，减少高频请求下的日志丢失）
request_logs = deque(maxlen=300)
stats = {"total": 0, "success": 0, "error": 0}
from converters import (
    anthropic_to_openai,
    openai_to_anthropic_nonstream,
    StreamConverter,
)

app = FastAPI()


def _truncate_text(value: Any, limit: int = 4000) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated)"


def _safe_json_dump(value: Any, limit: int = 4000) -> str:
    try:
        dumped = json.dumps(value, ensure_ascii=False)
    except Exception:
        dumped = str(value)
    return _truncate_text(dumped, limit)


def _sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    redacted = {}
    sensitive_keys = {
        "authorization",
        "x-api-key",
        "api-key",
        "cookie",
        "set-cookie",
        "proxy-authorization",
    }
    for key, value in headers.items():
        if key.lower() in sensitive_keys:
            redacted[key] = "***"
        else:
            redacted[key] = _truncate_text(value, 500)
    return redacted


def _elapsed_ms(start_ts: float) -> int:
    return max(0, int((time.perf_counter() - start_ts) * 1000))


def _append_request_log(
    *,
    method: str,
    path: str,
    status: int,
    model: str,
    request_id: str,
    latency_ms: int,
    headers: Dict[str, str] | None = None,
    body: str = "",
    reasoning: str = "",
    content: str = "",
    error: str = "",
    effective_model: str = "",
    upstream_status: int | None = None,
) -> None:
    entry: Dict[str, Any] = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "method": method,
        "path": path,
        "status": status,
        "model": model,
        "request_id": request_id,
        "latency_ms": latency_ms,
    }

    if headers:
        entry["headers"] = headers
    if body:
        entry["body"] = _truncate_text(body, 4000)
    if reasoning:
        entry["reasoning"] = _truncate_text(reasoning, 3000)
    if content:
        entry["content"] = _truncate_text(content, 1000)
    if error:
        entry["error"] = _truncate_text(error, 2000)
    if effective_model:
        entry["effective_model"] = effective_model
    if upstream_status is not None:
        entry["upstream_status"] = upstream_status

    request_logs.appendleft(entry)

def make_openai_error(status: int, message: str, err_type: str = "api_error"):
    return JSONResponse({"error": {"message": message, "type": err_type, "code": status}}, status_code=status)

def make_anthropic_error(status: int, message: str, err_type: str = "api_error"):
    return JSONResponse({"type": "error", "error": {"type": err_type, "message": message}}, status_code=status)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
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

        /* System Info */
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }
        .info-item { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: var(--bg-hover); border-radius: 8px; }
        .info-label { color: var(--text-muted); font-size: 0.9rem; }
        .info-value { color: var(--text-main); font-weight: 600; font-family: monospace; }

        /* Usage Examples */
        .usage-section { margin-top: 24px; }
        .example-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
        .example-title { font-size: 1rem; font-weight: 600; margin-bottom: 8px; color: var(--primary); }
        .example-code { background: #0b1120; padding: 12px; border-radius: 6px; overflow-x: auto; font-family: monospace; font-size: 0.85rem; color: #e2e8f0; border: 1px solid var(--border); }
        
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

        <div class="models-container">
            <div class="section-title">⚙️ 系统信息</div>
            <div class="card">
                <div class="info-grid" id="sysinfo">
                    <div class="info-item"><span class="info-label">Python版本</span><span class="info-value" id="pyVersion">--</span></div>
                    <div class="info-item"><span class="info-label">平台</span><span class="info-value" id="platform">--</span></div>
                    <div class="info-item"><span class="info-label">CPU使用</span><span class="info-value" id="cpu">--</span></div>
                    <div class="info-item"><span class="info-label">内存使用</span><span class="info-value" id="memory">--</span></div>
                    <div class="info-item"><span class="info-label">运行时间</span><span class="info-value" id="uptime">--</span></div>
                    <div class="info-item"><span class="info-label">进程PID</span><span class="info-value" id="pid">--</span></div>
                </div>
            </div>
        </div>

        <div class="usage-section">
            <div class="section-title">📖 API 使用示例</div>
            <div class="example-card">
                <div class="example-title">OpenAI 格式 - 对话补全</div>
                <div class="example-code">curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "glm-4.7",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'</div>
            </div>
            <div class="example-card">
                <div class="example-title">Anthropic 格式 - 消息对话</div>
                <div class="example-code">curl http://localhost:8000/v1/messages \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "deepseek-v3",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello"}]
  }'</div>
            </div>
            <div class="example-card">
                <div class="example-title">思考模式 - GLM-4.7</div>
                <div class="example-code">curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "glm-4.7",
    "messages": [{"role": "user", "content": "解释量子纠缠"}],
    "reasoning_effort": "high"
  }'</div>
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

                if (l.request_id || l.latency_ms !== undefined || l.effective_model || l.upstream_status !== undefined) {
                    const meta = {
                        request_id: l.request_id || '',
                        latency_ms: l.latency_ms ?? '',
                        effective_model: l.effective_model || l.model || '',
                        upstream_status: l.upstream_status ?? ''
                    };
                    const content = JSON.stringify(meta, null, 2);
                    detailsHtml += `
                        <div class="detail-section">
                            <div class="detail-title">Meta <button class="copy-btn" onclick="event.stopPropagation();copyToClipboard('${escapeJs(content)}')">Copy</button></div>
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

                if (l.error) {
                    detailsHtml += `
                        <div class="detail-section">
                            <div class="detail-title" style="color:#ef4444">❌ Error</div>
                            <div class="code-block" style="border-color: #ef444433;">${escapeHtml(l.error)}</div>
                        </div>`;
                }

                return `
                <div class="log-item">
                    <div class="log-header" onclick="toggle(${i})">
                        <span class="time">${l.time}</span>
                        <span class="method">${l.method}</span>
                        <span class="path" title="${l.path}">${l.path}</span>
                        <span class="badge ${statusClass}">${l.status}</span>
                        ${(l.effective_model || l.model) ? `<span class="model-tag">${l.effective_model || l.model}${(l.latency_ms !== undefined && l.latency_ms !== null) ? ` · ${l.latency_ms}ms` : ''}</span>` : '<span></span>'}
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
                (l.method || '').toLowerCase().includes(q) ||
                (l.request_id || '').toLowerCase().includes(q)
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
                const res = await fetch('/v1/models?t=' + Date.now());
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const m = await res.json();

                if (m.data && Array.isArray(m.data) && m.data.length) {
                    container.innerHTML = m.data.map(x => `<span class="chip">${x.id}</span>`).join('');
                } else {
                    container.innerHTML = '<span style="color:var(--text-muted)">无可用模型 (列表为空)</span>';
                }
            } catch (e) {
                console.error("Load models failed:", e);
                container.innerHTML = `<span style="color:var(--danger)">加载失败: ${e.message}</span>`;
            }
        }

        async function loadSystemInfo() {
            try {
                const info = await (await fetch('/admin/sysinfo')).json();
                document.getElementById('pyVersion').textContent = info.python_version;
                document.getElementById('platform').textContent = info.platform;
                document.getElementById('cpu').textContent = info.cpu_percent + '%';
                document.getElementById('memory').textContent = info.memory_percent + '%';
                document.getElementById('uptime').textContent = info.uptime;
                document.getElementById('pid').textContent = info.pid;
            } catch (e) {
                console.error("Load system info failed:", e);
            }
        }

        // Init
        refresh();
        loadModels();
        loadSystemInfo();
        setInterval(refresh, 3000);
        setInterval(loadSystemInfo, 5000);
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

@app.get("/admin/sysinfo")
async def get_sysinfo():
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    uptime_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": f"{platform.system()} {platform.release()}",
        "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
        "memory_percent": round(psutil.virtual_memory().percent, 1),
        "uptime": uptime_str,
        "pid": os.getpid()
    }

@app.get("/health")
@app.get("/v1/health")
async def health_check():
    return {"status": "ok", "service": "iflow2api"}

@app.get("/v1/models")
async def models(request: Request):
    proxy = get_proxy()
    return await proxy.get_models()

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request_started = time.perf_counter()
    headers_for_log = _sanitize_headers(dict(request.headers))
    body_for_log = ""

    try:
        body_bytes = await request.body()
        body = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        stats["total"] += 1
        stats["error"] += 1
        _append_request_log(
            method="POST",
            path="/v1/chat/completions",
            status=400,
            model="unknown",
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            error=f"Invalid JSON: {e}",
        )
        return make_openai_error(400, f"Invalid JSON: {e}", "invalid_request_error")
    except Exception:
        stats["total"] += 1
        stats["error"] += 1
        _append_request_log(
            method="POST",
            path="/v1/chat/completions",
            status=400,
            model="unknown",
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            error="Invalid JSON",
        )
        return make_openai_error(400, "Invalid JSON", "invalid_request_error")

    model = body.get("model", "unknown")
    body_for_log = _safe_json_dump(body)
    body["max_tokens"] = max(body.get("max_tokens", 4096), 1024)

    # 验证消息数组
    messages = body.get("messages", [])
    if not messages or not isinstance(messages, list):
        stats["total"] += 1
        stats["error"] += 1
        _append_request_log(
            method="POST",
            path="/v1/chat/completions",
            status=400,
            model=model,
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            body=body_for_log,
            error="messages array is required and must be non-empty",
            effective_model=model,
        )
        return make_openai_error(400, "messages array is required and must be non-empty", "invalid_request_error")

    logger.info(f"Request model={model}, thinking={body.get('thinking')}, has_tools={bool(body.get('tools'))}")

    try:
        proxy = get_proxy()

        if body.get("stream"):
            body["stream_options"] = {"include_usage": True}
            reasoning_parts = []
            content_parts = []

            async def stream():
                try:
                    MAX_CONTINUATIONS = 5
                    continuation_count = 0
                    current_body = body.copy()
                    accumulated_content = ""
                    accumulated_reasoning = ""

                    while continuation_count <= MAX_CONTINUATIONS:
                        last_finish_reason = None

                        async for chunk in await proxy.proxy_request("/chat/completions", current_body, model, stream=True):
                            line = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                            if line and line.startswith("data: ") and not line.endswith("[DONE]"):
                                try:
                                    data = json.loads(line[6:])
                                    choice = data.get("choices", [{}])[0]
                                    delta = choice.get("delta", {})
                                    last_finish_reason = choice.get("finish_reason")

                                    if delta.get("reasoning_content"):
                                        reasoning_parts.append(delta["reasoning_content"])
                                        accumulated_reasoning += delta["reasoning_content"]
                                        logger.info(f"[Thinking] {delta['reasoning_content'][:100]}")
                                    if delta.get("content"):
                                        content_parts.append(delta["content"])
                                        accumulated_content += delta["content"]
                                except Exception as e:
                                    logger.warning(f"Parse chunk error: {e}")

                            # 不发送 [DONE]，由续写逻辑控制
                            if line and "[DONE]" not in line:
                                yield line if line.endswith("\n\n") else line + "\n\n"

                        # 检查是否需要续写
                        if last_finish_reason != "length":
                            break

                        continuation_count += 1
                        if continuation_count > MAX_CONTINUATIONS:
                            break

                        logger.info(f"流式输出被截断，自动续写 ({continuation_count}/{MAX_CONTINUATIONS})")

                        # 追加已生成的内容，继续请求
                        assistant_msg = {"role": "assistant", "content": accumulated_content}
                        if accumulated_reasoning:
                            assistant_msg["reasoning_content"] = accumulated_reasoning
                        current_body["messages"] = current_body.get("messages", []) + [assistant_msg]

                    # 发送最终的 [DONE]
                    yield "data: [DONE]\n\n"

                    stats["total"] += 1
                    stats["success"] += 1
                    _append_request_log(
                        method="POST",
                        path="/v1/chat/completions",
                        status=200,
                        model=model,
                        request_id=request_id,
                        latency_ms=_elapsed_ms(request_started),
                        headers=headers_for_log,
                        body=body_for_log,
                        reasoning="".join(reasoning_parts),
                        content="".join(content_parts),
                        effective_model=model,
                    )
                except httpx.HTTPStatusError as e:
                    stats["total"] += 1
                    stats["error"] += 1
                    upstream_status = e.response.status_code
                    _append_request_log(
                        method="POST",
                        path="/v1/chat/completions",
                        status=502,
                        model=model,
                        request_id=request_id,
                        latency_ms=_elapsed_ms(request_started),
                        headers=headers_for_log,
                        body=body_for_log,
                        error=f"Upstream API error: HTTP {upstream_status}",
                        effective_model=model,
                        upstream_status=upstream_status,
                    )
                    logger.error(f"上游 API 返回错误 HTTP {upstream_status} for model={model}: {e}")
                    raise
                except Exception as e:
                    stats["total"] += 1
                    stats["error"] += 1
                    _append_request_log(
                        method="POST",
                        path="/v1/chat/completions",
                        status=500,
                        model=model,
                        request_id=request_id,
                        latency_ms=_elapsed_ms(request_started),
                        headers=headers_for_log,
                        body=body_for_log,
                        error=f"{type(e).__name__}: {e}",
                        effective_model=model,
                    )
                    logger.error(f"请求处理失败 for model={model}: {type(e).__name__}: {e}")
                    raise

            return StreamingResponse(stream(), media_type="text/event-stream")

        data = await proxy.proxy_request("/chat/completions", body, model, stream=False)
        logger.info(f"Non-stream response usage: {data.get('usage')}")

        # 自动续写：当因 max_tokens 截断时，继续请求
        MAX_CONTINUATIONS = 5
        continuation_count = 0
        while continuation_count < MAX_CONTINUATIONS:
            choice = data.get("choices", [{}])[0]
            finish_reason = choice.get("finish_reason")
            if finish_reason != "length":
                break

            continuation_count += 1
            logger.info(f"输出被截断，自动续写 ({continuation_count}/{MAX_CONTINUATIONS})")

            # 将当前回复追加到消息中，继续请求
            assistant_msg = choice.get("message", {})
            body["messages"] = body.get("messages", []) + [assistant_msg]

            next_data = await proxy.proxy_request("/chat/completions", body, model, stream=False)

            # 合并内容
            next_choice = next_data.get("choices", [{}])[0]
            next_msg = next_choice.get("message", {})

            # 合并 content
            if next_msg.get("content"):
                current_content = assistant_msg.get("content", "") or ""
                assistant_msg["content"] = current_content + next_msg["content"]

            # 合并 reasoning_content
            if next_msg.get("reasoning_content"):
                current_reasoning = assistant_msg.get("reasoning_content", "") or ""
                assistant_msg["reasoning_content"] = current_reasoning + next_msg["reasoning_content"]

            # 更新 finish_reason 和 usage
            choice["finish_reason"] = next_choice.get("finish_reason")
            choice["message"] = assistant_msg
            if next_data.get("usage"):
                prev_usage = data.get("usage", {})
                next_usage = next_data.get("usage", {})
                data["usage"] = {
                    "prompt_tokens": next_usage.get("prompt_tokens", 0),
                    "completion_tokens": prev_usage.get("completion_tokens", 0) + next_usage.get("completion_tokens", 0),
                    "total_tokens": next_usage.get("prompt_tokens", 0) + prev_usage.get("completion_tokens", 0) + next_usage.get("completion_tokens", 0)
                }
            data["choices"][0] = choice

        reasoning = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        stats["total"] += 1
        stats["success"] += 1
        _append_request_log(
            method="POST",
            path="/v1/chat/completions",
            status=200,
            model=model,
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            body=body_for_log,
            reasoning=reasoning,
            content=content,
            effective_model=model,
        )
        return data
    except httpx.HTTPStatusError as e:
        stats["total"] += 1
        stats["error"] += 1
        status_code = e.response.status_code
        _append_request_log(
            method="POST",
            path="/v1/chat/completions",
            status=502,
            model=model,
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            body=body_for_log,
            error=f"Upstream API error: HTTP {status_code}",
            effective_model=model,
            upstream_status=status_code,
        )
        logger.error(f"上游 API 返回错误 HTTP {status_code} for model={model}: {e}")
        return make_openai_error(502, f"Upstream API error: HTTP {status_code}", "upstream_error")
    except Exception as e:
        stats["total"] += 1
        stats["error"] += 1
        _append_request_log(
            method="POST",
            path="/v1/chat/completions",
            status=500,
            model=model,
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            body=body_for_log,
            error=f"{type(e).__name__}: {e}",
            effective_model=model,
        )
        logger.error(f"请求处理失败 for model={model}: {type(e).__name__}: {e}")
        return make_openai_error(500, str(e), "internal_error")

@app.post("/v1/messages/count_tokens")
async def count_tokens(request: Request):
    try:
        body = await request.json()
    except:
        return make_anthropic_error(400, "Invalid JSON", "invalid_request_error")

    # 简单估算：每个字符约 0.25 token
    def estimate_tokens(text: str) -> int:
        return max(1, int(len(text) * 0.25))

    total = 0
    if body.get("system"):
        total += estimate_tokens(body["system"])

    for msg in body.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for block in content:
                if block.get("type") == "text":
                    total += estimate_tokens(block.get("text", ""))

    return {"input_tokens": total}

@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request_started = time.perf_counter()
    headers_for_log = _sanitize_headers(dict(request.headers))
    body_for_log = ""

    try:
        body_bytes = await request.body()
        body = json.loads(body_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        stats["total"] += 1
        stats["error"] += 1
        _append_request_log(
            method="POST",
            path="/v1/messages",
            status=400,
            model="unknown",
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            error=f"Invalid JSON: {e}",
        )
        return make_anthropic_error(400, f"Invalid JSON: {e}", "invalid_request_error")
    except Exception:
        stats["total"] += 1
        stats["error"] += 1
        _append_request_log(
            method="POST",
            path="/v1/messages",
            status=400,
            model="unknown",
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            error="Invalid JSON",
        )
        return make_anthropic_error(400, "Invalid JSON", "invalid_request_error")

    openai_req = anthropic_to_openai(body)
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    model = body.get("model", "")
    body_for_log = _safe_json_dump(body)
    openai_req["max_tokens"] = max(openai_req.get("max_tokens", 4096), 1024)

    logger.info(f"Request model={model}, thinking={openai_req.get('thinking')}, has_tools={bool(openai_req.get('tools'))}")

    try:
        proxy = get_proxy()

        if body.get("stream"):
            openai_req["stream_options"] = {"include_usage": True}
            reasoning_parts = []
            content_parts = []

            async def stream():
                try:
                    converter = StreamConverter(model, msg_id)
                    async for chunk in await proxy.proxy_request("/chat/completions", openai_req, model, stream=True):
                        line = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                        if line and line.startswith("data: ") and not line.endswith("[DONE]"):
                            try:
                                data = json.loads(line[6:])
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                if delta.get("reasoning_content"):
                                    reasoning_parts.append(delta["reasoning_content"])
                                    logger.info(f"[Thinking] {delta['reasoning_content'][:100]}")
                                if delta.get("content"):
                                    content_parts.append(delta["content"])
                            except Exception as e:
                                logger.warning(f"Parse chunk error: {e}")
                        if line:
                            for event in converter.convert_chunk(line):
                                yield event
                    stats["total"] += 1
                    stats["success"] += 1
                    _append_request_log(
                        method="POST",
                        path="/v1/messages",
                        status=200,
                        model=model,
                        request_id=request_id,
                        latency_ms=_elapsed_ms(request_started),
                        headers=headers_for_log,
                        body=body_for_log,
                        reasoning="".join(reasoning_parts),
                        content="".join(content_parts),
                        effective_model=model,
                    )
                except httpx.HTTPStatusError as e:
                    stats["total"] += 1
                    stats["error"] += 1
                    upstream_status = e.response.status_code
                    _append_request_log(
                        method="POST",
                        path="/v1/messages",
                        status=502,
                        model=model,
                        request_id=request_id,
                        latency_ms=_elapsed_ms(request_started),
                        headers=headers_for_log,
                        body=body_for_log,
                        error=f"Upstream API error: HTTP {upstream_status}",
                        effective_model=model,
                        upstream_status=upstream_status,
                    )
                    logger.error(f"上游 API 返回错误 HTTP {upstream_status} for model={model}: {e}")
                    raise
                except Exception as e:
                    stats["total"] += 1
                    stats["error"] += 1
                    _append_request_log(
                        method="POST",
                        path="/v1/messages",
                        status=500,
                        model=model,
                        request_id=request_id,
                        latency_ms=_elapsed_ms(request_started),
                        headers=headers_for_log,
                        body=body_for_log,
                        error=f"{type(e).__name__}: {e}",
                        effective_model=model,
                    )
                    raise

            return StreamingResponse(stream(), media_type="text/event-stream")

        data = await proxy.proxy_request("/chat/completions", openai_req, model, stream=False)
        logger.info(f"Non-stream response usage: {data.get('usage')}")
        reasoning = data.get("choices", [{}])[0].get("message", {}).get("reasoning_content", "")
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        stats["total"] += 1
        stats["success"] += 1
        _append_request_log(
            method="POST",
            path="/v1/messages",
            status=200,
            model=model,
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            body=body_for_log,
            reasoning=reasoning,
            content=content,
            effective_model=model,
        )
        return JSONResponse(openai_to_anthropic_nonstream(data))
    except httpx.HTTPStatusError as e:
        stats["total"] += 1
        stats["error"] += 1
        status_code = e.response.status_code
        _append_request_log(
            method="POST",
            path="/v1/messages",
            status=502,
            model=model,
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            body=body_for_log,
            error=f"Upstream API error: HTTP {status_code}",
            effective_model=model,
            upstream_status=status_code,
        )
        logger.error(f"上游 API 返回错误 HTTP {status_code} for model={model}: {e}")
        return make_anthropic_error(502, f"Upstream API error: HTTP {status_code}", "upstream_error")
    except Exception as e:
        stats["total"] += 1
        stats["error"] += 1
        _append_request_log(
            method="POST",
            path="/v1/messages",
            status=500,
            model=model,
            request_id=request_id,
            latency_ms=_elapsed_ms(request_started),
            headers=headers_for_log,
            body=body_for_log,
            error=f"{type(e).__name__}: {e}",
            effective_model=model,
        )
        return make_anthropic_error(500, str(e), "internal_error")

def run_server():
    """API 服务入口"""
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser(description="iFlow2API Service")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the service on")
    args = parser.parse_args()

    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    run_server()
