from __future__ import annotations

import unittest

from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.core.workspace_settings import (
    DockerSettings,
    Ec2Settings,
    SelectedEnvironments,
    WorkspaceConnection,
)


class WorkspaceSettingsTest(unittest.TestCase):
    def test_json_mappings_are_converted_at_the_workspace_boundary(self) -> None:
        workspace = Workspace(
            id="ws_typed",
            name="Local/Typed",
            branch="Typed",
            connection={"type": "local", "path": "/tmp/typed"},
            selected_environments={
                "codespace": "local",
                "simulator": "local_docker",
                "target": "ssh_scp",
            },
            ec2={"host": "sim-host", "private_ip": "10.0.1.25", "region": "ap-test-1"},
            docker={"container": "gar-sim", "bridge_port": 9090},
        )

        self.assertIsInstance(workspace.connection, WorkspaceConnection)
        self.assertIsInstance(workspace.selected_environments, SelectedEnvironments)
        self.assertIsInstance(workspace.ec2, Ec2Settings)
        self.assertIsInstance(workspace.docker, DockerSettings)
        self.assertEqual("local_docker", workspace.selected_environments.simulator)
        self.assertEqual("sim-host", workspace.ec2.host)
        self.assertEqual("10.0.1.25", workspace.ec2.private_ip)
        self.assertEqual(9090, workspace.docker.bridge_port)

    def test_typed_settings_keep_mapping_compatibility_at_legacy_boundaries(self) -> None:
        settings = DockerSettings(container="gar-sim", bridge_port=8080)

        self.assertEqual("gar-sim", settings.get("container"))
        self.assertEqual(8080, settings["bridge_port"])
        self.assertEqual(
            {"container": "gar-sim", "bridge_port": 8080},
            settings.to_dict(),
        )


if __name__ == "__main__":
    unittest.main()
