"""Programmatic GAR API shared by the CLI and other callers."""

from __future__ import annotations

from dataclasses import dataclass

from scripts.gar_lib.artifacts.store import BuildArtifactStore, LocalArtifactStore
from scripts.gar_lib.build.environment import build_environment_for
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.hardware import HardwareDefinition, load_hw_definition
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.composition import (
    hardware_control_for,
    simulation_environment_for,
    simulation_host_for,
)
from scripts.gar_lib.simulation.diagnostics.model import SimulationDiagnosticReport
from scripts.gar_lib.simulation.hardware.control import HardwareControlResult
from scripts.gar_lib.simulation.host.contract import (
    SimulationHostStartResult,
    SimulationHostState,
)
from scripts.gar_lib.simulation.session.manager import VsCodeSimulationSessionManager
from scripts.gar_lib.target.application import target_application_from_artifact
from scripts.gar_lib.target.composition import target_environment_for, target_lifecycle_for
from scripts.gar_lib.target.environment import TargetPlacementError
from scripts.gar_lib.target.lifecycle import (
    TargetApplication,
    TargetDeploymentConvergenceError,
    TargetDeploymentReport,
    TargetDiagnosticReport,
    TargetLifecycle,
    TargetLifecycleResult,
)


@dataclass(frozen=True)
class TargetDeploymentResult:
    artifact: Artifact
    report: TargetDeploymentReport


class Gar:
    def __init__(self, workspace: Workspace, artifacts: BuildArtifactStore | None = None):
        artifact_store = artifacts if artifacts is not None else LocalArtifactStore()
        self.sim = Simulation(workspace, artifact_store)
        self.target = Target(workspace, artifact_store)


