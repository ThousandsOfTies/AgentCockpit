"""Explicit registry of physical-target access environments."""

from scripts.gar_lib.environments.registry.target.adb_usb import AdbUsbEnvironment
from scripts.gar_lib.environments.registry.target.adb_win import AdbWinEnvironment
from scripts.gar_lib.environments.registry.target.esp32_esptool import (
    Esp32EsptoolEnvironment,
)
from scripts.gar_lib.environments.registry.target.ssh_scp import SshScpEnvironment
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption

ENVIRONMENT_OPTIONS: tuple[type[EnvironmentSetupOption], ...] = (
    AdbUsbEnvironment,
    AdbWinEnvironment,
    Esp32EsptoolEnvironment,
    SshScpEnvironment,
)
