"""gar-tools repository の探索と取得。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from scripts.gar_lib.config import PROJECT_ROOT

DEFAULT_GAR_TOOLS_REPO = "https://github.com/ThousandsOfTies/gar-tools"


def gar_tools_root() -> Path:
    existing = find_gar_tools_root()
    if existing is not None:
        return existing
    return PROJECT_ROOT / ".gar" / "tools"


def find_gar_tools_root() -> Path | None:
    for candidate in gar_tools_root_candidates():
        if (candidate / "targets").is_dir():
            return candidate
    return None


def gar_tools_root_candidates() -> list[Path]:
    raw = os.environ.get("GAR_TOOLS_ROOT")
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw).expanduser())

    candidates.extend(
        [
            PROJECT_ROOT / "gar-tools",
            PROJECT_ROOT / ".gar" / "tools",
            PROJECT_ROOT.parent / "gar-tools",
        ]
    )

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve(strict=False))
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def ensure_gar_tools_available(*, auto_clone: bool = True) -> Path | None:
    existing = find_gar_tools_root()
    if existing is not None or not auto_clone:
        return existing

    destination = PROJECT_ROOT / ".gar" / "tools"
    repository = os.environ.get("GAR_TOOLS_REPO", DEFAULT_GAR_TOOLS_REPO)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["git", "clone", "--depth", "1", repository, str(destination)], check=False)
    return destination if result.returncode == 0 else None
