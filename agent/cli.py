import argparse
import json
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psutil
import uvicorn

from app.server import app

APP_HOME = Path.home() / ".iflow2api"
PID_FILE = APP_HOME / "agent.pid"
AUTOSTART_STATE_FILE = APP_HOME / "autostart_state.json"
TASK_NAME = "iFlow2API-Agent"
DEFAULT_PORT = 8000


def _ensure_app_home() -> None:
    APP_HOME.mkdir(parents=True, exist_ok=True)


def _load_autostart_state() -> dict:
    if not AUTOSTART_STATE_FILE.exists():
        return {}
    try:
        data = json.loads(AUTOSTART_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_autostart_state(state: dict) -> None:
    _ensure_app_home()
    AUTOSTART_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _set_autostart_state(*, prompted: bool, enabled: Optional[bool]) -> None:
    state = _load_autostart_state()
    state["prompted"] = bool(prompted)
    state["enabled"] = enabled
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_autostart_state(state)


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


def _autostart_task_exists() -> bool:
    if platform.system() != "Windows":
        return False
    code, _ = _run_schtasks(["schtasks", "/Query", "/TN", TASK_NAME])
    return code == 0


def _is_interactive_console() -> bool:
    stdin = getattr(sys, "stdin", None)
    stdout = getattr(sys, "stdout", None)
    return bool((stdin and stdin.isatty()) or (stdout and stdout.isatty()))


def _autostart_prompt_disabled() -> bool:
    value = os.getenv("IFLOW_AGENT_AUTOSTART_PROMPT", "").strip().lower()
    return value in {"0", "false", "no", "off"}


def _prompt_yes_no(title: str, message: str) -> Optional[bool]:
    if platform.system() != "Windows":
        return None
    try:
        import ctypes

        MB_YESNO = 0x00000004
        MB_ICONQUESTION = 0x00000020
        MB_TOPMOST = 0x00040000
        IDYES = 6
        result = ctypes.windll.user32.MessageBoxW(
            None,
            message,
            title,
            MB_YESNO | MB_ICONQUESTION | MB_TOPMOST,
        )
        return result == IDYES
    except Exception:
        if not _is_interactive_console():
            return None
        while True:
            answer = input(f"{message}\n(y/n): ").strip().lower()
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False


def _prompt_autostart_opt_in(port: int) -> Optional[bool]:
    message = (
        f"Enable iFlow2API Agent to auto start at Windows logon on port {port}?\n\n"
        "You can disable later by running:\n"
        "iflow_agent.py uninstall-autostart"
    )
    return _prompt_yes_no("iFlow2API Agent", message)


def _maybe_setup_autostart(command: str, port: int) -> None:
    if command not in {"run", "start"}:
        return
    if platform.system() != "Windows":
        return

    state = _load_autostart_state()
    if state.get("prompted"):
        return

    if _autostart_task_exists():
        _set_autostart_state(prompted=True, enabled=True)
        return

    if _autostart_prompt_disabled() or not _is_interactive_console():
        return

    choice = _prompt_autostart_opt_in(port)
    if choice is None:
        return
    if choice:
        code = cmd_install_autostart(port)
        if code != 0:
            print("Autostart install failed during first-run setup")
        return

    _set_autostart_state(prompted=True, enabled=False)
    print("Autostart skipped. You can enable later with: iflow_agent.py install-autostart")


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
    _set_autostart_state(prompted=True, enabled=True)
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
    _set_autostart_state(prompted=True, enabled=False)
    print(f"Autostart removed: {TASK_NAME}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="iFlow2API Agent")
    sub = parser.add_subparsers(dest="command")

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
    command = args.command or "start"
    port = getattr(args, "port", DEFAULT_PORT)
    _maybe_setup_autostart(command, port)

    if command == "run":
        return cmd_run(port)
    if command == "start":
        return cmd_start(port)
    if command == "stop":
        return cmd_stop()
    if command == "status":
        return cmd_status()
    if command == "install-autostart":
        return cmd_install_autostart(port)
    if command == "uninstall-autostart":
        return cmd_uninstall_autostart()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
