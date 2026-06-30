from __future__ import annotations

import sys
from unittest.mock import MagicMock

from app import native_dialog


def test_native_dialogs_disabled_in_pytest():
    assert native_dialog.native_dialogs_enabled() is False


def test_native_dialogs_enabled_on_windows(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("MECHBAY_NATIVE_DIALOGS", "1")
    monkeypatch.setattr(sys, "platform", "win32")
    assert native_dialog.native_dialogs_enabled() is True


def test_native_dialogs_disabled_with_opt_out(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("MECHBAY_NO_NATIVE_DIALOGS", "1")
    monkeypatch.setattr(sys, "platform", "win32")
    assert native_dialog.native_dialogs_enabled() is False


def test_dialog_command_includes_main_py_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setattr(sys, "executable", "python.exe")
    cmd = native_dialog._dialog_command("open", "inventory")
    assert cmd[0] == "python.exe"
    assert cmd[-3:] == ["--file-dialog", "open", "inventory"]
    assert cmd[1].endswith("main.py")


def test_dialog_command_uses_executable_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", "MechBay.exe")
    cmd = native_dialog._dialog_command("save", "force", default_name="Alpha.mbforce")
    assert cmd == ["MechBay.exe", "--file-dialog", "save", "force", "Alpha.mbforce"]


def test_pick_file_path_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(native_dialog, "native_dialogs_enabled", lambda: False)
    assert native_dialog.pick_file_path("open", "inventory") is None


def test_pick_file_path_returns_stdout_path(monkeypatch):
    monkeypatch.setattr(native_dialog, "native_dialogs_enabled", lambda: True)
    completed = MagicMock(returncode=0, stdout="C:\\data\\test.mechbay\n")
    monkeypatch.setattr(native_dialog.subprocess, "run", lambda *a, **k: completed)
    monkeypatch.setattr(native_dialog, "_dialog_command", lambda *a, **k: ["cmd"])

    assert native_dialog.pick_file_path("open", "inventory") == "C:\\data\\test.mechbay"
