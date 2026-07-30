from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.runtime.mujoco import MujocoSimulationEnvironment


class MujocoSimulationEnvironmentTest(unittest.TestCase):
    def test_deploy_materializes_app_files_in_runtime_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "artifact"
            source = bundle / "files" / "model.xml"
            source.parent.mkdir(parents=True)
            source.write_text("<mujoco model='deployed'/>", encoding="utf-8")
            _write_manifest(bundle, destination="models/product.xml")
            workspace_dir = root / "runtime"
            environment = MujocoSimulationEnvironment(
                workspace_dir=workspace_dir,
                process_channel=mock.Mock(),
            )

            with mock.patch.object(environment, "_validate_model_or_raise") as validate:
                environment.deploy(_artifact(bundle))

            self.assertEqual(
                "<mujoco model='deployed'/>",
                (workspace_dir / "models" / "product.xml").read_text(encoding="utf-8"),
            )
            validate.assert_called_once_with()

    def test_deploy_rejects_destination_outside_runtime_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "artifact"
            source = bundle / "files" / "model.xml"
            source.parent.mkdir(parents=True)
            source.write_text("model", encoding="utf-8")
            _write_manifest(bundle, destination="../escaped.xml")
            environment = MujocoSimulationEnvironment(
                workspace_dir=root / "runtime",
                process_channel=mock.Mock(),
            )

            with self.assertRaisesRegex(GarDomainError, "workspace相対path"):
                environment.deploy(_artifact(bundle))

            self.assertFalse((root / "escaped.xml").exists())


def _artifact(bundle: Path) -> Artifact:
    workspace = Workspace(
        id="mujoco-test",
        name="Local/Mujoco",
        branch="Mujoco",
        connection={"type": "local", "path": str(bundle.parent)},
    )
    return Artifact(ArtifactKind.SIM_APP, workspace, bundle)


def _write_manifest(bundle: Path, *, destination: str) -> None:
    (bundle / "artifact.json").write_text(
        json.dumps(
            {
                "deploy": {
                    "app": {
                        "files": [
                            {
                                "src": "files/model.xml",
                                "dest": destination,
                                "mode": "0644",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
