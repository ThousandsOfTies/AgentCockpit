from __future__ import annotations

import contextlib
import io
import json
import stat
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from scripts.gar_lib.access.channel import AccessResult
from scripts.gar_lib.api import Gar
from scripts.gar_lib.artifacts.metadata import (
    CURRENT_SCHEMA_VERSION,
    ArtifactKernel,
    ArtifactMetadata,
    ArtifactTarget,
    sha256_checksums,
    write_artifact_metadata,
)
from scripts.gar_lib.artifacts.provenance import TargetToolsProvenance
from scripts.gar_lib.cli import main
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.target.compatibility import (
    ArtifactCompatibilityError,
    deployment_marker_destination,
    require_target_compatibility,
)
from scripts.gar_lib.target.file_transfer import FileTransferTargetEnvironment


class FakeCommandChannel:
    def __init__(self, stdout: str, *, returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode
        self.commands: list[str] = []

    def run(self, command: str) -> AccessResult:
        self.commands.append(command)
        return AccessResult(("target-probe",), self.returncode, self.stdout, "")


class InspectingFileChannel:
    def __init__(self):
        self.destinations: list[str] = []
        self.marker_payload: dict[str, object] | None = None
        self.marker_mode: int | None = None
        self.source_modes: list[int] = []

    def push(self, source: Path, destination: str) -> AccessResult:
        self.destinations.append(destination)
        self.source_modes.append(stat.S_IMODE(source.stat().st_mode))
        marker = source / ".artifact-info.json"
        if marker.is_file():
            self.marker_mode = stat.S_IMODE(marker.stat().st_mode)
            self.marker_payload = json.loads(marker.read_text(encoding="utf-8"))
        return AccessResult(("push",), 0)

    def pull(self, source: str, destination: Path) -> AccessResult:
        del source, destination
        return AccessResult(("pull",), 0)


def workspace(root: Path, target_id: str = "raspberry-pi-5") -> Workspace:
    return Workspace(
        id="ws_compatibility",
        name="Local/Compatibility",
        branch="Compatibility",
        connection={"type": "local", "path": str(root)},
        selected_target=target_id,
        selected_environments={"codespace": "local", "target": "ssh_scp"},
    )


def target_stdout(
    *,
    target_id: str = "raspberry-pi-5",
    architecture: str = "aarch64",
    abi: str = "gnu",
    libc: str = "glibc",
    triple: str = "aarch64-linux-gnu",
    kernel: str = "6.12.1",
    installed_target_id: str = "raspberry-pi-5",
    installed_recipe_version: str = "2",
    installed_gar_tools_commit: str = "b" * 40,
) -> str:
    return "\n".join(
        (
            f"target_id={target_id}",
            f"architecture={architecture}",
            f"abi={abi}",
            f"libc={libc}",
            f"toolchain_triple={triple}",
            f"kernel_release={kernel}",
            f"installed_target_id={installed_target_id}",
            f"installed_recipe_version={installed_recipe_version}",
            f"installed_gar_tools_commit={installed_gar_tools_commit}",
        )
    )


def write_v2_artifact(
    root: Path,
    selected_workspace: Workspace,
    *,
    target: ArtifactTarget | None = None,
    kernel: ArtifactKernel | None = None,
) -> Artifact:
    payload = root / "files" / "demo" / "run"
    payload.parent.mkdir(parents=True)
    payload.write_text("#!/bin/sh\n", encoding="utf-8")
    (root / "artifact.json").write_text(
        json.dumps(
            {
                "name": "demo-target",
                "target": selected_workspace.selected_target,
                "deploy": {
                    "app": {
                        "files": [
                            {
                                "src": "files/demo",
                                "dest": "/opt/gar/apps/demo",
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    metadata = ArtifactMetadata(
        schema_version=CURRENT_SCHEMA_VERSION,
        kind=ArtifactKind.TARGET_APP.value,
        product="demo-target",
        workspace_id=selected_workspace.id,
        workspace_name=selected_workspace.name,
        workspace_branch=selected_workspace.branch,
        target=target
        or ArtifactTarget(
            id="raspberry-pi-5",
            architecture="aarch64",
            abi="gnu",
            libc="glibc",
            toolchain_triple="aarch64-linux-gnu",
        ),
        entrypoint="/opt/gar/apps/demo/run",
        source_commit="a" * 40,
        gar_tools_commit="b" * 40,
        target_recipe_version="2",
        checksums=sha256_checksums(root),
        build_id="20260811T000000000000Z-deadbeef",
        build_timestamp="2026-08-11T00:00:00+00:00",
        kernel=kernel,
    )
    write_artifact_metadata(root, metadata)
    return Artifact(ArtifactKind.TARGET_APP, selected_workspace, root)


class TargetCompatibilityTest(unittest.TestCase):
    def test_matching_measured_target_is_accepted_and_resolves_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = write_v2_artifact(root, workspace(root))
            channel = FakeCommandChannel(target_stdout())

            metadata, report = require_target_compatibility(
                artifact,
                channel,
                active_tools=TargetToolsProvenance(
                    target_id="raspberry-pi-5",
                    gar_tools_commit="b" * 40,
                    target_recipe_version="2",
                ),
            )

        self.assertTrue(report.compatible)
        self.assertEqual("20260811T000000000000Z-deadbeef", metadata.build_id)
        self.assertEqual("demo", metadata.app_name)
        self.assertEqual(
            "/opt/gar/apps/demo/.artifact-info.json",
            deployment_marker_destination(metadata),
        )
        self.assertEqual(
            "/opt/gar/apps/demo/.artifact-info.json",
            deployment_marker_destination(replace(metadata, entrypoint="/opt/gar/apps/demo/bin/run")),
        )
        self.assertEqual(1, len(channel.commands))
        self.assertIn("uname -m", channel.commands[0])
        self.assertIn(
            "/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1",
            channel.commands[0],
        )
        self.assertIn(
            "/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3",
            channel.commands[0],
        )

    def test_active_gar_tools_drift_is_rejected_before_probe_or_transfer(self) -> None:
        cases = (
            (
                "gar_tools_commit",
                TargetToolsProvenance(
                    target_id="raspberry-pi-5",
                    gar_tools_commit="c" * 40,
                    target_recipe_version="2",
                ),
            ),
            (
                "target_recipe_version",
                TargetToolsProvenance(
                    target_id="raspberry-pi-5",
                    gar_tools_commit="b" * 40,
                    target_recipe_version="3",
                ),
            ),
        )
        for field, active_tools in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                selected_workspace = workspace(root)
                artifact = write_v2_artifact(root, selected_workspace)
                artifacts = mock.Mock()
                artifacts.latest.return_value = artifact
                command_channel = FakeCommandChannel(target_stdout())
                file_channel = mock.Mock()
                environment = FileTransferTargetEnvironment(
                    command_channel,
                    file_channel,
                    active_tools_provenance=active_tools,
                )

                with (
                    mock.patch(
                        "scripts.gar_lib.api.target_environment_for",
                        return_value=environment,
                    ),
                    self.assertRaisesRegex(
                        ArtifactCompatibilityError,
                        rf"tools drift.*{field} mismatch",
                    ),
                ):
                    Gar(selected_workspace, artifacts).target.deploy_report()

                self.assertEqual([], command_channel.commands)
                file_channel.push.assert_not_called()

    def test_installed_recipe_identity_drift_is_rejected_after_probe(self) -> None:
        cases = (
            (
                "installed_recipe.target_id",
                {"installed_target_id": "luckfox-rk3506"},
            ),
            (
                "installed_recipe.version",
                {"installed_recipe_version": "1"},
            ),
            (
                "installed_recipe.gar_tools_commit",
                {"installed_gar_tools_commit": "c" * 40},
            ),
        )
        active_tools = TargetToolsProvenance(
            target_id="raspberry-pi-5",
            gar_tools_commit="b" * 40,
            target_recipe_version="2",
        )
        for field, probe_overrides in cases:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                artifact = write_v2_artifact(root, workspace(root))
                channel = FakeCommandChannel(target_stdout(**probe_overrides))

                with self.assertRaises(ArtifactCompatibilityError) as raised:
                    require_target_compatibility(
                        artifact,
                        channel,
                        active_tools=active_tools,
                    )

                self.assertEqual(1, len(channel.commands))
                assert raised.exception.report is not None
                self.assertIn(field, {issue.field for issue in raised.exception.report.issues})

    def test_ssh_deploy_requires_active_tools_identity_before_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = write_v2_artifact(root, workspace(root))
            command_channel = FakeCommandChannel(target_stdout())
            file_channel = mock.Mock()
            environment = FileTransferTargetEnvironment(
                command_channel,
                file_channel,
                require_active_tools_provenance=True,
            )

            with self.assertRaisesRegex(
                ArtifactCompatibilityError,
                "provenance.*deploy",
            ):
                environment.validate_deployment(artifact)

        self.assertEqual([], command_channel.commands)
        file_channel.push.assert_not_called()

    def test_compatible_directory_deploy_injects_dot_metadata_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = write_v2_artifact(root, workspace(root))
            command_channel = FakeCommandChannel(target_stdout())
            file_channel = InspectingFileChannel()
            environment = FileTransferTargetEnvironment(command_channel, file_channel)

            environment.validate_deployment(artifact)
            environment.deploy(artifact)

        self.assertEqual(["/opt/gar/apps/demo"], file_channel.destinations)
        self.assertIsNotNone(file_channel.marker_payload)
        assert file_channel.marker_payload is not None
        self.assertEqual(
            "20260811T000000000000Z-deadbeef",
            file_channel.marker_payload["build_id"],
        )
        self.assertEqual(0o444, file_channel.marker_mode)

    def test_read_only_application_directory_accepts_marker_without_changing_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = write_v2_artifact(root, workspace(root))
            source = root / "files" / "demo"
            source.chmod(0o555)
            file_channel = InspectingFileChannel()
            environment = FileTransferTargetEnvironment(
                FakeCommandChannel(target_stdout()),
                file_channel,
            )
            try:
                environment.deploy(artifact)

                self.assertEqual(0o555, stat.S_IMODE(source.stat().st_mode))
                self.assertEqual([0o555], file_channel.source_modes)
                self.assertIsNotNone(file_channel.marker_payload)
                self.assertEqual(0o444, file_channel.marker_mode)
            finally:
                source.chmod(0o755)

    def test_marker_composition_filesystem_failure_is_a_json_domain_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected_workspace = workspace(root)
            artifact = write_v2_artifact(root, selected_workspace)
            environment = FileTransferTargetEnvironment(
                FakeCommandChannel(target_stdout()),
                InspectingFileChannel(),
            )
            target_api = mock.Mock()
            target_api.deploy_report.side_effect = lambda: environment.deploy(artifact)
            output = io.StringIO()
            errors = io.StringIO()

            with (
                mock.patch(
                    "scripts.gar_lib.target.file_transfer.shutil.copy2",
                    side_effect=PermissionError("marker denied"),
                ),
                mock.patch(
                    "scripts.gar_lib.commands.target.resolve_workspace",
                    return_value=selected_workspace,
                ),
                mock.patch(
                    "scripts.gar_lib.commands.target.Gar",
                    return_value=mock.Mock(target=target_api),
                ),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(errors),
            ):
                exit_code = main(
                    [
                        "target",
                        "deploy",
                        "--json",
                        "--workspace",
                        selected_workspace.name,
                    ]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["placed"])
        self.assertIn("target deploy marker", payload["error"])
        self.assertIn("marker denied", payload["error"])
        self.assertEqual("", errors.getvalue())

    def test_manifest_and_source_errors_do_not_leak_human_stderr_in_json_mode(self) -> None:
        for failure in ("manifest", "source"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                selected_workspace = workspace(root)
                if failure == "manifest":
                    (root / "artifact.json").write_text("{invalid\n", encoding="utf-8")
                else:
                    (root / "artifact.json").write_text(
                        json.dumps(
                            {
                                "deploy": {
                                    "app": {
                                        "files": [
                                            {
                                                "src": "files/missing",
                                                "dest": "/opt/gar/apps/demo",
                                            }
                                        ]
                                    }
                                }
                            }
                        ),
                        encoding="utf-8",
                    )
                artifact = Artifact(ArtifactKind.TARGET_APP, selected_workspace, root)
                environment = FileTransferTargetEnvironment(
                    FakeCommandChannel(target_stdout()),
                    InspectingFileChannel(),
                )
                target_api = mock.Mock()
                target_api.deploy_report.side_effect = (
                    lambda environment=environment, artifact=artifact: environment.deploy(artifact)
                )
                output = io.StringIO()
                errors = io.StringIO()

                with (
                    mock.patch(
                        "scripts.gar_lib.commands.target.resolve_workspace",
                        return_value=selected_workspace,
                    ),
                    mock.patch(
                        "scripts.gar_lib.commands.target.Gar",
                        return_value=mock.Mock(target=target_api),
                    ),
                    contextlib.redirect_stdout(output),
                    contextlib.redirect_stderr(errors),
                ):
                    exit_code = main(
                        [
                            "target",
                            "deploy",
                            "--json",
                            "--workspace",
                            selected_workspace.name,
                        ]
                    )

                payload = json.loads(output.getvalue())
                self.assertEqual(1, exit_code)
                self.assertFalse(payload["placed"])
                self.assertFalse(payload["ok"])
                self.assertEqual("", errors.getvalue())

    def test_aarch64_artifact_is_rejected_by_measured_armv7l_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = write_v2_artifact(root, workspace(root))
            channel = FakeCommandChannel(
                target_stdout(
                    target_id="luckfox-rk3506",
                    architecture="armv7l",
                    abi="gnueabihf",
                    triple="arm-linux-gnueabihf",
                    kernel="6.1.84",
                )
            )

            with self.assertRaisesRegex(
                ArtifactCompatibilityError,
                "rejected before transfer",
            ) as raised:
                require_target_compatibility(artifact, channel)

        self.assertIsNotNone(raised.exception.report)
        fields = {issue.field for issue in raised.exception.report.issues}
        self.assertIn("target.id", fields)
        self.assertIn("target.architecture", fields)
        self.assertIn("target.abi", fields)

    def test_api_rejects_mismatch_before_file_environment_transfers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected_workspace = workspace(root)
            artifact = write_v2_artifact(root, selected_workspace)
            artifacts = mock.Mock()
            artifacts.latest.return_value = artifact
            command_channel = FakeCommandChannel(
                target_stdout(
                    target_id="luckfox-rk3506",
                    architecture="armv7l",
                    abi="gnueabihf",
                    triple="arm-linux-gnueabihf",
                    kernel="6.1.84",
                )
            )
            file_channel = mock.Mock()
            environment = FileTransferTargetEnvironment(command_channel, file_channel)

            with (
                mock.patch(
                    "scripts.gar_lib.api.target_environment_for",
                    return_value=environment,
                ),
                self.assertRaises(ArtifactCompatibilityError),
            ):
                Gar(selected_workspace, artifacts).target.deploy_report()

        file_channel.push.assert_not_called()

    def test_buildroot_vendor_triple_matches_measured_canonical_triple(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected_workspace = workspace(root, "luckfox-rk3506")
            artifact = write_v2_artifact(
                root,
                selected_workspace,
                target=ArtifactTarget(
                    id="luckfox-rk3506",
                    architecture="armv7l",
                    abi="gnueabihf",
                    libc="glibc",
                    toolchain_triple="arm-buildroot-linux-gnueabihf",
                ),
            )
            channel = FakeCommandChannel(
                target_stdout(
                    target_id="luckfox-rk3506",
                    architecture="armv7l",
                    abi="gnueabihf",
                    triple="arm-linux-gnueabihf",
                    kernel="6.1.84",
                )
            )

            _, report = require_target_compatibility(artifact, channel)

        self.assertTrue(report.compatible)

    def test_kernel_module_artifact_rejects_other_target_kernel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = write_v2_artifact(
                root,
                workspace(root),
                kernel=ArtifactKernel(
                    release="6.1.84",
                    vermagic=("6.1.84 SMP preempt mod_unload ARMv7",),
                ),
            )
            channel = FakeCommandChannel(target_stdout(kernel="6.12.1"))

            with self.assertRaises(ArtifactCompatibilityError) as raised:
                require_target_compatibility(artifact, channel)

        self.assertIsNotNone(raised.exception.report)
        self.assertIn("kernel.release", {issue.field for issue in raised.exception.report.issues})

    def test_legacy_bundle_is_rejected_before_target_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected_workspace = workspace(root)
            (root / "artifact.json").write_text("{}\n", encoding="utf-8")
            artifact = Artifact(ArtifactKind.TARGET_APP, selected_workspace, root)
            channel = FakeCommandChannel(target_stdout())

            with self.assertRaisesRegex(ArtifactCompatibilityError, "rebuild before deploy"):
                require_target_compatibility(artifact, channel)

        self.assertEqual([], channel.commands)

    def test_tampered_v2_bundle_is_rejected_before_target_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = write_v2_artifact(root, workspace(root))
            (root / "files" / "demo" / "run").write_text("tampered\n", encoding="utf-8")
            channel = FakeCommandChannel(target_stdout())

            with self.assertRaisesRegex(ArtifactCompatibilityError, "checksum mismatch"):
                require_target_compatibility(artifact, channel)

        self.assertEqual([], channel.commands)


if __name__ == "__main__":
    unittest.main()
