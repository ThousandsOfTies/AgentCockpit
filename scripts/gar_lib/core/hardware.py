"""Hardware definition CSV の読込とテンプレート生成。"""

from __future__ import annotations

import csv
import re
from pathlib import Path

HardwareDefinition = dict[str, list[dict[str, str]]]


HW_TEMPLATE_FILES: dict[str, list[str]] = {
    "components.csv": ["component_id", "name", "kind", "part_number", "description"],
    "gpio.csv": [
        "name",
        "chip",
        "line",
        "direction",
        "role",
        "active",
        "initial",
        "pull",
        "sim_control",
        "description",
    ],
    "i2c.csv": ["name", "bus", "dev", "address", "driver", "sim", "description"],
    "spi.csv": [
        "name",
        "bus",
        "chip_select",
        "dev",
        "mode",
        "max_speed_hz",
        "driver",
        "sim",
        "description",
    ],
    "video.csv": ["name", "dev", "driver", "sim", "width", "height", "fps", "description"],
    "connections.csv": ["source", "source_pin", "target", "target_pin", "signal", "description"],
}

DEFAULT_HW_TARGET = "linux-device"
TARGET_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _resolve_hw_dir(output_dir: str | None) -> Path:
    if output_dir:
        path = Path(output_dir).expanduser()
        return path if path.is_absolute() else Path.cwd() / path
    return Path.cwd() / "hardware"


def _read_hw_csv(hw_dir: Path, name: str) -> list[dict[str, str]]:
    path = hw_dir / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [
            {str(key): (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]


def load_hw_definition(*, hw_dir: str | None = None) -> HardwareDefinition:
    """Load hardware assignment CSV files as plain row dictionaries."""

    # Assignment CSVs are product inputs.  Never fall back to a selected
    # target or the caller's CWD, because a Target Pack describes board
    # capability, not an application's components or wiring.
    if hw_dir is None:
        return {
            "components": [],
            "gpio": [],
            "i2c": [],
            "spi": [],
            "video": [],
            "connections": [],
        }
    root = _resolve_hw_dir(hw_dir)
    return {
        "components": _read_hw_csv(root, "components.csv"),
        "gpio": _read_hw_csv(root, "gpio.csv"),
        "i2c": _read_hw_csv(root, "i2c.csv"),
        "spi": _read_hw_csv(root, "spi.csv"),
        "video": _read_hw_csv(root, "video.csv"),
        "connections": _read_hw_csv(root, "connections.csv"),
    }


def write_hw_template(
    *,
    output_dir: str | None = None,
    force: bool = False,
    target_id: str = DEFAULT_HW_TARGET,
) -> int:
    """Create empty product-owned hardware assignment CSV files."""

    if not isinstance(target_id, str) or not TARGET_ID_PATTERN.fullmatch(target_id):
        print(f"gar hw init: invalid target id: {target_id!r}")
        return 1

    hw_dir = _resolve_hw_dir(output_dir)
    existing = [name for name in HW_TEMPLATE_FILES if (hw_dir / name).exists()]
    if existing and not force:
        print("gar hw init: already exists: " + ", ".join(str(hw_dir / name) for name in existing))
        print("gar hw init: use --force to overwrite template files")
        return 1

    hw_dir.mkdir(parents=True, exist_ok=True)
    for name, headers in HW_TEMPLATE_FILES.items():
        path = hw_dir / name
        with path.open("w", encoding="utf-8", newline="") as file:
            csv.writer(file, lineterminator="\n").writerow(headers)
        print(f"created {path}")
    return 0
