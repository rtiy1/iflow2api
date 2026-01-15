import json
import uuid

def anthropic_to_openai(req: dict) -> dict:
    messages = []
    if req.get("system"):
        messages.append({"role": "system", "content": req["system"]})
    for msg in req.get("messages", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    return {
        "model": req.get("model"),
        "messages": messages,
        "max_tokens": req.get("max_tokens", 1024),
        "stream": req.get("stream", False),
        "temperature": req.get("temperature", 1.0),
    }

def openai_to_anthropic(resp: dict) -> dict:
    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = resp.get("usage", {})
    return {
        "id": resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": resp.get("model"),
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
    }

def make_anthropic_stream_events(model: str, msg_id: str):
    yield f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "content": [], "model": model}})}\n\n'
    yield f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})}\n\n'

def convert_openai_chunk_to_anthropic(line: str) -> str:
    if not line.startswith("data: ") or line == "data: [DONE]":
        return ""
    try:
        data = json.loads(line[6:])
        delta = data.get("choices", [{}])[0].get("delta", {})
        text = delta.get("content", "")
        if text:
            return f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}})}\n\n'
    except:
        pass
    return ""

def make_anthropic_stream_end():
    yield f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": 0})}\n\n'
    yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": "end_turn"}})}\n\n'
    yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'
