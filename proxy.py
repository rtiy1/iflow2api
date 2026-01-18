"""API 代理服务 - 转发请求到 iFlow API"""

import httpx
from typing import AsyncIterator, Optional
from config import CONFIG


# iFlow CLI 特殊 User-Agent，用于解锁更多模型
IFLOW_CLI_USER_AGENT = "iFlow-Cli"


class IFlowProxy:
    """iFlow API 代理"""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

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
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_models(self) -> dict:
        """获取可用模型列表"""
        models = [
            "glm-4.7", "iFlow-ROME-30BA3B", "deepseek-v3.2-chat", "qwen3-coder-plus",
            "kimi-k2-thinking", "minimax-m2.1", "kimi-k2-0905", "glm-4.6",
            "deepseek-r1", "deepseek-v3", "qwen3-max", "qwen3-235b"
        ]

        import time
        current_time = int(time.time())

        return {
            "object": "list",
            "data": [
                {
                    "id": model,
                    "object": "model",
                    "created": current_time,
                    "owned_by": "iflow",
                }
                for model in models
            ],
        }

    async def chat_completions(
        self,
        request_body: dict,
        stream: bool = False,
    ) -> dict | AsyncIterator[bytes]:
        """调用 chat completions API"""
        client = await self._get_client()

        if stream:
            return self._stream_chat_completions(client, request_body)
        else:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=request_body,
            )
            response.raise_for_status()
            result = response.json()

            if "usage" not in result:
                result["usage"] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }

            return result

    async def _stream_chat_completions(
        self,
        client: httpx.AsyncClient,
        request_body: dict,
    ) -> AsyncIterator[bytes]:
        """流式调用 chat completions API"""
        async with client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._get_headers(),
            json=request_body,
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                yield chunk


# 全局代理实例
_proxy: Optional[IFlowProxy] = None


def get_proxy() -> IFlowProxy:
    """获取代理实例"""
    global _proxy
    if _proxy is None:
        _proxy = IFlowProxy(CONFIG["api_key"], CONFIG["base_url"])
    return _proxy
