#!/usr/bin/env python3
"""Run product-parent CI checks through GAR's canonical contracts.

The product hooks create mutable staging bundles.  This helper asks GAR's
``LocalArtifactStore`` to capture those bundles, which is the production path
that creates schema-v2 metadata and checksums.  It then validates the captured
artifacts, the selected Target, the product hardware contract, and the shared
system/scenario documents without contacting a simulation host or Target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gar-root", type=Path, required=True)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--sim-bundle", type=Path, required=True)
    parser.add_argument("--target-bundle", type=Path, required=True)
    parser.add_argument("--sim-target", required=True)
    parser.add_argument("--sim-architecture", required=True)
    parser.add_argument("--sim-abi", required=True)
    parser.add_argument("--sim-toolchain", required=True)
    parser.add_argument("--sim-payload", choices=("elf", "python"), required=True)
    parser.add_argument("--sim-entry", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--target-architecture", required=True)
    parser.add_argument("--target-abi", required=True)
    parser.add_argument("--target-toolchain", required=True)
    parser.add_argument("--target-payload", choices=("elf", "python"), required=True)
    parser.add_argument("--target-entry", type=Path, required=True)
    parser.add_argument("--target-build-mode", choices=("production", "ci-contract-stub"), required=True)
    parser.add_argument("--system-file", type=Path, required=True)
    parser.add_argument("--scenario-file", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def git_commit(root: Path) -> str:
    result = subprocess.run(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        check=False,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if result.returncode or not COMMIT.fullmatch(value):
        raise ValueError(f"cannot resolve repository commit: {root}")
    return value


def target_contract(product_root: Path, target_id: str) -> tuple[dict[str, str], str]:
    target_root = product_root / "sources" / "gar-tools" / "targets" / target_id
    manifest_path = target_root / "target.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("id") != target_id:
        raise ValueError(f"invalid Target manifest identity: {manifest_path}")
    compatibility = raw.get("compatibility")
    values = compatibility if isinstance(compatibility, dict) else {}
    declared = {
        "architecture": str(values.get("architecture") or ""),
        "abi": str(values.get("abi") or ""),
        "libc": str(values.get("libc") or ""),
        "toolchain_triple": str(values.get("toolchainTriple") or ""),
    }
    provisioning = raw.get("provisioning")
    ssh_recipe = provisioning.get("ssh_scp") if isinstance(provisioning, dict) else None
    version = ssh_recipe.get("recipeVersion") if isinstance(ssh_recipe, dict) else None
    if isinstance(version, int) and not isinstance(version, bool) and version > 0:
        recipe = str(version)
    else:
        digest = hashlib.sha256()
        for path in sorted(item for item in target_root.rglob("*") if item.is_file() and not item.is_symlink()):
            digest.update(path.relative_to(target_root).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        recipe = f"sha256:{digest.hexdigest()}"
    return declared, recipe


def elf_architecture(path: Path) -> tuple[str, str | None]:
    data = path.read_bytes()[:64]
    if len(data) < 40 or data[:4] != b"\x7fELF":
        raise ValueError(f"ELF executable required: {path}")
    elf_class, encoding = data[4], data[5]
    if encoding not in (1, 2):
        raise ValueError(f"unsupported ELF byte order: {path}")
    endian = "<" if encoding == 1 else ">"
    machine = struct.unpack_from(f"{endian}H", data, 18)[0]
    if machine == 183 and elf_class == 2:
        return "aarch64", None
    if machine == 40 and elf_class == 1:
        flags = struct.unpack_from(f"{endian}I", data, 36)[0]
        return "armv7l", "gnueabihf" if flags & 0x400 else "gnueabi"
    raise ValueError(f"unsupported ELF machine/class ({machine}/{elf_class}): {path}")


def validate_payload(bundle: Path, entry: Path, payload: str, architecture: str, abi: str) -> dict[str, object]:
    path = bundle / entry
    if payload == "elf":
        actual_architecture, actual_abi = elf_architecture(path)
        if actual_architecture != architecture:
            raise ValueError(f"payload architecture mismatch: expected={architecture}, actual={actual_architecture}")
        if architecture == "armv7l" and actual_abi != abi:
            raise ValueError(f"payload ABI mismatch: expected={abi}, actual={actual_abi}")
        return {"path": str(path), "format": "elf", "architecture": actual_architecture, "abi": actual_abi}
    sources = sorted(path.rglob("*.py")) if path.is_dir() else ([path] if path.suffix == ".py" else [])
    if not sources:
        raise ValueError(f"Python application sources are missing: {path}")
    compiled = sorted(path.rglob("*.pyc")) if path.is_dir() else []
    return {
        "path": str(path),
        "format": "python-source",
        "architecture": "portable",
        "deployment_architecture": architecture,
        "source_files": len(sources),
        "compiled_files": len(compiled),
    }


class Checks:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, object]] = {}

    def run(self, name: str, operation: Callable[[], object]) -> object | None:
        try:
            detail = operation()
            self.values[name] = {"ok": True, "detail": detail}
            return detail
        except Exception as error:  # each contract gets an independent report entry
            self.values[name] = {
                "ok": False,
                "error": str(error),
                "exception": type(error).__name__,
            }
            return None

    @property
    def ok(self) -> bool:
        return bool(self.values) and all(bool(value["ok"]) for value in self.values.values())


def main() -> int:
    args = parse_args()
    gar_root = args.gar_root.resolve()
    product_root = args.product_root.resolve()
    sim_bundle = (product_root / args.sim_bundle).resolve()
    target_bundle = (product_root / args.target_bundle).resolve()
    system_file = args.system_file.resolve()
    scenario_file = args.scenario_file.resolve()
    report_path = (product_root / args.report).resolve()
    sys.path.insert(0, str(gar_root))

    from scripts.gar_lib.artifacts.manifest import load_artifact_manifest
    from scripts.gar_lib.artifacts.metadata import (
        CURRENT_SCHEMA_VERSION,
        ArtifactTarget,
        load_artifact_metadata,
        verify_artifact_checksums,
    )
    from scripts.gar_lib.artifacts.provenance import CaptureProvenance, TargetToolsProvenance
    from scripts.gar_lib.artifacts.store import LocalArtifactStore
    from scripts.gar_lib.core.artifact import ArtifactKind
    from scripts.gar_lib.core.hardware_validation import validate_hardware_contract
    from scripts.gar_lib.core.workspace import Workspace
    from scripts.gar_lib.system.model import load_topology
    from scripts.gar_lib.system.scenario import load_scenario
    from scripts.gar_lib.target.compatibility import TargetCapabilities, check_target_compatibility

    checks = Checks()
    source_commit = checks.run("source_commit", lambda: git_commit(product_root))
    tools_root = product_root / "sources" / "gar-tools"
    tools_commit = checks.run("gar_tools_commit", lambda: git_commit(tools_root))

    def manifest_check(bundle: Path, expected_target: str) -> dict[str, object]:
        loaded = load_artifact_manifest(bundle)
        if loaded is None:
            raise ValueError(f"GAR rejected artifact manifest: {bundle}")
        _, manifest = loaded
        section = manifest.deploy.get("app")
        if section is None or not section.files:
            raise ValueError("artifact manifest requires deploy.app.files")
        if manifest.target != expected_target:
            raise ValueError(f"artifact Target mismatch: expected={expected_target}, actual={manifest.target}")
        return {"name": manifest.name, "target": manifest.target, "files": len(section.files)}

    checks.run("sim_manifest", lambda: manifest_check(sim_bundle, args.sim_target))
    checks.run("target_manifest", lambda: manifest_check(target_bundle, args.target))
    checks.run(
        "sim_payload_architecture",
        lambda: validate_payload(sim_bundle, args.sim_entry, args.sim_payload, args.sim_architecture, args.sim_abi),
    )
    checks.run(
        "target_payload_architecture",
        lambda: validate_payload(
            target_bundle,
            args.target_entry,
            args.target_payload,
            args.target_architecture,
            args.target_abi,
        ),
    )

    target_values = checks.run("target_manifest_contract", lambda: target_contract(product_root, args.target))
    sim_values = checks.run("sim_target_contract", lambda: target_contract(product_root, args.sim_target))
    target_metadata: Any = None

    def capture_and_validate(
        *,
        bundle: Path,
        kind: Any,
        target_id: str,
        architecture: str,
        abi: str,
        toolchain: str,
        recipe: str,
    ) -> dict[str, object]:
        if source_commit is None or tools_commit is None:
            raise ValueError("repository provenance is unavailable")
        relative_bundle = bundle.relative_to(product_root)
        workspace = Workspace(
            id=f"ci_{product_root.name.lower()}",
            name=f"Local/{product_root.name}",
            branch=os.environ.get("GITHUB_REF_NAME") or "ci",
            connection={"type": "local", "path": str(product_root)},
            selected_environments={"codespace": "local", "target": "ssh_scp"},
            selected_target=args.target,
        )
        provenance = CaptureProvenance(
            source_commit=str(source_commit),
            gar_tools_commit=str(tools_commit),
            target=ArtifactTarget(
                id=target_id,
                architecture=architecture,
                abi=abi,
                libc="glibc",
                toolchain_triple=toolchain,
            ),
            target_recipe_version=recipe,
        )
        with tempfile.TemporaryDirectory(prefix="gar-parent-ci-") as temporary:
            store = LocalArtifactStore(relative_root=relative_bundle, snapshot_root=Path(temporary) / "snapshots")
            artifact = store.capture(kind, workspace, provenance)
            metadata = load_artifact_metadata(artifact.bundle_path)
            if metadata is None:
                raise ValueError("GAR did not create artifact metadata")
            verify_artifact_checksums(artifact.bundle_path, metadata)
            if metadata.schema_version != CURRENT_SCHEMA_VERSION:
                raise ValueError(f"metadata schema mismatch: {metadata.schema_version}")
            if metadata.kind != kind.value:
                raise ValueError(f"metadata kind mismatch: {metadata.kind}")
            if not metadata.checksums:
                raise ValueError("metadata checksums are empty")
            for field, value in (
                ("source_commit", metadata.source_commit),
                ("gar_tools_commit", metadata.gar_tools_commit),
                ("target_recipe_version", metadata.target_recipe_version),
                ("entrypoint", metadata.entrypoint),
            ):
                if not isinstance(value, str) or not value or value == "unknown":
                    raise ValueError(f"metadata {field} is incomplete")
            return {
                "metadata": metadata,
                "summary": {
                    "schema_version": metadata.schema_version,
                    "kind": metadata.kind,
                    "build_id": metadata.build_id,
                    "entrypoint": metadata.entrypoint,
                    "target": metadata.target.id,
                    "architecture": metadata.target.architecture,
                    "checksums": len(metadata.checksums),
                },
            }

    sim_recipe = str(sim_values[1]) if isinstance(sim_values, tuple) else "unavailable"
    checks.run(
        "sim_metadata_v2",
        lambda: capture_and_validate(
            bundle=sim_bundle,
            kind=ArtifactKind.SIM_APP,
            target_id=args.sim_target,
            architecture=args.sim_architecture,
            abi=args.sim_abi,
            toolchain=args.sim_toolchain,
            recipe=sim_recipe,
        ),
    )
    target_recipe = str(target_values[1]) if isinstance(target_values, tuple) else "unavailable"
    target_capture = checks.run(
        "target_metadata_v2",
        lambda: capture_and_validate(
            bundle=target_bundle,
            kind=ArtifactKind.TARGET_APP,
            target_id=args.target,
            architecture=args.target_architecture,
            abi=args.target_abi,
            toolchain=args.target_toolchain,
            recipe=target_recipe,
        ),
    )
    if isinstance(target_capture, dict):
        target_metadata = target_capture["metadata"]

    def compatibility_check() -> dict[str, object]:
        if target_metadata is None or not isinstance(target_values, tuple):
            raise ValueError("target metadata or Target manifest contract is unavailable")
        declared, recipe = target_values
        expected = {
            "architecture": args.target_architecture,
            "abi": args.target_abi,
            "libc": "glibc",
            "toolchain_triple": args.target_toolchain,
        }
        if declared != expected:
            raise ValueError(f"Target compatibility declaration mismatch: expected={expected}, actual={declared}")
        active_tools = TargetToolsProvenance(
            target_id=args.target,
            gar_tools_commit=str(tools_commit),
            target_recipe_version=str(recipe),
        )
        capabilities = TargetCapabilities(
            target_id=args.target,
            architecture=args.target_architecture,
            abi=args.target_abi,
            libc="glibc",
            toolchain_triple=args.target_toolchain,
            kernel_release=target_metadata.kernel.release if target_metadata.kernel is not None else "ci-static",
            installed_target_id=args.target,
            installed_recipe_version=str(recipe),
            installed_gar_tools_commit=str(tools_commit),
        )
        result = check_target_compatibility(
            target_metadata,
            capabilities,
            selected_target_id=args.target,
            active_tools=active_tools,
        )
        if not result.compatible:
            raise ValueError(json.dumps(result.as_dict(), sort_keys=True))
        return result.as_dict()

    checks.run("target_compatibility", compatibility_check)

    def hardware_check() -> dict[str, object]:
        result = validate_hardware_contract(
            requirements_path=product_root / "hardware" / "requirements.json",
            capabilities_path=tools_root / "targets" / args.target / "hardware" / "capabilities.json",
            binding_path=product_root / "hardware" / "bindings" / f"{args.target}.json",
            selected_target_id=args.target,
        )
        if not result.ok:
            raise ValueError(json.dumps(result.as_dict(), sort_keys=True))
        return result.as_dict()

    checks.run("hardware_contract", hardware_check)

    topology: Any = None

    def system_check() -> dict[str, object]:
        nonlocal topology
        topology = load_topology(system_file)
        return {
            "name": topology.name,
            "nodes": sorted(topology.nodes),
            "links": sorted(topology.links),
            "order": list(topology.order),
        }

    checks.run("system_topology", system_check)

    def scenario_check() -> dict[str, object]:
        if topology is None:
            raise ValueError("canonical system topology did not load")
        scenario = load_scenario(scenario_file, topology)
        return {"name": scenario.name, "steps": len(scenario.steps), "cleanup": len(scenario.cleanup)}

    checks.run("golden_scenario", scenario_check)

    # Remove typed objects before serializing the report; only canonical summaries
    # and pass/fail details are retained as Actions artifacts.
    for name in ("sim_metadata_v2", "target_metadata_v2"):
        detail = checks.values.get(name, {}).get("detail")
        if isinstance(detail, dict) and "summary" in detail:
            checks.values[name]["detail"] = detail["summary"]

    report = {
        "schema_version": 1,
        "kind": "garstream-product-parent-ci",
        "ok": checks.ok,
        "product": product_root.name,
        "target": args.target,
        "target_build_mode": args.target_build_mode,
        "checks": checks.values,
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        traceback.print_exc(file=sys.stderr)
        raise
    return 0 if checks.ok else 1


def guarded_main() -> int:
    try:
        return main()
    except Exception as error:
        try:
            args = parse_args()
            product_root = args.product_root.resolve()
            report_path = (product_root / args.report).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "garstream-product-parent-ci",
                        "ok": False,
                        "product": product_root.name,
                        "target": args.target,
                        "target_build_mode": args.target_build_mode,
                        "checks": {
                            "validator": {
                                "ok": False,
                                "error": str(error),
                                "exception": type(error).__name__,
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(guarded_main())
