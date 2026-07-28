"""Docker implementation of SimulationHostController."""

from __future__ import annotations

import shlex

from scripts.gar_lib.access.channel import CommandChannel
from scripts.gar_lib.access.docker import DockerCliCommandChannel
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.simulation.docker_spec import DockerHostSpec
from scripts.gar_lib.simulation.host import SimulationHostStartResult, SimulationHostState

BACKEND_ID = "docker"

DEFAULT_CONTAINER = "gar-sim"
DEFAULT_ADDRESS = "127.0.0.1"

ABSENT_STATE = "absent"


class DockerSimulationHostController:
    """simulation host のライフサイクルを container のライフサイクルとして扱う。"""

    def __init__(
        self,
        *,
        container: str,
        spec: DockerHostSpec,
        docker: DockerCliCommandChannel,
        repository_channel: CommandChannel,
        address: str = DEFAULT_ADDRESS,
        repository_path: str | None = None,
    ):
        self.container = container
        self.spec = spec
        self.docker = docker
        self.repository_channel = repository_channel
        self.address = address
        self.repository_path = repository_path

    @property
    def image(self) -> str:
        return self.spec.image

    @property
    def bridge_port(self) -> int:
        return self.spec.bridge_port

    def start(
        self,
        *,
        update_address: bool = True,
        update_repository: bool = False,
    ) -> SimulationHostStartResult:
        current = self.status()
        if current.state == ABSENT_STATE:
            self._create()
        elif not current.running:
            self._require_success(
                self.docker.run(("start", self.container)),
                "container の起動に失敗しました",
            )

        state = self.status()
        if not state.running:
            raise GarDomainError(f"container が running ではありません: {state.state}")

        repository_updated = False
        repository_update_skipped = False
        if update_repository:
            if self.repository_path:
                result = self.repository_channel.run(
                    f"cd {shlex.quote(self.repository_path)} && git pull --ff-only"
                )
                self._require_success(result, "container 内の git pull に失敗しました")
                repository_updated = True
            else:
                repository_update_skipped = True

        # container のアドレスは publish 済みポートで固定なので、更新すべき設定はない。
        return SimulationHostStartResult(
            state=state,
            address_updated=False,
            repository_updated=repository_updated,
            repository_update_skipped=repository_update_skipped,
        )

    def stop(self) -> None:
        state = self.status()
        if state.state == ABSENT_STATE:
            raise GarDomainError(f"container が存在しません: {self.container}")
        self._require_success(
            self.docker.run(("stop", self.container)),
            "container の停止に失敗しました",
        )

    def status(self) -> SimulationHostState:
        result = self.docker.run(
            ("inspect", "--format", "{{.State.Status}}", self.container)
        )
        state = result.stdout.strip() if result.returncode == 0 else ABSENT_STATE
        return SimulationHostState(
            host=self.container,
            backend=BACKEND_ID,
            id=self.container,
            state=state or ABSENT_STATE,
            address=self.address if state == "running" else None,
            details={"image": self.spec.image, "bridge_port": str(self.spec.bridge_port)},
        )

    def _create(self) -> None:
        self._ensure_image()
        arguments = (
            "run",
            "--detach",
            "--name",
            self.container,
            "--publish",
            f"{self.spec.bridge_port}:{self.spec.bridge_port}",
            *self.spec.run_options,
            self.spec.image,
            *self.spec.init_command,
        )
        self._require_success(self.docker.run(arguments), "container の作成に失敗しました")

    def _ensure_image(self) -> None:
        if self.docker.run(("image", "inspect", self.spec.image)).returncode == 0:
            return
        if self.spec.build_context is None:
            raise GarDomainError(
                f"container image が見つかりません: {self.spec.image}。"
                "target定義に buildContext を追加するか、image を先に用意してください"
            )
        self._require_success(
            self.docker.run(
                ("build", "--tag", self.spec.image, self.spec.build_context)
            ),
            "container image の作成に失敗しました",
        )

    @staticmethod
    def _require_success(result, message: str) -> None:
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise GarDomainError(f"{message} (exit {result.returncode}): {detail}")