class Simulation:
    def __init__(self, workspace: Workspace, artifacts: BuildArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts
        self.app = SimulationApp(workspace, artifacts)
        self.runtime = SimulationRuntime(workspace, artifacts)
        self.host = SimulationHost(workspace)
        self.gpio = SimulationGpio(workspace)
        self.io = SimulationIo(workspace)


class SimulationApp:
    def __init__(self, workspace: Workspace, artifacts: BuildArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts

    def build(self) -> Artifact:
        build = build_environment_for(self.workspace, self.artifacts)
        return build.build(ArtifactKind.SIM_APP, self.workspace)

    def clean(self) -> None:
        build_environment_for(self.workspace, self.artifacts).clean(ArtifactKind.SIM_APP, self.workspace)

    def deploy(self) -> Artifact:
        artifact = self.artifacts.latest(ArtifactKind.SIM_APP, self.workspace)
        simulation_environment_for(self.workspace).deploy(artifact)
        return artifact


class SimulationRuntime:
    def __init__(self, workspace: Workspace, artifacts: BuildArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts

    @property
    def session_host(self) -> str | None:
        return simulation_environment_for(self.workspace).session_host

    def build(self) -> Artifact | None:
        if not simulation_environment_for(self.workspace).requires_runtime_artifact:
            return None
        return build_environment_for(self.workspace, self.artifacts).build(ArtifactKind.SIM_RUNTIME, self.workspace)

    def deploy(self) -> Artifact | None:
        environment = simulation_environment_for(self.workspace)
        if not environment.requires_runtime_artifact:
            return None
        artifact = self.artifacts.latest(ArtifactKind.SIM_RUNTIME, self.workspace)
        environment.deploy(artifact)
        return artifact

    def start(
        self,
        *,
        settings: str | None = None,
        profile_name: str | None = None,
        no_port_forward: bool = False,
        panel_port: int = 8080,
    ) -> int:
        environment = simulation_environment_for(self.workspace)
        exit_code = environment.start(_workspace_hardware(self.workspace))
        host = environment.session_host
        if exit_code != 0 or host is None:
            return exit_code

        sessions = VsCodeSimulationSessionManager()
        sessions.configure_terminal(host, settings=settings, profile_name=profile_name)
        if no_port_forward:
            return 0
        return sessions.start(host, panel_port=panel_port)

    def stop(self, *, keep_port_forward: bool = False) -> int:
        environment = simulation_environment_for(self.workspace)
        exit_code = environment.stop(_workspace_hardware(self.workspace))
        host = environment.session_host
        if exit_code != 0 or host is None or keep_port_forward:
            return exit_code
        return VsCodeSimulationSessionManager().stop(host)

    def status(self) -> int:
        environment = simulation_environment_for(self.workspace)
        host = environment.session_host
        session_exit = VsCodeSimulationSessionManager().status(host) if host is not None else 0
        runtime_exit = environment.status(_workspace_hardware(self.workspace))
        return session_exit or runtime_exit

    def log(self) -> int:
        return simulation_environment_for(self.workspace).log()

    def diag(self) -> SimulationDiagnosticReport:
        environment = simulation_environment_for(self.workspace)
        return environment.diag(_workspace_hardware(self.workspace))


class SimulationHost:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def start(
        self,
        *,
        no_update_ssh: bool = False,
        pull: bool = False,
    ) -> SimulationHostStartResult:
        return simulation_host_for(self.workspace).start(
            update_address=not no_update_ssh,
            update_repository=pull,
        )

    def stop(self) -> None:
        simulation_host_for(self.workspace).stop()

    def status(self) -> SimulationHostState:
        return simulation_host_for(self.workspace).status()


class SimulationGpio:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def install(self) -> HardwareControlResult:
        return self._run("install")

    def start(self) -> HardwareControlResult:
        return self._run("start")

    def stop(self) -> HardwareControlResult:
        return self._run("stop")

    def plan(self) -> HardwareControlResult:
        return self._run("plan")

    def status(self) -> HardwareControlResult:
        return self._run("status")

    def check(self) -> HardwareControlResult:
        return self._run("check")

    def _run(self, action: str) -> HardwareControlResult:
        return hardware_control_for(self.workspace).gpio(
            action,
            _workspace_hardware(self.workspace),
        )


class SimulationIo:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def state(self, **params: object) -> HardwareControlResult:
        return self._run("state", params)

    def press(self, **params: object) -> HardwareControlResult:
        return self._run("press", params)

    def set(self, **params: object) -> HardwareControlResult:
        return self._run("set", params)

    def clear(self, **params: object) -> HardwareControlResult:
        return self._run("clear", params)

    def _run(self, action: str, params: dict[str, object]) -> HardwareControlResult:
        return hardware_control_for(self.workspace).io(action, params)


def _workspace_hardware(workspace: Workspace) -> HardwareDefinition:
    hardware_dir = str(workspace.hardware_dir) if workspace.hardware_dir is not None else None
    return load_hw_definition(hw_dir=hardware_dir)


class Target:
    def __init__(self, workspace: Workspace, artifacts: BuildArtifactStore):
        self.workspace = workspace
        self.artifacts = artifacts

    def build(self) -> Artifact:
        build = build_environment_for(self.workspace, self.artifacts)
        return build.build(ArtifactKind.TARGET_APP, self.workspace)

    def prepare(self) -> None:
        target_environment_for(self.workspace).prepare()

    def deploy(self) -> Artifact:
        return self.deploy_report().artifact

    def deploy_report(self) -> TargetDeploymentResult:
        artifact = self.artifacts.latest(ArtifactKind.TARGET_APP, self.workspace)
        environment = target_environment_for(self.workspace)
        environment.validate_deployment(artifact)
        lifecycle = target_lifecycle_for(self.workspace)
        application = (
            target_application_from_artifact(artifact, require_build_id=True) if lifecycle is not None else None
        )
        verification = "lifecycle-v1" if lifecycle is not None else "unavailable"
        try:
            environment.deploy(artifact)
        except TargetPlacementError as error:
            report = TargetDeploymentReport(
                application=application,
                artifact_path=str(artifact.bundle_path),
                placed=True,
                verification=verification,
                partial=error.partial,
                placed_destinations=error.placed_destinations,
                failure=str(error),
            )
            raise TargetDeploymentConvergenceError(report) from error

        if lifecycle is None:
            return TargetDeploymentResult(
                artifact=artifact,
                report=TargetDeploymentReport(
                    application=None,
                    artifact_path=str(artifact.bundle_path),
                    placed=True,
                    verification="unavailable",
                ),
            )

        assert application is not None
        reload_result = None
        try:
            reload_result = lifecycle.reload(application)
            diagnostic = lifecycle.diag(application)
        except Exception as error:
            report = TargetDeploymentReport(
                application=application,
                artifact_path=str(artifact.bundle_path),
                placed=True,
                reload=reload_result,
                verification=verification,
                failure=str(error),
            )
            raise TargetDeploymentConvergenceError(report) from error
        report = TargetDeploymentReport(
            application=application,
            artifact_path=str(artifact.bundle_path),
            placed=True,
            reload=reload_result,
            diagnostic=diagnostic,
            verification=verification,
        )
        if not reload_result.ok or not report.ok:
            raise TargetDeploymentConvergenceError(report)
        return TargetDeploymentResult(artifact=artifact, report=report)

    def status(self, *, app: str | None = None) -> TargetLifecycleResult:
        lifecycle, application = self._lifecycle_application(app)
        return lifecycle.status(application)

    def log(self, *, app: str | None = None, lines: int = 200) -> TargetLifecycleResult:
        lifecycle, application = self._lifecycle_application(app)
        return lifecycle.log(application, lines=lines)

    def diag(self, *, app: str | None = None) -> TargetDiagnosticReport:
        lifecycle, application = self._lifecycle_application(app)
        return lifecycle.diag(application)

    def fetch(self) -> Artifact:
        return build_environment_for(self.workspace, self.artifacts).fetch(
            ArtifactKind.TARGET_APP,
            self.workspace,
        )

    def _lifecycle_application(self, app: str | None) -> tuple[TargetLifecycle, TargetApplication]:
        lifecycle = target_lifecycle_for(self.workspace)
        if lifecycle is None:
            raise GarDomainError(
                "選択したTargetはapplication lifecycle capabilityを提供していません。"
                "Target recipeを更新してgar target prepareを実行してください"
            )
        if app is not None:
            return lifecycle, TargetApplication(app)
        artifact = self.artifacts.latest(ArtifactKind.TARGET_APP, self.workspace)
        return lifecycle, target_application_from_artifact(artifact)
