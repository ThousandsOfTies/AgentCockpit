"""Build ESP32/M5Stack firmware through the unified target build path.

This environment lets ``gar target build`` produce an ESP32 firmware bundle in
the same artifact store location the generic target build uses, so a following
``gar target deploy`` (``esp32_esptool`` target) can flash it without any
ESP32-specific CLI subcommand.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from scripts.gar_lib.artifacts.store import LocalArtifactStore
from scripts.gar_lib.core.artifact import Artifact, ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace
from scripts.gar_lib.target.esp32_firmware import (
    DEFAULT_ESP32_CODESPACE_PROJECT_ROOT,
    DEFAULT_ESP32_PIO_ENV,
    FLASH_LAYOUT,
    build_esp32_firmware_codespace,
    build_esp32_firmware_local,
)


def _workspace_string(workspace: Workspace, key: str) -> str | None:
    value = workspace.esp32.get(key)
    return value if isinstance(value, str) and value else None


class Esp32BuildEnvironment:
    """Build ESP32 firmware and materialize it into the artifact store."""

    def __init__(self, artifacts: LocalArtifactStore, *, use_codespaces: bool):
        self.artifacts = artifacts
        self.use_codespaces = use_codespaces

    def build(self, kind: ArtifactKind, workspace: Workspace) -> Artifact:
        if kind is not ArtifactKind.TARGET_APP:
            raise GarDomainError(f"ESP32 build が対応しない artifact 種別です: {kind.value}")

        pio_env = _workspace_string(workspace, "pio_env") or DEFAULT_ESP32_PIO_ENV

        # 分岐点: build 環境は workspace の selected_environments["codespace"] で決まる
        # （resolver が use_codespaces を渡す）。ESP32 固有の pio_env / remote_project_root は
        # workspace.esp32 から解決し、未設定時のみ既定値へフォールバックする。
        if self.use_codespaces:
            firmware_dir = build_esp32_firmware_codespace(
                codespace_name=workspace.codespace_name,
                remote_project_root=(
                    _workspace_string(workspace, "remote_project_root")
                    or DEFAULT_ESP32_CODESPACE_PROJECT_ROOT
                ),
                pio_env=pio_env,
            )
        else:
            firmware_dir = build_esp32_firmware_local(pio_env=pio_env)

        bundle_path = self._materialize(firmware_dir, workspace)
        return Artifact(kind=ArtifactKind.TARGET_APP, workspace=workspace, bundle_path=bundle_path)

    def clean(self, kind: ArtifactKind, workspace: Workspace) -> None:
        del kind
        bundle_path = self.artifacts.bundle_path(workspace)
        if bundle_path.exists():
            shutil.rmtree(bundle_path)

    def fetch(self, workspace: Workspace) -> None:
        # ESP32 は build 時に firmware artifact を取得・materialize するため、
        # 独立した fetch 操作は不要。
        del workspace

    def _materialize(self, firmware_dir: Path, workspace: Workspace) -> Path:
        # TODO(esp32-e2e): この materialize（firmware 一式を artifact store の bundle へコピー
        # + artifact.json 生成）は unit test のみで、実機/Codespace を通した
        # `gar target build` -> `gar target deploy` の end-to-end 疎通は未検証。
        # 実機で回すとき、deploy 側 Esp32TargetEnvironment が bundle_path から firmware を
        # 解決して flash できることを確認すること。
        required = [name for _, name in FLASH_LAYOUT]
        missing = [name for name in required if not (firmware_dir / name).is_file()]
        if missing:
            raise GarDomainError(
                "ESP32 build 成果物に firmware 一式がありません: " + ", ".join(missing)
            )

        bundle_path = self.artifacts.bundle_path(workspace)
        bundle_path.mkdir(parents=True, exist_ok=True)

        copied: list[str] = []
        for name in [*required, "SHA256SUMS"]:
            source = firmware_dir / name
            if source.is_file():
                shutil.copy2(source, bundle_path / name)
                copied.append(name)

        manifest = {
            "deploy": {
                "app": {"files": [{"src": name, "dest": name} for name in copied if name in required]}
            }
        }
        (bundle_path / "artifact.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Artifact: {bundle_path}")
        return bundle_path
