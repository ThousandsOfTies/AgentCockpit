"""`gar target ...` の本体。設定から object を作り、verb を呼び、結果を表示する。"""

from __future__ import annotations

import sys
from argparse import Namespace

from scripts.gar_lib.artifacts.store import LocalArtifactStore
from scripts.gar_lib.build.backends import build_environment_for
from scripts.gar_lib.commands.common.workspace import workspace_for
from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.command import GarCommand
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.recovery.access import report_access_failure
from scripts.gar_lib.target.backends import target_environment_for


def run_target_command(args: Namespace) -> int:
    """`gar target ...` を subject command runner へ dispatch する。"""

    command: GarCommand = args.gar_command
    if command.group != "target":
        raise GarDomainError(f"target command ではありません: {command.group}")
    workspace_selector = getattr(args, "workspace", None)
    try:
        workspace = workspace_for(workspace_selector)
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1
    try:
        if command.subject != "app":
            raise GarDomainError(f"未対応の target subject: {command.subject}")
        return run_target_app_command(command, workspace, args)
    except AccessConnectionError as error:
        device = getattr(args, "device", None)
        return report_access_failure(
            error,
            workspace=workspace,
            retry_command=command.to_cli(
                workspace=workspace_selector,
                options=("--device", str(device)) if device else (),
            ),
            purpose="target",
        )
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1


def run_target_app_command(command: GarCommand, workspace: Workspace, args: Namespace) -> int:
    """`gar target app ...` の action を検証して実行する。"""

    if command.subject != "app":
        raise GarDomainError(f"app command ではありません: {command.subject}")
    actions = {
        "build": run_target_app_build,
        "deploy": run_target_app_deploy,
        "fetch": run_target_app_fetch,
    }
    try:
        return actions[command.action](workspace, args)
    except KeyError as error:
        raise GarDomainError(f"未対応の target app action: {command.action}") from error


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
