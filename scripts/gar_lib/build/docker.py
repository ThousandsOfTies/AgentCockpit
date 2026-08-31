"""Run Product build hooks in a Linux container owned by the Build layer."""

from __future__ import annotations

import hashlib
import os
from pathlib import PurePosixPath

from scripts.gar_lib.access.docker import DockerCliChannel, DockerCliCommandChannel
from scripts.gar_lib.artifacts.store import BuildArtifactStore
from scripts.gar_lib.build.spec import ProductBuildSpecResolver
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.config import PROJECT_ROOT
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace

DEFAULT_BUILD_IMAGE = "gar-build-env:ubuntu-24.04"
CONTAINER_WORKSPACE = PurePosixPath("/workspace")
DOCKER_SOCKET = "/var/run/docker.sock"
BUILD_SPEC_FINGERPRINT_LABEL = "io.gapless-agent-runtime.build-spec"


class DockerBuildEnvironment:
    """Bind a Product workspace and execute its hook through container Bash."""

    def __init__(
        self,
        artifacts: BuildArtifactStore,
        *,
        docker: DockerCliCommandChannel | None = None,
        specs: ProductBuildSpecResolver | None = None,
    ):
        self.artifacts = artifacts
        self.docker = docker or DockerCliChannel()
        self.specs = specs or ProductBuildSpecResolver()

    def build(self, kind: ArtifactKind, workspace: Workspace) -> Artifact:
        self._run_hook(kind, workspace)
        return self.artifacts.capture(kind, workspace)

    def clean(self, kind: ArtifactKind, workspace: Workspace) -> None:
        self._run_hook(kind, workspace, action="clean")
        self.artifacts.remove(kind, workspace)

    def fetch(self, kind: ArtifactKind, workspace: Workspace) -> Artifact:
        return self.artifacts.latest(kind, workspace)

    def _run_hook(
        self,
        kind: ArtifactKind,
        workspace: Workspace,
        *,
        action: str | None = None,
    ) -> None:
        spec = self.specs.for_artifact(kind, workspace)
        script = workspace.local_root / spec.script
        if not script.is_file():
            raise GarDomainError(f"product build hook が見つかりません: {script}")

        image = workspace.build.image or DEFAULT_BUILD_IMAGE
        if image == DEFAULT_BUILD_IMAGE:
            self._ensure_default_image(image)

        arguments: list[str] = [
            "run",
            "--rm",
            "--mount",
            f"type=bind,source={workspace.local_root},target={CONTAINER_WORKSPACE}",
            "--workdir",
            str(CONTAINER_WORKSPACE),
            "--env",
            "HOME=/tmp/gar-home",
        ]
        if workspace.build.docker_socket:
            arguments.extend(
                (
                    "--mount",
                    f"type=bind,source={DOCKER_SOCKET},target={DOCKER_SOCKET}",
                )
            )
        self._add_posix_identity(arguments, include_socket_group=workspace.build.docker_socket)
        for name, value in sorted(spec.variables.items()):
            arguments.extend(("--env", f"{name}={value}"))

        container_script = CONTAINER_WORKSPACE / PurePosixPath(spec.script)
        arguments.extend((image, "bash", str(container_script)))
        if action is not None:
            arguments.append(action)

        result = self.docker.run(tuple(arguments))
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            suffix = f": {detail}" if detail else ""
            raise GarDomainError(f"{kind.value} {action or 'build'} が失敗しました (exit {result.returncode}){suffix}")

    def _ensure_default_image(self, image: str) -> None:
        context = PROJECT_ROOT / "infra" / "build"
        fingerprint = hashlib.sha256((context / "Dockerfile").read_bytes()).hexdigest()
        inspection = self.docker.run(
            (
                "image",
                "inspect",
                "--format",
                f'{{{{ index .Config.Labels "{BUILD_SPEC_FINGERPRINT_LABEL}" }}}}',
                image,
            )
        )
        if inspection.returncode == 0 and inspection.stdout.strip() == fingerprint:
            return
        result = self.docker.run(
            (
                "build",
                "--build-arg",
                f"GAR_BUILD_SPEC_FINGERPRINT={fingerprint}",
                "--tag",
                image,
                str(context),
            )
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise GarDomainError(
                f"Docker build imageを作成できませんでした (exit {result.returncode})"
                + (f": {detail}" if detail else "")
            )

    @staticmethod
    def _add_posix_identity(arguments: list[str], *, include_socket_group: bool) -> None:
        if os.name == "nt" or not hasattr(os, "getuid") or not hasattr(os, "getgid"):
            return
        arguments.extend(("--user", f"{os.getuid()}:{os.getgid()}"))
        if not include_socket_group:
            return
        try:
            socket_group = os.stat(DOCKER_SOCKET).st_gid
        except OSError:
            return
        arguments.extend(("--group-add", str(socket_group)))
