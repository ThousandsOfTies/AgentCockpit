"""Workspace registration phase for ``gar setup``."""

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

from scripts.gar_lib.core.config import (
    save_config,
    saved_workspaces,
    set_saved_workspaces,
)
from scripts.gar_lib.vscode.terminal_ui import (
    BLUE,
    BOLD,
    DIM,
    GREEN,
    RED,
    YELLOW,
    safe_input,
    style,
)


def configure_workspace_root(config: dict) -> str | None:
    """Edit registered workspaces and return the workspace to configure now."""

    workspaces = saved_workspaces(config)
    print(style("Product Workspaces:", BOLD, BLUE))
    if not sys.stdin.isatty():
        if workspaces:
            print(f"  {style('設定済み', GREEN)}")
            for entry in workspaces:
                print_workspace_entry(entry, indent="    - ")
        else:
            print(f"  {style('未設定', YELLOW)} 対話的に `gar setup` を実行して登録してください。")
        return workspaces[0]["id"] if len(workspaces) == 1 else None

    changed = False
    while True:
        if workspaces:
            print(f"  {style('設定済み:', GREEN)}")
            for index, entry in enumerate(workspaces, start=1):
                print_workspace_entry(entry, indent=f"    {index}. ")
        else:
            print(f"  {style('未設定', YELLOW)}")

        action = (
            safe_input(
                "  workspaceを追加(a)、削除(d)、修正(e)、次へ(Enter): ",
                default_on_eof="",
            )
            .strip()
            .lower()
        )
        if not action:
            break
        if action in {"a", "add", "追加"}:
            changed |= _add_workspace(workspaces)
            continue
        if action in {"d", "delete", "削除"}:
            changed |= _delete_workspace(workspaces)
            continue
        if action in {"e", "edit", "modify", "修正"}:
            if _edit_workspace(workspaces):
                changed = True
                break
            continue
        print(f"  {style('a（追加）/ d（削除）/ e（修正）/ Enter（次へ）を入力してください。', YELLOW)}")

    if changed:
        set_saved_workspaces(config, workspaces)
        save_config(config)

    return _select_active_workspace(config, workspaces)


def _add_workspace(workspaces: list[dict]) -> bool:
    entry = prompt_workspace_entry()
    if entry is None:
        return False
    if workspace_duplicate(entry, workspaces):
        print(f"  {style('既に登録済みです:', YELLOW)} {entry['name']}")
        return False
    workspaces.append(entry)
    print(f"  {style('追加しました:', GREEN)} {entry['name']}")
    return True


def _delete_workspace(workspaces: list[dict]) -> bool:
    if not workspaces:
        print(f"  {style('削除できる workspace がありません。', YELLOW)}")
        return False
    answer = safe_input("  削除する番号: ", default_on_eof="").strip()
    try:
        index = int(answer) - 1
        removed = workspaces.pop(index)
    except (ValueError, IndexError):
        print(f"  {style('番号が正しくありません。', RED)}")
        return False
    print(f"  {style('削除しました:', GREEN)} {removed['name']}")
    return True


def _edit_workspace(workspaces: list[dict]) -> bool:
    if not workspaces:
        print(f"  {style('修正できる workspace がありません。', YELLOW)}")
        return False
    answer = safe_input("  修正する番号: ", default_on_eof="").strip()
    try:
        index = int(answer) - 1
        previous = workspaces[index]
    except (ValueError, IndexError):
        print(f"  {style('番号が正しくありません。', RED)}")
        return False

    entry = prompt_workspace_entry(existing=previous)
    if entry is None:
        return False
    other_entries = [candidate for candidate in workspaces if candidate["id"] != previous["id"]]
    if workspace_duplicate(entry, other_entries):
        print(f"  {style('既に登録済みです:', YELLOW)} {entry['name']}")
        return False
    workspaces[index] = entry
    print(f"  {style('修正しました:', GREEN)} {entry['name']}")
    return True


def _select_active_workspace(config: dict, workspaces: list[dict]) -> str | None:
    if not workspaces:
        return None
    active_id = config.get("workspace_id")
    if isinstance(active_id, str) and any(entry["id"] == active_id for entry in workspaces):
        return active_id
    if len(workspaces) == 1:
        return workspaces[0]["id"]

    while True:
        answer = safe_input("  設定する workspace の番号 [1]: ", default_on_eof="1").strip()
        if not answer:
            return workspaces[0]["id"]
        try:
            return workspaces[int(answer) - 1]["id"]
        except (ValueError, IndexError):
            print(f"  {style('番号が正しくありません。', RED)}")


def print_workspace_entry(entry: dict, *, indent: str) -> None:
    connection = entry["connection"]
    type_label = {
        "local": "local",
        "codespaces": "Codespaces",
        "network": "network",
    }[connection["type"]]
    location = connection["path"]
    if connection["type"] == "codespaces":
        location = f"{connection['codespace']}:{location}"
    elif connection["type"] == "network":
        location = f"{connection['host']}:{location}"
    print(f"{indent}{style(entry['name'], BOLD)} ({type_label} · {entry['branch']})")
    print(f"       {style(location, DIM)}")


