"""iFlow Token 管理和刷新模块"""

import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
import httpx


# iFlow OAuth 配置
IFLOW_OAUTH_TOKEN_ENDPOINT = "https://iflow.cn/oauth/token"
IFLOW_USER_INFO_ENDPOINT = "https://iflow.cn/api/oauth/getUserInfo"
IFLOW_OAUTH_CLIENT_ID = "10009311001"
IFLOW_OAUTH_CLIENT_SECRET = "4Z3YjXycVsQvyGF1etiNlIBB4RsqSDtW"


class IFlowTokenStorage:
    """iFlow Token 存储类"""

    def __init__(self, data: Optional[Dict[str, Any]] = None):
        data = data or {}
        self.access_token = data.get("access_token", "")
        self.refresh_token = data.get("refresh_token", "")
        self.expiry_date = data.get("expiry_date", 0)
        self.api_key = data.get("apiKey", "")
        self.token_type = data.get("token_type", "bearer")
        self.scope = data.get("scope", "")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expiry_date": self.expiry_date,
            "token_type": self.token_type,
            "scope": self.scope,
            "apiKey": self.api_key,
        }

    def is_expired(self) -> bool:
        """检查 Token 是否过期（提前 45 小时判断）"""
        try:
            if not self.expiry_date:
                return False

            current_time = int(time.time() * 1000)
            cron_near_minutes = 60 * 45  # 45 小时
            cron_near_minutes_in_millis = cron_near_minutes * 60 * 1000

            # 解析过期时间
            expire_value = self.expiry_date

            # 检查是否为数字（毫秒时间戳）
            if isinstance(expire_value, (int, float)):
                expire_time = int(expire_value)
            elif isinstance(expire_value, str):
                # 检查是否为纯数字字符串（毫秒时间戳）
                if expire_value.isdigit():
                    expire_time = int(expire_value)
                elif 'T' in expire_value:
                    # ISO 8601 格式
                    from datetime import datetime
                    expire_time = int(datetime.fromisoformat(expire_value.replace('Z', '+00:00')).timestamp() * 1000)
                else:
                    # 格式：2006-01-02 15:04
                    from datetime import datetime
                    expire_time = int(datetime.strptime(expire_value + ':00', '%Y-%m-%d %H:%M:%S').timestamp() * 1000)
            else:
                print(f"[iFlow] Invalid expiry date type: {type(expire_value)}")
                return False

            # 计算剩余时间
            time_remaining = expire_time - current_time

            # 判断是否已过期或接近过期
            is_expired_flag = time_remaining <= 0
            is_near = time_remaining > 0 and time_remaining <= cron_near_minutes_in_millis
            needs_refresh = is_expired_flag or is_near

            from datetime import datetime
            expire_date_str = datetime.fromtimestamp(expire_time / 1000).isoformat()
            time_remaining_minutes = time_remaining // 60000
            time_remaining_hours = round(time_remaining / 3600000, 2)

            print(f"[iFlow] Token expiry check: Expiry={expire_date_str}, Remaining={time_remaining_hours}h ({time_remaining_minutes}min), Threshold={cron_near_minutes}min, Expired={is_expired_flag}, Near={is_near}, NeedsRefresh={needs_refresh}")

            return needs_refresh
        except Exception as e:
            print(f"[iFlow] Error checking expiry date: {e}")
            return False


async def load_token_from_file(file_path: str) -> Optional[IFlowTokenStorage]:
    """从文件加载 Token"""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / file_path

        if not path.exists():
            print(f"[iFlow] Token file not found: {file_path}")
            return None

        data = json.loads(path.read_text(encoding="utf-8"))
        refresh_token = data.get("refresh_token", "")
        print(f"[iFlow] Token loaded from: {file_path} (refresh_token: {refresh_token[:8] if refresh_token else 'EMPTY'}...)")

        return IFlowTokenStorage(data)
    except Exception as e:
        print(f"[iFlow] Failed to load token: {e}")
        return None


async def save_token_to_file(file_path: str, token: IFlowTokenStorage):
    """保存 Token 到文件"""
    try:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path.cwd() / file_path

        path.parent.mkdir(parents=True, exist_ok=True)

        data = token.to_dict()
        if not data["refresh_token"]:
            print("[iFlow] WARNING: Saving token with empty refresh_token!")
        if not data["apiKey"]:
            print("[iFlow] WARNING: Saving token with empty apiKey!")

        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[iFlow] Token saved to: {file_path}")
    except Exception as e:
        raise Exception(f"[iFlow] Failed to save token: {e}")


async def refresh_oauth_tokens(refresh_token: str) -> Dict[str, Any]:
    """使用 refresh_token 刷新 OAuth Token"""
    if not refresh_token or not refresh_token.strip():
        raise Exception("[iFlow] refresh_token is empty")

    print("[iFlow] Refreshing OAuth tokens...")

    import base64
    basic_auth = base64.b64encode(
        f"{IFLOW_OAUTH_CLIENT_ID}:{IFLOW_OAUTH_CLIENT_SECRET}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            IFLOW_OAUTH_TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": IFLOW_OAUTH_CLIENT_ID,
                "client_secret": IFLOW_OAUTH_CLIENT_SECRET,
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Authorization": f"Basic {basic_auth}",
            },
        )

        if response.status_code != 200:
            raise Exception(f"[iFlow] Token refresh failed: {response.status_code} {response.text}")

        token_data = response.json()
        if not token_data.get("access_token"):
            raise Exception("[iFlow] Missing access_token in response")

        expires_in = token_data.get("expires_in", 3600)
        expiry_timestamp = int(time.time() * 1000) + expires_in * 1000

        result = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token", refresh_token),
            "token_type": token_data.get("token_type", "Bearer"),
            "scope": token_data.get("scope", ""),
            "expiry_date": expiry_timestamp,
        }

        print("[iFlow] OAuth tokens refreshed successfully")

        # 获取用户信息以获取 API Key
        user_info = await fetch_user_info(result["access_token"])
        if user_info and user_info.get("apiKey"):
            result["apiKey"] = user_info["apiKey"]

        return result


async def fetch_user_info(access_token: str) -> Dict[str, Any]:
    """获取用户信息（包含 API Key）"""
    if not access_token or not access_token.strip():
        raise Exception("[iFlow] access_token is empty")

    url = f"{IFLOW_USER_INFO_ENDPOINT}?accessToken={access_token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers={"Accept": "application/json"})

        if response.status_code != 200:
            raise Exception(f"[iFlow] Fetch user info failed: {response.status_code} {response.text}")

        result = response.json()
        if not result.get("success"):
            raise Exception("[iFlow] User info request not successful")

        if not result.get("data") or not result["data"].get("apiKey"):
            raise Exception("[iFlow] Missing apiKey in user info response")

        return {
            "apiKey": result["data"]["apiKey"],
            "email": result["data"].get("email", ""),
            "phone": result["data"].get("phone", ""),
        }
