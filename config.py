import json
from pathlib import Path

def load_config():
    path = Path.home() / ".iflow" / "settings.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {
            "api_key": data.get("apiKey") or data.get("api_key", ""),
            "base_url": data.get("baseUrl") or data.get("base_url") or "https://apis.iflow.cn/v1",
            "cna": data.get("cna", "")
        }
    except FileNotFoundError:
        return {"api_key": "", "base_url": "https://apis.iflow.cn/v1", "cna": ""}

CONFIG = load_config()
