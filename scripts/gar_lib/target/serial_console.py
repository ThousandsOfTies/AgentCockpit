"""Small dependency-free serial-console readiness probe."""

from __future__ import annotations

import os
import select
import termios
import time
from pathlib import Path

from scripts.gar_lib.core.errors import GarDomainError


def wait_for_serial_pattern(
    port: str,
    *,
    baud: int,
    pattern: str,
    timeout_seconds: float,
) -> None:
    """Wait until a USB-UART console emits *pattern*.

    The FRDM debug UART is exposed as a normal Linux character device, so this
    intentionally uses only POSIX termios/select primitives and does not add a
    Python serial-package dependency to the GAR runtime.
    """

    if os.name != "posix":
        raise GarDomainError("USB-C serial verificationはLinux/WSLのPOSIX serial deviceに対応しています")
    path = Path(port)
    if not path.is_char_device():
        raise GarDomainError(f"serial console deviceが見つかりません: {port}")
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    except OSError as error:
        raise GarDomainError(f"serial consoleを開けません: {port}: {error}") from error

    try:
        attributes = termios.tcgetattr(fd)
        termios.cfmakeraw(attributes)
        speed = getattr(termios, f"B{baud}", None)
        if speed is None:
            raise GarDomainError(f"未対応のserial baud rateです: {baud}")
        attributes[4] = speed
        attributes[5] = speed
        termios.tcsetattr(fd, termios.TCSANOW, attributes)
        deadline = time.monotonic() + timeout_seconds
        received = bytearray()
        expected = pattern.encode("utf-8")
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                break
            try:
                received.extend(os.read(fd, 4096))
            except BlockingIOError:
                continue
            if expected in received:
                return
    finally:
        os.close(fd)

    raise GarDomainError(f"serial consoleで起動確認文字列を受信できませんでした: {pattern!r}")
