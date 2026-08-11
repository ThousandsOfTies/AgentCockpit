"""Versioned provenance metadata for immutable GAR artifact snapshots."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

CURRENT_SCHEMA_VERSION = 2
METADATA_FILENAME = "gar-artifact.json"
DEPLOYED_METADATA_FILENAME = ".gar-artifact.json"
UNKNOWN_PROVENANCE = "unknown"


class ArtifactMetadataError(ValueError):
    """Artifact snapshot metadata is missing, unsupported, or inconsistent."""


@dataclass(frozen=True)
class ArtifactTarget:
    id: str | None = None
    architecture: str | None = None
    abi: str | None = None
    libc: str | None = None
    toolchain_triple: str | None = None


@dataclass(frozen=True)
class ArtifactKernel:
    release: str
    vermagic: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactMetadata:
    """Typed view of schema v1 or v2 ``gar-artifact.json`` metadata."""

    schema_version: int
    kind: str
    workspace_id: str
    build_id: str
    build_timestamp: str
    product: str | None = None
    workspace_name: str | None = None
    workspace_branch: str | None = None
    target: ArtifactTarget = field(default_factory=ArtifactTarget)
    entrypoint: str | None = None
    source_commit: str | None = None
    gar_tools_commit: str | None = None
    target_recipe_version: str | None = None
    checksums: Mapping[str, str] = field(default_factory=dict)
    kernel: ArtifactKernel | None = None

    @property
    def is_legacy(self) -> bool:
        return self.schema_version < CURRENT_SCHEMA_VERSION

    @property
    def app_name(self) -> str | None:
        """Return the app segment from ``/opt/gar/apps/<app>/...``."""

        if self.entrypoint is None:
            return None
        parts = PurePosixPath(self.entrypoint).parts
        if len(parts) < 5 or parts[:4] != ("/", "opt", "gar", "apps"):
            return None
        return parts[4]

    def as_dict(self) -> dict[str, Any]:
        """Serialize using the canonical schema v2 field layout."""

        if self.schema_version != CURRENT_SCHEMA_VERSION:
            raise ArtifactMetadataError("only schema v2 metadata can be serialized")
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "product": self.product,
            "workspace": {
                "id": self.workspace_id,
                "name": self.workspace_name,
                "branch": self.workspace_branch,
            },
            "target": {
                "id": self.target.id,
                "architecture": self.target.architecture,
                "abi": self.target.abi,
                "libc": self.target.libc,
                "toolchain_triple": self.target.toolchain_triple,
            },
            "entrypoint": self.entrypoint,
            "source_commit": self.source_commit,
            "gar_tools_commit": self.gar_tools_commit,
            "target_recipe_version": self.target_recipe_version,
            "checksums": {"sha256": dict(sorted(self.checksums.items()))},
            "build_id": self.build_id,
            "build_timestamp": self.build_timestamp,
        }
        if self.kernel is not None:
            payload["kernel"] = {
                "release": self.kernel.release,
                "vermagic": list(self.kernel.vermagic),
            }
        return payload


def parse_artifact_metadata(payload: object) -> ArtifactMetadata:
    """Parse schema v1/v2 metadata without silently accepting newer schemas."""

    if not isinstance(payload, dict):
        raise ArtifactMetadataError("artifact metadata root must be an object")
    version = payload.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ArtifactMetadataError("artifact metadata schema_version must be an integer")
    if version == 1:
        return _parse_v1(payload)
    if version == CURRENT_SCHEMA_VERSION:
        return _parse_v2(payload)
    raise ArtifactMetadataError(f"unsupported artifact metadata schema_version: {version}")


def load_artifact_metadata(bundle_root: Path) -> ArtifactMetadata | None:
    """Load snapshot metadata, returning ``None`` for pre-snapshot bundles."""

    path = bundle_root / METADATA_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactMetadataError(f"artifact metadataを読めません: {path}: {error}") from error
    try:
        return parse_artifact_metadata(payload)
    except ArtifactMetadataError as error:
        raise ArtifactMetadataError(f"{error}: {path}") from error


def write_artifact_metadata(bundle_root: Path, metadata: ArtifactMetadata) -> None:
    path = bundle_root / METADATA_FILENAME
    descriptor = json.dumps(metadata.as_dict(), ensure_ascii=False, indent=2) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".gar-artifact-", suffix=".json", dir=bundle_root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o644)
            output.write(descriptor)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def sha256_checksums(bundle_root: Path) -> dict[str, str]:
    """Hash every regular snapshot file except the metadata envelope itself."""

    checksums: dict[str, str] = {}
    for path in sorted(bundle_root.rglob("*")):
        if not path.is_file() or path == bundle_root / METADATA_FILENAME:
            continue
        relative = path.relative_to(bundle_root).as_posix()
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        checksums[relative] = digest.hexdigest()
    return checksums


def verify_artifact_checksums(bundle_root: Path, metadata: ArtifactMetadata) -> None:
    """Verify v2 file integrity; schema v1 snapshots intentionally have no hashes."""

    symlink = _first_symlink(bundle_root)
    if symlink is not None:
        location = "." if symlink == bundle_root else symlink.relative_to(bundle_root).as_posix()
        raise ArtifactMetadataError(f"artifact bundle contains symlink: {location}")
    if metadata.is_legacy:
        return
    actual = sha256_checksums(bundle_root)
    expected = dict(metadata.checksums)
    if actual == expected:
        return
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    changed = sorted(path for path in set(actual) & set(expected) if actual[path] != expected[path])
    details: list[str] = []
    if missing:
        details.append(f"missing={','.join(missing)}")
    if unexpected:
        details.append(f"unexpected={','.join(unexpected)}")
    if changed:
        details.append(f"changed={','.join(changed)}")
    raise ArtifactMetadataError("artifact checksum mismatch: " + "; ".join(details))


def _first_symlink(bundle_root: Path) -> Path | None:
    if bundle_root.is_symlink():
        return bundle_root
    return next((path for path in sorted(bundle_root.rglob("*")) if path.is_symlink()), None)


def discover_kernel_dependency(bundle_root: Path) -> ArtifactKernel | None:
    """Read Linux module vermagic strings when an artifact ships ``*.ko`` files."""

    vermagic_values: set[str] = set()
    modules = sorted(bundle_root.rglob("*.ko"))
    missing_vermagic: list[str] = []
    for module in modules:
        match = re.search(rb"(?:^|\x00)vermagic=([^\x00\n]+)", module.read_bytes())
        if match is None:
            missing_vermagic.append(module.relative_to(bundle_root).as_posix())
            continue
        vermagic_values.add(match.group(1).decode("utf-8", errors="replace").strip())
    if missing_vermagic:
        raise ArtifactMetadataError("kernel module vermagic is missing: " + ", ".join(missing_vermagic))
    if not modules:
        return None
    releases = {value.split(maxsplit=1)[0] for value in vermagic_values}
    if len(releases) != 1:
        raise ArtifactMetadataError(
            "artifact contains kernel modules for multiple releases: " + ", ".join(sorted(releases))
        )
    return ArtifactKernel(release=releases.pop(), vermagic=tuple(sorted(vermagic_values)))


def _parse_v1(payload: Mapping[str, Any]) -> ArtifactMetadata:
    return ArtifactMetadata(
        schema_version=1,
        kind=_required_string(payload, "kind"),
        workspace_id=_required_string(payload, "workspace_id"),
        build_id=_required_string(payload, "build_id"),
        build_timestamp=_required_string(payload, "captured_at"),
    )


def _parse_v2(payload: Mapping[str, Any]) -> ArtifactMetadata:
    workspace = _required_object(payload, "workspace")
    target = _required_object(payload, "target")
    checksums = _required_object(_required_object(payload, "checksums"), "sha256")
    validated_checksums: dict[str, str] = {}
    for path, digest in checksums.items():
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ArtifactMetadataError("artifact metadata checksum paths must stay inside the bundle")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ArtifactMetadataError(f"artifact metadata checksum is not sha256: {path}")
        validated_checksums[path] = digest

    raw_kernel = payload.get("kernel")
    kernel = None
    if raw_kernel is not None:
        if not isinstance(raw_kernel, dict):
            raise ArtifactMetadataError("artifact metadata kernel must be an object")
        raw_vermagic = raw_kernel.get("vermagic", [])
        if not isinstance(raw_vermagic, list) or any(not isinstance(item, str) or not item for item in raw_vermagic):
            raise ArtifactMetadataError("artifact metadata kernel.vermagic must be a string list")
        kernel = ArtifactKernel(
            release=_required_string(raw_kernel, "release"),
            vermagic=tuple(raw_vermagic),
        )

    return ArtifactMetadata(
        schema_version=CURRENT_SCHEMA_VERSION,
        kind=_required_string(payload, "kind"),
        product=_optional_string(payload, "product"),
        workspace_id=_required_string(workspace, "id"),
        workspace_name=_optional_string(workspace, "name"),
        workspace_branch=_optional_string(workspace, "branch"),
        target=ArtifactTarget(
            id=_optional_string(target, "id"),
            architecture=_optional_string(target, "architecture"),
            abi=_optional_string(target, "abi"),
            libc=_optional_string(target, "libc"),
            toolchain_triple=_optional_string(target, "toolchain_triple"),
        ),
        entrypoint=_optional_string(payload, "entrypoint"),
        source_commit=_optional_string(payload, "source_commit"),
        gar_tools_commit=_optional_string(payload, "gar_tools_commit"),
        target_recipe_version=_optional_string(payload, "target_recipe_version"),
        checksums=validated_checksums,
        build_id=_required_string(payload, "build_id"),
        build_timestamp=_required_string(payload, "build_timestamp"),
        kernel=kernel,
    )


def _required_object(payload: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ArtifactMetadataError(f"artifact metadata {name} must be an object")
    return value


def _required_string(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ArtifactMetadataError(f"artifact metadata {name} must be a non-empty string")
    return value


def _optional_string(payload: Mapping[str, Any], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ArtifactMetadataError(f"artifact metadata {name} must be a non-empty string or null")
    return value
