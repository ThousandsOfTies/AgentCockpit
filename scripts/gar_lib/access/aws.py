"""AWS CLI access channel without simulation-specific decisions."""

from __future__ import annotations

import shutil
import subprocess
from typing import Protocol

from scripts.gar_lib.access.channel import AccessResult, run_cli
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError

_AUTH_FAILURE_MARKERS = (
    "expiredtoken",
    "invalidclienttokenid",
    "unrecognizedclientexception",
    "security token included in the request",
    "session has expired",
    "unable to locate credentials",
    "could not find credentials",
    "credentials are still expired",
)


class AwsCommandChannel(Protocol):
    def run(self, arguments: tuple[str, ...]) -> AccessResult: ...


class AwsCliChannel:
    def __init__(self, region: str):
        self.region = region

    def run(self, arguments: tuple[str, ...]) -> AccessResult:
        executable = shutil.which("aws")
        if executable is None:
            raise GarDomainError("aws CLIが見つかりません。GARのsetupでAWS CLIを導入してください。")

        argv = (executable, *arguments, "--region", self.region)
        result = run_cli(argv, runner=subprocess.run)
        output = f"{result.stderr}\n{result.stdout}"
        if result.returncode != 0 and self._is_authentication_failure(output):
            raise AccessConnectionError(
                channel="aws",
                endpoint=self.region,
                reason="authentication",
                returncode=result.returncode,
            )
        return result

    @staticmethod
    def _is_authentication_failure(stderr: str) -> bool:
        lowered = stderr.lower()
        return any(marker in lowered for marker in _AUTH_FAILURE_MARKERS)
