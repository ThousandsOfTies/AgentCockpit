"""Resolve a product-neutral target application from artifact metadata."""

from __future__ import annotations

import contextlib
import io
from pathlib import PurePosixPath

from scripts.gar_lib.artifacts.manifest import load_deploy_files
from scripts.gar_lib.artifacts.metadata import ArtifactMetadataError, load_artifact_metadata
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.target.lifecycle import TargetApplication


def target_application_from_artifact(
    artifact: Artifact,
    *,
    explicit_name: str | None = None,
    require_build_id: bool = False,
) -> TargetApplication:
    """Return the app identity used by the lifecycle-v1 capability.

    Schema v2 metadata is authoritative.  The deploy destination fallback
    keeps status/log useful for schema v1 snapshots while newer deploys still
    require an explicit build ID before placing files.
    """

    if artifact.kind is not ArtifactKind.TARGET_APP:
        raise GarDomainError(f"target applicationを解決できないartifactです: {artifact.kind.value}")

    try:
        metadata = load_artifact_metadata(artifact.bundle_path)
    except ArtifactMetadataError as error:
        raise GarDomainError(str(error)) from error

    metadata_name = metadata.app_name if metadata is not None else None
    if explicit_name is not None and metadata_name is not None and explicit_name != metadata_name:
        raise GarDomainError(
            f"指定したapplicationとartifact entrypointが一致しません: {explicit_name} != {metadata_name}"
        )
    name = explicit_name or metadata_name or _application_name_from_deploy_manifest(artifact)
    if name is None:
        raise GarDomainError(
            "target application名をartifactから解決できません。schema v2 entrypointまたは--appを指定してください"
        )

    build_id = metadata.build_id if metadata is not None else None
    if require_build_id and not build_id:
        raise GarDomainError("deploy収束にはschema v2 artifact build IDが必要です。もう一度target buildしてください")
    return TargetApplication(
        name=name,
        expected_build_id=build_id,
        entrypoint=metadata.entrypoint if metadata is not None else None,
    )


def _application_name_from_deploy_manifest(artifact: Artifact) -> str | None:
    diagnostics = io.StringIO()
    with contextlib.redirect_stderr(diagnostics):
        loaded = load_deploy_files(artifact.bundle_path, "app")
    if loaded is None:
        detail = diagnostics.getvalue().strip()
        suffix = f": {detail}" if detail else ""
        raise GarDomainError(f"target artifact manifestを読み込めません{suffix}")
    _, files = loaded
    candidates = {
        name
        for entry in files
        if isinstance(entry.get("dest"), str)
        for name in (_application_name_from_destination(entry["dest"]),)
        if name is not None
    }
    if len(candidates) > 1:
        raise GarDomainError("target artifactに複数applicationがあり、lifecycle対象を一意に決定できません")
    return next(iter(candidates), None)


def _application_name_from_destination(destination: str) -> str | None:
    path = PurePosixPath(destination)
    parts = path.parts
    if len(parts) < 5 or parts[:4] != ("/", "opt", "gar", "apps"):
        return None
    return parts[4]
