from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.gar_lib.simulation.process import LocalProcessChannel


class GarSimulationProcessTest(unittest.TestCase):
    def test_local_process_channel_launches_without_simulator_specific_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "runtime.log"
            process = mock.Mock(pid=1234)
            with mock.patch(
                "scripts.gar_lib.simulation.process.subprocess.Popen", return_value=process
            ) as popen:
                result = LocalProcessChannel().start(
                    ("simulator", "--project", str(root)),
                    cwd=root,
                    log_path=log_path,
                )

        self.assertEqual(1234, result.pid)
        self.assertEqual(("simulator", "--project", str(root)), result.argv)
        self.assertEqual(root, popen.call_args.kwargs["cwd"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
