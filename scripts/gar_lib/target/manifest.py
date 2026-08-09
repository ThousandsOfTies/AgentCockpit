"""Load and validate target manifests provided by gar-tools."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.tools_repository import gar_tools_root
from scripts.gar_lib.environments.setup_option import EnvironmentSetupOption


@dataclass(frozen=True)
class TargetManifest:
    id: str
    display_name: str
    description: str
    tools_root: str
    default_backends: dict[str, str]
    backend_notes: dict[str, str]
    simulation: dict[str, dict[str, Any]] = field(default_factory=dict)
    provisioning: dict[str, dict[str, str]] = field(default_factory=dict)
    source_path: Path | None = None

    def simulation_settings(self, backend_id: str) -> dict[str, Any]:
        return self.simulation.get(backend_id, {})

    def provisioning_settings(self, backend_id: str) -> dict[str, str]:
        return self.provisioning.get(backend_id, {})

    def provisioning_recipe_path(self, backend_id: str) -> Path | None:
        settings = self.provisioning_settings(backend_id)
        relative_path = settings.get("path")
        if relative_path is None:
            return None
        if self.source_path is None:
            raise GarDomainError(f"target provisioning recipeの場所を解決できません: {self.id}")
        repository_root = self.source_path.parent.parent.parent.resolve()
        tools_root = (repository_root / self.tools_root).resolve()
        recipe = (tools_root / relative_path).resolve()
        if not recipe.is_relative_to(tools_root):
            raise GarDomainError(f"target provisioning recipeがtoolsRoot外を参照しています: {self.id}")
        if not recipe.is_dir():
            raise GarDomainError(f"target provisioning recipeが見つかりません: {recipe}")
        return recipe


@dataclass(frozen=True)
class TargetManifestValidationIssue:
    path: Path
    field: str
    message: str
    candidates: tuple[str, ...] = ()

    def __str__(self) -> str:
        location = f"{self.path}:{self.field}" if self.field else str(self.path)
        candidate_text = f"; candidates: {', '.join(self.candidates)}" if self.candidates else ""
        return f"{location}: {self.message}{candidate_text}"


class TargetManifestValidationError(GarDomainError):
    def __init__(self, issues: Sequence[TargetManifestValidationIssue]):
        self.issues = tuple(issues)
        details = "\n".join(f"  - {issue}" for issue in self.issues)
        super().__init__(f"target manifest validation failed:\n{details}")


def discover_target_manifests(
    environments: Sequence[type[EnvironmentSetupOption]] | None = None,
) -> list[TargetManifest]:
    """Return valid manifests, or raise with every path-specific issue found."""

    targets_root = _targets_root()
    if not targets_root.is_dir():
        return []
    if environments is None:
        from scripts.gar_lib.environments.discovery import discover_environments

        environments = discover_environments()

    backend_ids = _backend_ids_by_category(environments)
    manifests: list[TargetManifest] = []
    issues: list[TargetManifestValidationIssue] = []
    manifest_paths: dict[str, Path] = {}
    for path in sorted(targets_root.glob("*/target.json")):
        manifest = _load_target_manifest(path, backend_ids, issues)
        if manifest is None:
            continue
        previous_path = manifest_paths.get(manifest.id)
        if previous_path is not None:
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    "id",
                    f"duplicate target id {manifest.id!r}; first declared in {previous_path}",
                )
            )
            continue
        manifest_paths[manifest.id] = path
        manifests.append(manifest)

    if issues:
        raise TargetManifestValidationError(issues)
    return manifests


def target_by_id(
    targets: Sequence[TargetManifest],
    target_id: str | None,
) -> TargetManifest | None:
    return next((target for target in targets if target.id == target_id), None)


def _targets_root() -> Path:
    configured = os.environ.get("GAR_TOOLS_TARGETS")
    return Path(configured).expanduser() if configured else gar_tools_root() / "targets"


def _backend_ids_by_category(
    environments: Sequence[type[EnvironmentSetupOption]],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for environment in environments:
        result.setdefault(environment.category_id, set()).add(environment.environment_id)
    return result


def _load_target_manifest(
    path: Path,
    backend_ids: Mapping[str, set[str]],
    issues: list[TargetManifestValidationIssue],
) -> TargetManifest | None:
    issue_count_before = len(issues)
    data = _read_json_object(path, issues)
    if data is None:
        return None

    target_id = _required_string(data, "id", path, issues)
    display_name = _required_string(data, "displayName", path, issues)
    description = _required_string(data, "description", path, issues)
    tools_root = _required_string(data, "toolsRoot", path, issues)
    default_backends = _validate_default_backends(data, path, backend_ids, issues)
    backend_notes = _validate_string_mapping(data, "backendNotes", path, issues)
    simulation = _validate_simulation_settings(data, path, issues)
    provisioning = _validate_provisioning_settings(data, path, backend_ids.get("target", set()), issues)

    if len(issues) != issue_count_before:
        return None
    return TargetManifest(
        id=target_id,
        display_name=display_name,
        description=description,
        tools_root=tools_root,
        default_backends=default_backends,
        backend_notes=backend_notes,
        simulation=simulation,
        provisioning=provisioning,
        source_path=path,
    )


def _read_json_object(
    path: Path,
    issues: list[TargetManifestValidationIssue],
) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        issues.append(TargetManifestValidationIssue(path, "", f"cannot read file: {error}"))
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        issues.append(
            TargetManifestValidationIssue(
                path,
                "",
                f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}",
            )
        )
        return None
    if not isinstance(data, dict):
        issues.append(TargetManifestValidationIssue(path, "", "JSON root must be an object"))
        return None
    return data


def _required_string(
    data: Mapping[str, Any],
    key: str,
    path: Path,
    issues: list[TargetManifestValidationIssue],
) -> str:
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value
    issues.append(TargetManifestValidationIssue(path, key, "required field must be a non-empty string"))
    return ""


def _validate_default_backends(
    data: Mapping[str, Any],
    path: Path,
    backend_ids: Mapping[str, set[str]],
    issues: list[TargetManifestValidationIssue],
) -> dict[str, str]:
    raw_backends = data.get("defaultBackends")
    if not isinstance(raw_backends, dict):
        issues.append(
            TargetManifestValidationIssue(
                path,
                "defaultBackends",
                "required field must be an object",
            )
        )
        return {}

    validated: dict[str, str] = {}
    for category_id, environment_id in raw_backends.items():
        field_name = f"defaultBackends.{category_id}"
        if not isinstance(category_id, str) or not category_id:
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    "defaultBackends",
                    "category ids must be non-empty strings",
                )
            )
            continue
        if not isinstance(environment_id, str) or not environment_id:
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    field_name,
                    "backend id must be a non-empty string",
                )
            )
            continue

        available = backend_ids.get(category_id)
        if available is None:
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    field_name,
                    f"unknown environment category {category_id!r}",
                    tuple(sorted(backend_ids)),
                )
            )
            continue
        if environment_id not in available:
            actual_category = _category_for_backend(backend_ids, environment_id)
            if actual_category is None:
                message = f"unknown backend id {environment_id!r} for category {category_id!r}"
            else:
                message = (
                    f"backend id {environment_id!r} belongs to category " f"{actual_category!r}, not {category_id!r}"
                )
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    field_name,
                    message,
                    tuple(sorted(available)),
                )
            )
            continue
        validated[category_id] = environment_id
    return validated


def _category_for_backend(
    backend_ids: Mapping[str, set[str]],
    environment_id: str,
) -> str | None:
    return next(
        (category_id for category_id, category_backends in backend_ids.items() if environment_id in category_backends),
        None,
    )


def _validate_string_mapping(
    data: Mapping[str, Any],
    key: str,
    path: Path,
    issues: list[TargetManifestValidationIssue],
) -> dict[str, str]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        issues.append(TargetManifestValidationIssue(path, key, "field must be an object"))
        return {}

    validated: dict[str, str] = {}
    for item_key, item_value in value.items():
        if not isinstance(item_key, str) or not isinstance(item_value, str):
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    key,
                    "keys and values must be strings",
                )
            )
            continue
        validated[item_key] = item_value
    return validated


def _validate_simulation_settings(
    data: Mapping[str, Any],
    path: Path,
    issues: list[TargetManifestValidationIssue],
) -> dict[str, dict[str, Any]]:
    value = data.get("simulation", {})
    if not isinstance(value, dict):
        issues.append(TargetManifestValidationIssue(path, "simulation", "field must be an object"))
        return {}

    validated: dict[str, dict[str, Any]] = {}
    for backend_id, settings in value.items():
        if not isinstance(backend_id, str) or not isinstance(settings, dict):
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    "simulation",
                    "backend keys must be strings and settings must be objects",
                )
            )
            continue
        validated[backend_id] = dict(settings)
    return validated


def _validate_provisioning_settings(
    data: Mapping[str, Any],
    path: Path,
    target_backend_ids: set[str],
    issues: list[TargetManifestValidationIssue],
) -> dict[str, dict[str, str]]:
    value = data.get("provisioning", {})
    if not isinstance(value, dict):
        issues.append(TargetManifestValidationIssue(path, "provisioning", "field must be an object"))
        return {}

    validated: dict[str, dict[str, str]] = {}
    for backend_id, settings in value.items():
        field = f"provisioning.{backend_id}"
        if not isinstance(backend_id, str) or backend_id not in target_backend_ids:
            issues.append(
                TargetManifestValidationIssue(
                    path,
                    field,
                    "key must be a registered target backend id",
                    tuple(sorted(target_backend_ids)),
                )
            )
            continue
        if not isinstance(settings, dict):
            issues.append(TargetManifestValidationIssue(path, field, "settings must be an object"))
            continue
        recipe_type = settings.get("type")
        recipe_path = settings.get("path")
        if recipe_type != "ssh-script":
            issues.append(TargetManifestValidationIssue(path, f"{field}.type", "must be 'ssh-script'"))
            continue
        if not isinstance(recipe_path, str) or not recipe_path or Path(recipe_path).is_absolute():
            issues.append(TargetManifestValidationIssue(path, f"{field}.path", "must be a relative path"))
            continue
        if ".." in Path(recipe_path).parts:
            issues.append(TargetManifestValidationIssue(path, f"{field}.path", "must not escape toolsRoot"))
            continue
        validated[backend_id] = {"type": recipe_type, "path": recipe_path}
    return validated
