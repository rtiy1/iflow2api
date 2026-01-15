import json
import uuid

def anthropic_to_openai(req: dict) -> dict:
    """转换 Anthropic 请求格式到 OpenAI 格式，支持工具调用"""
    messages = []
    if req.get("system"):
        messages.append({"role": "system", "content": req["system"]})

    for msg in req.get("messages", []):
        role = msg["role"]
        content = msg.get("content")

        # 处理简单字符串内容
        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue

        # 处理复杂内容块 (list)
        if isinstance(content, list):
            text_parts = []
            tool_calls = []
            tool_results = []

            for block in content:
                block_type = block.get("type")

                if block_type == "text":
                    text_parts.append(block.get("text", ""))

                elif block_type == "tool_use":
                    # Anthropic tool_use -> OpenAI tool_calls
                    tool_calls.append({
                        "id": block.get("id", f"call_{uuid.uuid4().hex[:24]}"),
                        "type": "function",
                        "function": {
                            "name": block.get("name"),
                            "arguments": json.dumps(block.get("input", {}))
                        }
                    })

                elif block_type == "tool_result":
                    # Anthropic tool_result -> OpenAI tool message
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        result_content = "".join(
                            b.get("text", "") for b in result_content if b.get("type") == "text"
                        )
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id"),
                        "content": result_content
                    })

            # 添加 assistant 消息（带 tool_calls）
            if role == "assistant":
                msg_obj = {"role": "assistant", "content": "\n".join(text_parts) or None}
                if tool_calls:
                    msg_obj["tool_calls"] = tool_calls
                messages.append(msg_obj)

            # 添加 tool results 作为独立消息
            elif tool_results:
                messages.extend(tool_results)

            # 普通 user 消息
            else:
                messages.append({"role": role, "content": "\n".join(text_parts)})

    result = {
        "model": req.get("model"),
        "messages": messages,
        "max_tokens": req.get("max_tokens", 4096),
        "stream": req.get("stream", False),
        "temperature": req.get("temperature", 1.0),
    }

    # 转换 tools 定义
    if req.get("tools"):
        result["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}})
                }
            }
            for t in req["tools"]
        ]

    # 转换 tool_choice
    if req.get("tool_choice"):
        tc = req["tool_choice"]
        if isinstance(tc, dict) and tc.get("type") == "tool":
            result["tool_choice"] = {"type": "function", "function": {"name": tc.get("name")}}
        elif tc == "auto":
            result["tool_choice"] = "auto"
        elif tc == "any":
            result["tool_choice"] = "required"
        elif tc == "none":
            result["tool_choice"] = "none"

    return result

def openai_to_anthropic(resp: dict) -> dict:
    """转换 OpenAI 响应格式到 Anthropic 格式，支持工具调用"""
    choice = resp.get("choices", [{}])[0]
    message = choice.get("message", {})
    usage = resp.get("usage", {})

    content = []

    # 添加文本内容
    if message.get("content"):
        content.append({"type": "text", "text": message["content"]})

    # 转换 tool_calls
    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            func = tc.get("function", {})
            try:
                input_data = json.loads(func.get("arguments", "{}"))
            except:
                input_data = {}
            content.append({
                "type": "tool_use",
                "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                "name": func.get("name"),
                "input": input_data
            })

    # 确定 stop_reason
    finish_reason = choice.get("finish_reason", "end_turn")
    stop_reason = "tool_use" if message.get("tool_calls") else (
        "end_turn" if finish_reason in ("stop", None) else finish_reason
    )

    return {
        "id": resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "content": content if content else [{"type": "text", "text": ""}],
        "model": resp.get("model"),
        "stop_reason": stop_reason,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
    }

def make_anthropic_stream_events(model: str, msg_id: str):
    yield f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": msg_id, "type": "message", "role": "assistant", "content": [], "model": model}})}\n\n'

def make_anthropic_stream_end(stop_reason: str = "end_turn"):
    yield f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": stop_reason}})}\n\n'
    yield f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n'

class StreamConverter:
    """流式转换器，维护状态以处理工具调用"""

    def __init__(self):
        self.content_index = 0
        self.tool_calls = {}  # id -> {name, arguments}
        self.text_started = False
        self.current_tool_index = None

    def convert_chunk(self, line: str) -> list:
        """转换单个 OpenAI chunk 到 Anthropic 事件列表"""
        if not line.startswith("data: ") or line == "data: [DONE]":
            return []

        try:
            data = json.loads(line[6:])
        except:
            return []

        events = []
        delta = data.get("choices", [{}])[0].get("delta", {})

        # 处理文本内容
        text = delta.get("content", "")
        if text:
            if not self.text_started:
                events.append(f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": self.content_index, "content_block": {"type": "text", "text": ""}})}\n\n')
                self.text_started = True
            events.append(f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": self.content_index, "delta": {"type": "text_delta", "text": text}})}\n\n')

        # 处理工具调用
        tool_calls = delta.get("tool_calls", [])
        for tc in tool_calls:
            tc_index = tc.get("index", 0)
            tc_id = tc.get("id")
            func = tc.get("function", {})

            if tc_id:  # 新工具调用开始
                # 关闭之前的文本块
                if self.text_started:
                    events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": self.content_index})}\n\n')
                    self.content_index += 1
                    self.text_started = False

                self.tool_calls[tc_index] = {"id": tc_id, "name": func.get("name", ""), "arguments": ""}
                self.current_tool_index = tc_index

                events.append(f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": self.content_index, "content_block": {"type": "tool_use", "id": tc_id, "name": func.get("name", ""), "input": {}}})}\n\n')

            # 累积参数
            if tc_index in self.tool_calls and func.get("arguments"):
                args_delta = func["arguments"]
                self.tool_calls[tc_index]["arguments"] += args_delta
                events.append(f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": self.content_index, "delta": {"type": "input_json_delta", "partial_json": args_delta}})}\n\n')

        return events

    def finish(self) -> list:
        """生成结束事件"""
        events = []
        if self.text_started or self.tool_calls:
            events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": self.content_index})}\n\n')

        stop_reason = "tool_use" if self.tool_calls else "end_turn"
        events.extend(make_anthropic_stream_end(stop_reason))
        return events

# 保留旧函数以兼容
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
