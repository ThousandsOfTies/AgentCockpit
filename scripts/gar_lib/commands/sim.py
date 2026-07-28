"""`gar sim ...` の本体。設定から object を作り、verb を呼び、結果を表示する。"""

from __future__ import annotations

import json
import sys
from argparse import Namespace

from scripts.gar_lib.artifacts.store import LocalArtifactStore
from scripts.gar_lib.build.backends import build_environment_for
from scripts.gar_lib.commands.common.hardware import load_hw_definition
from scripts.gar_lib.commands.common.workspace import workspace_for
from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.command import GarCommand
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.recovery.access import report_access_failure
from scripts.gar_lib.simulation.backends import (
    hardware_control_for,
    simulation_environment_for,
    simulation_host_for,
)
from scripts.gar_lib.simulation.session import VsCodeSimulationSessionManager

IO_PARAMETERS = ("device", "button", "line", "duration_ms", "value", "uid")


def run_sim_command(args: Namespace) -> int:
    """`gar sim ...` を subject command runner へ dispatch する。"""

    command: GarCommand = args.gar_command
    if command.group != "sim":
        raise GarDomainError(f"simulation command ではありません: {command.group}")
    workspace_selector = getattr(args, "workspace", None)
    try:
        workspace = workspace_for(workspace_selector)
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1
    runners = {
        "app": run_sim_app_command,
        "runtime": run_sim_runtime_command,
        "host": run_sim_host_command,
        "gpio": run_sim_gpio_command,
        "io": run_sim_io_command,
    }
    try:
        return runners[command.subject](command, workspace, args)
    except AccessConnectionError as error:
        device = getattr(args, "device", None)
        return report_access_failure(
            error,
            workspace=workspace,
            retry_command=command.to_cli(
                workspace=workspace_selector,
                options=("--device", str(device)) if device else (),
            ),
            purpose="simulation",
        )
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1
    except KeyError as error:
        raise GarDomainError(f"未対応の simulation subject: {command.subject}") from error


def _run_sim_subject_command(
    command: GarCommand,
    workspace: Workspace,
    args: Namespace,
    *,
    subject: str,
    actions: dict[str, object],
) -> int:
    """subject ごとの action を検証して実行する。"""

    if command.subject != subject:
        raise GarDomainError(f"{subject} command ではありません: {command.subject}")
    try:
        action = actions[command.action]
    except KeyError as error:
        raise GarDomainError(f"未対応の sim {subject} action: {command.action}") from error
    return action(workspace, args)  # type: ignore[operator]


def run_sim_app_command(command: GarCommand, workspace: Workspace, args: Namespace) -> int:
    return _run_sim_subject_command(command, workspace, args, subject="app", actions={
        "build": run_sim_app_build, "clean": run_sim_app_clean, "deploy": run_sim_app_deploy,
    })


def run_sim_runtime_command(command: GarCommand, workspace: Workspace, args: Namespace) -> int:
    return _run_sim_subject_command(command, workspace, args, subject="runtime", actions={
        "build": run_sim_runtime_build, "deploy": run_sim_runtime_deploy,
        "start": run_sim_runtime_start, "stop": run_sim_runtime_stop,
        "status": run_sim_runtime_status, "log": run_sim_runtime_log,
        "diag": run_sim_runtime_diag,
    })


def run_sim_host_command(command: GarCommand, workspace: Workspace, args: Namespace) -> int:
    return _run_sim_subject_command(command, workspace, args, subject="host", actions={
        "start": run_sim_host_start, "stop": run_sim_host_stop, "status": run_sim_host_status,
    })


def run_sim_gpio_command(command: GarCommand, workspace: Workspace, args: Namespace) -> int:
    return _run_sim_subject_command(command, workspace, args, subject="gpio", actions={
        "install": run_sim_gpio, "start": run_sim_gpio, "stop": run_sim_gpio,
        "plan": run_sim_gpio, "status": run_sim_gpio, "check": run_sim_gpio,
    })


def run_sim_io_command(command: GarCommand, workspace: Workspace, args: Namespace) -> int:
    return _run_sim_subject_command(command, workspace, args, subject="io", actions={
        "state": run_sim_io, "press": run_sim_io, "set": run_sim_io, "clear": run_sim_io,
    })


def run_sim_app_build(workspace: Workspace, args: Namespace) -> int:
    artifacts = LocalArtifactStore()
    build = build_environment_for(workspace, artifacts)
    artifact = build.build(ArtifactKind.SIM_APP, workspace)
    print(f"Artifact: {artifact.bundle_path}")
    return 0


def run_sim_app_clean(workspace: Workspace, args: Namespace) -> int:
    artifacts = LocalArtifactStore()
    build = build_environment_for(workspace, artifacts)
    build.clean(ArtifactKind.SIM_APP, workspace)
    print("Simulation artifactを削除しました。")
    return 0


def run_sim_app_deploy(workspace: Workspace, args: Namespace) -> int:
    artifact = LocalArtifactStore().latest(ArtifactKind.SIM_APP, workspace)
    simulation_environment_for(workspace).deploy(artifact)
    print(f"Artifact: {artifact.bundle_path}")
    return 0


