import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


def _install_import_stubs() -> None:
    psutil_mod = types.ModuleType("psutil")
    psutil_mod.pid_exists = lambda _pid: False

    class TimeoutExpired(Exception):
        pass

    class NoSuchProcess(Exception):
        pass

    class Process:
        def __init__(self, _pid):
            self.pid = _pid

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return None

        def kill(self):
            return None

    psutil_mod.TimeoutExpired = TimeoutExpired
    psutil_mod.NoSuchProcess = NoSuchProcess
    psutil_mod.Process = Process
    sys.modules["psutil"] = psutil_mod

    uvicorn_mod = types.ModuleType("uvicorn")
    uvicorn_mod.run = lambda *args, **kwargs: None
    sys.modules["uvicorn"] = uvicorn_mod

    app_mod = types.ModuleType("app")
    app_mod.__path__ = []
    server_mod = types.ModuleType("app.server")
    server_mod.app = object()
    sys.modules["app"] = app_mod
    sys.modules["app.server"] = server_mod
    app_mod.server = server_mod


_install_import_stubs()
sys.modules.pop("agent.cli", None)
sys.modules.pop("agent", None)
cli = importlib.import_module("agent.cli")


class AgentCliAutostartTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.app_home = Path(self.tmpdir.name)
        self.pid_file = self.app_home / "agent.pid"
        self.state_file = self.app_home / "autostart_state.json"

        self.patchers = [
            patch.object(cli, "APP_HOME", self.app_home),
            patch.object(cli, "PID_FILE", self.pid_file),
            patch.object(cli, "AUTOSTART_STATE_FILE", self.state_file),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmpdir.cleanup()

    def test_first_run_prompt_accept_installs_autostart(self):
        with patch.object(cli, "_autostart_task_exists", return_value=False), patch.object(
            cli, "_is_interactive_console", return_value=True
        ), patch.object(cli, "_autostart_prompt_disabled", return_value=False), patch.object(
            cli, "_prompt_autostart_opt_in", return_value=True
        ), patch.object(
            cli, "platform"
        ) as platform_mock, patch.object(
            cli, "_run_schtasks", return_value=(0, "ok")
        ), patch.object(
            cli, "_autostart_command", return_value="fake-command"
        ):
            platform_mock.system.return_value = "Windows"
            cli._maybe_setup_autostart("start", 8000)

        state = cli._load_autostart_state()
        self.assertTrue(state.get("prompted"))
        self.assertTrue(state.get("enabled"))

    def test_first_run_prompt_decline_records_disabled(self):
        with patch.object(cli, "_autostart_task_exists", return_value=False), patch.object(
            cli, "_is_interactive_console", return_value=True
        ), patch.object(cli, "_autostart_prompt_disabled", return_value=False), patch.object(
            cli, "_prompt_autostart_opt_in", return_value=False
        ), patch.object(
            cli, "platform"
        ) as platform_mock:
            platform_mock.system.return_value = "Windows"
            cli._maybe_setup_autostart("run", 8000)

        state = cli._load_autostart_state()
        self.assertTrue(state.get("prompted"))
        self.assertFalse(state.get("enabled"))

    def test_existing_task_marks_enabled_without_prompt(self):
        with patch.object(cli, "_autostart_task_exists", return_value=True), patch.object(
            cli, "_prompt_autostart_opt_in"
        ) as prompt_mock, patch.object(cli, "platform") as platform_mock:
            platform_mock.system.return_value = "Windows"
            cli._maybe_setup_autostart("run", 8000)

        prompt_mock.assert_not_called()
        state = cli._load_autostart_state()
        self.assertTrue(state.get("prompted"))
        self.assertTrue(state.get("enabled"))

    def test_non_start_commands_skip_bootstrap(self):
        with patch.object(cli, "_autostart_task_exists") as task_mock, patch.object(
            cli, "_prompt_autostart_opt_in"
        ) as prompt_mock, patch.object(cli, "platform") as platform_mock:
            platform_mock.system.return_value = "Windows"
            cli._maybe_setup_autostart("status", 8000)

        task_mock.assert_not_called()
        prompt_mock.assert_not_called()
        self.assertFalse(self.state_file.exists())

    def test_manual_install_and_uninstall_update_state(self):
        with patch.object(cli, "platform") as platform_mock, patch.object(
            cli, "_run_schtasks", return_value=(0, "ok")
        ), patch.object(cli, "_autostart_command", return_value="fake-command"):
            platform_mock.system.return_value = "Windows"
            install_code = cli.cmd_install_autostart(9000)
            uninstall_code = cli.cmd_uninstall_autostart()

        self.assertEqual(install_code, 0)
        self.assertEqual(uninstall_code, 0)
        state = cli._load_autostart_state()
        self.assertTrue(state.get("prompted"))
        self.assertFalse(state.get("enabled"))

    def test_main_without_args_defaults_to_start(self):
        with patch.object(cli.sys, "argv", ["iflow2api-agent.exe"]), patch.object(
            cli, "_maybe_setup_autostart"
        ) as maybe_mock, patch.object(cli, "cmd_start", return_value=0) as start_mock:
            exit_code = cli.main()

        self.assertEqual(exit_code, 0)
        maybe_mock.assert_called_once_with("start", cli.DEFAULT_PORT)
        start_mock.assert_called_once_with(cli.DEFAULT_PORT)


if __name__ == "__main__":
    unittest.main()
