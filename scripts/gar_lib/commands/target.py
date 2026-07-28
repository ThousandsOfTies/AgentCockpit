"""CLI adapter for ``gar target <action>``."""

from __future__ import annotations

import sys
from argparse import Namespace
from collections.abc import Callable

from scripts.gar_lib.api import Gar, Target
from scripts.gar_lib.commands.common.workspace import workspace_for
from scripts.gar_lib.core.command import GarCommand
from scripts.gar_lib.core.errors import AccessConnectionError, GarDomainError
from scripts.gar_lib.recovery.access import report_access_failure

TargetAction = Callable[[Target], int]


def run_target_command(args: Namespace) -> int:
    """Resolve a workspace and invoke the method selected by argparse."""

    command: GarCommand = args.gar_command
    if command.group != "target":
        raise GarDomainError(f"target command ではありません: {command.group}")
    workspace_selector = getattr(args, "workspace", None)
    try:
        workspace = workspace_for(workspace_selector)
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1
    try:
        if command.subject is not None:
            raise GarDomainError(f"target commandにsubjectはありません: {command.subject}")
        action: TargetAction = args.action_handler
        return action(Gar(workspace).target)
    except AccessConnectionError as error:
        device = getattr(args, "device", None)
        return report_access_failure(
            error,
            workspace=workspace,
            retry_command=command.to_cli(
                workspace=workspace_selector,
                options=("--device", str(device)) if device else (),
            ),
            purpose="target",
        )
    except GarDomainError as error:
        print(f"gar: {error}", file=sys.stderr)
        return 1
