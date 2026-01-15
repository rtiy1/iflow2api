import subprocess
import sys

# 使用 PyInstaller 打包
subprocess.run([
    sys.executable, "-m", "PyInstaller",
    "--onefile", "--windowed",
    "--name", "iFlow2API",
    "--hidden-import", "main",
    "--hidden-import", "config",
    "--hidden-import", "converters",
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.lifespan.on",
    "--collect-submodules", "flet",
    "gui.py"
])
