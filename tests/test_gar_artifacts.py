from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.gar_lib.artifacts.manifest import parse_artifact_manifest, resolve_artifact_src
from scripts.gar_lib.artifacts.store import LocalArtifactStore
from scripts.gar_lib.core.artifact import ArtifactKind
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.workspace import Workspace


def local_workspace(root: Path) -> Workspace:
    return Workspace(
        id="ws_artifacts",
        name="Local/Artifacts",
        branch="Artifacts",
        connection={"type": "local", "path": str(root)},
        selected_environments={"codespace": "local"},
    )


def write_app_bundle(root: Path, content: str) -> None:
    artifact_file = root / "files" / "app"
    artifact_file.parent.mkdir(parents=True, exist_ok=True)
    artifact_file.write_text(content, encoding="utf-8")
    (root / "artifact.json").write_text(
        json.dumps(
            {
                "deploy": {
                    "app": {
                        "files": [
                            {
                                "src": "files/app",
                                "dest": "~/app",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )


class ArtifactManifestTest(unittest.TestCase):
    def test_manifest_accepts_file_and_product_artifact_sections(self) -> None:
        manifest = parse_artifact_manifest(
            {
                "name": "vibe-remote",
                "deploy": {
                    "vscodeExtension": {
                        "files": [
                            {
                                "src": "files/vibe-remote-extension",
                                "dest": "~/vibe-remote-extension",
                            }
                        ]
                    },
                    "m5stickcFirmware": {"artifact": "files/m5stickc-firmware"},
                    "optionalFirmware": {"artifact": None},
                },
            }
        )

        self.assertEqual(
            (
                "files/vibe-remote-extension",
                "files/m5stickc-firmware",
            ),
            manifest.sources,
        )

    def test_artifact_source_resolution_rejects_internal_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            files = bundle / "files"
            files.mkdir()
            (files / "real").write_text("content", encoding="utf-8")
            (files / "linked").symlink_to("real")

            with contextlib.redirect_stderr(io.StringIO()):
                resolved = resolve_artifact_src(bundle, "files/linked")

        self.assertIsNone(resolved)

    def test_artifact_source_resolution_rejects_nested_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            directory = bundle / "files" / "application"
            directory.mkdir(parents=True)
            (directory / "real").write_text("content", encoding="utf-8")
            (directory / "linked").symlink_to("real")

            with contextlib.redirect_stderr(io.StringIO()):
                resolved = resolve_artifact_src(bundle, "files/application")

        self.assertIsNone(resolved)


class LocalArtifactStoreTest(unittest.TestCase):
    def test_artifact_kinds_keep_independent_immutable_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = local_workspace(root / "product")
            staging = workspace.local_root / "artifacts" / "from-codespace"
            store = LocalArtifactStore(snapshot_root=root / "snapshots")

            write_app_bundle(staging, "simulation")
            simulation = store.capture(ArtifactKind.SIM_APP, workspace)

            write_app_bundle(staging, "target")
            target = store.capture(ArtifactKind.TARGET_APP, workspace)

            latest_simulation = store.latest(ArtifactKind.SIM_APP, workspace)
            latest_target = store.latest(ArtifactKind.TARGET_APP, workspace)

            self.assertNotEqual(simulation.bundle_path, target.bundle_path)
            self.assertEqual(
                "simulation",
                (latest_simulation.bundle_path / "files" / "app").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "target",
                (latest_target.bundle_path / "files" / "app").read_text(encoding="utf-8"),
            )

    def test_capture_rejects_symlinks_in_the_staging_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = local_workspace(root / "product")
            staging = workspace.local_root / "artifacts" / "from-codespace"
            store = LocalArtifactStore(snapshot_root=root / "snapshots")
            write_app_bundle(staging, "placeholder")
            outside = root / "outside"
            outside.write_text("must not be captured", encoding="utf-8")
            (staging / "files" / "app").unlink()
            (staging / "files" / "app").symlink_to(outside)

            with self.assertRaisesRegex(GarDomainError, "symlink"):
                store.capture(ArtifactKind.SIM_APP, workspace)

            self.assertFalse((root / "snapshots").exists())


if __name__ == "__main__":
    unittest.main()
