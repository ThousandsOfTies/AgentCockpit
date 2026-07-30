from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.gar_lib.core.archive import UnsafeArchiveError, safe_extract_tar


class SafeTarExtractionTest(unittest.TestCase):
    def test_extracts_regular_files_inside_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tarball = root / "bundle.tar.gz"
            destination = root / "output"
            _write_file_member(tarball, "renode/bin/renode", b"launcher")

            safe_extract_tar(tarball, destination)

            self.assertEqual(
                b"launcher",
                (destination / "renode" / "bin" / "renode").read_bytes(),
            )

    def test_rejects_member_outside_destination_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tarball = root / "bundle.tar"
            destination = root / "output"
            _write_file_member(tarball, "../output-neighbor/escaped", b"unsafe")

            with self.assertRaisesRegex(UnsafeArchiveError, "escapes destination"):
                safe_extract_tar(tarball, destination)

            self.assertFalse((root / "output-neighbor" / "escaped").exists())

    def test_rejects_absolute_member_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tarball = root / "bundle.tar"
            _write_file_member(tarball, "/tmp/gar-unsafe", b"unsafe")

            with self.assertRaisesRegex(UnsafeArchiveError, "absolute path"):
                safe_extract_tar(tarball, root / "output")

    def test_rejects_symbolic_and_hard_links(self) -> None:
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
            with self.subTest(member_type=member_type), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                tarball = root / "bundle.tar"
                with tarfile.open(tarball, "w") as archive:
                    member = tarfile.TarInfo("renode-link")
                    member.type = member_type
                    member.linkname = "/tmp/gar-unsafe"
                    archive.addfile(member)

                with self.assertRaisesRegex(UnsafeArchiveError, "link member"):
                    safe_extract_tar(tarball, root / "output")


def _write_file_member(tarball: Path, name: str, content: bytes) -> None:
    with tarfile.open(tarball, "w:gz" if tarball.suffix == ".gz" else "w") as archive:
        member = tarfile.TarInfo(name)
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))


if __name__ == "__main__":
    unittest.main()
