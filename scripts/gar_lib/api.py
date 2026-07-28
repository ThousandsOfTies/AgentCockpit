"""Programmatic GAR API shared by the CLI and other callers."""

from __future__ import annotations

from scripts.gar_lib.artifacts.store import ArtifactStore, LocalArtifactStore
from scripts.gar_lib.build.backends import build_environment_for
from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.target.backends import target_environment_for


class Gar:
    def __init__(self, workspace: Workspace, artifacts: ArtifactStore | None = None):
        artifact_store = artifacts if artifacts is not None else LocalArtifactStore()
        self.target = Target(workspace, artifact_store)


class Target:
    def __init__(self, workspace: Workspace, artifacts: ArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts

    def build(self) -> int:
        build = build_environment_for(self.workspace, self.artifacts)
        artifact = build.build(ArtifactKind.TARGET_APP, self.workspace)
        print(f"Artifact: {artifact.bundle_path}")
        return 0

    def deploy(self) -> int:
        artifact = self.artifacts.latest(ArtifactKind.TARGET_APP, self.workspace)
        target_environment_for(self.workspace).deploy(artifact)
        print(f"Artifact: {artifact.bundle_path}")
        return 0

    def fetch(self) -> int:
        build_environment_for(self.workspace, self.artifacts).fetch(self.workspace)
        print("artifact bundle を WSL hub へ取得しました。")
        return 0
