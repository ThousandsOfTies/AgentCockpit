from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.target.manifest import TargetManifest
from scripts.gar_lib.target.uuu import UuuTargetEnvironment


def _artifact(root: Path) -> Artifact:
    (root / "images").mkdir()
    (root / "images" / "image.wic.zst").write_bytes(b"image")
    (root / "artifact.json").write_text(
        '{"name":"demo","deploy":{"image":{"files":[{"src":"images/image.wic.zst","dest":"image.wic.zst"}]}}}',
        encoding="utf-8",
    )
    workspace = Workspace(
        id="ws",
        name="Local/Product",
        branch="Product",
        connection={"type": "local", "path": str(root)},
    )
    return Artifact(ArtifactKind.TARGET_APP, workspace, root)


class UuuTargetEnvironmentTests(unittest.TestCase):
    def test_deploy_expands_configured_image_command_without_a_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _artifact(root)
            manifest = TargetManifest(
                id="frdm-imx91s",
                display_name="FRDM-IMX91S",
                description="",
                tools_root="targets/frdm-imx91s",
                default_backends={"target": "uuu"},
                backend_notes={},
                provisioning={
                    "uuu": {
                        "type": "uuu",
                        "command": ["uuu", "-b", "sd_all", "{image}"],
                        "imageSection": "image",
                    }
                },
            )
            environment = UuuTargetEnvironment(manifest)
            completed = subprocess.CompletedProcess([], 0)
            with mock.patch("scripts.gar_lib.target.uuu.subprocess.run", return_value=completed) as run:
                environment.deploy(artifact)

        run.assert_called_once_with(
            ["uuu", "-b", "sd_all", str(root / "images" / "image.wic.zst")],
            cwd=root / "images",
            check=False,
        )

    def test_serial_verification_uses_workspace_console_port_after_flash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = _artifact(root)
            manifest = TargetManifest(
                id="frdm-imx91s",
                display_name="FRDM-IMX91S",
                description="",
                tools_root="targets/frdm-imx91s",
                default_backends={"target": "uuu"},
                backend_notes={},
                provisioning={
                    "uuu": {
                        "type": "uuu",
                        "command": ["uuu", "{image}"],
                        "imageSection": "image",
                        "serialVerify": {"pattern": "login:", "baud": 115200, "timeoutSeconds": 5},
                    }
                },
            )
            environment = UuuTargetEnvironment(manifest, console_port="/dev/ttyCH343USB0")
            with (
                mock.patch(
                    "scripts.gar_lib.target.uuu.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0),
                ),
                mock.patch("scripts.gar_lib.target.uuu.wait_for_serial_pattern") as verify,
            ):
                environment.deploy(artifact)

        verify.assert_called_once_with(
            "/dev/ttyCH343USB0",
            baud=115200,
            pattern="login:",
            timeout_seconds=5.0,
        )
