"""Programmatic GAR API shared by the CLI and other callers."""

from __future__ import annotations

import json
import sys

from scripts.gar_lib.artifacts.store import ArtifactStore, LocalArtifactStore
from scripts.gar_lib.build.backends import build_environment_for
from scripts.gar_lib.commands.common.hardware import load_hw_definition
from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.backends import (
    hardware_control_for,
    simulation_environment_for,
    simulation_host_for,
)
from scripts.gar_lib.simulation.session import VsCodeSimulationSessionManager
from scripts.gar_lib.target.backends import target_environment_for


class Gar:
    def __init__(self, workspace: Workspace, artifacts: ArtifactStore | None = None):
        artifact_store = artifacts if artifacts is not None else LocalArtifactStore()
        self.sim = Simulation(workspace, artifact_store)
        self.target = Target(workspace, artifact_store)


class Simulation:
    def __init__(self, workspace: Workspace, artifacts: ArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts
        self.app = SimulationApp(workspace, artifacts)
        self.runtime = SimulationRuntime(workspace, artifacts)
        self.host = SimulationHost(workspace)
        self.gpio = SimulationGpio(workspace)
        self.io = SimulationIo(workspace)


class SimulationApp:
    def __init__(self, workspace: Workspace, artifacts: ArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts

    def build(self) -> int:
        build = build_environment_for(self.workspace, self.artifacts)
        artifact = build.build(ArtifactKind.SIM_APP, self.workspace)
        print(f"Artifact: {artifact.bundle_path}")
        return 0

    def clean(self) -> int:
        build_environment_for(self.workspace, self.artifacts).clean(
            ArtifactKind.SIM_APP, self.workspace
        )
        print("Simulation artifactを削除しました。")
        return 0

    def deploy(self) -> int:
        artifact = self.artifacts.latest(ArtifactKind.SIM_APP, self.workspace)
        simulation_environment_for(self.workspace).deploy(artifact)
        print(f"Artifact: {artifact.bundle_path}")
        return 0


class SimulationRuntime:
    def __init__(self, workspace: Workspace, artifacts: ArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts

    def build(self) -> int:
        if not simulation_environment_for(self.workspace).requires_runtime_artifact:
            print("このsimulation environmentには個別のruntime artifactは不要です。")
            return 0
        artifact = build_environment_for(self.workspace, self.artifacts).build(
            ArtifactKind.SIM_RUNTIME, self.workspace
        )
        print(f"Artifact: {artifact.bundle_path}")
        return 0

    def deploy(self) -> int:
        environment = simulation_environment_for(self.workspace)
        if not environment.requires_runtime_artifact:
            print("このsimulation environmentには個別のruntime artifactは不要です。")
            return 0
        artifact = self.artifacts.latest(ArtifactKind.SIM_RUNTIME, self.workspace)
        environment.deploy(artifact)
        print(f"Artifact: {artifact.bundle_path}")
        return 0

    def start(
        self,
        *,
        settings: str | None = None,
        profile_name: str | None = None,
        no_port_forward: bool = False,
    ) -> int:
        environment = simulation_environment_for(self.workspace)
        exit_code = environment.start(load_hw_definition())
        host = environment.runtime_host
        if exit_code != 0 or host is None:
            return exit_code

        sessions = VsCodeSimulationSessionManager()
        sessions.configure_terminal(host, settings=settings, profile_name=profile_name)
        if no_port_forward:
            return 0
        return sessions.start(host)

    def stop(self, *, keep_port_forward: bool = False) -> int:
        environment = simulation_environment_for(self.workspace)
        exit_code = environment.stop(load_hw_definition())
        host = environment.runtime_host
        if exit_code != 0 or host is None or keep_port_forward:
            return exit_code
        return VsCodeSimulationSessionManager().stop(host)

    def status(self) -> int:
        environment = simulation_environment_for(self.workspace)
        host = environment.runtime_host
        session_exit = VsCodeSimulationSessionManager().status(host) if host is not None else 0
        runtime_exit = environment.status(load_hw_definition())
        return session_exit or runtime_exit

    def log(self) -> int:
        return simulation_environment_for(self.workspace).log()

    def diag(self, *, json_output: bool = False) -> int:
        report = simulation_environment_for(self.workspace).diag(load_hw_definition())
        host = self.workspace.ec2.get("host")
        payload = report.to_payload(host=host if isinstance(host, str) else None)
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_diagnostic(payload)
        return report.exit_code


class SimulationHost:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def start(self, *, no_update_ssh: bool = False, pull: bool = False) -> int:
        result = simulation_host_for(self.workspace).start(
            update_address=not no_update_ssh,
            update_repository=pull,
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

    def stop(self) -> int:
        simulation_host_for(self.workspace).stop()
        print("gar sim host: shutdown要求を送信しました。")
        return 0

    def status(self, *, json_output: bool = False) -> int:
        state = simulation_host_for(self.workspace).status()
        if json_output:
            print(json.dumps(state.to_payload(), ensure_ascii=False, indent=2))
            return 0
        print(f"backend : {state.backend}")
        print(f"id      : {state.id}")
        print(f"state   : {state.state}")
        print(f"address : {state.address or '(none)'}")
        for name, value in state.details.items():
            print(f"{name:8}: {value}")
        return 0


class SimulationGpio:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def install(self, *, json_output: bool = False) -> int:
        return self._run("install", json_output=json_output)

    def start(self, *, json_output: bool = False) -> int:
        return self._run("start", json_output=json_output)

    def stop(self, *, json_output: bool = False) -> int:
        return self._run("stop", json_output=json_output)

    def plan(self, *, json_output: bool = False) -> int:
        return self._run("plan", json_output=json_output)

    def status(self, *, json_output: bool = False) -> int:
        return self._run("status", json_output=json_output)

    def check(self, *, json_output: bool = False) -> int:
        return self._run("check", json_output=json_output)

    def _run(self, action: str, *, json_output: bool) -> int:
        result = hardware_control_for(self.workspace).gpio(action, load_hw_definition())
        result.render(json_output=json_output)
        return result.exit_code


class SimulationIo:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def state(self, **params: object) -> int:
        return self._run("state", params)

    def press(self, **params: object) -> int:
        return self._run("press", params)

    def set(self, **params: object) -> int:
        return self._run("set", params)

    def clear(self, **params: object) -> int:
        return self._run("clear", params)

    def _run(self, action: str, params: dict[str, object]) -> int:
        json_output = bool(params.pop("json_output", False))
        result = hardware_control_for(self.workspace).io(action, params)
        result.render(json_output=json_output)
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
