"""Docker implementation of SimulationHostController."""

from __future__ import annotations

import json
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from scripts.gar_lib.access.channel import CommandChannel
from scripts.gar_lib.access.docker import DockerCliCommandChannel
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.simulation.host.contract import SimulationHostStartResult, SimulationHostState
from scripts.gar_lib.simulation.host.docker_spec import DockerHostSpec

BACKEND_ID = "docker"

DEFAULT_CONTAINER = "gar-sim"
DEFAULT_ADDRESS = "127.0.0.1"

ABSENT_STATE = "absent"
SPEC_FINGERPRINT_LABEL = "io.gapless-agent-runtime.simulation-host-spec"


@dataclass(frozen=True)
class DockerPortBinding:
    container_port: int
    published_port: int
    protocol: str
    host_ip: str

    def render(self) -> str:
        host = _render_host(self.host_ip or "0.0.0.0")
        return f"{host}:{self.published_port}->{self.container_port}/{self.protocol}"


@dataclass(frozen=True)
class DockerContainerInspection:
    state: str
    image: str
    port_bindings: tuple[DockerPortBinding, ...]
    spec_fingerprint: str | None

    @classmethod
    def from_json(cls, value: str) -> DockerContainerInspection:
        try:
            document = json.loads(value)
        except json.JSONDecodeError as exc:
            raise GarDomainError(f"docker inspect のJSONを解釈できません: {exc}") from exc
        if not isinstance(document, Mapping):
            raise GarDomainError("docker inspect がobjectを返しませんでした")

        state = _string_at(document, "State", "Status") or "unknown"
        image = _string_at(document, "Config", "Image") or "unknown"
        fingerprint = _string_at(
            document,
            "Config",
            "Labels",
            SPEC_FINGERPRINT_LABEL,
        )
        return cls(
            state=state,
            image=image,
            port_bindings=_port_bindings(document),
            spec_fingerprint=fingerprint,
        )


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
        return self.spec.published_bridge_port

    def start(
        self,
        *,
        update_address: bool = True,
        update_repository: bool = False,
    ) -> SimulationHostStartResult:
        inspection = self._inspect()
        if inspection is None:
            self._create()
        else:
            self._require_current_spec(inspection)

        if inspection is not None and inspection.state != "running":
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
                result = self.repository_channel.run(f"cd {shlex.quote(self.repository_path)} && git pull --ff-only")
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
        if self._inspect() is None:
            raise GarDomainError(f"container が存在しません: {self.container}")
        self._require_success(
            self.docker.run(("stop", self.container)),
            "container の停止に失敗しました",
        )

    def status(self) -> SimulationHostState:
        inspection = self._inspect()
        if inspection is None:
            return SimulationHostState(
                host=self.container,
                backend=BACKEND_ID,
                id=self.container,
                state=ABSENT_STATE,
                details={"spec_matches": "false", "spec_drift": "container is absent"},
            )

        drift = self._spec_drift(inspection)
        details = self._status_details(inspection, drift)
        return SimulationHostState(
            host=self.container,
            backend=BACKEND_ID,
            id=self.container,
            state=inspection.state,
            address=self.address if inspection.state == "running" else None,
            details=details,
        )

    def _inspect(self) -> DockerContainerInspection | None:
        result = self.docker.run(("inspect", "--format", "{{json .}}", self.container))
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).lower()
            if "no such object" in detail or "no such container" in detail:
                return None
            self._require_success(result, "container の状態確認に失敗しました")
        return DockerContainerInspection.from_json(result.stdout)

    def _require_current_spec(self, inspection: DockerContainerInspection) -> None:
        drift = self._spec_drift(inspection)
        if not drift:
            return
        differences = "; ".join(drift)
        raise GarDomainError(
            f"既存container {self.container} は現在のtarget specと一致しません: "
            f"{differences}。`docker rm -f {self.container}` で削除してから再実行してください"
        )

    def _spec_drift(self, inspection: DockerContainerInspection) -> tuple[str, ...]:
        differences: list[str] = []
        if inspection.image != self.spec.image:
            differences.append(f"image={inspection.image!r} (expected {self.spec.image!r})")

        expected_binding = (
            self.spec.container_bridge_port,
            self.spec.published_bridge_port,
            "tcp",
            self.spec.published_host,
        )
        actual_bindings = {
            (
                binding.container_port,
                binding.published_port,
                binding.protocol,
                binding.host_ip or "0.0.0.0",
            )
            for binding in inspection.port_bindings
        }
        if expected_binding not in actual_bindings:
            rendered = ", ".join(binding.render() for binding in inspection.port_bindings)
            expected_host = _render_host(self.spec.published_host)
            differences.append(
                f"bridge port={rendered or '(none)'} "
                f"(expected {expected_host}:"
                f"{self.spec.published_bridge_port}->"
                f"{self.spec.container_bridge_port}/tcp)"
            )

        if inspection.spec_fingerprint != self.spec.fingerprint:
            if inspection.spec_fingerprint is None:
                differences.append("spec fingerprint label is missing")
            else:
                differences.append("spec fingerprint differs")
        return tuple(differences)

    def _status_details(
        self,
        inspection: DockerContainerInspection,
        drift: tuple[str, ...],
    ) -> dict[str, str]:
        bindings = ", ".join(binding.render() for binding in inspection.port_bindings)
        details = {
            "image": inspection.image,
            "port_bindings": bindings or "(none)",
            "spec_matches": str(not drift).lower(),
            "expected_image": self.spec.image,
            "expected_port_binding": (
                f"{_render_host(self.spec.published_host)}:"
                f"{self.spec.published_bridge_port}->"
                f"{self.spec.container_bridge_port}/tcp"
            ),
        }
        if drift:
            details["spec_drift"] = "; ".join(drift)
        return details

    def _create(self) -> None:
        self._ensure_image()
        published_bridge = ":".join(
            (
                _render_host(self.spec.published_host),
                str(self.spec.published_bridge_port),
                str(self.spec.container_bridge_port),
            )
        )
        arguments = (
            "run",
            "--detach",
            "--name",
            self.container,
            "--label",
            f"{SPEC_FINGERPRINT_LABEL}={self.spec.fingerprint}",
            "--publish",
            published_bridge,
            "--env",
            f"GAR_BRIDGE_PORT={self.spec.container_bridge_port}",
            *self.spec.run_options,
            self.spec.image,
            *self.spec.init_command,
        )
        self._require_success(self.docker.run(arguments), "container の作成に失敗しました")

    def _ensure_image(self) -> None:
        if self.spec.build_context is not None and self.spec.build_context_fingerprint is not None:
            self._require_success(
                self.docker.run(("build", "--tag", self.spec.image, self.spec.build_context)),
                "container image のbuildに失敗しました",
            )
            return
        if self.docker.run(("image", "inspect", self.spec.image)).returncode == 0:
            return
        if self.spec.build_context is None:
            raise GarDomainError(
                f"container image が見つかりません: {self.spec.image}。"
                "target定義に buildContext を追加するか、image を先に用意してください"
            )
        self._require_success(
            self.docker.run(("build", "--tag", self.spec.image, self.spec.build_context)),
            "container image の作成に失敗しました",
        )

    @staticmethod
    def _require_success(result, message: str) -> None:
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise GarDomainError(f"{message} (exit {result.returncode}): {detail}")


