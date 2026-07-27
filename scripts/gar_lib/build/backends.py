"""workspace が選んだ codespace backend から、build を行うオブジェクトを作る。"""

from __future__ import annotations

from scripts.gar_lib.artifacts.store import ArtifactStore
from scripts.gar_lib.build._base import BuildEnvironment
from scripts.gar_lib.build.codespaces import CodespacesBuildEnvironment
from scripts.gar_lib.build.esp32 import Esp32BuildEnvironment
from scripts.gar_lib.build.local import LocalBuildEnvironment
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace


def build_environment_for(workspace: Workspace, artifacts: ArtifactStore) -> BuildEnvironment:
    """成果物をビルドするオブジェクトを作る。"""

    backend = workspace.selected_environments.get("codespace")
    if backend not in ("local", "github_codespaces"):
        raise GarDomainError(f"build environment はまだ未対応です: {backend or '(未設定)'}")

    use_codespaces = backend == "github_codespaces"
    if workspace.selected_environments.get("target") == "esp32_esptool":
        return Esp32BuildEnvironment(artifacts, use_codespaces=use_codespaces)
    if use_codespaces:
        return CodespacesBuildEnvironment(artifacts)
    return LocalBuildEnvironment(artifacts)
