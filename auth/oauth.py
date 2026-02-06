"""iFlow OAuth 认证模块"""

import asyncio
import secrets
import json
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import httpx
import base64
from typing import Optional, Dict, Any, Tuple


# iFlow OAuth 配置
IFLOW_OAUTH_CONFIG = {
    "token_endpoint": "https://iflow.cn/oauth/token",
    "authorize_endpoint": "https://iflow.cn/oauth",
    "user_info_endpoint": "https://iflow.cn/api/oauth/getUserInfo",
    "client_id": "10009311001",
    "client_secret": "4Z3YjXycVsQvyGF1etiNlIBB4RsqSDtW",
    "callback_port": 8087,
}


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """OAuth 回调处理器"""

    auth_result = None

    def log_message(self, format, *args):
        """禁用日志输出"""
        pass

    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        if parsed.path == "/oauth2callback":
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            state = params.get("state", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                OAuthCallbackHandler.auth_result = {"error": error}
                self.send_response(400)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h1>授权失败</h1><p>{error}</p>".encode())
            elif code and state:
                OAuthCallbackHandler.auth_result = {"code": code, "state": state}
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h1>授权成功！</h1><p>您可以关闭此页面</p>".encode())
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h1>授权失败</h1><p>缺少参数</p>".encode())
        else:
            self.send_response(404)
            self.end_headers()


def generate_auth_url(state: str, port: int) -> Tuple[str, str]:
    """生成授权 URL"""
    redirect_uri = f"http://localhost:{port}/oauth2callback"
    params = {
        "loginMethod": "phone",
        "type": "phone",
        "redirect": redirect_uri,
        "state": state,
        "client_id": IFLOW_OAUTH_CONFIG["client_id"],
    }
    from urllib.parse import urlencode
    auth_url = f"{IFLOW_OAUTH_CONFIG['authorize_endpoint']}?{urlencode(params)}"
    return auth_url, redirect_uri


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> Dict[str, Any]:
    """交换授权码获取令牌"""
    basic_auth = base64.b64encode(
        f"{IFLOW_OAUTH_CONFIG['client_id']}:{IFLOW_OAUTH_CONFIG['client_secret']}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            IFLOW_OAUTH_CONFIG["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": IFLOW_OAUTH_CONFIG["client_id"],
                "client_secret": IFLOW_OAUTH_CONFIG["client_secret"],
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Authorization": f"Basic {basic_auth}",
            },
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.status_code} {response.text}")

        token_data = response.json()
        if not token_data.get("access_token"):
            raise Exception("Missing access_token in response")

        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token", ""),
            "token_type": token_data.get("token_type", "bearer"),
            "scope": token_data.get("scope", ""),
            "expires_in": token_data.get("expires_in", 3600),
        }


async def fetch_user_info(access_token: str) -> Dict[str, Any]:
    """获取用户信息"""
    url = f"{IFLOW_OAUTH_CONFIG['user_info_endpoint']}?accessToken={access_token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers={"Accept": "application/json"})

        if response.status_code != 200:
            raise Exception(f"Fetch user info failed: {response.status_code} {response.text}")

        result = response.json()
        if not result.get("success"):
            raise Exception("User info request not successful")

        if not result.get("data") or not result["data"].get("apiKey"):
            raise Exception("Missing apiKey in user info response")

        return {
            "apiKey": result["data"]["apiKey"],
            "email": result["data"].get("email", "") or result["data"].get("phone", ""),
        }


async def start_oauth_flow(save_path: Optional[str] = None, on_auth_url=None) -> Dict[str, Any]:
    """启动 OAuth 流程

    Args:
        save_path: 凭据保存路径
        on_auth_url: 可选的回调函数，接收 auth_url 参数，用于自定义处理（如自动打开浏览器）
    """
    state = secrets.token_urlsafe(16)
    port = IFLOW_OAUTH_CONFIG["callback_port"]

    auth_url, redirect_uri = generate_auth_url(state, port)

    if on_auth_url:
        on_auth_url(auth_url)
    else:
        print(f"\n请在浏览器中打开以下链接进行授权：\n{auth_url}\n")

    # 启动回调服务器
    server = HTTPServer(("0.0.0.0", port), OAuthCallbackHandler)
    print(f"[iFlow OAuth] 回调服务器已启动于端口 {port}")

    # 等待回调
    while OAuthCallbackHandler.auth_result is None:
        server.handle_request()

    result = OAuthCallbackHandler.auth_result
    server.server_close()

    if "error" in result:
        raise Exception(f"OAuth failed: {result['error']}")

    if result["state"] != state:
        raise Exception("State verification failed")

    # 交换令牌
    print("[iFlow OAuth] 正在交换令牌...")
    token_data = await exchange_code_for_tokens(result["code"], redirect_uri)

    # 获取用户信息
    print("[iFlow OAuth] 正在获取用户信息...")
    user_info = await fetch_user_info(token_data["access_token"])

    # 组合凭据
    import time
    credentials = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expiry_date": int(time.time() * 1000) + token_data["expires_in"] * 1000,
        "token_type": token_data["token_type"],
        "scope": token_data["scope"],
        "apiKey": user_info["apiKey"],
    }

    # 保存凭据
    if save_path is None:
        save_path = Path.home() / ".iflow" / "oauth_creds.json"
    else:
        save_path = Path(save_path)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    save_path.write_text(json.dumps(credentials, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[iFlow OAuth] 凭据已保存到: {save_path}")
    print(f"[iFlow OAuth] 账户: {user_info['email']}")

    return credentials
