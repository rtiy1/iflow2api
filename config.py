import json
from pathlib import Path
from typing import Optional


class IFlowConfig:
    """iFlow 配置类"""

    def __init__(self, api_key: str, base_url: str = "https://apis.iflow.cn/v1", cna: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.cna = cna


def load_iflow_config() -> IFlowConfig:
    """加载 iFlow 配置"""
    path = Path.home() / ".iflow" / "settings.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        api_key = data.get("apiKey") or data.get("api_key", "")
        base_url = data.get("baseUrl") or data.get("base_url") or "https://apis.iflow.cn/v1"
        cna = data.get("cna", "")

        if not api_key:
            raise ValueError("API Key 未配置")

        return IFlowConfig(api_key=api_key, base_url=base_url, cna=cna)
    except FileNotFoundError:
        raise FileNotFoundError("iFlow 配置文件不存在，请先运行 iflow 命令完成登录")


def check_iflow_login() -> bool:
    """检查是否已登录 iFlow"""
    try:
        config = load_iflow_config()
        return bool(config.api_key)
    except (FileNotFoundError, ValueError):
        return False


def load_config():
    """兼容旧版本的配置加载函数"""
    try:
        config = load_iflow_config()
        return {
            "api_key": config.api_key,
            "base_url": config.base_url,
            "cna": config.cna
        }
    except (FileNotFoundError, ValueError):
        return {"api_key": "", "base_url": "https://apis.iflow.cn/v1", "cna": ""}


CONFIG = load_config()
