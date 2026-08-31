"""Compatibility wrapper for the cross-platform serial readiness adapter."""

from __future__ import annotations

from scripts.gar_lib.access.serial import PySerialPatternVerifier


def wait_for_serial_pattern(
    port: str,
    *,
    baud: int,
    pattern: str,
    timeout_seconds: float,
) -> None:
    """Wait until a serial console emits *pattern* on COM or ``/dev``."""

    PySerialPatternVerifier().wait(
        port,
        baud=baud,
        pattern=pattern,
        timeout_seconds=timeout_seconds,
    )