def workspace_duplicate(candidate: dict, entries: Sequence[dict]) -> bool:
    if any(entry["name"] == candidate["name"] for entry in entries):
        return True
    connection = candidate["connection"]
    fingerprint = (
        connection["type"],
        connection.get("codespace") or connection.get("host") or "",
        connection["path"],
        candidate["branch"],
    )
    return any(
        (
            entry["connection"]["type"],
            entry["connection"].get("codespace") or entry["connection"].get("host") or "",
            entry["connection"]["path"],
            entry["branch"],
        )
        == fingerprint
        for entry in entries
    )


def default_workspace_name(connection_type: str, product_name: str) -> str:
    """Return the concise, user-facing selector for a workspace."""

    type_label = {
        "local": "Local",
        "codespaces": "Codespaces",
        "network": "Network",
    }[connection_type]
    return f"{type_label}/{product_name}"


def default_workspace_product_name(branch: str, workspace_path: str) -> str:
    """Prefer the product branch over gar-build-env's shared remote name."""

    if branch != "main":
        return branch
    return Path(workspace_path).name or "workspace"


def prompt_workspace_entry(
    connection_type: str | None = None,
    *,
    existing: dict | None = None,
    path_override: str | None = None,
) -> dict | None:
    connection = existing.get("connection", {}) if existing else {}
    selected_type = connection_type or connection.get("type")
    if selected_type is None:
        print("  接続種別を選択してください:")
        print("    1. Codespaces")
        print("    2. Local")
        print("    3. Network (SSH)")
        selected = safe_input("  番号 [2]: ", default_on_eof="").strip() or "2"
        selected_type = {"1": "codespaces", "2": "local", "3": "network"}.get(selected)
        if selected_type is None:
            print(f"  {style('番号が正しくありません。', RED)}")
            return None

    if selected_type == "local":
        workspace_connection, branch = _prompt_local_connection(connection, path_override)
    elif selected_type == "codespaces":
        workspace_connection, branch = _prompt_codespaces_connection(connection)
    else:
        workspace_connection, branch = _prompt_network_connection(connection)
    if workspace_connection is None:
        return None

    if not branch:
        branch = safe_input("  branch [main]: ", default_on_eof="main").strip() or "main"
    product_name = default_workspace_product_name(branch, workspace_connection["path"])
    default_name = default_workspace_name(selected_type, product_name)
    name = (
        safe_input(
            f"  workspace名（--workspace に使用） [{default_name}]: ",
            default_on_eof=default_name,
        ).strip()
        or default_name
    )
    return {
        "id": existing["id"] if existing else f"ws_{uuid.uuid4().hex}",
        "name": name,
        "connection": workspace_connection,
        "branch": branch,
    }


def _prompt_local_connection(
    connection: dict,
    path_override: str | None,
) -> tuple[dict | None, str | None]:
    default_path = path_override or connection.get("path", "")
    answer = (
        path_override
        or safe_input(
            f"  local path{f' [{default_path}]' if default_path else ''}: ",
            default_on_eof=default_path,
        ).strip()
        or default_path
    )
    if not answer:
        return None, None
    path = Path(answer).expanduser().resolve()
    if not path.is_dir():
        print(f"  {style('存在しない directory です:', RED)} {path}")
        return None, None
    return {"type": "local", "path": str(path)}, probe_git_workspace(["git", "-C", str(path)])[1]


def _prompt_codespaces_connection(connection: dict) -> tuple[dict | None, str | None]:
    print_codespace_candidates()
    default_codespace = connection.get("codespace", "")
    codespace = (
        safe_input(
            f"  Codespace名{f' [{default_codespace}]' if default_codespace else ''}: ",
            default_on_eof=default_codespace,
        ).strip()
        or default_codespace
    )
    if not codespace:
        return None, None
    default_path = connection.get("path", "/workspaces/gar-build-env")
    path = (
        safe_input(
            f"  Codespace内の path [{default_path}]: ",
            default_on_eof=default_path,
        ).strip()
        or default_path
    )
    branch = probe_git_workspace(["gh", "codespace", "ssh", "-c", codespace, "--", "git", "-C", path])[1]
    return {"type": "codespaces", "codespace": codespace, "path": path}, branch


def _prompt_network_connection(connection: dict) -> tuple[dict | None, str | None]:
    default_host = connection.get("host", "")
    host = (
        safe_input(
            f"  IP address または SSH host{f' [{default_host}]' if default_host else ''}: ",
            default_on_eof=default_host,
        ).strip()
        or default_host
    )
    if not host:
        return None, None
    default_path = connection.get("path", "")
    path = (
        safe_input(
            f"  remote path{f' [{default_path}]' if default_path else ''}: ",
            default_on_eof=default_path,
        ).strip()
        or default_path
    )
    if not path:
        return None, None
    branch = probe_git_workspace(["ssh", host, "git", "-C", path])[1]
    return {"type": "network", "host": host, "path": path}, branch


def print_codespace_candidates() -> None:
    if shutil.which("gh") is None:
        return
    result = subprocess.run(
        ["gh", "codespace", "list"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        print(f"  {style('利用可能な Codespaces:', DIM)}")
        for line in result.stdout.splitlines():
            print(f"    {line}")


def probe_git_workspace(command_prefix: list[str]) -> tuple[str | None, str | None]:
    try:
        branch_result = subprocess.run(
            [*command_prefix, "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        repo_result = subprocess.run(
            [*command_prefix, "config", "--get", "remote.origin.url"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return None, None
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    remote = repo_result.stdout.strip() if repo_result.returncode == 0 else ""
    repo_name = Path(remote.removesuffix(".git")).name if remote else None
    return repo_name, branch
