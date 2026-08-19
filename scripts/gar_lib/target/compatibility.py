"""Pre-transfer compatibility checks for physical Target artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from scripts.gar_lib.access.channel import CommandChannel
from scripts.gar_lib.artifacts.metadata import (
    CURRENT_SCHEMA_VERSION,
    DEPLOYED_METADATA_FILENAME,
    UNKNOWN_PROVENANCE,
    ArtifactMetadata,
    ArtifactMetadataError,
    load_artifact_metadata,
    verify_artifact_checksums,
)
from scripts.gar_lib.artifacts.provenance import TargetToolsProvenance
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError

_TARGET_CAPABILITY_PROBE = r"""
set -u
gar_arch=$(uname -m) || exit 20
gar_kernel=$(uname -r) || exit 21
gar_target_id=
if [ -r /etc/gar/target-id ]; then
    IFS= read -r gar_target_id </etc/gar/target-id || true
fi
gar_installed_target_id=
gar_installed_recipe_version=
gar_installed_tools_commit=
if [ -r /etc/gar/recipe-version ]; then
    while IFS='=' read -r gar_identity_name gar_identity_value; do
        case "$gar_identity_name" in
            target_id) gar_installed_target_id=$gar_identity_value ;;
            recipe_version) gar_installed_recipe_version=$gar_identity_value ;;
            gar_tools_commit) gar_installed_tools_commit=$gar_identity_value ;;
        esac
    done </etc/gar/recipe-version
fi
gar_libc=
gar_abi=
gar_getconf=
if command -v getconf >/dev/null 2>&1; then
    gar_getconf=$(getconf GNU_LIBC_VERSION 2>/dev/null || true)
fi
case "$gar_getconf" in
    glibc*) gar_libc=glibc ;;
esac
if [ -e /lib/ld-linux-armhf.so.3 ] || [ -e /usr/lib/ld-linux-armhf.so.3 ] || \
   [ -e /lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 ] || \
   [ -e /usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 ]; then
    gar_libc=${gar_libc:-glibc}
    gar_abi=gnueabihf
elif [ -e /lib/ld-linux.so.3 ] || [ -e /usr/lib/ld-linux.so.3 ] || \
     [ -e /lib/arm-linux-gnueabi/ld-linux.so.3 ] || \
     [ -e /usr/lib/arm-linux-gnueabi/ld-linux.so.3 ]; then
    gar_libc=${gar_libc:-glibc}
    gar_abi=gnueabi
elif [ -e /lib/ld-linux-aarch64.so.1 ] || [ -e /lib64/ld-linux-aarch64.so.1 ] || \
     [ -e /usr/lib/ld-linux-aarch64.so.1 ] || \
     [ -e /lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 ] || \
     [ -e /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1 ]; then
    gar_libc=${gar_libc:-glibc}
    gar_abi=gnu
elif [ -e /lib64/ld-linux-x86-64.so.2 ] || [ -e /lib/ld-linux-x86-64.so.2 ] || \
     [ -e /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 ] || \
     [ -e /usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 ]; then
    gar_libc=${gar_libc:-glibc}
    gar_abi=gnu
fi
for gar_loader in /lib/ld-musl-*.so.1 /usr/lib/ld-musl-*.so.1; do
    if [ -e "$gar_loader" ]; then
        gar_libc=musl
        case "$gar_loader" in
            *armhf*) gar_abi=musleabihf ;;
            *) gar_abi=musl ;;
        esac
        break
    fi
done
if [ -z "$gar_abi" ] && [ "$gar_libc" = glibc ]; then
    case "$gar_arch" in
        aarch64|arm64|x86_64|amd64) gar_abi=gnu ;;
    esac
fi
gar_triple=
case "$gar_arch:$gar_abi" in
    aarch64:gnu|arm64:gnu) gar_triple=aarch64-linux-gnu ;;
    armv7*:gnueabihf|arm*:gnueabihf) gar_triple=arm-linux-gnueabihf ;;
    armv7*:gnueabi|arm*:gnueabi) gar_triple=arm-linux-gnueabi ;;
    x86_64:gnu|amd64:gnu) gar_triple=x86_64-linux-gnu ;;
