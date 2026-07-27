"""`gar target ...` の本体。設定から object を作り、verb を呼び、結果を表示する。"""

from __future__ import annotations

from argparse import Namespace

from scripts.gar_lib.artifacts.store import LocalArtifactStore
from scripts.gar_lib.build.backends import build_environment_for
from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.target.backends import target_environment_for


def run_target_app_build(workspace: Workspace, args: Namespace) -> int:
    artifacts = LocalArtifactStore()
    build = build_environment_for(workspace, artifacts)
    artifact = build.build(ArtifactKind.TARGET_APP, workspace)
    print(f"Artifact: {artifact.bundle_path}")
    return 0


def run_target_app_deploy(workspace: Workspace, args: Namespace) -> int:
    artifact = LocalArtifactStore().latest(ArtifactKind.TARGET_APP, workspace)
    target_environment_for(workspace).deploy(artifact)
    print(f"Artifact: {artifact.bundle_path}")
    return 0


def run_target_app_fetch(workspace: Workspace, args: Namespace) -> int:
    artifacts = LocalArtifactStore()
    build_environment_for(workspace, artifacts).fetch(workspace)
    print("artifact bundle を WSL hub へ取得しました。")
    return 0
