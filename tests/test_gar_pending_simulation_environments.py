from __future__ import annotations

import unittest
from pathlib import Path

from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.simulation.composition import simulation_environment_for
from scripts.gar_lib.simulation.runtime.aws_ssm import AwsSsmSimulationEnvironment
from scripts.gar_lib.simulation.runtime.esp32_qemu import Esp32QemuSimulationEnvironment
from scripts.gar_lib.simulation.runtime.renode import RenodeSimulationEnvironment


def workspace(environment_id: str, *, ec2: dict[str, str] | None = None) -> Workspace:
    return Workspace(
        id="ws_pending",
        name="Local/Pending",
        branch="Pending",
        connection={"type": "local", "path": str(Path("/tmp/pending"))},
        selected_environments={"simulator": environment_id},
        ec2=ec2 or {},
    )


class PendingSimulationEnvironmentTest(unittest.TestCase):
    def test_setup_environment_ids_resolve_to_named_components(self) -> None:
        cases = (
            ("renode_mcu", RenodeSimulationEnvironment, {}, False),
            ("esp32_qemu_firmware", Esp32QemuSimulationEnvironment, {}, False),
            (
                "aws_ssm",
                AwsSsmSimulationEnvironment,
                {"instance_id": "i-0123456789", "region": "ap-northeast-1"},
                True,
            ),
        )

        for environment_id, expected_type, ec2, requires_runtime_artifact in cases:
            with self.subTest(environment_id=environment_id):
                environment = simulation_environment_for(workspace(environment_id, ec2=ec2))

                self.assertIsInstance(environment, expected_type)
                self.assertEqual(
                    requires_runtime_artifact,
                    environment.requires_runtime_artifact,
                )
                artifact = Artifact(
                    ArtifactKind.SIM_APP,
                    workspace(environment_id),
                    Path("/tmp/artifact"),
                )
                operations = (
                    ("deploy", (artifact,)),
                    ("start", ({},)),
                    ("stop", ({},)),
                    ("status", ({},)),
                    ("diag", ({},)),
                    ("log", ()),
                )
                for operation, arguments in operations:
                    with self.subTest(environment_id=environment_id, operation=operation):
                        with self.assertRaisesRegex(
                            GarDomainError,
                            rf"{environment_id} SimulationEnvironmentの{operation}はまだ実装されていません",
                        ):
                            getattr(environment, operation)(*arguments)

    def test_aws_ssm_requires_instance_and_region_to_compose(self) -> None:
        with self.assertRaisesRegex(
            GarDomainError,
            r"AWS SSM設定が不足しています \(instance_id, region\)",
        ):
            simulation_environment_for(workspace("aws_ssm"))


if __name__ == "__main__":
    unittest.main()
