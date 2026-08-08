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
                    "private_ip": {"value": "10.0.1.25"},
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
                mock.patch("scripts.gar_lib.commands.infra._inject_aws_cli_credentials", return_value=True),
                mock.patch("scripts.gar_lib.commands.infra.load_config", return_value=config),
                mock.patch(
                    "scripts.gar_lib.commands.infra._run_terraform",
                    side_effect=[completed, completed, output_result, completed],
                ) as run_tf,
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = run_sim_infra_command(
                        "setup",
                        key_name="gar-key",
                        region="ap-test-2",
                        ssh_cidr="203.0.113.4/32",
                    )

        self.assertEqual(0, result)
        self.assertEqual(["init", "-input=false"], run_tf.call_args_list[0].args[0])
        self.assertEqual(
            ["workspace", "select", "-or-create=true", "default"],
            run_tf.call_args_list[1].args[0],
        )
        self.assertEqual(["output", "-json"], run_tf.call_args_list[2].args[0])
        self.assertEqual(["plan", "-input=false"], run_tf.call_args_list[3].args[0])
        env = run_tf.call_args_list[3].kwargs["env"]
        self.assertEqual("ap-test-2", env["TF_VAR_aws_region"])
        self.assertEqual("ap-test-2", env["AWS_REGION"])
        self.assertEqual("gar-key", env["TF_VAR_key_name"])
        self.assertEqual("203.0.113.4/32", env["TF_VAR_ssh_ingress_cidr"])
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
                    "private_ip": {"value": "10.0.1.25"},
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
                mock.patch("scripts.gar_lib.commands.infra._inject_aws_cli_credentials", return_value=True),
                mock.patch("scripts.gar_lib.commands.infra.load_config", return_value=config),
                mock.patch("scripts.gar_lib.commands.infra.save_config") as save_config,
                mock.patch(
                    "scripts.gar_lib.commands.infra._run_terraform",
                    side_effect=[init_result, init_result, apply_result, output_result],
                ) as run_tf,
                mock.patch("scripts.gar_lib.commands.infra.SshConfigHostAddressUpdater") as updater_type,
            ):
                updater_type.return_value.update.return_value = True
                result = run_sim_infra_command(
                    "apply",
                    region="ap-test-2",
                    ssh_cidr="203.0.113.4/32",
                    auto_approve=True,
                )

        self.assertEqual(0, result)
        self.assertEqual(
            ["workspace", "select", "-or-create=true", "default"],
            run_tf.call_args_list[1].args[0],
        )
        self.assertEqual(["apply", "-input=false", "-auto-approve"], run_tf.call_args_list[2].args[0])
        saved_config = save_config.call_args.args[0]
        self.assertEqual("i-from-tf", saved_config["ec2"]["instance_id"])
        self.assertEqual("10.0.1.25", saved_config["ec2"]["private_ip"])
        self.assertEqual("ap-test-2", saved_config["ec2"]["region"])
        updater_type.return_value.update.assert_called_once_with("configured-ec2", "203.0.113.55")

    def test_workspace_state_uses_the_active_gar_workspace_id(self) -> None:
        completed = mock.Mock(returncode=0, stdout="", stderr="")
        config = {
            "workspace_id": "ws_abc123",
            "selected_environments": {},
            "ec2": {"region": "ap-test-1"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch("scripts.gar_lib.commands.infra.TERRAFORM_DIR", Path(tmp)),
                mock.patch("scripts.gar_lib.commands.infra._terraform_available", return_value=True),
                mock.patch("scripts.gar_lib.commands.infra._inject_aws_cli_credentials", return_value=True),
                mock.patch("scripts.gar_lib.commands.infra.load_config", return_value=config),
                mock.patch(
                    "scripts.gar_lib.commands.infra._run_terraform",
                    side_effect=[completed, completed, completed, completed],
                ) as run_tf,
            ):
                result = run_sim_infra_command("setup", ssh_cidr="203.0.113.4/32")

        self.assertEqual(0, result)
        self.assertEqual(
            ["workspace", "select", "-or-create=true", "gar-ws_abc123"],
            run_tf.call_args_list[1].args[0],
        )

    def test_aws_login_credentials_are_injected_only_into_the_child_environment(self) -> None:
        credentials = {
            "Version": 1,
            "AccessKeyId": "ASIAEXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
        }
        with (
            mock.patch("scripts.gar_lib.commands.infra.shutil.which", return_value="/usr/bin/aws"),
            mock.patch(
                "scripts.gar_lib.commands.infra.subprocess.run",
                return_value=mock.Mock(returncode=0, stdout=json.dumps(credentials)),
            ),
        ):
            from scripts.gar_lib.commands.infra import _inject_aws_cli_credentials

            env: dict[str, str] = {}
            result = _inject_aws_cli_credentials(env)

        self.assertTrue(result)
        self.assertEqual("ASIAEXAMPLE", env["AWS_ACCESS_KEY_ID"])
        self.assertEqual("secret", env["AWS_SECRET_ACCESS_KEY"])
        self.assertEqual("token", env["AWS_SESSION_TOKEN"])

    def test_infra_requires_an_explicit_ssh_cidr(self) -> None:
        with mock.patch("scripts.gar_lib.commands.infra._terraform_available", return_value=True):
            result = run_sim_infra_command("setup", region="ap-test-1")

        self.assertEqual(1, result)

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
