"""iFlow OAuth 认证 CLI 工具"""

import asyncio
import sys
from pathlib import Path
from .oauth import start_oauth_flow


async def main():
    """主函数"""
    print("=" * 60)
    print("iFlow OAuth 认证工具")
    print("=" * 60)
    print()

    try:
        # 启动 OAuth 流程
        credentials = await start_oauth_flow()

        print()
        print("=" * 60)
        print("✓ 认证成功！")
        print("=" * 60)
        print(f"API Key: {credentials['apiKey'][:20]}...")
        print(f"凭证已保存到: {Path.home() / '.iflow' / 'oauth_creds.json'}")
        print()
        print("现在可以启动 API 服务了：")
        print("  python main.py")
        print()

        return 0
    except KeyboardInterrupt:
        print("\n\n认证已取消")
        return 1
    except Exception as e:
        print(f"\n\n✗ 认证失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