esac
printf 'target_id=%s\n' "$gar_target_id"
printf 'architecture=%s\n' "$gar_arch"
printf 'abi=%s\n' "$gar_abi"
printf 'libc=%s\n' "$gar_libc"
printf 'toolchain_triple=%s\n' "$gar_triple"
printf 'kernel_release=%s\n' "$gar_kernel"
printf 'installed_target_id=%s\n' "$gar_installed_target_id"
printf 'installed_recipe_version=%s\n' "$gar_installed_recipe_version"
printf 'installed_gar_tools_commit=%s\n' "$gar_installed_tools_commit"
""".strip()


@dataclass(frozen=True)
class TargetCapabilities:
    target_id: str | None
    architecture: str
    abi: str | None
    libc: str | None
    toolchain_triple: str | None
    kernel_release: str
    installed_target_id: str | None = None
    installed_recipe_version: str | None = None
    installed_gar_tools_commit: str | None = None


@dataclass(frozen=True)
class CompatibilityIssue:
    field: str
    expected: str | None
    actual: str | None
    message: str


@dataclass(frozen=True)
class CompatibilityReport:
    artifact_build_id: str
    target: TargetCapabilities
    issues: tuple[CompatibilityIssue, ...]

    @property
    def compatible(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict[str, object]:
        return {
            "compatible": self.compatible,
            "artifact_build_id": self.artifact_build_id,
            "target": {
                "id": self.target.target_id,
                "architecture": self.target.architecture,
                "abi": self.target.abi,
                "libc": self.target.libc,
                "toolchain_triple": self.target.toolchain_triple,
                "kernel_release": self.target.kernel_release,
                "installed_target_id": self.target.installed_target_id,
                "installed_recipe_version": self.target.installed_recipe_version,
                "installed_gar_tools_commit": self.target.installed_gar_tools_commit,
            },
            "issues": [
                {
                    "field": issue.field,
                    "expected": issue.expected,
                    "actual": issue.actual,
                    "message": issue.message,
                }
                for issue in self.issues
            ],
        }


class ArtifactCompatibilityError(GarDomainError):
    def __init__(self, message: str, report: CompatibilityReport | None = None):
        self.report = report
        super().__init__(message)


def probe_target_capabilities(command_channel: CommandChannel) -> TargetCapabilities:
    """Measure the connected Linux Target rather than trusting local setup state."""

    result = command_channel.run(_TARGET_CAPABILITY_PROBE)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise ArtifactCompatibilityError(f"target compatibility probe failed (exit {result.returncode}){suffix}")
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        name, separator, value = line.partition("=")
        if separator and name in {
            "target_id",
            "architecture",
            "abi",
            "libc",
            "toolchain_triple",
            "kernel_release",
            "installed_target_id",
            "installed_recipe_version",
            "installed_gar_tools_commit",
        }:
            values[name] = value.strip()
    architecture = values.get("architecture", "")
    kernel_release = values.get("kernel_release", "")
    if not architecture or not kernel_release:
        raise ArtifactCompatibilityError("target compatibility probe returned incomplete uname data")
    return TargetCapabilities(
        target_id=values.get("target_id") or None,
        architecture=_normalize_architecture(architecture),
        abi=values.get("abi") or None,
        libc=values.get("libc") or None,
        toolchain_triple=values.get("toolchain_triple") or None,
        kernel_release=kernel_release,
        installed_target_id=values.get("installed_target_id") or None,
        installed_recipe_version=values.get("installed_recipe_version") or None,
        installed_gar_tools_commit=values.get("installed_gar_tools_commit") or None,
    )


def require_target_compatibility(
    artifact: Artifact,
    command_channel: CommandChannel,
    *,
    active_tools: TargetToolsProvenance | None = None,
) -> tuple[ArtifactMetadata, CompatibilityReport]:
    """Reject incomplete, corrupt, or incompatible artifacts before transfer."""

    if artifact.kind is not ArtifactKind.TARGET_APP:
        raise ArtifactCompatibilityError(f"targetへ配置できないartifactです: {artifact.kind.value}")
    try:
        metadata = load_artifact_metadata(artifact.bundle_path)
        if metadata is None:
            raise ArtifactMetadataError(
                "artifact has no artifact-info.json (legacy gar-artifact.json is also accepted)"
            )
        verify_artifact_checksums(artifact.bundle_path, metadata)
    except ArtifactMetadataError as error:
        raise ArtifactCompatibilityError(
            f"target deploy requires a valid schema v2 artifact; rebuild before deploy: {error}"
        ) from error
    if metadata.schema_version != CURRENT_SCHEMA_VERSION:
        raise ArtifactCompatibilityError(
            f"target deploy does not accept legacy artifact schema v{metadata.schema_version}; rebuild before deploy"
        )
    if metadata.kind != artifact.kind.value or metadata.workspace_id != artifact.workspace.id:
        raise ArtifactCompatibilityError("target artifact kind/workspace does not match the requested deployment")

    missing = _missing_provenance(metadata)
    if missing:
        raise ArtifactCompatibilityError(
            "target artifact provenance is incomplete; rebuild before deploy: " + ", ".join(missing)
        )
    if active_tools is not None:
        _require_active_tools_match(metadata, active_tools)
    capabilities = probe_target_capabilities(command_channel)
    report = check_target_compatibility(
        metadata,
        capabilities,
        selected_target_id=artifact.workspace.selected_target,
        active_tools=active_tools,
    )
    if not report.compatible:
        details = "; ".join(issue.message for issue in report.issues)
        if any(issue.field.startswith("installed_recipe.") for issue in report.issues):
            details += "; synchronize gar-tools and run gar target prepare before retrying deploy"
        raise ArtifactCompatibilityError(
            f"target compatibility rejected before transfer: {details}",
            report,
        )
    return metadata, report


def check_target_compatibility(
    metadata: ArtifactMetadata,
    capabilities: TargetCapabilities,
    *,
    selected_target_id: str | None = None,
    active_tools: TargetToolsProvenance | None = None,
) -> CompatibilityReport:
    """Compare v2 requirements with observed Target facts without I/O."""

    issues: list[CompatibilityIssue] = []
    expected_target = metadata.target
    _compare(
        issues,
        "selected_target_id",
        expected_target.id,
        selected_target_id,
        required=selected_target_id is not None,
    )
    _compare(
        issues,
        "target.id",
        expected_target.id,
        capabilities.target_id,
        required=expected_target.id is not None,
    )
    _compare(
        issues,
        "target.architecture",
        _normalize_architecture(expected_target.architecture),
        _normalize_architecture(capabilities.architecture),
        required=True,
    )
    _compare(issues, "target.abi", expected_target.abi, capabilities.abi, required=expected_target.abi is not None)
    _compare(
        issues,
        "target.libc",
        _normalize_libc(expected_target.libc),
        _normalize_libc(capabilities.libc),
        required=expected_target.libc is not None,
    )
    if expected_target.toolchain_triple is not None:
        actual_triple = capabilities.toolchain_triple
        if actual_triple is None:
            issues.append(
                CompatibilityIssue(
                    "target.toolchain_triple",
                    expected_target.toolchain_triple,
                    None,
                    "TargetのABIからtoolchain triple互換性を実測できません",
                )
            )
        elif _triple_signature(expected_target.toolchain_triple) != _triple_signature(actual_triple):
            issues.append(
                CompatibilityIssue(
                    "target.toolchain_triple",
                    expected_target.toolchain_triple,
                    actual_triple,
                    "target.toolchain_triple mismatch: "
                    f"artifact={expected_target.toolchain_triple}, target={actual_triple}",
                )
            )
    if metadata.kernel is not None:
        _compare(
            issues,
            "kernel.release",
            metadata.kernel.release,
            capabilities.kernel_release,
            required=True,
        )
    if active_tools is not None:
        _compare(
            issues,
            "installed_recipe.target_id",
            metadata.target.id,
            capabilities.installed_target_id,
            required=True,
        )
        _compare(
            issues,
            "installed_recipe.version",
            metadata.target_recipe_version,
            capabilities.installed_recipe_version,
            required=True,
        )
        _compare(
            issues,
            "installed_recipe.gar_tools_commit",
            metadata.gar_tools_commit,
            capabilities.installed_gar_tools_commit,
            required=True,
        )
    return CompatibilityReport(
        artifact_build_id=metadata.build_id,
        target=capabilities,
        issues=tuple(issues),
    )


def deployment_marker_destination(metadata: ArtifactMetadata) -> str:
    """Resolve the standard lifecycle marker in the application root."""

    if metadata.app_name is None or metadata.entrypoint is None:
        raise ArtifactCompatibilityError("target artifact entrypoint must be under /opt/gar/apps/<app>")
    return str(PurePosixPath("/opt/gar/apps") / metadata.app_name / DEPLOYED_METADATA_FILENAME)


def _missing_provenance(metadata: ArtifactMetadata) -> list[str]:
    missing: list[str] = []
    required = {
        "product": metadata.product,
        "entrypoint": metadata.entrypoint,
        "source_commit": metadata.source_commit,
        "gar_tools_commit": metadata.gar_tools_commit,
        "target_recipe_version": metadata.target_recipe_version,
        "target.id": metadata.target.id,
        "target.architecture": metadata.target.architecture,
    }
    for field, value in required.items():
        if value is None or value == UNKNOWN_PROVENANCE:
            missing.append(field)
    if metadata.target.abi is None and metadata.target.libc is None and metadata.target.toolchain_triple is None:
        missing.append("target.abi/libc/toolchain_triple")
    if not metadata.checksums:
        missing.append("checksums.sha256")
    return missing


def _require_active_tools_match(
    metadata: ArtifactMetadata,
    active_tools: TargetToolsProvenance,
) -> None:
    """Reject a recipe copy different from the one captured at build time."""

    mismatches: list[str] = []
    pairs = (
        ("target_id", metadata.target.id, active_tools.target_id),
        ("gar_tools_commit", metadata.gar_tools_commit, active_tools.gar_tools_commit),
        (
            "target_recipe_version",
            metadata.target_recipe_version,
            active_tools.target_recipe_version,
        ),
    )
    for field, artifact_value, active_value in pairs:
        if active_value is None or active_value == UNKNOWN_PROVENANCE:
            mismatches.append(f"active {field} cannot be measured")
        elif artifact_value != active_value:
            mismatches.append(f"{field} mismatch: artifact={artifact_value}, active={active_value}")
    if mismatches:
        raise ArtifactCompatibilityError(
            "target tools drift rejected before transfer: "
            + "; ".join(mismatches)
            + "; sync workspace sources/gar-tools with the active gar-tools copy and rebuild"
        )


def _compare(
    issues: list[CompatibilityIssue],
    field: str,
    expected: str | None,
    actual: str | None,
    *,
    required: bool,
) -> None:
    if expected is None:
        if required:
            issues.append(CompatibilityIssue(field, None, actual, f"artifact metadataに{field}がありません"))
        return
    if actual is None:
        if required:
            issues.append(CompatibilityIssue(field, expected, None, f"Targetの{field}を実測できません"))
        return
    if expected != actual:
        issues.append(
            CompatibilityIssue(
                field,
                expected,
                actual,
                f"{field} mismatch: artifact={expected}, target={actual}",
            )
        )


def _normalize_architecture(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"arm64", "aarch64"}:
        return "aarch64"
    if lowered.startswith("armv7"):
        return "armv7l"
    if lowered in {"amd64", "x86-64", "x86_64"}:
        return "x86_64"
    return lowered


def _normalize_libc(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"gnu", "gnu libc", "glibc"}:
        return "glibc"
    return lowered


def _triple_signature(value: str) -> tuple[str, str]:
    lowered = value.strip().lower()
    architecture = lowered.split("-", maxsplit=1)[0]
    if architecture == "arm64":
        architecture = "aarch64"
    elif architecture.startswith("armv7"):
        architecture = "arm"
    abi = lowered.rsplit("-", maxsplit=1)[-1]
    return architecture, abi
