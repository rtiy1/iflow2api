import asyncio
import sys

from auth.cli import main


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
