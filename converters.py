"""OpenAI <-> Anthropic 格式转换器 - 完全参考 CLIProxyAPI 实现"""

import json
import uuid
from typing import Dict, Any, List, Optional


def anthropic_to_openai(req: dict) -> dict:
    """将 Anthropic 请求转换为 OpenAI 格式"""
    out = {"model": "", "messages": []}

    # 模型
    out["model"] = req.get("model", "")

    # max_tokens
    if "max_tokens" in req:
        out["max_tokens"] = req["max_tokens"]

    # temperature
    if "temperature" in req:
        out["temperature"] = req["temperature"]
    elif "top_p" in req:
        out["top_p"] = req["top_p"]

    # stop_sequences -> stop
    if "stop_sequences" in req and isinstance(req["stop_sequences"], list):
        stops = req["stop_sequences"]
        if len(stops) == 1:
            out["stop"] = stops[0]
        elif len(stops) > 1:
            out["stop"] = stops

    # stream
    out["stream"] = req.get("stream", False)

    # thinking: 转换 budget_tokens 到 reasoning_effort
    if "thinking" in req and isinstance(req["thinking"], dict):
        thinking_type = req["thinking"].get("type")
        if thinking_type == "enabled":
            budget = req["thinking"].get("budget_tokens", -1)
            if budget == 0:
                pass  # disabled
            elif budget > 0:
                # 简化映射：参考 Go 代码的 thinking.ConvertBudgetToLevel
                if budget < 5000:
                    out["reasoning_effort"] = "low"
                elif budget < 15000:
                    out["reasoning_effort"] = "medium"
                else:
                    out["reasoning_effort"] = "high"
            else:
                out["reasoning_effort"] = "auto"
        elif thinking_type == "disabled":
            pass  # 不设置 reasoning_effort

    # 处理 system 消息
    messages = []
    if "system" in req:
        system_content = []
        if isinstance(req["system"], str):
            if req["system"]:
                system_content.append({"type": "text", "text": req["system"]})
        elif isinstance(req["system"], list):
            for item in req["system"]:
                if part := _convert_content_part(item):
                    system_content.append(part)
        if system_content:
            messages.append({"role": "system", "content": system_content})

    # 处理 messages
    for msg in req.get("messages", []):
        role = msg.get("role", "")
        content = msg.get("content")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            content_items = []
            reasoning_parts = []
            tool_calls = []
            tool_results = []

            for block in content:
                block_type = block.get("type", "")

                if block_type == "thinking":
                    # 只允许 assistant 消息包含 thinking
                    if role == "assistant":
                        thinking_text = block.get("thinking", "")
                        if thinking_text.strip():
                            reasoning_parts.append(thinking_text)

                elif block_type == "redacted_thinking":
                    # 忽略 redacted_thinking
                    pass

                elif block_type in ("text", "image"):
                    if part := _convert_content_part(block):
                        content_items.append(part)

                elif block_type == "tool_use":
                    # 只允许 assistant 消息包含 tool_use
                    if role == "assistant":
                        tool_calls.append({
                            "id": block.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": block.get("name", ""),
                                "arguments": json.dumps(block.get("input", {}))
                            }
                        })

                elif block_type == "tool_result":
                    # tool_result 转换为独立的 tool 消息
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": _convert_tool_result_content(block.get("content"))
                    })

            # 先添加 tool_results（响应之前的 tool_calls）
            messages.extend(tool_results)

            # 构建当前消息
            if role == "assistant":
                if content_items or reasoning_parts or tool_calls:
                    msg_obj = {"role": "assistant"}

                    # content
                    if content_items:
                        msg_obj["content"] = content_items
                    else:
                        msg_obj["content"] = ""

                    # reasoning_content
                    if reasoning_parts:
                        msg_obj["reasoning_content"] = "\n\n".join(reasoning_parts)

                    # tool_calls
                    if tool_calls:
                        msg_obj["tool_calls"] = tool_calls

                    messages.append(msg_obj)
            else:
                # 非 assistant 消息
                if content_items:
                    messages.append({"role": role, "content": content_items})

    out["messages"] = messages

    # 处理 tools
    if "tools" in req and isinstance(req["tools"], list):
        tools = []
        for tool in req["tools"]:
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {})
                }
            })
        if tools:
            out["tools"] = tools

    # tool_choice
    if "tool_choice" in req:
        tc = req["tool_choice"]
        if isinstance(tc, dict):
            tc_type = tc.get("type")
            if tc_type == "auto":
                out["tool_choice"] = "auto"
            elif tc_type == "any":
                out["tool_choice"] = "required"
            elif tc_type == "tool":
                out["tool_choice"] = {
                    "type": "function",
                    "function": {"name": tc.get("name", "")}
                }
        elif tc == "auto":
            out["tool_choice"] = "auto"
        elif tc == "any":
            out["tool_choice"] = "required"
        elif tc == "none":
            out["tool_choice"] = "none"

    # user
    if "user" in req:
        out["user"] = req["user"]

    return out


