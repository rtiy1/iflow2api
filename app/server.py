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


def _estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _estimate_content_tokens(content: Any) -> int:
    if isinstance(content, str):
        return _estimate_text_tokens(content)
    if isinstance(content, list):
        total = 0
        for item in content:
            if isinstance(item, str):
                total += _estimate_text_tokens(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text":
                total += _estimate_text_tokens(str(item.get("text", "")))
            elif item_type == "thinking":
                total += _estimate_text_tokens(str(item.get("thinking", "")))
            elif item_type in ("input_text", "output_text"):
                total += _estimate_text_tokens(str(item.get("text", "")))
            elif item_type == "tool_use":
                try:
                    total += _estimate_text_tokens(json.dumps(item.get("input", {}), ensure_ascii=False))
                except Exception:
                    pass
            elif item_type == "tool_result":
                total += _estimate_content_tokens(item.get("content", ""))
        return total
    return 0


def _estimate_openai_prompt_tokens(body: Dict[str, Any]) -> int:
    total = 0
    messages = body.get("messages", [])
    if not isinstance(messages, list):
        return 0

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        total += _estimate_content_tokens(msg.get("content", ""))
        if "reasoning_content" in msg:
            total += _estimate_content_tokens(msg.get("reasoning_content"))
    return total


def _estimate_anthropic_input_tokens(body: Dict[str, Any]) -> int:
    total = 0
    if "system" in body:
        total += _estimate_content_tokens(body.get("system"))

    messages = body.get("messages", [])
    if not isinstance(messages, list):
        return total

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        total += _estimate_content_tokens(msg.get("content", ""))
    return total


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


def map_upstream_status(status_code: int) -> int:
    # 透传具有明确客户端语义的上游状态，其余统一为网关错误。
    if status_code in (429, 503):
        return status_code
    return 502


def format_openai_stream_error_chunk(status: int, message: str, err_type: str = "upstream_error") -> str:
    payload = {
        "error": {
            "message": message,
            "type": err_type,
            "code": status,
        }
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def format_anthropic_stream_error_event(message: str, err_type: str = "api_error") -> str:
    payload = {
        "type": "error",
        "error": {
            "type": err_type,
            "message": message,
        },
    }
    return f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

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
            --bg-body: #060913;
            --bg-panel: #0f1425;
            --bg-card: #141b31;
            --bg-hover: #1d2644;
            --text-main: #e7edf9;
            --text-muted: #97a7c6;
            --accent: #36d0a8;
            --accent-2: #5b8cff;
            --danger: #ff6b81;
            --success: #2fd18f;
            --warning: #f3b24f;
            --border: #2a3558;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: "Microsoft YaHei UI", "PingFang SC", "Source Han Sans SC", sans-serif;
            color: var(--text-main);
            line-height: 1.55;
            font-size: 14px;
            background:
                radial-gradient(1200px 500px at 20% -10%, rgba(54, 208, 168, 0.12), transparent 60%),
                radial-gradient(900px 400px at 90% 0%, rgba(91, 140, 255, 0.16), transparent 55%),
                var(--bg-body);
        }

        .container { max-width: 1220px; margin: 0 auto; padding: 20px; }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 22px;
            padding: 16px 18px;
            border: 1px solid var(--border);
            border-radius: 14px;
            background: linear-gradient(135deg, rgba(15, 20, 37, 0.95), rgba(20, 27, 49, 0.88));
            backdrop-filter: blur(3px);
        }
        h1 {
            font-family: "Bahnschrift", "Microsoft YaHei UI", sans-serif;
            font-size: 1.5rem;
            letter-spacing: 0.02em;
            font-weight: 700;
            color: #d8f4ff;
        }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; margin-bottom: 20px; }
        .card {
            background: linear-gradient(170deg, rgba(20, 27, 49, 0.95), rgba(15, 20, 37, 0.92));
            border-radius: 12px;
            padding: 18px;
            border: 1px solid var(--border);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28);
            transition: transform 0.16s ease, border-color 0.16s ease;
        }
        .card:hover { transform: translateY(-1px); border-color: #3b4c79; }
        .stat-label {
            color: var(--text-muted);
            font-size: 0.82rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .stat-value { font-size: 1.85rem; font-weight: 700; color: var(--text-main); }
        .stat-value.success { color: var(--success); }
        .stat-value.error { color: var(--danger); }

        .models-container { margin-bottom: 20px; }
        .section-title {
            font-family: "Bahnschrift", "Microsoft YaHei UI", sans-serif;
            font-size: 1.04rem;
            font-weight: 700;
            margin-bottom: 10px;
            color: #d6e3ff;
            display: flex;
            align-items: center;
            gap: 8px;
            letter-spacing: 0.02em;
        }
        .chip-container { display: flex; flex-wrap: wrap; gap: 8px; }
        .chip {
            background: linear-gradient(145deg, #1a2340, #151d34);
            padding: 6px 11px;
            border-radius: 999px;
            font-size: 0.82rem;
            color: #d7e2fa;
            border: 1px solid #2f3d68;
        }

        .accounts-container { margin-bottom: 20px; }
        .account-summary {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 12px;
        }
        .summary-chip {
            padding: 6px 10px;
            border-radius: 999px;
            border: 1px solid #30406d;
            background: rgba(22, 34, 63, 0.8);
            font-size: 0.8rem;
            color: #d4e3ff;
        }
        .summary-chip strong {
            color: #f0f6ff;
            margin-left: 4px;
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
        }
        .accounts-list {
            display: grid;
            gap: 10px;
        }
        .account-item {
            border: 1px solid #2a3a64;
            border-radius: 9px;
            padding: 10px 12px;
            background: rgba(14, 24, 46, 0.72);
        }
        .account-head {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 8px;
            align-items: center;
            margin-bottom: 7px;
        }
        .account-id {
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
            color: #dbe8ff;
            font-size: 0.84rem;
            word-break: break-all;
        }
        .account-status {
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .account-status.ok { background: rgba(47, 209, 143, 0.2); color: var(--success); }
        .account-status.cooldown { background: rgba(243, 178, 79, 0.2); color: var(--warning); }
        .account-status.offline { background: rgba(255, 107, 129, 0.2); color: var(--danger); }
        .account-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 8px 12px;
            color: #9cb0d7;
            font-size: 0.76rem;
        }
        .account-error {
            margin-top: 6px;
            color: #ff9aab;
            font-size: 0.74rem;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .usage-section { margin-top: 20px; }
        .example-card { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; padding: 14px; margin-bottom: 12px; }
        .example-title {
            font-size: 0.98rem;
            font-weight: 700;
            margin-bottom: 8px;
            color: #83afff;
        }
        .example-code {
            background: #0a1020;
            padding: 12px;
            border-radius: 8px;
            overflow-x: auto;
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
            font-size: 0.82rem;
            color: #dfe9ff;
            border: 1px solid #263259;
            line-height: 1.48;
        }

        .toolbar {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            margin-bottom: 0;
        }
        input[type="text"] {
            background: #0f1630;
            border: 1px solid #2f3d69;
            color: var(--text-main);
            padding: 9px 12px;
            border-radius: 8px;
            width: 320px;
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        input[type="text"]:focus {
            border-color: var(--accent-2);
            box-shadow: 0 0 0 3px rgba(91, 140, 255, 0.17);
        }
        .btn {
            padding: 8px 14px;
            border-radius: 8px;
            border: 1px solid transparent;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.82rem;
            letter-spacing: 0.01em;
        }
        .btn-primary {
            background: linear-gradient(145deg, #3a8cff, #3f77ff);
            color: #f7fbff;
            border-color: #4f81ff;
        }
        .btn-primary:hover { filter: brightness(1.06); }
        .btn-danger {
            background: rgba(255, 107, 129, 0.12);
            color: #ff8ea0;
            border-color: rgba(255, 107, 129, 0.35);
        }
        .btn-danger:hover { background: rgba(255, 107, 129, 0.2); }

        .logs-wrapper {
            background: rgba(15, 20, 37, 0.9);
            border-radius: 12px;
            border: 1px solid var(--border);
            overflow: hidden;
            box-shadow: 0 14px 36px rgba(0, 0, 0, 0.22);
        }
        .log-item { border-bottom: 1px solid #263259; transition: background 0.15s; }
        .log-item:last-child { border-bottom: none; }
        .log-header {
            padding: 12px 14px;
            display: grid;
            grid-template-columns: 84px 72px 1fr 86px 180px;
            align-items: center;
            gap: 10px;
            cursor: pointer;
        }
        .log-header:hover { background: rgba(44, 61, 104, 0.25); }

        .badge { padding: 2px 8px; border-radius: 6px; font-size: 0.74rem; font-weight: 700; text-align: center; }
        .badge-2xx { background: rgba(47, 209, 143, 0.18); color: var(--success); }
        .badge-4xx { background: rgba(243, 178, 79, 0.18); color: var(--warning); }
        .badge-5xx { background: rgba(255, 107, 129, 0.2); color: var(--danger); }

        .method,
        .path,
        .model-tag,
        .time {
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
        }
        .method { font-weight: 700; color: #89a1d6; }
        .path { color: #e4ecff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .time { color: var(--text-muted); font-size: 0.83rem; }
        .model-tag {
            font-size: 0.78rem;
            color: #8ad9ff;
            background: rgba(91, 140, 255, 0.15);
            padding: 2px 6px;
            border-radius: 6px;
            justify-self: start;
        }

        .log-detail {
            display: none;
            padding: 14px;
            background: #0a1020;
            border-top: 1px solid #243055;
            font-family: "JetBrains Mono", "Cascadia Code", "Consolas", monospace;
            font-size: 0.82rem;
        }
        .log-detail.active { display: block; }
        .detail-section { margin-bottom: 14px; }
        .detail-title {
            color: #8da0c5;
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
            margin-bottom: 7px;
            display: flex;
            justify-content: space-between;
        }
        .code-block {
            background: #111a31;
            padding: 11px;
            border-radius: 8px;
            overflow-x: auto;
            color: #d9e6ff;
            white-space: pre-wrap;
            word-break: break-all;
            border: 1px solid #26345c;
        }
        .copy-btn {
            font-size: 0.68rem;
            background: transparent;
            border: 1px solid #41527d;
            color: #9fb4da;
            padding: 2px 6px;
            border-radius: 4px;
            cursor: pointer;
        }
        .copy-btn:hover { color: #eff5ff; border-color: #8ea9da; }
        .empty-state { padding: 34px; text-align: center; color: var(--text-muted); }

        @media (max-width: 900px) {
            .container { padding: 12px; }
            .log-header {
                grid-template-columns: 74px 62px 1fr 70px;
            }
            .model-tag { grid-column: 1 / -1; margin-top: 4px; }
            input[type="text"] { width: 100%; }
        }

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #0c1225; }
        ::-webkit-scrollbar-thumb { background: #2d3b63; border-radius: 6px; }
        ::-webkit-scrollbar-thumb:hover { background: #3b4f86; }
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

        <div class="accounts-container">
            <div class="section-title">👥 凭证账号池</div>
            <div class="card">
                <div class="account-summary">
                    <span class="summary-chip">模式<strong id="accounts-mode">-</strong></span>
                    <span class="summary-chip">策略<strong id="accounts-strategy">-</strong></span>
                    <span class="summary-chip">总账号<strong id="accounts-total">0</strong></span>
                    <span class="summary-chip">可用账号<strong id="accounts-available">0</strong></span>
                </div>
                <div id="accounts-list" class="accounts-list">
                    <div class="empty-state">账号池信息加载中...</div>
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

        async function refreshStats() {
            try {
                const s = await (await fetch('/admin/stats')).json();
                document.getElementById('total').textContent = s.total;
                document.getElementById('success').textContent = s.success;
                document.getElementById('error').textContent = s.error;
                document.getElementById('rate').textContent = s.total > 0 ? Math.round(s.success / s.total * 100) + '%' : '-';
            } catch (e) {
                console.error("Failed to refresh stats", e);
            }
        }

        async function refreshLogs() {
            try {
                allLogs = await (await fetch('/admin/logs')).json();
                filterLogs();
            } catch (e) {
                console.error("Failed to refresh logs", e);
            }
        }

        async function refreshAccounts() {
            const container = document.getElementById('accounts-list');
            try {
                const res = await fetch('/admin/accounts?t=' + Date.now());
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                const payload = await res.json();

                const mode = payload.mode || '-';
                const strategy = payload.routing_strategy || '-';
                const total = payload.total_accounts ?? 0;
                const available = payload.available_accounts ?? 0;
                const rows = Array.isArray(payload.accounts) ? payload.accounts : [];

                document.getElementById('accounts-mode').textContent = mode;
                document.getElementById('accounts-strategy').textContent = strategy;
                document.getElementById('accounts-total').textContent = String(total);
                document.getElementById('accounts-available').textContent = String(available);

                if (rows.length === 0) {
                    container.innerHTML = '<div class="empty-state">暂无可用账号配置</div>';
                    return;
                }

                container.innerHTML = rows.map((row) => {
                    const enabled = !!row.enabled;
                    const availableNow = !!row.available;
                    const cooldownSeconds = Number(row.cooldown_seconds || 0);
                    let statusText = '不可用';
                    let statusClass = 'offline';
                    if (enabled && availableNow) {
                        statusText = '可用';
                        statusClass = 'ok';
                    } else if (enabled && cooldownSeconds > 0) {
                        statusText = `冷却 ${cooldownSeconds}s`;
                        statusClass = 'cooldown';
                    }

                    const accountId = escapeHtml(String(row.account_id || 'unknown'));
                    const priority = Number(row.priority || 0);
                    const selectedCount = Number(row.selected_count || 0);
                    const failureCount = Number(row.failure_count || 0);
                    const fileName = escapeHtml(String(row.file || ''));
                    const errText = row.last_error ? `<div class="account-error">${escapeHtml(String(row.last_error))}</div>` : '';

                    return `
                        <div class="account-item">
                            <div class="account-head">
                                <div class="account-id">${accountId}</div>
                                <span class="account-status ${statusClass}">${statusText}</span>
                            </div>
                            <div class="account-meta">
                                <span>priority: ${priority}</span>
                                <span>selected: ${selectedCount}</span>
                                <span>failures: ${failureCount}</span>
                                <span>file: ${fileName || '-'}</span>
                            </div>
                            ${errText}
                        </div>
                    `;
                }).join('');
            } catch (e) {
                console.error("Failed to refresh accounts", e);
                container.innerHTML = `<div class="empty-state" style="color:var(--danger)">账号池加载失败: ${escapeHtml(e.message || String(e))}</div>`;
            }
        }

        async function refresh() {
            await Promise.all([refreshStats(), refreshLogs(), refreshAccounts()]);
        }

        async function clearLogs() {
            if (confirm('确定清空所有日志?')) {
                await fetch('/admin/logs', { method: 'DELETE' });
                await Promise.all([refreshStats(), refreshLogs()]);
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

        // Init
        refresh();
        loadModels();
        // 仅自动刷新统计与账号池，不自动刷新日志，避免展开详情被打断
        setInterval(refreshStats, 3000);
        setInterval(refreshAccounts, 3000);
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


@app.get("/admin/accounts")
async def get_accounts():
    proxy = get_proxy()
    return await proxy.get_account_pool_status()

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
            estimated_prompt_tokens = _estimate_openai_prompt_tokens(body)
            reasoning_parts = []
            content_parts = []

            async def stream():
                try:
                    MAX_CONTINUATIONS = 5
                    continuation_count = 0
                    current_body = body.copy()
                    accumulated_content = ""
                    accumulated_reasoning = ""
                    saw_usage = False

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
                                    if isinstance(data.get("usage"), dict):
                                        saw_usage = True

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

                    if not saw_usage:
                        estimated_completion_tokens = _estimate_text_tokens(accumulated_content + accumulated_reasoning)
                        usage_chunk = {
                            "id": f"chatcmpl_usage_{request_id}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": model,
                            "choices": [],
                            "usage": {
                                "prompt_tokens": estimated_prompt_tokens,
                                "completion_tokens": estimated_completion_tokens,
                                "total_tokens": estimated_prompt_tokens + estimated_completion_tokens,
                            },
                        }
                        yield f"data: {json.dumps(usage_chunk, ensure_ascii=False)}\n\n"

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
                    client_status = map_upstream_status(upstream_status)
                    _append_request_log(
                        method="POST",
                        path="/v1/chat/completions",
                        status=client_status,
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
                    yield format_openai_stream_error_chunk(
                        client_status,
                        f"Upstream API error: HTTP {upstream_status}",
                        "upstream_error",
                    )
                    yield "data: [DONE]\n\n"
                    return
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
                    yield format_openai_stream_error_chunk(500, str(e), "internal_error")
                    yield "data: [DONE]\n\n"
                    return

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
        client_status = map_upstream_status(status_code)
        _append_request_log(
            method="POST",
            path="/v1/chat/completions",
            status=client_status,
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
        return make_openai_error(client_status, f"Upstream API error: HTTP {status_code}", "upstream_error")
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

    return {"input_tokens": _estimate_anthropic_input_tokens(body)}

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
            estimated_input_tokens = _estimate_anthropic_input_tokens(body)

            async def stream():
                try:
                    converter = StreamConverter(model, msg_id, estimated_input_tokens=estimated_input_tokens)
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
                    client_status = map_upstream_status(upstream_status)
                    _append_request_log(
                        method="POST",
                        path="/v1/messages",
                        status=client_status,
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
                    yield format_anthropic_stream_error_event(
                        f"Upstream API error: HTTP {upstream_status}",
                        "upstream_error",
                    )
                    return
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
                    yield format_anthropic_stream_error_event(str(e), "internal_error")
                    return

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
        client_status = map_upstream_status(status_code)
        _append_request_log(
            method="POST",
            path="/v1/messages",
            status=client_status,
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
        return make_anthropic_error(client_status, f"Upstream API error: HTTP {status_code}", "upstream_error")
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
