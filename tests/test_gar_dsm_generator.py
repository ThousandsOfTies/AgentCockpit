from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import gen_gar_lib_dsm


class DsmGeneratorTest(unittest.TestCase):
    def test_check_reports_stale_content_without_overwriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            generated_path = Path(temporary_directory) / "generated.md"
            generated_path.write_text("old contents\n", encoding="utf-8")

            with contextlib.redirect_stderr(io.StringIO()):
                matches = gen_gar_lib_dsm.sync_generated_file(
                    generated_path,
                    "new contents\n",
                    check=True,
                )

            self.assertFalse(matches)
            self.assertEqual("old contents\n", generated_path.read_text(encoding="utf-8"))

    def test_generation_aborts_before_writing_when_source_has_invalid_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repo = Path(temporary_directory)
            scripts = repo / "scripts"
            scripts.mkdir()
            (scripts / "broken.py").write_text("def broken(:\n", encoding="utf-8")

            with (
                mock.patch.object(gen_gar_lib_dsm, "REPO", repo),
                mock.patch.object(gen_gar_lib_dsm, "SCAN_ROOTS", [scripts]),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = gen_gar_lib_dsm.generate()

            self.assertEqual(1, result)
            self.assertFalse((repo / "GAR_LIB_DSM.md").exists())
            self.assertFalse((repo / "GAR_LIB_DSM_file_level.csv").exists())
            self.assertFalse((repo / "GAR_LIB_PUBLIC_API_USAGE.md").exists())


if __name__ == "__main__":
    unittest.main()