def _convert_content_part(part: dict) -> Optional[dict]:
    """转换内容块"""
    part_type = part.get("type", "")

    if part_type == "text":
        text = part.get("text", "")
        if text.strip():
            return {"type": "text", "text": text}

    elif part_type == "image":
        image_url = ""
        if "source" in part:
            source = part["source"]
            source_type = source.get("type", "")
            if source_type == "base64":
                media_type = source.get("media_type", "application/octet-stream")
                data = source.get("data", "")
                if data:
                    image_url = f"data:{media_type};base64,{data}"
            elif source_type == "url":
                image_url = source.get("url", "")
        elif "url" in part:
            image_url = part["url"]

        if image_url:
            return {"type": "image_url", "image_url": {"url": image_url}}

    return None


def _convert_tool_result_content(content) -> str:
    """转换 tool_result 内容为字符串"""
    if not content:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" and "text" in item:
                    parts.append(item["text"])
                else:
                    parts.append(json.dumps(item))
        joined = "\n\n".join(parts)
        return joined if joined.strip() else json.dumps(content)

    if isinstance(content, dict):
        if "text" in content:
            return content["text"]
        return json.dumps(content)

    return str(content)


def openai_to_anthropic_nonstream(resp: dict) -> dict:
    """转换 OpenAI 非流式响应为 Anthropic 格式"""
    out = {
        "id": resp.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "model": resp.get("model", ""),
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": 0, "output_tokens": 0}
    }

    has_tool_call = False
    stop_reason_set = False

    choices = resp.get("choices", [])
    if choices:
        choice = choices[0]

        # finish_reason
        if "finish_reason" in choice:
            out["stop_reason"] = _map_finish_reason(choice["finish_reason"])
            stop_reason_set = True

        message = choice.get("message", {})

        # 处理 content（可能是数组或字符串）
        if "content" in message:
            content_val = message["content"]
            if isinstance(content_val, list):
                # 内容数组：处理 text, tool_calls, reasoning
                text_parts = []
                thinking_parts = []

                for item in content_val:
                    item_type = item.get("type", "")
                    if item_type == "text":
                        text_parts.append(item.get("text", ""))
                    elif item_type == "tool_calls":
                        # 先 flush text 和 thinking
                        if thinking_parts:
                            out["content"].append({"type": "thinking", "thinking": "".join(thinking_parts)})
                            thinking_parts = []
                        if text_parts:
                            out["content"].append({"type": "text", "text": "".join(text_parts)})
                            text_parts = []

                        # 处理 tool_calls
                        tool_calls = item.get("tool_calls", [])
                        if isinstance(tool_calls, list):
                            for tc in tool_calls:
                                has_tool_call = True
                                func = tc.get("function", {})
                                args_str = func.get("arguments", "{}")
                                try:
                                    input_data = json.loads(args_str) if args_str else {}
                                except:
                                    input_data = {}

                                out["content"].append({
                                    "type": "tool_use",
                                    "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                                    "name": func.get("name", ""),
                                    "input": input_data
                                })
                    elif item_type == "reasoning":
                        # flush text first
                        if text_parts:
                            out["content"].append({"type": "text", "text": "".join(text_parts)})
                            text_parts = []
                        thinking_parts.append(item.get("text", ""))

                # flush 剩余
                if thinking_parts:
                    out["content"].append({"type": "thinking", "thinking": "".join(thinking_parts)})
                if text_parts:
                    out["content"].append({"type": "text", "text": "".join(text_parts)})

            elif isinstance(content_val, str) and content_val:
                out["content"].append({"type": "text", "text": content_val})

        # reasoning_content
        if "reasoning_content" in message:
            reasoning_texts = _collect_reasoning_texts(message["reasoning_content"])
            for text in reasoning_texts:
                if text.strip():
                    out["content"].append({"type": "thinking", "thinking": text})

        # tool_calls
        if "tool_calls" in message:
            tool_calls = message["tool_calls"]
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    has_tool_call = True
                    func = tc.get("function", {})
                    args_str = func.get("arguments", "{}")
                    try:
                        input_data = json.loads(args_str) if args_str else {}
                    except:
                        input_data = {}

                    out["content"].append({
                        "type": "tool_use",
                        "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
                        "name": func.get("name", ""),
                        "input": input_data
                    })

    # usage
    if "usage" in resp:
        usage = resp["usage"]
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

        if cached_tokens > 0:
            input_tokens = max(0, input_tokens - cached_tokens)
            out["usage"]["cache_read_input_tokens"] = cached_tokens

        out["usage"]["input_tokens"] = input_tokens
        out["usage"]["output_tokens"] = output_tokens

    # 设置 stop_reason
    if not stop_reason_set:
        out["stop_reason"] = "tool_use" if has_tool_call else "end_turn"

    # 确保 content 不为空
    if not out["content"]:
        out["content"] = [{"type": "text", "text": ""}]

    return out


