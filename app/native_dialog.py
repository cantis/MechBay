"""Native file dialogs for the Windows desktop build."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import structlog

from .services.document_service import FORCE_EXTENSION, INVENTORY_EXTENSION

logger = structlog.get_logger()


def native_dialogs_enabled() -> bool:
    if os.environ.get("MECHBAY_NO_NATIVE_DIALOGS", "").lower() in ("1", "true", "yes"):
        return False
    if os.environ.get("TESTING") or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    if os.environ.get("MECHBAY_NATIVE_DIALOGS", "").lower() in ("1", "true", "yes"):
        return True
    # Tkinter file dialogs work on Windows in dev and frozen builds.
    return sys.platform == "win32"


def _dialog_command(mode: str, kind: str, *, default_name: str = "") -> list[str]:
    args = ["--file-dialog", mode, kind]
    if default_name:
        args.append(default_name)
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    return [sys.executable, str(main_py), *args]


def run_dialog_cli(argv: list[str]) -> None:
    """Entry point for `MechBay.exe --file-dialog <open|save> <inventory|force> [default_name]`."""
    import tkinter as tk
    from tkinter import filedialog

    if len(argv) < 2:
        sys.exit(2)

    mode = argv[0]
    kind = argv[1]
    default_name = argv[2] if len(argv) > 2 else ""

    if kind == "inventory":
        filetypes = [("MechBay inventory", f"*{INVENTORY_EXTENSION}"), ("All files", "*.*")]
        default_ext = INVENTORY_EXTENSION
    else:
        filetypes = [("MechBay force", f"*{FORCE_EXTENSION}"), ("All files", "*.*")]
        default_ext = FORCE_EXTENSION

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if mode == "open":
            path = filedialog.askopenfilename(filetypes=filetypes)
        elif mode == "save":
            path = filedialog.asksaveasfilename(
                defaultextension=default_ext,
                filetypes=filetypes,
                initialfile=default_name or None,
            )
        else:
            sys.exit(2)
    finally:
        root.destroy()

    if path:
        print(Path(path).resolve())
    sys.exit(0)


def pick_file_path(mode: str, kind: str, *, default_name: str = "") -> str | None:
    """Show a native dialog in a subprocess and return the chosen path."""
    if not native_dialogs_enabled():
        return None

    cmd = _dialog_command(mode, kind, default_name=default_name)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("native_dialog_failed", error=str(exc))
        return None

    if result.returncode != 0:
        return None

    path = result.stdout.strip()
    return path or None
