import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import psutil
import uvicorn

from app.server import app

APP_HOME = Path.home() / ".iflow2api"
PID_FILE = APP_HOME / "agent.pid"
TASK_NAME = "iFlow2API-Agent"
DEFAULT_PORT = 8000


def _ensure_app_home() -> None:
    APP_HOME.mkdir(parents=True, exist_ok=True)


def _read_pid() -> Optional[int]:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _write_pid(pid: int) -> None:
    _ensure_app_home()
    PID_FILE.write_text(str(pid), encoding="utf-8")


def _remove_pid() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink()


def _is_running(pid: Optional[int]) -> bool:
    if not pid:
        return False
    return psutil.pid_exists(pid)


def _get_python_executable() -> str:
    exe_path = Path(sys.executable)
    if exe_path.name.lower() == "python.exe":
        pythonw = exe_path.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
    return str(exe_path)


def _agent_entry_path() -> str:
    return str(Path(__file__).resolve().parents[1] / "iflow_agent.py")


def _run_argv(port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "run", "--port", str(port)]
    return [sys.executable, _agent_entry_path(), "run", "--port", str(port)]


def _autostart_command(port: int) -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" run --port {port}'
    return f'"{_get_python_executable()}" "{_agent_entry_path()}" run --port {port}'


def cmd_run(port: int) -> int:
    existing_pid = _read_pid()
    if _is_running(existing_pid) and existing_pid != os.getpid():
        print(f"iFlow2API agent is already running (pid={existing_pid})")
        return 1

    _write_pid(os.getpid())

    def _cleanup(*_args):
        _remove_pid()
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _cleanup)

    try:
        uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
    finally:
        _remove_pid()
    return 0


def cmd_start(port: int) -> int:
    existing_pid = _read_pid()
    if _is_running(existing_pid):
        print(f"iFlow2API agent is already running (pid={existing_pid})")
        return 0

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(
        _run_argv(port),
        creationflags=creationflags,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(30):
        pid = _read_pid()
        if _is_running(pid):
            print(f"iFlow2API agent started (pid={pid}, port={port})")
            return 0
        time.sleep(0.2)

    print("Failed to start iFlow2API agent")
    return 1


def cmd_stop() -> int:
    pid = _read_pid()
    if not pid:
        print("iFlow2API agent is not running")
        return 0

    if not _is_running(pid):
        _remove_pid()
        print("Removed stale pid file")
        return 0

    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=10)
    except psutil.TimeoutExpired:
        proc.kill()
    except psutil.NoSuchProcess:
        pass
    finally:
        _remove_pid()

    print("iFlow2API agent stopped")
    return 0


def cmd_status() -> int:
    pid = _read_pid()
    if _is_running(pid):
        print(f"iFlow2API agent is running (pid={pid})")
        return 0
    print("iFlow2API agent is not running")
    if pid:
        _remove_pid()
    return 1


def _run_schtasks(args: list[str]) -> tuple[int, str]:
    result = subprocess.run(args, capture_output=True, text=True, shell=False)
    output = (result.stdout or result.stderr or "").strip()
    return result.returncode, output


def cmd_install_autostart(port: int) -> int:
    if platform.system() != "Windows":
        print("Autostart install is only supported on Windows")
        return 1
    command = _autostart_command(port)
    code, output = _run_schtasks(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/SC", "ONLOGON", "/TR", command, "/F"]
    )
    if code != 0:
        print(f"Install autostart failed: {output}")
        return code
    print(f"Autostart installed: {TASK_NAME}")
    return 0


def cmd_uninstall_autostart() -> int:
    if platform.system() != "Windows":
        print("Autostart uninstall is only supported on Windows")
        return 1
    code, output = _run_schtasks(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    if code != 0:
        print(f"Uninstall autostart failed: {output}")
        return code
    print(f"Autostart removed: {TASK_NAME}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="iFlow2API Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run in foreground")
    p_run.add_argument("--port", type=int, default=DEFAULT_PORT)

    p_start = sub.add_parser("start", help="start in background")
    p_start.add_argument("--port", type=int, default=DEFAULT_PORT)

    sub.add_parser("stop", help="stop background process")
    sub.add_parser("status", help="show running status")

    p_install = sub.add_parser("install-autostart", help="install Windows autostart task")
    p_install.add_argument("--port", type=int, default=DEFAULT_PORT)

    sub.add_parser("uninstall-autostart", help="remove Windows autostart task")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        return cmd_run(args.port)
    if args.command == "start":
        return cmd_start(args.port)
    if args.command == "stop":
        return cmd_stop()
    if args.command == "status":
        return cmd_status()
    if args.command == "install-autostart":
        return cmd_install_autostart(args.port)
    if args.command == "uninstall-autostart":
        return cmd_uninstall_autostart()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
