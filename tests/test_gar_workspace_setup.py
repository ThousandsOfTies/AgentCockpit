from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.commands.setup.workspace_setup import _prompt_local_connection


class WorkspaceSetupTests(unittest.TestCase):
    def test_empty_local_path_keeps_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            existing_path = Path(tmp)
            with (
                mock.patch(
                    "scripts.gar_lib.commands.setup.workspace_setup.safe_input",
                    return_value="",
                ),
                mock.patch(
                    "scripts.gar_lib.commands.setup.workspace_setup.probe_git_workspace",
                    return_value=("origin", "GarStreamTx"),
                ),
            ):
                connection, branch = _prompt_local_connection(
                    {"path": str(existing_path)}, None
                )

        self.assertEqual({"type": "local", "path": str(existing_path)}, connection)
        self.assertEqual("GarStreamTx", branch)


if __name__ == "__main__":
    unittest.main()
