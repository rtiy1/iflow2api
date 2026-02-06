
import httpx
import gzip
import json
import io
import logging
import asyncio
import base64
import mimetypes
import os
import re
from urllib.parse import unquote
from typing import AsyncIterator, Optional, Dict, Any, List

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from core.config import CONFIG
from auth.token import IFlowTokenStorage, load_token_from_file, save_token_to_file, refresh_oauth_tokens
from core.thinking import apply_thinking

IFLOW_CLI_USER_AGENT = "iFlow-Cli"
logger = logging.getLogger(__name__)
MAX_LOCAL_IMAGE_BYTES = 10 * 1024 * 1024
FORCED_VISION_MODEL = "qwen3-vl-plus"
KNOWN_MULTIMODAL_MODELS = {
    "qwen3-vl-plus",
    "tstars2.0",
}


def remove_query_values_matching(url: str, key: str, match: str) -> str:

    if not url or not match:
        return url

    parsed = urlparse(url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    if key not in query_params:
        return url

    values = query_params[key]
    kept = [v for v in values if v != match]

    if not kept:
        del query_params[key]
    else:
        query_params[key] = kept

    new_query = urlencode(query_params, doseq=True)
    new_parsed = parsed._replace(query=new_query)
    return urlunparse(new_parsed)


def filter_beta_features(header: str, feature_to_remove: str) -> str:

    features = header.split(",")
    filtered = []

    for feature in features:
        trimmed = feature.strip()
        if trimmed and trimmed != feature_to_remove:
            filtered.append(trimmed)

    return ",".join(filtered)


def is_streaming_response(content_type: str) -> bool:
    """检测是否为流式响应（仅 SSE）

    注意：我们只将 text/event-stream 视为流式响应。
    Chunked transfer encoding 是传输层细节，不意味着我们不能解压完整响应。
    许多 JSON API 对普通响应使用 chunked encoding。
    """
    return "text/event-stream" in content_type


def _normalize_base64_data(data: str) -> str:
    if not data:
        return ""
    return "".join(data.split())


def _build_data_url(media_type: str, data: str) -> str:
    if not data:
        return ""
    if data.startswith("data:"):
        return data
    media_type = media_type or "image/png"
    data = _normalize_base64_data(data)
    if not data:
        return ""
    return f"data:{media_type};base64,{data}"


def _to_local_path(url: str) -> str:
    if not url:
        return ""
    value = url.strip()
    if value.startswith("file://"):
        path = unquote(value[7:])
        if path.startswith("/"):
            path = path.lstrip("/")
        path = path.replace("/", os.sep)
        # UNC path support (file://server/share)
        if not re.match(r"^[A-Za-z]:\\", path) and path.startswith("\\") is False and value.startswith("file://"):
            if "\\" not in path and "/" not in path:
                return path
            return "\\\\" + path.lstrip("\\")
        return path
    if re.match(r"^[A-Za-z]:\\", value) or re.match(r"^[A-Za-z]:/", value):
        return unquote(value).replace("/", os.sep)
    return ""


def _load_local_image_as_data_url(url: str) -> str:
    path = _to_local_path(url)
    if not path:
        return ""
    if not os.path.exists(path):
        logger.warning(f"[iFlow] 本地图片路径不存在: {path}")
        return ""
    try:
        size = os.path.getsize(path)
        if size > MAX_LOCAL_IMAGE_BYTES:
            logger.warning(f"[iFlow] 本地图片过大，已跳过: {path} ({size} bytes)")
            return ""
        with open(path, "rb") as f:
            data = f.read()
        media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{media_type};base64,{encoded}"
    except Exception as e:
        logger.warning(f"[iFlow] 读取本地图片失败: {path} ({e})")
        return ""


def _normalize_image_url(url: str) -> str:
    if not url:
        return ""
    value = url.strip()
    if value.startswith("data:") or value.startswith("http://") or value.startswith("https://"):
        return value
    if CONFIG.get("allow_local_file_images"):
        local_data = _load_local_image_as_data_url(value)
        if local_data:
            return local_data
    return value


def _extract_image_url_from_part(part: Dict[str, Any]) -> str:
    if not isinstance(part, dict):
        return ""

    image_url_field = part.get("image_url")
    if isinstance(image_url_field, dict):
        url = image_url_field.get("url", "")
        if url:
            return _normalize_image_url(url)
    elif isinstance(image_url_field, str):
        return _normalize_image_url(image_url_field)

    url_field = part.get("url")
    if isinstance(url_field, str) and url_field:
        return _normalize_image_url(url_field)

    source = part.get("source")
    if isinstance(source, dict):
        source_type = source.get("type", "")
        if source_type == "url":
            return _normalize_image_url(source.get("url", ""))
        if source_type == "base64":
            media_type = source.get("media_type") or part.get("media_type") or "image/png"
            return _build_data_url(media_type, source.get("data", ""))

    return ""


def _build_image_url_part(part: Dict[str, Any], url: str) -> Dict[str, Any]:
    image_url = {"url": url}
    detail = None
    image_url_field = part.get("image_url")
    if isinstance(image_url_field, dict):
        detail = image_url_field.get("detail")
    if detail is None:
        detail = part.get("detail")
    if detail:
        image_url["detail"] = detail
    return {"type": "image_url", "image_url": image_url}


def _normalize_openai_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize image content blocks to OpenAI image_url format."""
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue

        normalized = []
        changed = False

        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type", "")
                if part_type == "input_text" and "text" in part:
                    normalized.append({"type": "text", "text": part.get("text", "")})
                    changed = True
                    continue
                is_image_like = part_type in ("image", "image_url", "input_image") or "image_url" in part or "source" in part
                if is_image_like:
                    url = _extract_image_url_from_part(part)
                    if url:
                        normalized.append(_build_image_url_part(part, url))
                        changed = True
                        continue

            normalized.append(part)

        if changed:
            msg["content"] = normalized

    return messages


def _message_has_image(message: Dict[str, Any]) -> bool:
    content = message.get("content")
    if not isinstance(content, list):
        return False
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type", "")
        if part_type in ("image", "image_url", "input_image"):
            return True
        if "image_url" in part:
            return True
        source = part.get("source")
        if isinstance(source, dict) and source.get("type") in ("base64", "url"):
            return True
    return False


def _request_has_images(body: Dict[str, Any]) -> bool:
    messages = body.get("messages", [])
    if not isinstance(messages, list):
        return False
    return any(_message_has_image(msg) for msg in messages)


def _is_vision_model(model: str) -> bool:
    if not model:
        return False
    model_lower = model.lower()
    return (
        model_lower in KNOWN_MULTIMODAL_MODELS
        or "vl" in model_lower
        or "vision" in model_lower
        or "4v" in model_lower
        or "multimodal" in model_lower
    )


def _forced_model_is_multimodal() -> bool:
    return _is_vision_model(FORCED_VISION_MODEL)


def get_default_system_prompt() -> str:
    """生成默认系统提示词"""
    return """--- SYSTEM PROMPT BEGIN ---
## Tool Usage Strategy
- 严禁猜测代码位置。必须使用工具获取确切的符号关系和定义。
- 优先使用工具解决问题，避免盲目猜测和假设。
- 在进行代码阅读和修改前，务必先通过工具确认符号关系和定义，避免误操作。
- 在进行代码修改时，务必先通过工具分析影响范围，避免破坏现有功能。
## Tool Call Format (MANDATORY)
- 工具调用必须严格遵守规范格式，所有必需参数必须提供，禁止省略。
- 禁止发送空参数或缺少参数的工具调用，这会导致系统错误。
- 调用工具前必须确认所有 required 参数都已正确填写。
- 工具调用错误通常是路径或操作系统问题，请检查路径格式参数等是否正确。
- 如果在 plan 模式下工具调用失败可能导致循环调用，遇到错误时应停止重试并分析原因。
## Code Modification Rules
- 修改代码前必须分析可能的副作用，包括对其他模块、函数、测试的影响。
- 修改公共接口或共享代码时，必须检查所有调用方。
## File Reading Rules (CRITICAL)
- 禁止一次性读取超大文件（>10kb），必须使用 offset 和 limit 参数分段读取。
- 读取大文件前先评估文件大小，优先使用 Grep 搜索定位关键内容。
--- SYSTEM PROMPT END ---"""


class ReverseProxy:

    def __init__(self, upstream_url: str, api_key: str, token_file_path: Optional[str] = None):
        self.upstream_url = upstream_url.rstrip("/")
        self.api_key = api_key
        self.token_file_path = token_file_path
        self.token_storage: Optional[IFlowTokenStorage] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """初始化并刷新 token（如需要）"""
        if self.token_file_path:
            self.token_storage = await load_token_from_file(self.token_file_path)
            if self.token_storage:
                if self.token_storage.is_expired() and self.token_storage.refresh_token:
                    logger.info("[iFlow] Token expired or near expiry, refreshing...")
                    try:
                        refreshed = await refresh_oauth_tokens(self.token_storage.refresh_token)
                        self.token_storage = IFlowTokenStorage(refreshed)
                        await save_token_to_file(self.token_file_path, self.token_storage)
                        logger.info("[iFlow] Token refreshed and saved")
                    except Exception as e:
                        logger.warning(f"[iFlow] Token refresh failed: {e}")

                if self.token_storage.api_key:
                    self.api_key = self.token_storage.api_key

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _director(self, headers: Dict[str, str]) -> Dict[str, str]:
        """修改请求头（Director）

        参考 Go: proxy.Director = func(req *http.Request)
        - 删除客户端的 Authorization 头（仅用于 CLI Proxy API 认证）
        - 注入上游 API key

        注意：我们不在代理路径中过滤 Anthropic-Beta 头。
        通过 ampcode.com 代理的用户为服务付费，应该获得所有功能，
        包括 1M 上下文窗口 (context-1m-2025-08-07)。
        """
        modified = headers.copy()

        # 删除客户端的 Authorization 头 - 它仅用于 CLI Proxy API 认证
        # 我们将使用配置的 upstream-api-key 设置自己的 Authorization
        modified.pop("authorization", None)
        modified.pop("x-api-key", None)
        modified.pop("x-goog-api-key", None)

        # 注入上游 API key（仅使用配置中的 upstream-api-key）
        modified["x-api-key"] = self.api_key
        modified["authorization"] = f"Bearer {self.api_key}"
        modified["user-agent"] = IFLOW_CLI_USER_AGENT
        modified["content-type"] = "application/json"

        return modified

    def _modify_request_body(self, body: Dict[str, Any], model: str) -> Dict[str, Any]:
        """修改请求体"""
        processed = body.copy()
        processed["model"] = model
        processed = apply_thinking(processed, model)

        # 注入默认系统提示词
        default_prompt = get_default_system_prompt()
        messages = processed.get("messages", [])
        if isinstance(messages, list):
            _normalize_openai_messages(messages)

        # 查找是否已有 system 消息
        system_msg_idx = None
        for idx, msg in enumerate(messages):
            if msg.get("role") == "system":
                system_msg_idx = idx
                break

        if system_msg_idx is not None:
            # 追加到现有 system 消息
            existing_content = messages[system_msg_idx].get("content", "")
            if isinstance(existing_content, str):
                messages[system_msg_idx]["content"] = f"{default_prompt}\n\n{existing_content}"
            elif isinstance(existing_content, list):
                # 如果是列表格式,在开头插入文本块
                messages[system_msg_idx]["content"] = [{"type": "text", "text": default_prompt}] + existing_content
        else:
            # 在开头插入新的 system 消息
            messages.insert(0, {"role": "system", "content": default_prompt})

        processed["messages"] = messages
        return processed

    def _modify_response(self, content: bytes, status_code: int, headers: Dict[str, str]) -> bytes:
  
        # 只处理成功响应
        if status_code < 200 or status_code >= 300:
            return content

        # 跳过已标记为 gzip 的响应
        if headers.get("content-encoding", ""):
            return content

        # 跳过流式响应（SSE）
        content_type = headers.get("content-type", "")
        if is_streaming_response(content_type):
            return content

        # Peek 前 2 字节检测 gzip magic bytes
        if len(content) < 2:
            return content

        # 检查 gzip magic bytes (0x1f 0x8b)
        if content[0] == 0x1f and content[1] == 0x8b:
            try:
                # 解压
                decompressed = gzip.decompress(content)
                logger.debug(f"amp proxy: decompressed gzip response ({len(content)} -> {len(decompressed)} bytes)")
                return decompressed
            except Exception as e:
                logger.warning(f"amp proxy: gzip header detected but decompress failed: {e}")
                return content

        return content

    async def proxy_request(self, endpoint: str, body: Dict[str, Any], model: str, stream: bool = False):
        """代理请求"""
        await self.initialize()

        effective_model = model
        if _request_has_images(body) and not _is_vision_model(model):
            if not _forced_model_is_multimodal():
                logger.warning(f"[iFlow] 强制模型不支持多模态，跳过切换: {FORCED_VISION_MODEL}")
            else:
                logger.info(f"[iFlow] 检测到图片输入，强制切换模型: {model} -> {FORCED_VISION_MODEL}")
                effective_model = FORCED_VISION_MODEL

        # 修改请求体
        processed_body = self._modify_request_body(body, effective_model)

        # 修改请求头
        headers = self._director({})

        client = await self._get_client()

        if stream:
            return self._proxy_stream(client, endpoint, headers, processed_body)
        else:
            return await self._proxy_non_stream(client, endpoint, headers, processed_body)

    async def _proxy_non_stream(self, client: httpx.AsyncClient, endpoint: str, headers: Dict[str, str], body: Dict[str, Any]):
        """非流式代理 - 带重试"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.post(
                    f"{self.upstream_url}{endpoint}",
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()

                # 修改响应
                response_headers = dict(response.headers)
                content = self._modify_response(response.content, response.status_code, response_headers)
                result = json.loads(content)

                if "usage" not in result:
                    result["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

                return result
            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                logger.warning(f"上游 API 错误 (尝试 {attempt + 1}/{MAX_RETRIES}): HTTP {status_code} - {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
            except Exception as e:
                last_error = e
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        # 区分错误类型记录
        if isinstance(last_error, httpx.HTTPStatusError):
            logger.error(f"上游 API 持续返回错误 HTTP {last_error.response.status_code} for POST {endpoint}: {last_error}")
        else:
            logger.error(f"代理请求失败 for POST {endpoint}: {last_error}")
        raise last_error

    async def _proxy_stream(self, client: httpx.AsyncClient, endpoint: str, headers: Dict[str, str], body: Dict[str, Any]) -> AsyncIterator[bytes]:
        """流式代理 - 按 SSE 事件边界读取

        SSE 格式：data: {...}\n\n
        每个事件由 data: 行和空行组成，空行表示事件结束
        """
        try:
            async with client.stream(
                "POST",
                f"{self.upstream_url}{endpoint}",
                headers=headers,
                json=body,
            ) as response:
                response.raise_for_status()

                # 使用缓冲区按 SSE 事件边界分割
                # SSE 事件以 \n\n 分隔
                buffer = b""
                async for chunk in response.aiter_bytes():
                    buffer += chunk

                    # 查找完整的 SSE 事件（以 \n\n 结尾）
                    while b"\n\n" in buffer:
                        event, buffer = buffer.split(b"\n\n", 1)
                        # 发送完整的 SSE 事件（包含 \n\n）
                        yield event + b"\n\n"

                # 处理剩余数据（如果有）
                if buffer:
                    yield buffer
        except Exception as e:
            logger.error(f"amp upstream proxy error for POST {endpoint}: {e}")
            raise

    async def get_models(self) -> Dict[str, Any]:
        """获取模型列表"""
        await self.initialize()

        headers = self._director({})
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.upstream_url}/models",
                headers=headers
            )
            response.raise_for_status()

            response_headers = dict(response.headers)
            content = self._modify_response(response.content, response.status_code, response_headers)
            return json.loads(content)
        except Exception as e:
            logger.error(f"amp upstream proxy error for GET /models: {e}")
            raise


# 全局实例
_proxy: Optional[ReverseProxy] = None


def get_proxy() -> ReverseProxy:
    """获取代理实例"""
    global _proxy
    if _proxy is None:
        token_file = CONFIG.get("token_file_path")
        _proxy = ReverseProxy(CONFIG["base_url"], CONFIG["api_key"], token_file)
    return _proxy
