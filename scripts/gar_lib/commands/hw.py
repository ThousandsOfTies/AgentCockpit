"""CLI boundary for ``gar hw``."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from argparse import Namespace
from pathlib import Path

from scripts.gar_lib.commands.workspace_resolver import resolve_workspace
from scripts.gar_lib.core.errors import GarDomainError
from scripts.gar_lib.core.hardware import write_hw_template
from scripts.gar_lib.core.hardware_validation import validate_hardware_contract
from scripts.gar_lib.core.tools_repository import gar_tools_root


def add_hw_parser(
    subparsers: argparse._SubParsersAction,
) -> dict[str, argparse.ArgumentParser]:
    parser = subparsers.add_parser("hw", help="hardware 定義 CSV を管理します")
    commands = parser.add_subparsers(dest="hw_command", metavar="command")
    init_parser = commands.add_parser(
        "init",
        help="product所有のhardware定義CSVを空のschemaから作成します",
    )
    init_parser.add_argument(
        "--target",
        dest="target_id",
        default=None,
        help="互換用target ID（CSV schemaはtarget非依存）",
    )
    validate_parser = commands.add_parser(
        "validate",
        help="product requirement・target capability・binding の適合性を検証します",
    )
    validate_parser.add_argument("--workspace", default=None, metavar="NAME", help="検証する登録workspace")
    validate_parser.add_argument("--requirements", default=None, metavar="PATH", help="requirements.json のパス")
    validate_parser.add_argument("--capabilities", default=None, metavar="PATH", help="target capabilities.json のパス")
    validate_parser.add_argument("--binding", default=None, metavar="PATH", help="target binding JSON のパス")
    validate_parser.add_argument(
        "--json", dest="json_output", action="store_true", help="結果をstdoutの単一JSONで出力します"
    )
    init_parser.add_argument(
        "--dir",
        dest="output_dir",
        default=None,
        help="CSV を作成するproductディレクトリ（既定: ./hardware）",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="既存のテンプレート CSV を上書きします",
    )
    return {"hw": parser}


def run_hw_cli(args: Namespace, *, help_parser: argparse.ArgumentParser) -> int:
    if args.hw_command is None:
        help_parser.print_help()
        return 1
    if args.hw_command == "validate":
        if args.json_output:
            output, diagnostics = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(diagnostics):
                exit_code, payload = run_hw_validate(
                    workspace_selector=args.workspace,
                    requirements=args.requirements,
                    capabilities=args.capabilities,
                    binding=args.binding,
                )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            return exit_code
        exit_code, payload = run_hw_validate(
            workspace_selector=args.workspace,
            requirements=args.requirements,
            capabilities=args.capabilities,
            binding=args.binding,
        )
        if exit_code:
            for error in payload["errors"]:
                print(f"gar hw validate: {error['code']}: {error['message']}", file=sys.stderr)
        else:
            print(f"hardware validate: OK ({payload['product']} -> {payload['target_id']})")
        return exit_code
    return run_hw_command(args.hw_command, output_dir=args.output_dir, force=args.force, target_id=args.target_id)


def run_hw_command(
    command: str,
    *,
    output_dir: str | None = None,
    force: bool = False,
    target_id: str | None = None,
) -> int:
    if command == "init":
        return write_hw_template(
            output_dir=output_dir,
            force=force,
            target_id=target_id or "linux-device",
        )

    print(f"gar hw: unknown command: {command}")
    return 1


def run_hw_validate(
    *,
    workspace_selector: str | None,
    requirements: str | None,
    capabilities: str | None,
    binding: str | None,
) -> tuple[int, dict[str, object]]:
    """Resolve validate defaults from the selected product and run offline checks."""

    try:
        workspace = resolve_workspace(workspace_selector)
        selected_target = workspace.selected_target
        if not selected_target:
            raise GarDomainError("workspace に selected_target がありません")
        root = workspace.local_root
        requirement_path = _path_or_default(requirements, root / "hardware" / "requirements.json")
        capability_path = _path_or_default(
            capabilities, gar_tools_root() / "targets" / selected_target / "hardware" / "capabilities.json"
        )
        binding_path = _path_or_default(binding, root / "hardware" / "bindings" / f"{selected_target}.json")
        report = validate_hardware_contract(
            requirements_path=requirement_path,
            capabilities_path=capability_path,
            binding_path=binding_path,
            selected_target_id=selected_target,
        )
        payload = report.as_dict()
        payload["workspace"] = workspace.name
        return report.exit_code, payload
    except GarDomainError as error:
        return 1, {
            "schema_version": 1,
            "command": "hw.validate",
            "ok": False,
            "exit_code": 1,
            "workspace": workspace_selector,
            "product": None,
            "target_id": None,
            "platform": None,
            "paths": {
                "requirements": requirements,
                "capabilities": capabilities,
                "binding": binding,
            },
            "assignments": [],
            "errors": [{"code": "workspace_unavailable", "message": str(error)}],
        }


def _path_or_default(value: str | None, default: Path) -> Path:
    if value is None:
        return default
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path.cwd() / path
