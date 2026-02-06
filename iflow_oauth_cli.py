#!/usr/bin/env python3
"""iFlow OAuth CLI - 用于 Tauri 调用"""

import asyncio
import sys
import json
from pathlib import Path

# 导入 OAuth 模块
from iflow_oauth import start_oauth_flow, IFLOW_OAUTH_CONFIG


def open_browser(url: str):
    """打开系统浏览器"""
    import webbrowser
    webbrowser.open(url)


async def main():
    """主函数"""
    try:
        print(json.dumps({"status": "starting", "message": "正在启动 OAuth 流程..."}))

        # 启动 OAuth 流程，自动打开浏览器
        credentials = await start_oauth_flow(
            on_auth_url=open_browser
        )

        # 输出成功结果（JSON 格式供 Tauri 解析）
        print(json.dumps({
            "status": "success",
            "credentials": credentials
        }, ensure_ascii=False))

        return 0

    except Exception as e:
        print(json.dumps({
            "status": "error",
            "message": str(e)
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
