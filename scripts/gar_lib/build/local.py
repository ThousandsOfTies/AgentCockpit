"""Build product artifacts in the selected local development environment."""

from __future__ import annotations

import os
import subprocess

from scripts.gar_lib.artifacts.store import ArtifactStore
from scripts.gar_lib.build._base import ProductBuildSpecResolver
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace


class LocalBuildEnvironment:
    def __init__(self, artifacts: ArtifactStore, specs: ProductBuildSpecResolver | None = None):
        self.artifacts = artifacts
        self.specs = specs or ProductBuildSpecResolver()

    def build(self, kind: ArtifactKind, workspace: Workspace) -> Artifact:
        spec = self.specs.for_artifact(kind, workspace)
        script = workspace.local_root / spec.script
        if not script.is_file():
            raise GarDomainError(f"product build hook が見つかりません: {script}")
        result = subprocess.run(
            [str(script)],
            cwd=workspace.local_root,
            env={**os.environ, **spec.variables},
            check=False,
        )
        if result.returncode != 0:
            raise GarDomainError(f"{kind.value} build が失敗しました (exit {result.returncode})")
        return self.artifacts.latest(kind, workspace)

    def clean(self, kind: ArtifactKind, workspace: Workspace) -> None:
        spec = self.specs.for_artifact(kind, workspace)
        script = workspace.local_root / spec.script
        if not script.is_file():
            raise GarDomainError(f"product build hook が見つかりません: {script}")
        result = subprocess.run(
            [str(script), "clean"],
            cwd=workspace.local_root,
            env={**os.environ, **spec.variables},
            check=False,
        )
        if result.returncode != 0:
            raise GarDomainError(f"{kind.value} clean が失敗しました (exit {result.returncode})")

    def fetch(self, workspace: Workspace) -> None:
        # local build の成果物は既に WSL 側（workspace.local_root）にあるため取得は不要。
        del workspace
