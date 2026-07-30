"""ESP32 firmware artifact layout used by the physical target deployer."""

from __future__ import annotations

from pathlib import Path

FLASH_LAYOUT = (
    ("0x1000", "bootloader.bin"),
    ("0x8000", "partitions.bin"),
    ("0xE000", "boot_app0.bin"),
    ("0x10000", "firmware.bin"),
)


def resolve_esp32_artifact_dir(artifact_dir: str | None) -> Path | None:
    """Resolve the artifact explicitly supplied by the product build pipeline."""

    if artifact_dir is None:
        return None
    return Path(artifact_dir).expanduser().resolve()
