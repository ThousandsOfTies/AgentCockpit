import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.commands.infra import run_sim_infra_command
from scripts.gar_lib.simulation.host.ssh_config import SshConfigHostAddressUpdater


class GarSimulationInfrastructureTest(unittest.TestCase):
    def test_sim_infra_setup_shows_settings_and_runs_terraform_plan(self) -> None:
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        output_result = mock.Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "instance_id": {"value": "i-from-tf"},
                    "public_ip": {"value": "203.0.113.55"},
                }
            ),
            stderr="",
        )
        config = {
            "selected_environments": {},
            "ec2": {"host": "configured-ec2", "region": "ap-test-1"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch("scripts.gar_lib.commands.infra.TERRAFORM_DIR", Path(tmp)),
                mock.patch("scripts.gar_lib.commands.infra._terraform_available", return_value=True),
                mock.patch("scripts.gar_lib.commands.infra.load_config", return_value=config),
                mock.patch(
                    "scripts.gar_lib.commands.infra._run_terraform",
                    side_effect=[completed, output_result, completed],
                ) as run_tf,
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = run_sim_infra_command(
                        "setup",
                        key_name="gar-key",
                        region="ap-test-2",
                    )

        self.assertEqual(0, result)
        self.assertEqual(["init", "-input=false"], run_tf.call_args_list[0].args[0])
        self.assertEqual(["output", "-json"], run_tf.call_args_list[1].args[0])
        self.assertEqual(["plan", "-input=false"], run_tf.call_args_list[2].args[0])
        env = run_tf.call_args_list[2].kwargs["env"]
        self.assertEqual("ap-test-2", env["TF_VAR_aws_region"])
        self.assertEqual("gar-key", env["TF_VAR_key_name"])
        self.assertIn("Current simulation infra settings:", output.getvalue())
        self.assertIn("i-from-tf", output.getvalue())

    def test_sim_infra_apply_saves_instance_and_updates_ssh(self) -> None:
        init_result = mock.Mock(returncode=0, stdout="", stderr="")
        apply_result = mock.Mock(returncode=0, stdout="", stderr="")
        output_result = mock.Mock(
            returncode=0,
            stdout=json.dumps(
                {
                    "instance_id": {"value": "i-from-tf"},
                    "public_ip": {"value": "203.0.113.55"},
                }
            ),
            stderr="",
        )
        config = {
            "selected_environments": {},
            "ec2": {"host": "configured-ec2", "region": "ap-test-1"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch("scripts.gar_lib.commands.infra.TERRAFORM_DIR", Path(tmp)),
                mock.patch("scripts.gar_lib.commands.infra._terraform_available", return_value=True),
                mock.patch("scripts.gar_lib.commands.infra.load_config", return_value=config),
                mock.patch("scripts.gar_lib.commands.infra.save_config") as save_config,
                mock.patch(
                    "scripts.gar_lib.commands.infra._run_terraform",
                    side_effect=[init_result, apply_result, output_result],
                ) as run_tf,
                mock.patch("scripts.gar_lib.commands.infra.SshConfigHostAddressUpdater") as updater_type,
            ):
                updater_type.return_value.update.return_value = True
                result = run_sim_infra_command(
                    "apply",
                    region="ap-test-2",
                    auto_approve=True,
                )

        self.assertEqual(0, result)
        self.assertEqual(["apply", "-input=false", "-auto-approve"], run_tf.call_args_list[1].args[0])
        saved_config = save_config.call_args.args[0]
        self.assertEqual("i-from-tf", saved_config["ec2"]["instance_id"])
        self.assertEqual("ap-test-2", saved_config["ec2"]["region"])
        updater_type.return_value.update.assert_called_once_with("configured-ec2", "203.0.113.55")

    def test_update_ssh_config_hostname_rewrites_target_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config"
            config_path.write_text(
                "Host other\n"
                "    HostName 198.51.100.1\n"
                "\n"
                "Host vibecode-graviton\n"
                "    HostName 192.0.2.1\n"
                "    User ubuntu\n",
                encoding="utf-8",
            )

            updated = SshConfigHostAddressUpdater(config_path).update("vibecode-graviton", "203.0.113.5")

            self.assertTrue(updated)
            contents = config_path.read_text(encoding="utf-8")
            self.assertIn("HostName 203.0.113.5", contents)
            self.assertIn("HostName 198.51.100.1", contents)

    def test_update_ssh_config_hostname_adds_missing_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config"
            config_path.write_text(
                "Host vibecode-graviton\n" "    User ubuntu\n" "    IdentityFile ~/.ssh/vibecode-graviton.pem\n",
                encoding="utf-8",
            )

            updated = SshConfigHostAddressUpdater(config_path).update("vibecode-graviton", "203.0.113.5")

            self.assertTrue(updated)
            self.assertIn("    HostName 203.0.113.5\n", config_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