def run_sim_runtime_build(workspace: Workspace, args: Namespace) -> int:
    if not simulation_environment_for(workspace).requires_runtime_artifact:
        print("このsimulation environmentには個別のruntime artifactは不要です。")
        return 0
    artifacts = LocalArtifactStore()
    build = build_environment_for(workspace, artifacts)
    artifact = build.build(ArtifactKind.SIM_RUNTIME, workspace)
    print(f"Artifact: {artifact.bundle_path}")
    return 0


def run_sim_runtime_deploy(workspace: Workspace, args: Namespace) -> int:
    environment = simulation_environment_for(workspace)
    if not environment.requires_runtime_artifact:
        print("このsimulation environmentには個別のruntime artifactは不要です。")
        return 0
    artifact = LocalArtifactStore().latest(ArtifactKind.SIM_RUNTIME, workspace)
    environment.deploy(artifact)
    print(f"Artifact: {artifact.bundle_path}")
    return 0


def run_sim_runtime_start(workspace: Workspace, args: Namespace) -> int:
    environment = simulation_environment_for(workspace)
    exit_code = environment.start(load_hw_definition())
    host = environment.runtime_host
    if exit_code != 0 or host is None:
        return exit_code

    sessions = VsCodeSimulationSessionManager()
    sessions.configure_terminal(
        host,
        settings=getattr(args, "settings", None),
        profile_name=getattr(args, "profile_name", None),
    )
    if getattr(args, "no_port_forward", False):
        return 0
    return sessions.start(host)


def run_sim_runtime_stop(workspace: Workspace, args: Namespace) -> int:
    environment = simulation_environment_for(workspace)
    exit_code = environment.stop(load_hw_definition())
    host = environment.runtime_host
    if exit_code != 0 or host is None or getattr(args, "keep_port_forward", False):
        return exit_code
    return VsCodeSimulationSessionManager().stop(host)


def run_sim_runtime_status(workspace: Workspace, args: Namespace) -> int:
    environment = simulation_environment_for(workspace)
    host = environment.runtime_host
    session_exit = VsCodeSimulationSessionManager().status(host) if host is not None else 0
    runtime_exit = environment.status(load_hw_definition())
    return session_exit or runtime_exit


def run_sim_runtime_log(workspace: Workspace, args: Namespace) -> int:
    return simulation_environment_for(workspace).log()


def run_sim_runtime_diag(workspace: Workspace, args: Namespace) -> int:
    report = simulation_environment_for(workspace).diag(load_hw_definition())
    host = workspace.ec2.get("host")
    payload = report.to_payload(host=host if isinstance(host, str) else None)
    if getattr(args, "json_output", False):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_diagnostic(payload)
    return report.exit_code


def run_sim_host_start(workspace: Workspace, args: Namespace) -> int:
    result = simulation_host_for(workspace).start(
        update_address=not getattr(args, "no_update_ssh", False),
        update_repository=getattr(args, "pull", False),
    )
    print(f"gar sim host: running. address = {result.state.address or '(local)'}")
    if result.address_updated:
        print(
            f"gar sim host: SSH config の Host {result.state.host} を "
            f"{result.state.address} に更新しました。"
        )
    if result.repository_updated:
        print("gar sim host: simulation hostのrepositoryを更新しました。")
    if result.repository_update_skipped:
        print(
            "gar sim host: --pullが指定されましたがrepo_dirが未設定のため、"
            "git pullをスキップしました。",
            file=sys.stderr,
        )
    return 0


def run_sim_host_stop(workspace: Workspace, args: Namespace) -> int:
    simulation_host_for(workspace).stop()
    print("gar sim host: shutdown要求を送信しました。")
    return 0


def run_sim_host_status(workspace: Workspace, args: Namespace) -> int:
    state = simulation_host_for(workspace).status()
    if getattr(args, "json_output", False):
        print(json.dumps(state.to_payload(), ensure_ascii=False, indent=2))
        return 0
    print(f"backend : {state.backend}")
    print(f"id      : {state.id}")
    print(f"state   : {state.state}")
    print(f"address : {state.address or '(none)'}")
    for name, value in state.details.items():
        print(f"{name:8}: {value}")
    return 0


def run_sim_gpio(workspace: Workspace, args: Namespace) -> int:
    result = hardware_control_for(workspace).gpio(args.gar_command.action, load_hw_definition())
    result.render(json_output=getattr(args, "json_output", False))
    return result.exit_code


def run_sim_io(workspace: Workspace, args: Namespace) -> int:
    params = {
        name: value
        for name in IO_PARAMETERS
        if (value := getattr(args, name, None)) is not None
    }
    result = hardware_control_for(workspace).io(args.gar_command.action, params)
    result.render(json_output=getattr(args, "json_output", False))
    return result.exit_code


def _print_diagnostic(payload: dict[str, object]) -> None:
    print(f"status: {'ok' if payload.get('ok') is True else 'error'}")
    if payload.get("host"):
        print(f"host: {payload['host']}")
    if payload.get("error"):
        print(f"error: {payload['error']}")
    processes = payload.get("processes")
    if isinstance(processes, list):
        print(f"processes: {len(processes)}")
        for process in processes:
            if isinstance(process, dict):
                print(f"  {process.get('pid', '?')}: {process.get('cmd', '')}")
    devices = payload.get("devices")
    if isinstance(devices, dict):
        print("devices:")
        for path, available in devices.items():
            print(f"  {path}: {'OK' if available else 'missing'}")
    if payload.get("api") is not None:
        print("api:")
        print(json.dumps(payload["api"], ensure_ascii=False, indent=2))
