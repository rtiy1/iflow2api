import subprocess
import sys

subprocess.run([
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",
    "--windows-console-mode=disable",
    "--include-module=main",
    "--include-module=config",
    "--include-module=converters",
    "--include-module=uvicorn",
    "--include-module=httpx",
    "--include-module=fastapi",
    "--include-package=flet",
    "--output-filename=iFlow2API.exe",
    "gui.py"
])
