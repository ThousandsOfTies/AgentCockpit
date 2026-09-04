"""Repository-local Python runtime bootstrap shared by GAR launchers."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
GAR_REQUIREMENTS = ROOT / "requirements-gar.txt"

REQUIRED_IMPORTS = ("argcomplete", "serial", "psutil")


def ensure_venv() -> int:
    """Create the repository venv and install GAR runtime dependencies."""

    if not VENV_PYTHON.exists():
        result = subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=False)
        if result.returncode != 0 or not VENV_PYTHON.exists():
            print(
                "python3 -m venv がpip付きvenvを作成できませんでした。"
                " Pythonのvenv機能を導入してsetupを再実行してください。",
                file=sys.stderr,
            )
            return result.returncode or 1

    pip_check = subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if pip_check.returncode != 0:
        print(
            ".venvにpipがありません。既存の.venvを削除し、Pythonのvenv機能を導入してsetupを再実行してください。",
            file=sys.stderr,
        )
        return pip_check.returncode or 1

    dependency_check = subprocess.run(
        [
            str(VENV_PYTHON),
            "-c",
            "; ".join(f"import {module}" for module in REQUIRED_IMPORTS),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if dependency_check.returncode != 0:
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(GAR_REQUIREMENTS)],
            check=False,
        )
        if result.returncode != 0:
            return result.returncode

    return 0


def relaunch_in_venv(
    script: Path,
    argv: Sequence[str],
    *,
    environ: Mapping[str, str] | None = None,
) -> int | None:
    """Relaunch ``script`` once in the repository venv when needed.

    ``None`` means the caller already runs in the repository venv and should
    continue locally. An integer is the completed child process exit code.
    """

    environment = os.environ if environ is None else environ
    if environment.get("GAR_VENV") == str(VENV) or environment.get("VIRTUAL_ENV") == str(VENV):
        return None

    result = ensure_venv()
    if result != 0:
        return result

    child_environment = dict(environment)
    child_environment["GAR_VENV"] = str(VENV)
    return subprocess.run(
        [str(VENV_PYTHON), str(script), *argv],
        env=child_environment,
        check=False,
    ).returncode
