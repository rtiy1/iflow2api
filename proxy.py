
import httpx
import gzip
import json
import io
import logging
from typing import AsyncIterator, Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from config import CONFIG
from iflow_token import IFlowTokenStorage, load_token_from_file, save_token_to_file, refresh_oauth_tokens
from thinking import apply_thinking

IFLOW_CLI_USER_AGENT = "iFlow-Cli"
logger = logging.getLogger(__name__)


def remove_query_values_matching(url: str, key: str, match: str) -> str:
    """从 URL 查询参数中移除匹配的值

    参考 Go: removeQueryValuesMatching(req *http.Request, key string, match string)
    """
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
    """从逗号分隔的列表中过滤特定的 beta 功能

    参考 Go: filterBetaFeatures(header, featureToRemove string) string
    """
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


class ReverseProxy:
    """反向代理实现 - 完全参考 CLIProxyAPI/internal/api/modules/amp/proxy.go"""

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
        return processed

    def _modify_response(self, content: bytes, status_code: int, headers: Dict[str, str]) -> bytes:
        """修改响应（ModifyResponse）

        参考 Go: proxy.ModifyResponse = func(resp *http.Response) error
        处理没有 Content-Encoding 的 gzip 响应
        """
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

        # 修改请求体
        processed_body = self._modify_request_body(body, model)

        # 修改请求头
        headers = self._director({})

        client = await self._get_client()

        if stream:
            return self._proxy_stream(client, endpoint, headers, processed_body)
        else:
            return await self._proxy_non_stream(client, endpoint, headers, processed_body)

    async def _proxy_non_stream(self, client: httpx.AsyncClient, endpoint: str, headers: Dict[str, str], body: Dict[str, Any]):
        """非流式代理"""
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
        except Exception as e:
            logger.error(f"amp upstream proxy error for POST {endpoint}: {e}")
            raise

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
