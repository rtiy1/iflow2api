import json
from pathlib import Path
from typing import Optional

DEFAULT_VISION_MODEL = "qwen3-vl-plus"
DEFAULT_AUTO_VISION_MODEL = True


class IFlowConfig:
    """iFlow 配置类"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://apis.iflow.cn/v1",
        cna: str = "",
        token_file_path: Optional[str] = None,
        vision_model: str = "",
        auto_vision_model: bool = False,
        allow_local_file_images: bool = False,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.cna = cna
        self.token_file_path = token_file_path
        self.vision_model = vision_model
        self.auto_vision_model = auto_vision_model
        self.allow_local_file_images = allow_local_file_images


def load_iflow_config() -> IFlowConfig:
    """加载 iFlow 配置 - 支持 OAuth 和传统 API Key"""
    # 优先尝试加载 OAuth 凭证
    oauth_path = Path.home() / ".iflow" / "oauth_creds.json"
    if oauth_path.exists():
        try:
            data = json.loads(oauth_path.read_text(encoding="utf-8"))
            api_key = data.get("apiKey", "")
            vision_model = data.get("visionModel", "") or data.get("vision_model", "")
            auto_vision_model = data.get("autoVisionModel")
            if auto_vision_model is None:
                auto_vision_model = data.get("auto_vision_model")
            if auto_vision_model is None:
                auto_vision_model = DEFAULT_AUTO_VISION_MODEL
            if not vision_model:
                vision_model = DEFAULT_VISION_MODEL
            allow_local_file_images = data.get("allowLocalFileImages")
            if allow_local_file_images is None:
                allow_local_file_images = data.get("allow_local_file_images")
            if api_key:
                print(f"[Config] Loaded OAuth credentials from {oauth_path}")
                return IFlowConfig(
                    api_key=api_key,
                    base_url="https://apis.iflow.cn/v1",
                    token_file_path=str(oauth_path),
                    vision_model=vision_model,
                    auto_vision_model=bool(auto_vision_model),
                    allow_local_file_images=bool(allow_local_file_images),
                )
        except Exception as e:
            print(f"[Config] Failed to load OAuth credentials: {e}")

    # 回退到传统配置文件
    settings_path = Path.home() / ".iflow" / "settings.json"
    try:
        with open(settings_path, encoding="utf-8") as f:
            data = json.load(f)
        api_key = data.get("apiKey") or data.get("api_key", "")
        base_url = data.get("baseUrl") or data.get("base_url") or "https://apis.iflow.cn/v1"
        cna = data.get("cna", "")
        vision_model = data.get("visionModel") or data.get("vision_model") or ""
        auto_vision_model = data.get("autoVisionModel")
        if auto_vision_model is None:
            auto_vision_model = data.get("auto_vision_model")
        if auto_vision_model is None:
            auto_vision_model = DEFAULT_AUTO_VISION_MODEL
        if not vision_model:
            vision_model = DEFAULT_VISION_MODEL
        allow_local_file_images = data.get("allowLocalFileImages")
        if allow_local_file_images is None:
            allow_local_file_images = data.get("allow_local_file_images")

        if not api_key:
            raise ValueError("API Key 未配置")

        return IFlowConfig(
            api_key=api_key,
            base_url=base_url,
            cna=cna,
            vision_model=vision_model,
            auto_vision_model=bool(auto_vision_model),
            allow_local_file_images=bool(allow_local_file_images),
        )
    except FileNotFoundError:
        raise FileNotFoundError("iFlow 配置文件不存在，请先运行 OAuth 认证或配置 API Key")


def check_iflow_login() -> bool:
    """检查是否已登录 iFlow"""
    try:
        config = load_iflow_config()
        return bool(config.api_key)
    except (FileNotFoundError, ValueError):
        return False


def load_config():
    """加载配置"""
    try:
        config = load_iflow_config()
        return {
            "api_key": config.api_key,
            "base_url": config.base_url,
            "cna": config.cna,
            "token_file_path": config.token_file_path,
            "vision_model": config.vision_model,
            "auto_vision_model": config.auto_vision_model,
            "allow_local_file_images": config.allow_local_file_images,
        }
    except (FileNotFoundError, ValueError):
        return {
            "api_key": "",
            "base_url": "https://apis.iflow.cn/v1",
            "cna": "",
            "token_file_path": None,
            "vision_model": DEFAULT_VISION_MODEL,
            "auto_vision_model": DEFAULT_AUTO_VISION_MODEL,
            "allow_local_file_images": False
        }


CONFIG = load_config()
