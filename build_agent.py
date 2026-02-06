import subprocess
import sys
from pathlib import Path

VENV_DIR = "venv_gui"
ICON = "icon.ico"
OUTPUT_NAME = "iflow2api-agent"
MAIN_FILE = "iflow_agent.py"


def run(cmd: str):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def main():
    if not Path(VENV_DIR).exists():
        print(f"Creating virtual environment: {VENV_DIR}")
        run(f"{sys.executable} -m venv {VENV_DIR}")

    pip = str(Path(VENV_DIR) / "Scripts" / "pip.exe")
    python = str(Path(VENV_DIR) / "Scripts" / "python.exe")

    print("Installing dependencies...")
    run(f"{pip} install -r requirements.txt")
    run(f"{pip} install pyinstaller")

    print("Running PyInstaller...")
    cmd = [
        python, "-m", "PyInstaller",
        "--onefile",
        "--name", OUTPUT_NAME,
        "--icon", ICON,
        "--add-data", f"{ICON};.",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.lifespan.on",
        MAIN_FILE,
    ]
    run(" ".join(cmd))

    exe_path = Path("dist") / f"{OUTPUT_NAME}.exe"
    print(f"\nBuild complete: {exe_path}")
    if exe_path.exists():
        print(f"Size: {exe_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
