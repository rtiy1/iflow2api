import subprocess
import sys
import os
from pathlib import Path

VENV_DIR = "venv_gui"
ICON = "icon.ico"
OUTPUT_NAME = "iflow2api-gui"
MAIN_FILE = "gui_pyqt.py"

def run(cmd):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    # Create clean venv
    if not Path(VENV_DIR).exists():
        print(f"Creating virtual environment: {VENV_DIR}")
        run(f"{sys.executable} -m venv {VENV_DIR}")

    # Install dependencies
    pip = str(Path(VENV_DIR) / "Scripts" / "pip.exe")
    python = str(Path(VENV_DIR) / "Scripts" / "python.exe")

    print("Installing dependencies...")
    run(f"{pip} install -r requirements.txt")
    run(f"{pip} install pyinstaller")

    # Run PyInstaller
    print("Running PyInstaller...")
    cmd = [
        python, "-m", "PyInstaller",
        "--onefile",
        "--name", OUTPUT_NAME,
        "--icon", ICON,
        "--noconsole",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        MAIN_FILE
    ]
    run(" ".join(cmd))

    # Run UPX if available
    upx_path = Path("upx-4.2.4-win64") / "upx.exe"
    exe_path = Path("dist") / f"{OUTPUT_NAME}.exe"

    if upx_path.exists() and exe_path.exists():
        print("Running UPX compression...")
        try:
            run(f"{upx_path} --best --lzma --force {exe_path}")
        except:
            print("UPX compression failed, continuing...")

    print(f"\nBuild complete: {exe_path}")
    print(f"Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    main()