def _string_at(document: Mapping[str, Any], *path: str) -> str | None:
    current: Any = document
    for name in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(name)
    return current if isinstance(current, str) and current else None


def _render_host(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def _port_bindings(document: Mapping[str, Any]) -> tuple[DockerPortBinding, ...]:
    host_config = document.get("HostConfig")
    if not isinstance(host_config, Mapping):
        return ()
    raw_bindings = host_config.get("PortBindings")
    if not isinstance(raw_bindings, Mapping):
        return ()

    bindings: list[DockerPortBinding] = []
    for container_endpoint, host_bindings in raw_bindings.items():
        endpoint = _parse_container_endpoint(container_endpoint)
        if endpoint is None or not isinstance(host_bindings, Sequence):
            continue
        container_port, protocol = endpoint
        for host_binding in host_bindings:
            if not isinstance(host_binding, Mapping):
                continue
            published_port = _parse_port(host_binding.get("HostPort"))
            if published_port is None:
                continue
            host_ip = host_binding.get("HostIp")
            bindings.append(
                DockerPortBinding(
                    container_port=container_port,
                    published_port=published_port,
                    protocol=protocol,
                    host_ip=host_ip if isinstance(host_ip, str) else "",
                )
            )
    return tuple(bindings)


def _parse_container_endpoint(value: Any) -> tuple[int, str] | None:
    if not isinstance(value, str):
        return None
    port_text, separator, protocol = value.partition("/")
    port = _parse_port(port_text)
    if port is None:
        return None
    return port, protocol if separator and protocol else "tcp"


def _parse_port(value: Any) -> int | None:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None
