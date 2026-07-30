from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.gar_lib.vscode.terminal_requests import TerminalRequestStore


class TerminalRequestStoreTest(unittest.TestCase):
    def test_create_request_publishes_one_complete_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = TerminalRequestStore.under(root / ".gar")

            request, request_path = store.create_request(
                command="  echo hello  ",
                title="Test terminal",
                cwd=root,
                reason="Human authentication is required",
            )

            payload = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(request.id, payload["id"])
            self.assertEqual("echo hello", payload["command"])
            self.assertEqual("Test terminal", payload["title"])
            self.assertEqual(str(root.resolve()), payload["cwd"])
            self.assertEqual("Human authentication is required", payload["reason"])
            self.assertEqual([], list(store.request_dir.glob("*.tmp")))

    def test_read_status_rejects_paths_outside_the_status_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = TerminalRequestStore.under(Path(temporary_directory) / ".gar")

            for unsafe_id in ("../config", "/tmp/status", "nested/status", ""):
                with self.subTest(request_id=unsafe_id):
                    with self.assertRaisesRegex(ValueError, "id"):
                        store.read_status(unsafe_id)

    def test_list_statuses_marks_non_object_json_as_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = TerminalRequestStore.under(Path(temporary_directory) / ".gar")
            store.status_dir.mkdir(parents=True)
            (store.status_dir / "request-1.json").write_text("[]\n", encoding="utf-8")

            self.assertEqual(
                [{"id": "request-1", "status": "invalid-json"}],
                store.list_statuses(),
            )


if __name__ == "__main__":
    unittest.main()
