from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.artifacts.store import LocalArtifactStore
from scripts.gar_lib.build.codespaces import CodespacesBuildEnvironment
from scripts.gar_lib.build.local import LocalBuildEnvironment
from scripts.gar_lib.commands import sim
from scripts.gar_lib.commands.common.workspace import workspace_for
from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace


def local_workspace(root: Path) -> Workspace:
    return Workspace(
        id="ws_test",
        name="Local/Product",
        branch="Product",
        connection={"type": "local", "path": str(root)},
        selected_environments={"codespace": "local"},
    )


def cli_args(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**{"json_output": False, **values})


class GarSimulationArchitectureTest(unittest.TestCase):
    def test_workspace_lookup_resolves_workspace_name(self) -> None:
        entry = {
            "id": "ws_test",
            "name": "Local/Product",
            "branch": "Product",
            "connection": {"type": "local", "path": "/tmp/product"},
            "selected_environments": {"codespace": "local"},
            "target": {"host": "raspi", "dest": "/opt/product"},
        }
        with (
            mock.patch("scripts.gar_lib.commands.common.workspace.load_config", return_value={"workspaces": [entry]}),
            mock.patch("scripts.gar_lib.commands.common.workspace.saved_workspaces", return_value=[entry]),
        ):
            workspace = workspace_for("Local/Product")

        self.assertEqual("ws_test", workspace.id)
        self.assertEqual("local", workspace.selected_environments["codespace"])
        self.assertEqual("raspi", workspace.target["host"])

    def test_workspace_lookup_requires_selector_for_multiple_entries(self) -> None:
        entries = [
            {
                "id": f"ws_{index}",
                "name": f"Local/Product{index}",
                "branch": f"Product{index}",
                "connection": {"type": "local", "path": f"/tmp/product{index}"},
            }
            for index in (1, 2)
        ]
        with (
            mock.patch("scripts.gar_lib.commands.common.workspace.load_config", return_value={"workspaces": entries}),
            mock.patch("scripts.gar_lib.commands.common.workspace.saved_workspaces", return_value=entries),
        ):
            with self.assertRaises(GarDomainError):
                workspace_for(None)

    def test_local_build_environment_runs_product_hook_and_returns_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hook = root / "scripts" / "product-sim-build.sh"
            hook.parent.mkdir()
            hook.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            artifact_root = root / "artifacts" / "from-codespace"
            artifact_file = artifact_root / "files" / "app"
            artifact_file.parent.mkdir(parents=True)
            artifact_file.write_text("app", encoding="utf-8")
            (artifact_root / "artifact.json").write_text(
                json.dumps(
                    {
                        "deploy": {
                            "app": {
                                "files": [{"src": "files/app", "dest": "~/app"}],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            workspace = local_workspace(root)
            completed = mock.Mock(returncode=0)
            with mock.patch("scripts.gar_lib.build.local.subprocess.run", return_value=completed) as run:
                artifact = LocalBuildEnvironment(LocalArtifactStore()).build(ArtifactKind.SIM_APP, workspace)

        self.assertEqual(ArtifactKind.SIM_APP, artifact.kind)
        run.assert_called_once_with([str(hook)], cwd=root, check=False, env=mock.ANY)

    def test_sim_app_build_uses_the_workspace_build_environment(self) -> None:
        workspace = local_workspace(Path("/tmp/product"))
        artifact = mock.Mock(bundle_path="/tmp/bundle")
        build_environment = mock.Mock()
        build_environment.build.return_value = artifact

        with (
            mock.patch(
                "scripts.gar_lib.commands.sim.build_environment_for",
                return_value=build_environment,
            ) as build_for,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = sim.run_sim_app_build(workspace, cli_args())

        self.assertEqual(0, exit_code)
        build_for.assert_called_once_with(workspace, mock.ANY)
        build_environment.build.assert_called_once_with(ArtifactKind.SIM_APP, workspace)

    def test_sim_app_clean_uses_the_workspace_build_environment(self) -> None:
        workspace = local_workspace(Path("/tmp/product"))
        build_environment = mock.Mock()

        with (
            mock.patch(
                "scripts.gar_lib.commands.sim.build_environment_for",
                return_value=build_environment,
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = sim.run_sim_app_clean(workspace, cli_args())

        self.assertEqual(0, exit_code)
        build_environment.clean.assert_called_once_with(ArtifactKind.SIM_APP, workspace)

    def test_codespaces_build_runs_hook_and_materializes_artifact(self) -> None:
        workspace = Workspace(
            id="ws_test",
            name="Codespaces/Product",
            branch="Product",
            connection={
                "type": "codespaces",
                "path": "/workspaces/product",
                "codespace": "product-space",
            },
            selected_environments={"codespace": "github_codespaces"},
        )
        artifact = mock.Mock()
        artifacts = mock.Mock(spec=LocalArtifactStore)
        artifacts.latest.return_value = artifact
        completed = mock.Mock(returncode=0)

        with mock.patch("scripts.gar_lib.build.codespaces.subprocess.run", return_value=completed) as run:
            result = CodespacesBuildEnvironment(artifacts).build(ArtifactKind.SIM_APP, workspace)

        self.assertIs(artifact, result)
        run.assert_called_once_with(
            [
                "gh",
                "codespace",
                "ssh",
                "-c",
                "product-space",
                "--",
                "cd /workspaces/product && scripts/product-sim-build.sh",
            ],
            check=False,
        )
        artifacts.sync_from_codespaces.assert_called_once_with(workspace)
        artifacts.latest.assert_called_once_with(ArtifactKind.SIM_APP, workspace)

    def test_wokwi_runtime_build_does_not_invoke_a_product_runtime_hook(self) -> None:
        workspace = local_workspace(Path("/tmp/product"))

        with (
            mock.patch(
                "scripts.gar_lib.commands.sim.simulation_environment_for",
                return_value=mock.Mock(requires_runtime_artifact=False),
            ),
            mock.patch("scripts.gar_lib.commands.sim.build_environment_for") as build_for,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = sim.run_sim_runtime_build(workspace, cli_args())

        self.assertEqual(0, exit_code)
        build_for.assert_not_called()

    def test_wokwi_runtime_deploy_does_not_require_an_artifact(self) -> None:
        workspace = local_workspace(Path("/tmp/product"))
        environment = mock.Mock(requires_runtime_artifact=False)
        artifacts = mock.Mock()

        with (
            mock.patch(
                "scripts.gar_lib.commands.sim.simulation_environment_for",
                return_value=environment,
            ),
            mock.patch(
                "scripts.gar_lib.commands.sim.LocalArtifactStore", return_value=artifacts
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            exit_code = sim.run_sim_runtime_deploy(workspace, cli_args())

        self.assertEqual(0, exit_code)
        artifacts.latest.assert_not_called()
        environment.deploy.assert_not_called()
