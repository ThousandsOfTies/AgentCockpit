#!/usr/bin/env python3
"""Collect approved, read-only evidence from pre-provisioned physical Targets."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SAFE_ALIAS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
TARGETS = {
    "tx": ("Local/GarStreamTx", "raspberry-pi-5", "gar-stream-tx"),
    "rx": ("Local/GarStreamRx", "luckfox-rk3506", "gar-stream-rx"),
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--approval-ref", required=True)
    parser.add_argument("--gar-root", type=Path, required=True)
    parser.add_argument("--tx-root", type=Path, required=True)
    parser.add_argument("--rx-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(value)
        if value and not value.endswith("\n"):
            output.write("\n")


def runtime_config(raw: str, tx_root: Path, rx_root: Path) -> tuple[dict[str, Any], dict[str, str], set[str]]:
    value = json.loads(raw)
    if not isinstance(value, dict) or not isinstance(value.get("workspaces"), list):
        raise ValueError("GAR HIL config requires a workspaces array")
    roots = {"Local/GarStreamTx": tx_root, "Local/GarStreamRx": rx_root}
    expected_targets = {item[0]: item[1] for item in TARGETS.values()}
    hosts: dict[str, str] = {}
    sensitive: set[str] = set()
    for item in value["workspaces"]:
        if not isinstance(item, dict) or item.get("name") not in roots:
            continue
        name = str(item["name"])
        if name in hosts:
            raise ValueError(f"GAR HIL config has duplicate workspace: {name}")
        if item.get("selected_target") != expected_targets[name]:
            raise ValueError(f"GAR HIL config selects the wrong physical Target: {name}")
        selected = item.get("selected_environments")
        if not isinstance(selected, dict) or selected.get("target") != "ssh_scp":
            raise ValueError(f"GAR HIL config requires ssh_scp Target access: {name}")
        target = item.get("target")
        host = target.get("host") if isinstance(target, dict) else None
        if not isinstance(host, str) or not SAFE_ALIAS.fullmatch(host):
            raise ValueError(f"physical Target host must be a safe SSH alias: {name}")
        item["connection"] = {"type": "local", "path": str(roots[name].resolve())}
        hosts[name] = host
        sensitive.add(host)
        for section_name in ("target", "ec2"):
            section = item.get(section_name)
            if isinstance(section, dict):
                for field in ("host", "private_ip", "instance_id"):
                    field_value = section.get(field)
                    if isinstance(field_value, str) and field_value:
                        sensitive.add(field_value)
    if set(hosts) != set(roots):
        raise ValueError("GAR HIL config is missing a required physical Target workspace")
    if len(set(hosts.values())) != 2:
        raise ValueError("TX and RX must use distinct physical Target aliases")
    return value, hosts, sensitive


def require_pinned_hosts(hosts: dict[str, str]) -> None:
    known_hosts = Path.home() / ".ssh" / "known_hosts"
    if not known_hosts.is_file():
        raise ValueError("self-hosted HIL runner has no pinned known_hosts file")
    for alias in hosts.values():
        result = subprocess.run(
            ("ssh-keygen", "-F", alias, "-f", str(known_hosts)),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode:
            raise ValueError("self-hosted HIL runner is missing a pinned Target host alias")


def redact(value: object, sensitive: set[str]) -> object:
    if isinstance(value, str):
        result = value
        for secret in sorted((item for item in sensitive if item), key=len, reverse=True):
            result = result.replace(secret, "[REDACTED]")
        return result
    if isinstance(value, list):
        return [redact(item, sensitive) for item in value]
    if isinstance(value, dict):
        return {str(key): redact(item, sensitive) for key, item in value.items()}
    return value


def command_json(command: tuple[str, ...], *, cwd: Path, environment: dict[str, str]) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=5 * 60,
    )
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        value = {
            "schema_version": 1,
            "command": f"target.{command[2]}" if len(command) > 2 else "target.unknown",
            "ok": False,
            "error": f"GAR did not return JSON: {error.msg}",
        }
    if not isinstance(value, dict):
        value = {"schema_version": 1, "ok": False, "error": "GAR returned non-object JSON"}
    return completed.returncode, value


def failure_evidence(output: Path, args: argparse.Namespace, reason: str) -> int:
    output.mkdir(parents=True, exist_ok=True)
    record = {
        "schema_version": 1,
        "kind": "garstream-physical-hil-read-only",
        "status": "failed",
        "event": args.event,
        "approval_ref": args.approval_ref,
        "coverage": "target-preflight-and-diag",
        "full_golden_scenario_executed": False,
        "full_golden_scenario_status": "not-implemented-with-a-physical-adapter",
        "physical_target_deploy_performed": False,
        "reason": reason,
        "targets": [],
    }
    (output / "hil-record.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (output / "hil-read-only.log").write_text(f"status=failed\nreason={reason}\n", encoding="utf-8")
    return 1


def main() -> int:
    args = arguments()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    raw_config = os.environ.get("GARSTREAM_HIL_CONFIG_JSON", "")
    artifact_source_raw = os.environ.get("GARSTREAM_HIL_ARTIFACTS_DIR", "")
    if not raw_config or not artifact_source_raw:
        return failure_evidence(output, args, "required protected HIL configuration is unavailable")
    if not args.approval_ref.strip():
        return failure_evidence(output, args, "approval_ref is required")

    gar_root = args.gar_root.resolve()
    config_path = gar_root / ".gar" / "config.json"
    artifact_root = gar_root / ".gar" / "artifacts"
    artifact_source = Path(artifact_source_raw).expanduser().resolve()
    backup_root = gar_root / ".gar" / f"artifacts.workflow-backup-{os.getpid()}"
    config_existed = config_path.is_file()
    original_config = config_path.read_bytes() if config_existed else None
    artifact_existed = artifact_root.exists()
    artifact_backup_moved = False
    artifact_copy_started = False
    sensitive = {artifact_source_raw, str(artifact_source)}
    try:
        config, hosts, config_sensitive = runtime_config(
            raw_config,
            args.tx_root.resolve(),
            args.rx_root.resolve(),
        )
        sensitive.update(config_sensitive)
        require_pinned_hosts(hosts)
        resolved_artifact_root = artifact_root.resolve(strict=False)
        if (
            not artifact_source.is_dir()
            or artifact_source == resolved_artifact_root
            or artifact_source.is_relative_to(resolved_artifact_root)
            or resolved_artifact_root.is_relative_to(artifact_source)
        ):
            raise ValueError("pre-provisioned HIL artifact snapshot directory is unavailable")
        write_private(config_path, json.dumps(config, ensure_ascii=False, indent=2))
        if artifact_existed:
            if backup_root.exists():
                raise ValueError("temporary HIL artifact backup path already exists")
            artifact_root.rename(backup_root)
            artifact_backup_moved = True
        artifact_copy_started = True
        shutil.copytree(artifact_source, artifact_root, symlinks=False)

        environment = os.environ.copy()
        environment.pop("GARSTREAM_HIL_CONFIG_JSON", None)
        environment.pop("GARSTREAM_HIL_ARTIFACTS_DIR", None)
        environment["GAR_TOOLS_ROOT"] = str(args.tx_root.resolve() / "sources" / "gar-tools")
        results: dict[str, dict[str, Any]] = {}
        return_codes: dict[str, int] = {}
        for node, (workspace, _target_id, application) in TARGETS.items():
            for action in ("preflight", "diag"):
                key = f"{node}-{action}"
                code, payload = command_json(
                    (
                        str(gar_root / "scripts" / "gar"),
                        "target",
                        action,
                        "--workspace",
                        workspace,
                        "--app",
                        application,
                        "--json",
                    ),
                    cwd=gar_root,
                    environment=environment,
                )
                sanitized = redact(payload, sensitive)
                assert isinstance(sanitized, dict)
                results[key] = sanitized
                return_codes[key] = code
                (output / f"{key}.json").write_text(
                    json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )

        targets: list[dict[str, object]] = []
        for node, (_workspace, target_id, application) in TARGETS.items():
            preflight = results[f"{node}-preflight"]
            diagnostic = results[f"{node}-diag"]
            artifact = diagnostic.get("artifact")
            targets.append(
                {
                    "node": node,
                    "target_id": target_id,
                    "application": application,
                    "preflight_ok": preflight.get("ok") is True,
                    "compatible": preflight.get("compatible") is True,
                    "artifact_build_id": preflight.get("build_id"),
                    "diagnostic_ok": diagnostic.get("ok") is True,
                    "status": diagnostic.get("status"),
                    "health": diagnostic.get("health"),
                    "expected_build_id": artifact.get("expected_build_id") if isinstance(artifact, dict) else None,
                    "running_build_id": artifact.get("running_build_id") if isinstance(artifact, dict) else None,
                    "build_matches": artifact.get("matches") if isinstance(artifact, dict) else None,
                }
            )
        ok = all(code == 0 for code in return_codes.values()) and all(
            result.get("ok") is True for result in results.values()
        )
        record = {
            "schema_version": 1,
            "kind": "garstream-physical-hil-read-only",
            "status": "passed" if ok else "failed",
            "event": args.event,
            "approval_ref": args.approval_ref,
            "observed_at": datetime.now(UTC).isoformat(),
            "coverage": "target-preflight-and-diag",
            "full_golden_scenario_executed": False,
            "full_golden_scenario_status": "not-implemented-with-a-physical-adapter",
            "physical_target_deploy_performed": False,
            "targets": targets,
        }
        (output / "hil-record.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (output / "hil-read-only.log").write_text(
            f"status={record['status']}\ncoverage=target-preflight-and-diag\n",
            encoding="utf-8",
        )
        return 0 if ok else 1
    except Exception as error:
        reason = redact(f"HIL read-only collection failed: {type(error).__name__}: {error}", sensitive)
        return failure_evidence(output, args, str(reason))
    finally:
        try:
            if artifact_copy_started and artifact_root.exists():
                shutil.rmtree(artifact_root)
            if artifact_backup_moved and backup_root.exists():
                backup_root.rename(artifact_root)
        except OSError:
            pass
        try:
            if config_existed and original_config is not None:
                write_private(config_path, original_config.decode("utf-8"))
            else:
                config_path.unlink(missing_ok=True)
        except (OSError, UnicodeError):
            pass


if __name__ == "__main__":
    sys.exit(main())
