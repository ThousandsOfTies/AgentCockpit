"""`gar sim infra`: Terraform-backed simulation host management."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.gar_lib.core.config import (
    PROJECT_ROOT,
    default_ec2_host,
    default_ec2_instance_id,
    default_ec2_region,
    load_config,
    save_config,
    set_default_ec2_instance_id,
    set_default_ec2_region,
)
from scripts.gar_lib.simulation.host.ssh_config import SshConfigHostAddressUpdater

TERRAFORM_DIR = PROJECT_ROOT / "infra" / "terraform"


def _terraform_available() -> bool:
    return shutil.which("terraform") is not None


def _run_terraform(args: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["terraform", *args],
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _terraform_env(
    region: str | None,
    key_name: str | None,
    ssh_cidr: str | None,
) -> dict[str, str]:
    env = os.environ.copy()
    if region:
        env["TF_VAR_aws_region"] = region
        # AWS CLI's console-login credential exporter also needs an explicit
        # region; the Terraform provider receives its region through TF_VAR.
        env["AWS_REGION"] = region
    if key_name:
        env["TF_VAR_key_name"] = key_name
    if ssh_cidr:
        env["TF_VAR_ssh_ingress_cidr"] = ssh_cidr
    return env


def _inject_aws_cli_credentials(env: dict[str, str]) -> bool:
    """Bridge ``aws login`` credentials to Terraform without persisting secrets.

    AWS CLI's console-login cache is understood by the CLI but not by the AWS
    Terraform provider.  ``export-credentials --format process`` refreshes the
    short-lived CLI credentials and returns the standard credential fields.  We
    pass them only to the Terraform child process environment.
    """

    if env.get("AWS_ACCESS_KEY_ID") and env.get("AWS_SECRET_ACCESS_KEY"):
        return True

    aws = shutil.which("aws")
    if aws is None:
        print("gar sim infra: AWS CLIが見つかりません。aws loginを実行できません。", file=sys.stderr)
        return False

    result = subprocess.run(
        [aws, "configure", "export-credentials", "--format", "process"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        print(
            "gar sim infra: AWS認証情報を取得できません。"
            "`aws login --remote --region <region>` を実行してから再試行してください。",
            file=sys.stderr,
        )
        return False

    try:
        credentials = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("gar sim infra: AWS CLIの認証情報形式を解析できません。", file=sys.stderr)
        return False

    fields = {
        "AWS_ACCESS_KEY_ID": credentials.get("AccessKeyId"),
        "AWS_SECRET_ACCESS_KEY": credentials.get("SecretAccessKey"),
        "AWS_SESSION_TOKEN": credentials.get("SessionToken"),
    }
    if not all(isinstance(value, str) and value for value in fields.values()):
        print("gar sim infra: AWS CLIから有効な一時認証情報を取得できません。", file=sys.stderr)
        return False
    env.update(fields)
    return True


def _print_completed(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)


def _terraform_init(env: dict[str, str]) -> bool:
    result = _run_terraform(["init", "-input=false"], cwd=TERRAFORM_DIR, env=env)
    _print_completed(result)
    return result.returncode == 0


def _terraform_workspace_name(config: dict) -> str:
    """Return a Terraform workspace isolated to one GAR product workspace."""

    workspace_id = config.get("workspace_id")
    if not isinstance(workspace_id, str) or not workspace_id:
        return "default"
    return re.sub(r"[^0-9A-Za-z_-]", "-", f"gar-{workspace_id}")


def _terraform_select_workspace(env: dict[str, str], config: dict) -> bool:
    """Select or create the Terraform state namespace for the active product."""

    workspace = _terraform_workspace_name(config)
    result = _run_terraform(
        ["workspace", "select", "-or-create=true", workspace],
        cwd=TERRAFORM_DIR,
        env=env,
    )
    _print_completed(result)
    return result.returncode == 0


def _terraform_output_json(env: dict[str, str], *, quiet: bool = False) -> dict[str, str]:
    result = _run_terraform(["output", "-json"], cwd=TERRAFORM_DIR, env=env)
    if result.returncode != 0:
        if not quiet:
            _print_completed(result)
        return {}
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"gar sim infra: terraform output -json の解析に失敗しました: {exc}", file=sys.stderr)
        return {}

    values: dict[str, str] = {}
    if isinstance(raw, dict):
        for key, item in raw.items():
            if isinstance(item, dict) and isinstance(item.get("value"), str):
                values[key] = item["value"]
    return values


def _sync_config_from_outputs(config: dict, outputs: dict[str, str], *, region: str | None) -> None:
    instance_id = outputs.get("instance_id")
    public_ip = outputs.get("public_ip")
    if not instance_id and not public_ip:
        return

    if instance_id:
        set_default_ec2_instance_id(config, instance_id)
    if region:
        set_default_ec2_region(config, region)
    save_config(config)

    if public_ip:
        host = default_ec2_host(config)
        if host is None:
            print(
                "gar sim infra: public IPは取得しましたがSSH hostが未設定です。"
                "`gar setup --ec2-host HOST` を実行してください。",
                file=sys.stderr,
            )
        elif SshConfigHostAddressUpdater().update(host, public_ip):
            print(f"gar sim infra: SSH config の Host {host} を {public_ip} に更新しました。")


def _print_current_settings(config: dict, outputs: dict[str, str], *, region: str) -> None:
    print("Current simulation infra settings:")
    print(f"  host       : {default_ec2_host(config) or '(none)'}")
    print(f"  region     : {region}")
    print(f"  instance_id: {outputs.get('instance_id') or default_ec2_instance_id(config) or '(none)'}")
    print(f"  public_ip  : {outputs.get('public_ip') or '(none)'}")


def run_sim_infra_command(
    command: str,
    *,
    key_name: str | None = None,
    region: str | None = None,
    ssh_cidr: str | None = None,
    auto_approve: bool = False,
) -> int:
    if not TERRAFORM_DIR.exists():
        print(f"gar sim infra: Terraform dir が見つかりません: {TERRAFORM_DIR}", file=sys.stderr)
        return 1
    if not _terraform_available():
        print("gar sim infra: terraform が見つかりません。Terraform を install してください。", file=sys.stderr)
        return 1

    config = load_config()
    resolved_region = region or default_ec2_region(config)
    if not resolved_region:
        print("gar sim infra: region が未設定です。--region を指定してください。", file=sys.stderr)
        return 1
    if ssh_cidr is None:
        print(
            "gar sim infra: SSH公開範囲を `--ssh-cidr <接続元IP>/32` で指定してください。",
            file=sys.stderr,
        )
        return 1

    env = _terraform_env(resolved_region, key_name, ssh_cidr)
    if not _inject_aws_cli_credentials(env):
        return 1

    if not _terraform_init(env):
        return 1
    if not _terraform_select_workspace(env, config):
        return 1

    if command == "setup":
        _print_current_settings(config, _terraform_output_json(env, quiet=True), region=resolved_region)
        args = ["plan", "-input=false"]
    elif command == "apply":
        args = ["apply", "-input=false"]
        if auto_approve:
            args.append("-auto-approve")
    elif command == "destroy":
        args = ["destroy", "-input=false"]
        if auto_approve:
            args.append("-auto-approve")
    else:
        print(f"unknown sim infra command: {command}", file=sys.stderr)
        return 1

    result = _run_terraform(args, cwd=TERRAFORM_DIR, env=env)
    _print_completed(result)
    if result.returncode != 0:
        return result.returncode

    if command == "apply":
        outputs = _terraform_output_json(env)
        _sync_config_from_outputs(config, outputs, region=resolved_region)

    return 0
