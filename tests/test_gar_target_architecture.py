from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.artifacts.store import LocalArtifactStore
from scripts.gar_lib.build.local import LocalBuildEnvironment
from scripts.gar_lib.cli import main
from scripts.gar_lib.commands import target as target_commands
from scripts.gar_lib.commands.setup import configure_target_connection
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import AccessConnectionError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.target.backends import target_environment_for
from scripts.gar_lib.target.esp32 import Esp32ArtifactInstaller
from scripts.gar_lib.target.file_transfer import FileTransferTargetEnvironment


def workspace(root: Path, *, target: str = "adb_usb") -> Workspace:
    return Workspace(
        id="ws_target",
        name="Local/Product",
        branch="Product",
        connection={"type": "local", "path": str(root)},
        selected_environments={"codespace": "local", "target": target},
    )


def cli_args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json_output": False, **values})


class GarTargetArchitectureTest(unittest.TestCase):
    def test_setup_saves_ssh_target_host_per_workspace(self) -> None:
        config = {"selected_environments": {"target": "ssh_scp"}}
        with (
            mock.patch("scripts.gar_lib.commands.setup.sys.stdin.isatty", return_value=True),
            mock.patch("scripts.gar_lib.commands.setup.safe_input", return_value="raspi-target"),
            mock.patch("scripts.gar_lib.commands.setup.save_config") as save,
        ):
            configure_target_connection(config)

        self.assertEqual("raspi-target", config["target"]["host"])
        save.assert_called_once_with(config)

    def test_local_target_build_runs_product_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hook = root / "scripts" / "product-target-build.sh"
            hook.parent.mkdir()
            hook.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            artifact_root = root / "artifacts" / "from-codespace"
            artifact_file = artifact_root / "files" / "app"
            artifact_file.parent.mkdir(parents=True)
            artifact_file.write_text("app", encoding="utf-8")
            (artifact_root / "artifact.json").write_text(
                json.dumps(
                    {"deploy": {"app": {"files": [{"src": "files/app", "dest": "~/app"}]}}}
                ),
                encoding="utf-8",
            )
            completed = mock.Mock(returncode=0)
            with mock.patch("scripts.gar_lib.build.local.subprocess.run", return_value=completed) as run:
                artifact = LocalBuildEnvironment(LocalArtifactStore()).build(
                    ArtifactKind.TARGET_APP,
                    workspace(root),
                )

        self.assertEqual(ArtifactKind.TARGET_APP, artifact.kind)
        run.assert_called_once_with([str(hook)], cwd=root, check=False, env=mock.ANY)

    def test_target_app_build_uses_the_workspace_build_environment(self) -> None:
        selected_workspace = workspace(Path("/tmp/product"))
        build_environment = mock.Mock()
        build_environment.build.return_value = mock.Mock(bundle_path="/tmp/bundle")

        with (
            mock.patch(
                "scripts.gar_lib.commands.target.build_environment_for",
                return_value=build_environment,
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = target_commands.run_target_app_build(selected_workspace, cli_args())

        self.assertEqual(0, exit_code)
        build_environment.build.assert_called_once_with(ArtifactKind.TARGET_APP, selected_workspace)

    def test_target_app_deploy_uses_latest_artifact_and_environment(self) -> None:
        selected_workspace = workspace(Path("/tmp/product"))
        artifact = mock.Mock(bundle_path="/tmp/bundle")
        artifacts = mock.Mock()
        artifacts.latest.return_value = artifact
        environment = mock.Mock()

        with (
            mock.patch(
                "scripts.gar_lib.commands.target.LocalArtifactStore", return_value=artifacts
            ),
            mock.patch(
                "scripts.gar_lib.commands.target.target_environment_for",
                return_value=environment,
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = target_commands.run_target_app_deploy(selected_workspace, cli_args())

        self.assertEqual(0, exit_code)
        artifacts.latest.assert_called_once_with(ArtifactKind.TARGET_APP, selected_workspace)
        environment.deploy.assert_called_once_with(artifact)

    def test_target_adb_failure_uses_shared_recovery_guidance(self) -> None:
        selected_workspace = workspace(Path("/tmp/product"))
        environment = mock.Mock()
        environment.deploy.side_effect = AccessConnectionError(
            channel="adb",
            endpoint="device-1",
            reason="no_device",
            returncode=1,
        )
        stderr = io.StringIO()
        with (
            mock.patch("scripts.gar_lib.commands.target.workspace_for", return_value=selected_workspace),
            mock.patch("scripts.gar_lib.commands.target.LocalArtifactStore"),
            mock.patch(
                "scripts.gar_lib.commands.target.target_environment_for",
                return_value=environment,
            ),
            mock.patch(
                "scripts.gar_lib.recovery.access.run_terminal_run_command"
            ) as terminal_request,
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(stderr),
        ):
            result = main(["target", "app", "deploy", "--workspace", "Local/Product"])

        self.assertEqual(1, result)
        terminal_request.assert_not_called()
        self.assertIn("gar usb attach", stderr.getvalue())

    def test_file_target_transfers_manifest_and_applies_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "files" / "app"
            source.parent.mkdir()
            source.write_text("app", encoding="utf-8")
            (root / "artifact.json").write_text(
                json.dumps(
                    {
                        "deploy": {
                            "app": {
                                "files": [
                                    {"src": "files/app", "dest": "bin/app", "mode": "0755"}
                                ]
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            selected_workspace = workspace(root)
            artifact = Artifact(ArtifactKind.TARGET_APP, selected_workspace, root)
            command_channel = mock.Mock()
            command_channel.run.return_value.returncode = 0
            file_channel = mock.Mock()
            file_channel.push.return_value.returncode = 0
            environment = FileTransferTargetEnvironment(
                command_channel,
                file_channel,
                base_destination="/opt/product",
            )

            environment.deploy(artifact)

        file_channel.push.assert_called_once_with(source, "/opt/product/bin/app")
        self.assertEqual(
            [mock.call("mkdir -p /opt/product/bin"), mock.call("chmod 0755 /opt/product/bin/app")],
            command_channel.run.call_args_list,
        )

    def test_target_resolver_composes_adb_channels(self) -> None:
        selected_workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={"target": "adb_usb"},
            target={"serial": "device-1", "dest": "/data/local/tmp"},
        )
        environment = target_environment_for(selected_workspace)

        completed = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch("scripts.gar_lib.access.adb.subprocess.run", return_value=completed) as run:
            artifact = mock.Mock(kind=ArtifactKind.TARGET_APP)
            with mock.patch(
                "scripts.gar_lib.target.file_transfer.load_deploy_files",
                return_value=(Path("/tmp"), [{"src": "app", "dest": "app"}]),
            ), mock.patch(
                "scripts.gar_lib.target.file_transfer.resolve_artifact_src",
                return_value=Path("/tmp/app"),
            ):
                environment.deploy(artifact)

        self.assertEqual(
            ("adb", "-s", "device-1", "push", "/tmp/app", "/data/local/tmp/app"),
            run.call_args_list[-1].args[0],
        )

    def test_target_resolver_uses_configured_ssh_host(self) -> None:
        selected_workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={"target": "ssh_scp"},
            target={"host": "raspi", "dest": "/opt/product"},
        )
        environment = target_environment_for(selected_workspace)

        self.assertEqual("raspi", environment.command_channel.host)
        self.assertEqual("raspi", environment.file_channel.host)
        self.assertEqual("/opt/product", environment.base_destination)

    def test_target_backend_composes_serial_installer(self) -> None:
        selected_workspace = Workspace(
            id="ws",
            name="Local/Product",
            branch="Product",
            connection={"type": "local", "path": "/tmp/product"},
            selected_environments={"target": "esp32_esptool"},
            esp32={"port": "COM4"},
        )

        environment = target_environment_for(selected_workspace)

        self.assertEqual("COM4", environment.installer.port)

    def test_esp32_installer_resolves_firmware_directory_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            firmware = root / "files" / "firmware"
            firmware.mkdir(parents=True)
            for name in ("bootloader.bin", "partitions.bin", "boot_app0.bin", "firmware.bin"):
                (firmware / name).write_bytes(b"firmware")
            (root / "artifact.json").write_text(
                json.dumps(
                    {
                        "deploy": {
                            "app": {
                                "files": [{"src": "files/firmware", "dest": "firmware"}]
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            selected_workspace = workspace(root, target="esp32_esptool")
            artifact = Artifact(ArtifactKind.TARGET_APP, selected_workspace, root)
            with mock.patch(
                "scripts.gar_lib.target.esp32.run_esp32_flash_command",
                return_value=0,
            ) as flash:
                result = Esp32ArtifactInstaller("COM4").install(artifact)

        self.assertEqual(0, result.returncode)
        flash.assert_called_once_with(artifact_dir=str(firmware), port="COM4")


if __name__ == "__main__":
    unittest.main()
