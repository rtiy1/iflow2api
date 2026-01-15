import uuid
import httpx
import logging
from datetime import datetime
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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = datetime.now()
    response = await call_next(request)
    if not request.url.path.startswith("/admin"):
        stats["total"] += 1
        if response.status_code < 400:
            stats["success"] += 1
        else:
            stats["error"] += 1
        request_logs.appendleft({
            "time": start.strftime("%H:%M:%S"),
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code
        })
    return response

@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return """<!DOCTYPE html><html><head><meta charset="utf-8"><title>iFlow2API</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:system-ui;background:#1a1a2e;color:#eee;padding:20px}
.card{background:#16213e;border-radius:8px;padding:15px;margin:10px 0}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stat{text-align:center}.stat h2{font-size:2em;color:#0f0}.stat.err h2{color:#f00}
input,button{padding:8px 12px;border:none;border-radius:4px;margin:5px}button{background:#4a69bd;color:#fff;cursor:pointer}
#logs{max-height:300px;overflow-y:auto;font-family:monospace;font-size:12px}
.log{padding:4px;border-bottom:1px solid #333}.models{display:flex;flex-wrap:wrap;gap:5px}
.model{background:#4a69bd;padding:4px 8px;border-radius:4px;font-size:12px}</style></head>
<body><h1>iFlow2API 管理面板</h1>
<div class="card"><h3>端口设置</h3><input id="port" type="number" value="8000" placeholder="端口">
<button onclick="alert('需要重启服务生效')">保存</button></div>
<div class="card grid"><div class="stat"><p>总请求</p><h2 id="total">0</h2></div>
<div class="stat"><p>成功</p><h2 id="success">0</h2></div>
<div class="stat err"><p>错误</p><h2 id="error">0</h2></div></div>
<div class="card"><h3>模型列表</h3><div id="models" class="models">加载中...</div></div>
<div class="card"><h3>请求日志</h3><div id="logs"></div></div>
<script>
async function refresh(){
  const s=await(await fetch('/admin/stats')).json();
  document.getElementById('total').textContent=s.total;
  document.getElementById('success').textContent=s.success;
  document.getElementById('error').textContent=s.error;
  const logs=await(await fetch('/admin/logs')).json();
  document.getElementById('logs').innerHTML=logs.map(l=>`<div class="log">${l.time} ${l.method} ${l.path} - ${l.status}${l.response?' | '+l.response:''}</div>`).join('');
}
async function loadModels(){
  try{const m=await(await fetch('/v1/models')).json();
  document.getElementById('models').innerHTML=(m.data||[]).map(x=>`<span class="model">${x.id}</span>`).join('')||'无模型';}
  catch(e){document.getElementById('models').textContent='加载失败';}
}
refresh();loadModels();setInterval(refresh,3000);
</script></body></html>"""

@app.get("/admin/stats")
async def get_stats():
    return stats

@app.get("/admin/logs")
async def get_logs():
    return list(request_logs)

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
    body = await request.json()
    headers = get_auth_headers(request)
    model = body.get("model", "unknown")

    if body.get("stream"):
        async def stream():
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", f"{IFLOW_URL}/chat/completions", json=body, headers=headers, timeout=120) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            yield line + "\n"
        return StreamingResponse(stream(), media_type="text/event-stream")

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{IFLOW_URL}/chat/completions", json=body, headers=headers, timeout=120)
        data = resp.json()
        # 记录响应详情
        request_logs.appendleft({
            "time": datetime.now().strftime("%H:%M:%S"),
            "method": "POST",
            "path": "/v1/chat/completions",
            "status": resp.status_code,
            "model": model,
            "response": str(data)[:500]
        })
        return data

@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    body = await request.json()
    openai_req = anthropic_to_openai(body)
    headers = get_auth_headers(request)
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    model = body.get("model", "")

    if body.get("stream"):
        async def stream():
            for event in make_anthropic_stream_events(model, msg_id):
                yield event
            converter = StreamConverter()
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", f"{IFLOW_URL}/chat/completions", json=openai_req, headers=headers, timeout=120) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            for event in converter.convert_chunk(line):
                                yield event
            for event in converter.finish():
                yield event
        return StreamingResponse(stream(), media_type="text/event-stream")

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{IFLOW_URL}/chat/completions", json=openai_req, headers=headers, timeout=120)
        return JSONResponse(openai_to_anthropic(resp.json()))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
