"""CLI adapter for declarative multi-node system operations."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from argparse import Namespace
from collections.abc import Mapping

from scripts.gar_lib.system.model import load_topology
from scripts.gar_lib.system.orchestrator import SystemOrchestrator

SYSTEM_ACTIONS = ("build", "deploy", "start", "status", "diag", "test")


def add_system_parser(subparsers: argparse._SubParsersAction) -> dict[str, argparse.ArgumentParser]:
    parser = subparsers.add_parser("system", help="宣言した複数workspace systemを順序どおり操作します")
    parser.set_defaults(help_target="system")
    actions = parser.add_subparsers(dest="system_action", metavar="action")
    for action in SYSTEM_ACTIONS:
        leaf = actions.add_parser(action, help=f"system {action} を実行します")
        leaf.add_argument(
            "--file", default="gar-system.json", metavar="PATH", help="system schema v1 JSON（既定: gar-system.json）"
        )
        leaf.add_argument("--json", dest="json_output", action="store_true", help="結果をstdoutの単一JSONで出力します")
    return {"system": parser}


def run_system_command(
    args: Namespace, *, subcommand_parsers: Mapping[str, argparse.ArgumentParser] | None = None
) -> int:
    action = getattr(args, "system_action", None)
    if action not in SYSTEM_ACTIONS:
        if subcommand_parsers is not None:
            subcommand_parsers["system"].print_help()
        return 1
    if getattr(args, "json_output", False):
        output, diagnostics = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(diagnostics):
            exit_code, payload = _run(action, args.file)
        # The system contract has exactly one stdout JSON object and no stderr, even on failure.
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return exit_code
    exit_code, payload = _run(action, args.file)
    if exit_code:
        error = payload.get("error")
        if not isinstance(error, str):
            failures = payload.get("failures")
            error = failures[0]["error"] if isinstance(failures, list) and failures else "system command failed"
        print(f"gar: {error}", file=sys.stderr)
    else:
        print(f"system {action}: {'OK' if payload['ok'] else 'FAIL'} ({payload['name']})")
    return exit_code


def _run(action: str, file: str) -> tuple[int, dict[str, object]]:
    try:
        report = SystemOrchestrator(load_topology(file)).run(action)
        return report.exit_code, report.as_dict()
    except Exception as error:
        return 1, {"schema_version": 1, "command": f"system.{action}", "ok": False, "exit_code": 1, "error": str(error)}
