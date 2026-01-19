"""API 代理服务 - 转发请求到 iFlow API"""

import httpx
import asyncio
import json
from typing import AsyncIterator, Optional
from config import CONFIG
from iflow_token import IFlowTokenStorage, load_token_from_file, save_token_to_file, refresh_oauth_tokens


# iFlow CLI 特殊 User-Agent，用于解锁更多模型
IFLOW_CLI_USER_AGENT = "iFlow-Cli"

# 支持 thinking 的模型前缀
THINKING_MODEL_PREFIXES = ["glm-4", "qwen3-235b-a22b-thinking", "deepseek-r1"]

# 默认模型列表
IFLOW_MODELS = [
    "iflow-rome-30ba3b", "qwen3-coder-plus", "qwen3-max", "qwen3-vl-plus",
    "qwen3-max-preview", "qwen3-32b", "qwen3-235b-a22b-thinking-2507",
    "qwen3-235b-a22b-instruct", "qwen3-235b", "kimi-k2-0905", "kimi-k2",
    "glm-4.6", "glm-4.7", "deepseek-v3.2", "deepseek-r1", "deepseek-v3"
]


class IFlowProxy:
    """iFlow API 代理"""

    def __init__(self, api_key: str, base_url: str, token_file_path: Optional[str] = None, max_retries: int = 3, base_delay: int = 1000):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.token_file_path = token_file_path
        self.token_storage: Optional[IFlowTokenStorage] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._is_initialized = False
        self.max_retries = max_retries
        self.base_delay = base_delay / 1000.0  # Convert to seconds

    async def initialize(self):
        """初始化服务，加载 OAuth 凭证"""
        if self._is_initialized:
            return

        if self.token_file_path:
            self.token_storage = await load_token_from_file(self.token_file_path)
            if self.token_storage and self.token_storage.api_key:
                self.api_key = self.token_storage.api_key
                print(f"[iFlow] Loaded API key from token file")

        self._is_initialized = True

    async def _check_and_refresh_token(self):
        """检查并刷新 Token"""
        if not self.token_storage or not self.token_file_path:
            return

        if self.token_storage.is_expired():
            print("[iFlow] Token is expiring soon, refreshing...")
            try:
                token_data = await refresh_oauth_tokens(self.token_storage.refresh_token)
                self.token_storage = IFlowTokenStorage(token_data)
                self.api_key = self.token_storage.api_key
                await save_token_to_file(self.token_file_path, self.token_storage)
                print("[iFlow] Token refreshed successfully")
            except Exception as e:
                print(f"[iFlow] Token refresh failed: {e}")

    def _get_headers(self) -> dict:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": IFLOW_CLI_USER_AGENT,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_keepalive_connections=5,
                max_connections=100,
                keepalive_expiry=120.0
            )
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=10.0),
                follow_redirects=True,
                limits=limits,
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _preserve_reasoning_content(self, body: dict, model: str) -> dict:
        """保留消息历史中的 reasoning_content"""
        if not body or not model:
            return body

        lower_model = model.lower()
        needs_preservation = (lower_model.startswith("glm-4") or
                            "thinking" in lower_model or
                            lower_model.startswith("deepseek-r1"))
        if not needs_preservation:
            return body

        messages = body.get("messages", [])
        if not isinstance(messages, list):
            return body

        has_reasoning = any(
            msg.get("role") == "assistant" and msg.get("reasoning_content")
            for msg in messages
        )

        if has_reasoning:
            print(f"[iFlow] reasoning_content found in message history for {model}")

        return body

    def _preprocess_request_body(self, body: dict, model: str) -> dict:
        """预处理请求体，应用 iFlow 特定配置"""
        processed = body.copy()
        processed["model"] = model

        # 处理 thinking 配置
        reasoning_effort = processed.get("reasoning_effort")
        if reasoning_effort is not None:
            enable_thinking = reasoning_effort not in ("none", "")

            # 移除 reasoning_effort 和 thinking
            processed.pop("reasoning_effort", None)
            processed.pop("thinking", None)

            # GLM-4.x: 使用 chat_template_kwargs
            if model.lower().startswith("glm-4"):
                processed["chat_template_kwargs"] = {
                    **processed.get("chat_template_kwargs", {}),
                    "enable_thinking": enable_thinking,
                }
                if enable_thinking:
                    processed["chat_template_kwargs"]["clear_thinking"] = False

        # 保留 reasoning_content
        processed = self._preserve_reasoning_content(processed, model)

        # 确保 tools 数组不为空（避免某些模型的问题）
        if "tools" in processed and isinstance(processed["tools"], list) and len(processed["tools"]) == 0:
            processed["tools"] = [{
                "type": "function",
                "function": {
                    "name": "noop",
                    "description": "Placeholder tool to stabilise streaming",
                    "parameters": {"type": "object"}
                }
            }]

        return processed

    async def get_models(self) -> dict:
        """获取可用模型列表"""
        await self.initialize()

        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/models",
                headers=self._get_headers()
            )
            response.raise_for_status()
            models_data = response.json()

            # 确保包含 glm-4.7
            if models_data and "data" in models_data and isinstance(models_data["data"], list):
                has_glm47 = any(m.get("id") == "glm-4.7" for m in models_data["data"])
                if not has_glm47:
                    import time
                    models_data["data"].append({
                        "id": "glm-4.7",
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "iflow"
                    })
                    print("[iFlow] Added glm-4.7 to models list")

            return models_data
        except Exception as e:
            print(f"[iFlow] Failed to fetch models from API: {e}, using default list")
            import time
            return {
                "object": "list",
                "data": [
                    {
                        "id": model,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "iflow",
                    }
                    for model in IFLOW_MODELS
                ],
            }

    async def _call_api(self, endpoint: str, body: dict, model: str, is_retry: bool = False, retry_count: int = 0):
        """调用 API（带重试逻辑）"""
        processed_body = self._preprocess_request_body(body, model)
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}{endpoint}",
                headers=self._get_headers(),
                json=processed_body,
            )
            response.raise_for_status()
            result = response.json()

            if "usage" not in result:
                result["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

            return result
        except httpx.HTTPStatusError as e:
            status = e.response.status_code

            # 401/400: 刷新token并重试一次
            if status in (400, 401) and not is_retry:
                print(f"[iFlow] Received {status}, refreshing token and retrying...")
                try:
                    await self._check_and_refresh_token()
                    return await self._call_api(endpoint, body, model, is_retry=True, retry_count=0)
                except Exception as refresh_error:
                    print(f"[iFlow] Token refresh failed: {refresh_error}")
                    raise e

            # 429: 指数退避重试
            if status == 429 and retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                print(f"[iFlow] Received 429, retrying in {delay}s... (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(delay)
                return await self._call_api(endpoint, body, model, is_retry, retry_count + 1)

            # 5xx: 服务器错误重试
            if 500 <= status < 600 and retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                print(f"[iFlow] Received {status}, retrying in {delay}s... (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(delay)
                return await self._call_api(endpoint, body, model, is_retry, retry_count + 1)

            raise
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
            # 网络错误重试
            if retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                print(f"[iFlow] Network error, retrying in {delay}s... (attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(delay)
                return await self._call_api(endpoint, body, model, is_retry, retry_count + 1)
            raise

    async def chat_completions(
        self,
        request_body: dict,
        stream: bool = False,
    ) -> dict | AsyncIterator[bytes]:
        """调用 chat completions API"""
        await self.initialize()
        await self._check_and_refresh_token()

        model = request_body.get("model", "unknown")

        if stream:
            return self._stream_chat_completions(request_body, model)
        else:
            return await self._call_api("/chat/completions", request_body, model)

    async def _stream_chat_completions(
        self,
        body: dict,
        model: str,
        is_retry: bool = False,
        retry_count: int = 0,
    ) -> AsyncIterator[bytes]:
        """流式调用 chat completions API（带SSE解析和重试）"""
        processed_body = self._preprocess_request_body({**body, "stream": True}, model)
        client = await self._get_client()

        try:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=processed_body,
            ) as response:
                response.raise_for_status()

                buffer = ""
                async for chunk in response.aiter_bytes():
                    buffer += chunk.decode("utf-8")

                    # 逐行处理
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line:
                            continue

                        # 处理 SSE data: 前缀
                        if line.startswith("data:"):
                            json_data = line[5:].strip()

                            if json_data == "[DONE]":
                                return

                            if not json_data:
                                continue

                            try:
                                # 返回原始 SSE 格式
                                yield f"data: {json_data}\n\n".encode("utf-8")
                            except Exception as e:
                                print(f"[iFlow] Failed to parse stream chunk: {e}")

                # 处理剩余buffer
                if buffer.strip():
                    line = buffer.strip()
                    if line.startswith("data:"):
                        json_data = line[5:].strip()
                        if json_data and json_data != "[DONE]":
                            yield f"data: {json_data}\n\n".encode("utf-8")

        except httpx.HTTPStatusError as e:
            status = e.response.status_code

            # 401/400: 刷新token并重试
            if status in (400, 401) and not is_retry:
                print(f"[iFlow] Received {status} during stream, refreshing token and retrying...")
                try:
                    await self._check_and_refresh_token()
                    async for chunk in self._stream_chat_completions(body, model, is_retry=True, retry_count=0):
                        yield chunk
                    return
                except Exception:
                    raise e

            # 429: 重试
            if status == 429 and retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                print(f"[iFlow] Received 429 during stream, retrying in {delay}s...")
                await asyncio.sleep(delay)
                async for chunk in self._stream_chat_completions(body, model, is_retry, retry_count + 1):
                    yield chunk
                return

            # 5xx: 重试
            if 500 <= status < 600 and retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                print(f"[iFlow] Received {status} during stream, retrying in {delay}s...")
                await asyncio.sleep(delay)
                async for chunk in self._stream_chat_completions(body, model, is_retry, retry_count + 1):
                    yield chunk
                return

            raise
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
            if retry_count < self.max_retries:
                delay = self.base_delay * (2 ** retry_count)
                print(f"[iFlow] Network error during stream, retrying in {delay}s...")
                await asyncio.sleep(delay)
                async for chunk in self._stream_chat_completions(body, model, is_retry, retry_count + 1):
                    yield chunk
                return
            raise


# 全局代理实例
_proxy: Optional[IFlowProxy] = None


def get_proxy() -> IFlowProxy:
    """获取代理实例"""
    global _proxy
    if _proxy is None:
        token_file = CONFIG.get("token_file_path")
        _proxy = IFlowProxy(CONFIG["api_key"], CONFIG["base_url"], token_file)
    return _proxy
