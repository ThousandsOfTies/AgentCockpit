"""Tests for the one-time constrained sudo bootstrap."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest import TestCase, mock

from scripts.gar_lib.target.ssh_prepare import prepare_ssh_target


class TargetPrepareTests(TestCase):
    def test_prepare_stages_and_runs_the_target_owned_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Path(tmp)
            (recipe / "prepare.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            (recipe / "gar-target-install").write_text("#!/bin/sh\n", encoding="utf-8")
            (recipe / "gar-app@.service").write_text("[Service]\n", encoding="utf-8")

            def completed(argv: tuple[str, ...], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                stdout = "user\n" if argv[-1] == "id -un" else ""
                return subprocess.CompletedProcess(argv, 0, stdout, "")

            with mock.patch("scripts.gar_lib.target.ssh_prepare.subprocess.run", side_effect=completed) as run:
                prepare_ssh_target("raspi5", recipe, config_path=Path("/tmp/ssh-config"))

        scp_command = run.call_args_list[2].args[0]
        self.assertEqual("scp", scp_command[0])
        self.assertIn(str(recipe / "prepare.sh"), scp_command)
        self.assertIn(str(recipe / "gar-target-install"), scp_command)
        self.assertIn(str(recipe / "gar-app@.service"), scp_command)

        bootstrap = run.call_args_list[3].args[0]
        self.assertIn("-tt", bootstrap)
        self.assertIn("/prepare.sh user ", bootstrap[-1])
        self.assertIn("/gar-app@.service", bootstrap[-1])
