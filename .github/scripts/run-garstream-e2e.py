#!/usr/bin/env python3
"""Execute the GarStream Golden scenario on pre-provisioned simulation EC2.

The runner creates an ephemeral, host-key-pinned SSH home for GAR's existing
``ssh_remote`` SimulationRuntime and forwards each remote loopback Bridge to a
distinct runner-local port.  It never builds, deploys, or contacts a physical
Target.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SAFE_ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
ALLOWED_SSH_DIRECTIVES = frozenset(
    {
        "host",
        "hostname",
        "user",
        "port",
        "proxyjump",
        "connecttimeout",
        "serveraliveinterval",
        "serveralivecountmax",
    }
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("ec2",), required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--gar-root", type=Path, required=True)
    parser.add_argument("--tx-root", type=Path, required=True)
    parser.add_argument("--rx-root", type=Path, required=True)
    parser.add_argument("--system-file", type=Path, required=True)
    parser.add_argument("--scenario-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--approval-ref", default="")
    return parser.parse_args()


def write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(value)
        if value and not value.endswith("\n"):
            output.write("\n")


def load_runtime_config(raw: str, tx_root: Path, rx_root: Path) -> tuple[dict[str, Any], dict[str, str]]:
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("workspaces"), list):
        raise ValueError("GAR runtime config requires a workspaces array")
    expected = {"Local/GarStreamTx": tx_root, "Local/GarStreamRx": rx_root}
    hosts: dict[str, str] = {}
    found: set[str] = set()
    for item in value["workspaces"]:
        if not isinstance(item, dict) or item.get("name") not in expected:
            continue
        name = str(item["name"])
        if name in found:
            raise ValueError(f"GAR runtime config has duplicate workspace: {name}")
        found.add(name)
        item["connection"] = {"type": "local", "path": str(expected[name].resolve())}
        selected = item.get("selected_environments")
        if not isinstance(selected, dict) or selected.get("simulator") != "ssh_remote":
            raise ValueError(f"EC2 E2E requires ssh_remote SimulationRuntime: {name}")
        ec2 = item.get("ec2")
        host = ec2.get("host") if isinstance(ec2, dict) else None
        if not isinstance(host, str) or not SAFE_ALIAS.fullmatch(host):
            raise ValueError(f"runtime host must be a safe SSH config alias: {name}")
        hosts[name] = host
    missing = set(expected) - found
    if missing:
        raise ValueError("GAR runtime config is missing required product workspaces")
    return value, hosts


def validate_topology_is_simulation(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    nodes = value.get("nodes") if isinstance(value, dict) else None
    if (
        not isinstance(nodes, list)
        or not nodes
        or any(not isinstance(node, dict) or node.get("environment") != "sim" for node in nodes)
    ):
        raise ValueError("Golden E2E may control pre-provisioned simulation nodes only")


def prepare_ssh_home(
    home: Path,
    aliases: list[str],
    *,
    ssh_config: str,
    private_key: str,
    known_hosts: str,
) -> None:
    if shutil.which("ssh-keygen") is None:
        raise ValueError("ssh-keygen is required for host-key pin validation")
    explicit_aliases: set[str] = set()
    for line in ssh_config.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        directive, _, setting = stripped.partition(" ")
        if directive.lower() not in ALLOWED_SSH_DIRECTIVES or not setting.strip():
            raise ValueError(f"unsupported directive in restricted EC2 SSH config: {directive}")
        if directive.lower() == "host":
            names = setting.split()
            if any(not SAFE_ALIAS.fullmatch(name) for name in names):
                raise ValueError("EC2 SSH config Host entries must be explicit aliases")
            explicit_aliases.update(names)
    if not set(aliases) <= explicit_aliases:
        raise ValueError("EC2 SSH config does not explicitly declare every runtime alias")

    ssh_dir = home / ".ssh"
    key_path = ssh_dir / "garstream_ci"
    known_hosts_path = ssh_dir / "known_hosts"
    config_path = ssh_dir / "config"
    write_private(key_path, private_key)
    write_private(known_hosts_path, known_hosts)
    safe_prefix = (
        "Host *\n"
        f"  IdentityFile {key_path}\n"
        f"  UserKnownHostsFile {known_hosts_path}\n"
        "  GlobalKnownHostsFile /dev/null\n"
        "  StrictHostKeyChecking yes\n"
        "  IdentitiesOnly yes\n"
        "  BatchMode yes\n"
        "  LogLevel ERROR\n"
    )
    write_private(config_path, safe_prefix + ssh_config)
    for alias in aliases:
        lookup = subprocess.run(
            ("ssh-keygen", "-F", alias, "-f", str(known_hosts_path)),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if lookup.returncode:
            raise ValueError("pinned known_hosts entry is missing for a runtime alias")


def bridge_port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as error:
        raise ValueError("remote Bridge port must be an integer") from error
    if not 1 <= port <= 65535:
        raise ValueError("remote Bridge port is outside 1..65535")
    return port


def reserve_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def open_bridge_tunnel(
    *,
    home: Path,
    alias: str,
    remote_port: int,
    environment: dict[str, str],
) -> tuple[subprocess.Popen[bytes], str]:
    local_port = reserve_local_port()
    process = subprocess.Popen(
        (
            "ssh",
            "-F",
            str(home / ".ssh" / "config"),
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            f"HostKeyAlias={alias}",
            "-N",
            "-L",
            f"127.0.0.1:{local_port}:127.0.0.1:{remote_port}",
            alias,
        ),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=environment,
    )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ValueError("SSH Bridge tunnel exited during startup")
        try:
            with socket.create_connection(("127.0.0.1", local_port), timeout=0.2):
                return process, f"http://127.0.0.1:{local_port}"
        except OSError:
            time.sleep(0.1)
    process.terminate()
    process.wait(timeout=5)
    raise ValueError("SSH Bridge tunnel did not become ready")


def git_commit(root: Path) -> str | None:
    result = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) else None


def redact(value: object, secrets: set[str]) -> object:
    if isinstance(value, str):
        result = value
        for secret in sorted((item for item in secrets if item), key=len, reverse=True):
            result = result.replace(secret, "[REDACTED]")
        return result
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, dict):
        return {str(key): redact(item, secrets) for key, item in value.items()}
    return value


def config_secrets(config: dict[str, Any], aliases: list[str]) -> set[str]:
    values = set(aliases)
    for item in config.get("workspaces", []):
        if not isinstance(item, dict):
            continue
        ec2 = item.get("ec2")
        if not isinstance(ec2, dict):
            continue
        for name in ("host", "private_ip", "instance_id"):
            value = ec2.get(name)
            if isinstance(value, str) and value:
                values.add(value)
    return values


def artifact_evidence(payload: dict[str, Any]) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        return evidence
    for node in nodes:
        if not isinstance(node, dict):
            continue
        artifacts = node.get("artifacts")
        evidence.append(
            {
                "node": node.get("id"),
                "artifacts": artifacts if isinstance(artifacts, list) else [],
            }
        )
    return evidence


def emit_without_run(
    output: Path,
    *,
    mode: str,
    event: str,
    status: str,
    reason: str,
    approval_ref: str,
) -> None:
    canonical = {
        "schema_version": 1,
        "command": "system.test",
        "ok": False,
        "exit_code": 0 if status == "skipped" else 1,
        "error": reason,
    }
    record = {
        "schema_version": 1,
        "kind": f"garstream-{mode}-e2e",
        "status": status,
        "event": event,
        "approval_ref": approval_ref or None,
        "pre_provisioned": True,
        "physical_target_deploy_performed": False,
        "system_test_executed": False,
        "reason": reason,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "system-test.json").write_text(json.dumps(canonical, indent=2) + "\n", encoding="utf-8")
    (output / "run-record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (output / "system-test.log").write_text(f"status={status}\nreason={reason}\n", encoding="utf-8")


def main() -> int:
    args = arguments()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    prefix = "GARSTREAM_EC2"
    names = {
        "config": f"{prefix}_CONFIG_JSON",
        "tx_bridge_port": f"{prefix}_TX_BRIDGE_PORT",
        "rx_bridge_port": f"{prefix}_RX_BRIDGE_PORT",
    }
    names.update(
        {
            "ssh_config": "GARSTREAM_EC2_SSH_CONFIG",
            "ssh_key": "GARSTREAM_EC2_SSH_KEY",
            "known_hosts": "GARSTREAM_EC2_KNOWN_HOSTS",
        }
    )
    missing = [name for name in names.values() if not os.environ.get(name)]
    if missing:
        status = "skipped"
        emit_without_run(
            output,
            mode=args.mode,
            event=args.event,
            status=status,
            reason="required protected configuration is unavailable",
            approval_ref=args.approval_ref,
        )
        return 0

    temporary: tempfile.TemporaryDirectory[str] | None = None
    tunnels: list[subprocess.Popen[bytes]] = []
    original_config: bytes | None = None
    config_existed = False
    try:
        validate_topology_is_simulation(args.system_file.resolve())
        raw_config = os.environ[names["config"]]
        config, hosts = load_runtime_config(
            raw_config,
            args.tx_root.resolve(),
            args.rx_root.resolve(),
        )
        aliases = list(hosts.values())
        if len(set(aliases)) != 2:
            raise ValueError("TX and RX must use distinct simulation SSH aliases")
        remote_ports = {
            "Local/GarStreamTx": bridge_port(os.environ[names["tx_bridge_port"]]),
            "Local/GarStreamRx": bridge_port(os.environ[names["rx_bridge_port"]]),
        }
        secrets = config_secrets(config, aliases)

        gar_root = args.gar_root.resolve()
        config_path = gar_root / ".gar" / "config.json"
        config_existed = config_path.is_file()
        original_config = config_path.read_bytes() if config_existed else None
        write_private(config_path, json.dumps(config, ensure_ascii=False, indent=2))
        command_env = os.environ.copy()
        for environment_name in names.values():
            command_env.pop(environment_name, None)
        temporary = tempfile.TemporaryDirectory(prefix="garstream-e2e-home-")
        isolated_home = Path(temporary.name)
        prepare_ssh_home(
            isolated_home,
            aliases,
            ssh_config=os.environ[names["ssh_config"]],
            private_key=os.environ[names["ssh_key"]],
            known_hosts=os.environ[names["known_hosts"]],
        )
        command_env["HOME"] = str(isolated_home)
        tx_tunnel, tx_bridge = open_bridge_tunnel(
            home=isolated_home,
            alias=hosts["Local/GarStreamTx"],
            remote_port=remote_ports["Local/GarStreamTx"],
            environment=command_env,
        )
        tunnels.append(tx_tunnel)
        rx_tunnel, rx_bridge = open_bridge_tunnel(
            home=isolated_home,
            alias=hosts["Local/GarStreamRx"],
            remote_port=remote_ports["Local/GarStreamRx"],
            environment=command_env,
        )
        tunnels.append(rx_tunnel)

        command = (
            str(gar_root / "scripts" / "gar"),
            "system",
            "test",
            "--file",
            str(args.system_file.resolve()),
            "--scenario",
            str(args.scenario_file.resolve()),
            "--bridge",
            f"tx={tx_bridge}",
            "--bridge",
            f"rx={rx_bridge}",
            "--json",
        )
        started = datetime.now(UTC).isoformat()
        completed = subprocess.run(
            command,
            cwd=gar_root,
            env=command_env,
            check=False,
            capture_output=True,
            text=True,
            timeout=35 * 60,
        )
        try:
            raw_payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raw_payload = {
                "schema_version": 1,
                "command": "system.test",
                "ok": False,
                "exit_code": completed.returncode or 1,
                "error": f"GAR did not return its canonical JSON contract: {error.msg}",
            }
        if not isinstance(raw_payload, dict):
            raw_payload = {
                "schema_version": 1,
                "command": "system.test",
                "ok": False,
                "exit_code": completed.returncode or 1,
                "error": "GAR system test returned a non-object JSON value",
            }
        payload = redact(raw_payload, secrets)
        assert isinstance(payload, dict)
        ok = completed.returncode == 0 and payload.get("ok") is True
        status = "passed" if ok else "failed"
        scenario = payload.get("scenario")
        metrics = scenario.get("metrics") if isinstance(scenario, dict) else {}
        record = {
            "schema_version": 1,
            "kind": f"garstream-{args.mode}-e2e",
            "status": status,
            "event": args.event,
            "approval_ref": args.approval_ref or None,
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "pre_provisioned": True,
            "simulation_runtime_ssh_used": True,
            "physical_target_deploy_performed": False,
            "system_test_executed": True,
            "exit_code": completed.returncode,
            "repository_builds": {
                "gar": git_commit(gar_root),
                "tx": git_commit(args.tx_root.resolve()),
                "rx": git_commit(args.rx_root.resolve()),
            },
            "artifact_builds": artifact_evidence(payload),
            "metrics": metrics if isinstance(metrics, dict) else {},
            "passed": ok,
        }
        sanitized_stderr = redact(completed.stderr, secrets)
        (output / "system-test.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (output / "run-record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (output / "system-test.log").write_text(
            f"status={status}\nexit_code={completed.returncode}\n"
            + (str(sanitized_stderr).rstrip() + "\n" if sanitized_stderr else ""),
            encoding="utf-8",
        )
        return 0 if ok else 1
    except subprocess.TimeoutExpired:
        emit_without_run(
            output,
            mode=args.mode,
            event=args.event,
            status="failed",
            reason="GAR system test exceeded the workflow timeout",
            approval_ref=args.approval_ref,
        )
        return 1
    except Exception as error:
        emit_without_run(
            output,
            mode=args.mode,
            event=args.event,
            status="failed",
            reason=f"E2E preflight failed: {type(error).__name__}: {error}",
            approval_ref=args.approval_ref,
        )
        return 1
    finally:
        config_path = args.gar_root.resolve() / ".gar" / "config.json"
        try:
            if config_existed and original_config is not None:
                write_private(config_path, original_config.decode("utf-8"))
            else:
                config_path.unlink(missing_ok=True)
        except OSError:
            pass
        for tunnel in reversed(tunnels):
            if tunnel.poll() is None:
                tunnel.terminate()
                try:
                    tunnel.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    tunnel.kill()
                    tunnel.wait(timeout=5)
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
