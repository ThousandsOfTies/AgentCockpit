from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.api import Gar
from scripts.gar_lib.artifacts.metadata import (
    ArtifactMetadata,
    ArtifactTarget,
    sha256_checksums,
    write_artifact_metadata,
)
from scripts.gar_lib.artifacts.provenance import TargetToolsProvenance
from scripts.gar_lib.cli import main
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.target.compatibility import ArtifactCompatibilityError
from scripts.gar_lib.target.esp32 import Esp32TargetEnvironment
from scripts.gar_lib.target.file_transfer import FileTransferTargetEnvironment

TOOLS_COMMIT = "a" * 40
SOURCE_COMMIT = "b" * 40


def selected_workspace(root: Path, *, backend: str = "ssh_scp") -> Workspace:
    return Workspace(
        id="ws-preflight",
        name="Local/Product",
        branch="Product",
        connection={"type": "local", "path": str(root)},
        selected_environments={"codespace": "local", "target": backend},
        selected_target="target-a",
        target={"host": "physical-target"},
        esp32={"port": "COM4"},
    )


def write_target_artifact(root: Path, workspace: Workspace) -> Artifact:
    application = root / "files" / "demo"
    application.mkdir(parents=True)
    (application / "run").write_text("#!/bin/sh\n", encoding="utf-8")
    (root / "artifact.json").write_text(
        json.dumps(
            {
                "schemaVersion": 2,
                "name": "demo",
                "target": "target-a",
                "entrypoint": "/opt/gar/apps/demo/run",
                "deploy": {
                    "app": {
                        "files": [
                            {
                                "src": "files/demo",
                                "dest": "/opt/gar/apps/demo",
                                "mode": "0755",
                            }
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    metadata = ArtifactMetadata(
        schema_version=2,
        kind=ArtifactKind.TARGET_APP.value,
        product="demo",
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        workspace_branch=workspace.branch,
        target=ArtifactTarget(
            id="target-a",
            architecture="aarch64",
            abi="gnu",
            libc="glibc",
            toolchain_triple="aarch64-linux-gnu",
        ),
        entrypoint="/opt/gar/apps/demo/run",
        source_commit=SOURCE_COMMIT,
        gar_tools_commit=TOOLS_COMMIT,
        target_recipe_version="4",
        checksums=sha256_checksums(root),
        build_id="build-123",
        build_timestamp="2026-08-11T00:00:00+00:00",
    )
    write_artifact_metadata(root, metadata)
    return Artifact(ArtifactKind.TARGET_APP, workspace, root)


def capability_probe(*, architecture: str = "aarch64", installed_recipe: str = "4") -> str:
    return "\n".join(
        (
            "target_id=target-a",
            f"architecture={architecture}",
            "abi=gnu",
            "libc=glibc",
            "toolchain_triple=aarch64-linux-gnu",
            "kernel_release=6.6.0",
            "installed_target_id=target-a",
            f"installed_recipe_version={installed_recipe}",
            f"installed_gar_tools_commit={TOOLS_COMMIT}",
        )
    )


def file_environment(probe: str | BaseException) -> tuple[FileTransferTargetEnvironment, mock.Mock, mock.Mock]:
    commands = mock.Mock()
    if isinstance(probe, BaseException):
        commands.run.side_effect = probe
    else:
        commands.run.return_value = subprocess.CompletedProcess([], 0, probe, "")
    files = mock.Mock()
    environment = FileTransferTargetEnvironment(
        commands,
        files,
        active_tools_provenance=TargetToolsProvenance(
            target_id="target-a",
            gar_tools_commit=TOOLS_COMMIT,
            target_recipe_version="4",
        ),
        require_active_tools_provenance=True,
    )
    return environment, commands, files


class GarTargetPreflightTest(unittest.TestCase):
    def test_api_preflight_validates_without_push_or_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = selected_workspace(Path(temporary))
            artifact = write_target_artifact(Path(temporary), workspace)
            artifacts = mock.Mock()
            artifacts.latest.return_value = artifact
            environment, commands, files = file_environment(capability_probe())
            validate = mock.Mock(wraps=environment.validate_deployment)
            environment.validate_deployment = validate
            environment.deploy = mock.Mock()
            environment.prepare = mock.Mock()
            environment.configure = mock.Mock()

            with (
                mock.patch("scripts.gar_lib.api.target_environment_for", return_value=environment),
                mock.patch(
                    "scripts.gar_lib.api.target_lifecycle_for",
                    side_effect=AssertionError("preflight must not compose lifecycle"),
                ) as lifecycle,
            ):
                result = Gar(workspace, artifacts).target.preflight(app="demo")

        self.assertTrue(result.ok)
        self.assertEqual("demo", result.application.name)
        self.assertEqual("build-123", result.build_id)
        artifacts.latest.assert_called_once_with(ArtifactKind.TARGET_APP, workspace)
        validate.assert_called_once_with(artifact)
        environment.deploy.assert_not_called()
        environment.prepare.assert_not_called()
        environment.configure.assert_not_called()
        commands.run.assert_called_once()
        files.push.assert_not_called()
        lifecycle.assert_not_called()

    def test_cli_preflight_reports_success_as_stdout_only_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = selected_workspace(Path(temporary))
            artifact = write_target_artifact(Path(temporary), workspace)
            artifacts = mock.Mock()
            artifacts.latest.return_value = artifact
            environment, _, files = file_environment(capability_probe())
            target = Gar(workspace, artifacts).target
            output = io.StringIO()
            errors = io.StringIO()

            with (
                mock.patch("scripts.gar_lib.commands.target.resolve_workspace", return_value=workspace),
                mock.patch("scripts.gar_lib.commands.target.Gar", return_value=mock.Mock(target=target)),
                mock.patch("scripts.gar_lib.api.target_environment_for", return_value=environment),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(errors),
            ):
                exit_code = main(["target", "preflight", "--workspace", workspace.name, "--app", "demo", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("target.preflight", payload["command"])
        self.assertEqual(workspace.name, payload["workspace"])
        self.assertEqual("target-a", payload["target_id"])
        self.assertEqual("demo", payload["app"])
        self.assertEqual("build-123", payload["build_id"])
        self.assertTrue(payload["compatible"])
        self.assertTrue(payload["ok"])
        self.assertEqual(0, payload["exit_code"])
        self.assertEqual("", errors.getvalue())
        files.push.assert_not_called()

    def test_preflight_rejects_wrong_architecture_and_installed_recipe_drift_before_push(self) -> None:
        cases = {
            "wrong architecture": capability_probe(architecture="x86_64"),
            "installed recipe drift": capability_probe(installed_recipe="3"),
        }
        for name, probe in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                workspace = selected_workspace(Path(temporary))
                artifact = write_target_artifact(Path(temporary), workspace)
                artifacts = mock.Mock()
                artifacts.latest.return_value = artifact
                environment, commands, files = file_environment(probe)
                with (
                    mock.patch("scripts.gar_lib.api.target_environment_for", return_value=environment),
                    self.assertRaises(ArtifactCompatibilityError) as caught,
                ):
                    Gar(workspace, artifacts).target.preflight()

                self.assertIn("rejected before transfer", str(caught.exception))
                self.assertIsNotNone(caught.exception.report)
                commands.run.assert_called_once()
                files.push.assert_not_called()

    def test_cli_preflight_compatibility_failure_keeps_identity_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = selected_workspace(Path(temporary))
            artifact = write_target_artifact(Path(temporary), workspace)
            artifacts = mock.Mock()
            artifacts.latest.return_value = artifact
            environment, _, files = file_environment(capability_probe(architecture="x86_64"))
            target = Gar(workspace, artifacts).target
            output = io.StringIO()
            errors = io.StringIO()
            with (
                mock.patch("scripts.gar_lib.commands.target.resolve_workspace", return_value=workspace),
                mock.patch("scripts.gar_lib.commands.target.Gar", return_value=mock.Mock(target=target)),
                mock.patch("scripts.gar_lib.api.target_environment_for", return_value=environment),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(errors),
            ):
                exit_code = main(["target", "preflight", "--workspace", workspace.name, "--app", "demo", "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("demo", payload["app"])
        self.assertEqual("build-123", payload["build_id"])
        self.assertFalse(payload["compatible"])
        self.assertFalse(payload["ok"])
        self.assertEqual(1, payload["exit_code"])
        self.assertFalse(payload["compatibility"]["compatible"])
        self.assertEqual("", errors.getvalue())
        files.push.assert_not_called()

    def test_preflight_rejects_checksum_damage_before_target_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = selected_workspace(root)
            artifact = write_target_artifact(root, workspace)
            (root / "files" / "demo" / "run").write_text("tampered\n", encoding="utf-8")
            artifacts = mock.Mock()
            artifacts.latest.return_value = artifact
            environment, commands, files = file_environment(capability_probe())

            with (
                mock.patch("scripts.gar_lib.api.target_environment_for", return_value=environment),
                self.assertRaises(ArtifactCompatibilityError) as caught,
            ):
                Gar(workspace, artifacts).target.preflight()

        self.assertIn("checksum mismatch", str(caught.exception))
        commands.run.assert_not_called()
        files.push.assert_not_called()

    def test_malformed_snapshot_error_remains_one_stdout_json_object(self) -> None:
        workspace = selected_workspace(Path("/tmp/product"))
        artifacts = mock.Mock()

        def fail_latest(*_: object) -> Artifact:
            print("raw artifact parser diagnostic", file=sys.stderr)
            raise GarDomainError("artifact metadataが不正です")

        artifacts.latest.side_effect = fail_latest
        output = io.StringIO()
        errors = io.StringIO()
        with (
            mock.patch("scripts.gar_lib.commands.target.resolve_workspace", return_value=workspace),
            mock.patch("scripts.gar_lib.api.LocalArtifactStore", return_value=artifacts),
            mock.patch("scripts.gar_lib.api.target_environment_for") as environment_for,
            contextlib.redirect_stdout(output),
            contextlib.redirect_stderr(errors),
        ):
            exit_code = main(["target", "preflight", "--workspace", workspace.name, "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertFalse(payload["ok"])
        self.assertFalse(payload["compatible"])
        self.assertEqual(1, payload["exit_code"])
        self.assertIn("artifact metadataが不正", payload["error"])
        self.assertIn("raw artifact parser diagnostic", payload["error"])
        self.assertEqual("", errors.getvalue())
        environment_for.assert_not_called()

    def test_access_failure_is_structured_without_push(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = selected_workspace(Path(temporary))
            artifact = write_target_artifact(Path(temporary), workspace)
            artifacts = mock.Mock()
            artifacts.latest.return_value = artifact
            access_error = AccessConnectionError(
                channel="ssh",
                endpoint="physical-target",
                reason="unreachable",
                returncode=255,
            )
            environment, _, files = file_environment(access_error)
            target = Gar(workspace, artifacts).target
            output = io.StringIO()
            errors = io.StringIO()
            with (
                mock.patch("scripts.gar_lib.commands.target.resolve_workspace", return_value=workspace),
                mock.patch("scripts.gar_lib.commands.target.Gar", return_value=mock.Mock(target=target)),
                mock.patch("scripts.gar_lib.api.target_environment_for", return_value=environment),
                contextlib.redirect_stdout(output),
                contextlib.redirect_stderr(errors),
            ):
                exit_code = main(["target", "preflight", "--workspace", workspace.name, "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertFalse(payload["compatible"])
        self.assertEqual(1, payload["exit_code"])
        self.assertEqual(255, payload["access"]["exit_code"])
        self.assertEqual("", errors.getvalue())
        files.push.assert_not_called()

    def test_preflight_rejects_target_without_compatibility_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = selected_workspace(Path(temporary), backend="esp32_esptool")
            artifact = write_target_artifact(Path(temporary), workspace)
            artifacts = mock.Mock()
            artifacts.latest.return_value = artifact
            environment = Esp32TargetEnvironment("COM4")
            with (
                mock.patch("scripts.gar_lib.api.target_environment_for", return_value=environment),
                mock.patch.object(environment, "validate_deployment") as validate,
                self.assertRaises(GarDomainError) as caught,
            ):
                Gar(workspace, artifacts).target.preflight()

        self.assertIn("preflightに対応していません", str(caught.exception))
        validate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