def _collect_reasoning_texts(node) -> List[str]:
    """收集 reasoning 文本"""
    texts = []

    if isinstance(node, str):
        if node:
            texts.append(node)
    elif isinstance(node, list):
        for item in node:
            texts.extend(_collect_reasoning_texts(item))
    elif isinstance(node, dict):
        if "text" in node:
            if node["text"]:
                texts.append(node["text"])

    return texts


def _map_finish_reason(reason: str) -> str:
    """映射 finish_reason"""
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
        "function_call": "tool_use"
    }
    return mapping.get(reason, "end_turn")


class StreamConverter:
    """流式转换器 - 完全参考 Go 实现"""

    def __init__(self, model: str, message_id: str):
        self.model = model
        self.message_id = message_id
        self.content_accumulator = []
        self.tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}
        self.text_content_block_started = False
        self.thinking_content_block_started = False
        self.finish_reason = ""
        self.content_blocks_stopped = False
        self.message_delta_sent = False
        self.message_started = False
        self.message_stop_sent = False
        self.tool_call_block_indexes: Dict[int, int] = {}
        self.text_content_block_index = -1
        self.thinking_content_block_index = -1
        self.next_content_block_index = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_tokens = 0

    def convert_chunk(self, line: str) -> List[str]:
        """转换单个 chunk"""
        if not line.startswith("data:"):
            return []

        # 兼容 "data:" 和 "data: " 两种格式
        data_str = line[5:].lstrip().strip()

        # [DONE]
        if data_str == "[DONE]":
            return self._handle_done()

        try:
            data = json.loads(data_str)
        except:
            return []

        events = []

        # message_start
        if not self.message_started:
            events.append(f'event: message_start\ndata: {json.dumps({"type": "message_start", "message": {"id": self.message_id, "type": "message", "role": "assistant", "model": self.model, "content": [], "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}})}\n\n')
            self.message_started = True

        choices = data.get("choices", [])
        if not choices:
            return events

        delta = choices[0].get("delta", {})

        # reasoning_content
        if "reasoning_content" in delta:
            reasoning_texts = _collect_reasoning_texts(delta["reasoning_content"])
            for text in reasoning_texts:
                if not text:
                    continue
                self._stop_text_content_block(events)
                if not self.thinking_content_block_started:
                    if self.thinking_content_block_index == -1:
                        self.thinking_content_block_index = self.next_content_block_index
                        self.next_content_block_index += 1
                    events.append(f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": self.thinking_content_block_index, "content_block": {"type": "thinking", "thinking": ""}})}\n\n')
                    self.thinking_content_block_started = True
                events.append(f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": self.thinking_content_block_index, "delta": {"type": "thinking_delta", "thinking": text}})}\n\n')

        # content
        if "content" in delta and delta["content"]:
            text = delta["content"]
            if not self.text_content_block_started:
                self._stop_thinking_content_block(events)
                if self.text_content_block_index == -1:
                    self.text_content_block_index = self.next_content_block_index
                    self.next_content_block_index += 1
                events.append(f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": self.text_content_block_index, "content_block": {"type": "text", "text": ""}})}\n\n')
                self.text_content_block_started = True
            events.append(f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": self.text_content_block_index, "delta": {"type": "text_delta", "text": text}})}\n\n')

        # tool_calls
        if "tool_calls" in delta:
            for tc in delta["tool_calls"]:
                tc_index = tc.get("index", 0)
                tc_id = tc.get("id")
                func = tc.get("function", {})

                if tc_id:
                    self._stop_thinking_content_block(events)
                    self._stop_text_content_block(events)

                    if tc_index not in self.tool_call_block_indexes:
                        self.tool_call_block_indexes[tc_index] = self.next_content_block_index
                        self.next_content_block_index += 1

                    block_index = self.tool_call_block_indexes[tc_index]
                    self.tool_calls_accumulator[tc_index] = {
                        "id": tc_id,
                        "name": func.get("name", ""),
                        "arguments": ""
                    }

                    events.append(f'event: content_block_start\ndata: {json.dumps({"type": "content_block_start", "index": block_index, "content_block": {"type": "tool_use", "id": tc_id, "name": func.get("name", ""), "input": {}}})}\n\n')

                # 累积参数
                if tc_index in self.tool_calls_accumulator and "arguments" in func:
                    args_delta = func["arguments"]
                    if args_delta:
                        block_index = self.tool_call_block_indexes[tc_index]
                        self.tool_calls_accumulator[tc_index]["arguments"] += args_delta

        # finish_reason
        if "finish_reason" in choices[0] and choices[0]["finish_reason"]:
            self.finish_reason = choices[0]["finish_reason"]

            # 停止所有 content blocks
            if self.thinking_content_block_started:
                events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": self.thinking_content_block_index})}\n\n')
                self.thinking_content_block_started = False

            self._stop_text_content_block(events)

            if not self.content_blocks_stopped:
                for tc_index in self.tool_calls_accumulator:
                    block_index = self.tool_call_block_indexes[tc_index]
                    acc = self.tool_calls_accumulator[tc_index]

                    # 发送完整的 arguments
                    if acc["arguments"]:
                        events.append(f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_index, "delta": {"type": "input_json_delta", "partial_json": acc["arguments"]}})}\n\n')

                    events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_index})}\n\n')

                self.content_blocks_stopped = True

        # usage
        if self.finish_reason and "usage" in data:
            usage = data["usage"]
            # 处理 usage 可能不是字典的情况
            if not isinstance(usage, dict):
                usage = {}
            self.input_tokens = usage.get("prompt_tokens", 0)
            self.output_tokens = usage.get("completion_tokens", 0)
            self.cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

            input_tokens = self.input_tokens
            if self.cached_tokens > 0:
                input_tokens = max(0, input_tokens - self.cached_tokens)

            msg_delta = {
                "type": "message_delta",
                "delta": {"stop_reason": _map_finish_reason(self.finish_reason), "stop_sequence": None},
                "usage": {"input_tokens": input_tokens, "output_tokens": self.output_tokens}
            }
            if self.cached_tokens > 0:
                msg_delta["usage"]["cache_read_input_tokens"] = self.cached_tokens

            events.append(f'event: message_delta\ndata: {json.dumps(msg_delta)}\n\n')
            self.message_delta_sent = True

            self._emit_message_stop_if_needed(events)

        return events

    def _handle_done(self) -> List[str]:
        """处理 [DONE]"""
        events = []

        # 停止所有 content blocks
        if self.thinking_content_block_started:
            events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": self.thinking_content_block_index})}\n\n')
            self.thinking_content_block_started = False

        self._stop_text_content_block(events)

        if not self.content_blocks_stopped:
            for tc_index in self.tool_calls_accumulator:
                block_index = self.tool_call_block_indexes[tc_index]
                acc = self.tool_calls_accumulator[tc_index]

                if acc["arguments"]:
                    events.append(f'event: content_block_delta\ndata: {json.dumps({"type": "content_block_delta", "index": block_index, "delta": {"type": "input_json_delta", "partial_json": acc["arguments"]}})}\n\n')

                events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": block_index})}\n\n')

            self.content_blocks_stopped = True

        # message_delta
        if self.finish_reason and not self.message_delta_sent:
            events.append(f'event: message_delta\ndata: {json.dumps({"type": "message_delta", "delta": {"stop_reason": _map_finish_reason(self.finish_reason), "stop_sequence": None}})}\n\n')
            self.message_delta_sent = True

        self._emit_message_stop_if_needed(events)

        return events

    def _stop_thinking_content_block(self, events: List[str]):
        """停止 thinking content block"""
        if not self.thinking_content_block_started:
            return
        events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": self.thinking_content_block_index})}\n\n')
        self.thinking_content_block_started = False

    def _stop_text_content_block(self, events: List[str]):
        """停止 text content block"""
        if not self.text_content_block_started:
            return
        events.append(f'event: content_block_stop\ndata: {json.dumps({"type": "content_block_stop", "index": self.text_content_block_index})}\n\n')
        self.text_content_block_started = False

    def _emit_message_stop_if_needed(self, events: List[str]):
        """发送 message_stop"""
        if self.message_stop_sent:
            return
        events.append(f'event: message_stop\ndata: {json.dumps({"type": "message_stop"})}\n\n')
        self.message_stop_sent = True
