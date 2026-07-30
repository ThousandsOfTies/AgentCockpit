#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAR_DIR = ROOT / ".gar"
REQUEST_DIR = GAR_DIR / "terminal-requests"
STATUS_DIR = GAR_DIR / "terminal-status"

sys.path.insert(0, str(ROOT))

from scripts.gar_lib.vscode.terminal_requests import TerminalRequestStore  # noqa: E402, I001


TOOLS = [
    {
        "name": "run_in_visible_terminal",
        "description": (
            "Create a Gapless Agent Runtime request that the VSCode extension runs in a "
            "visible integrated terminal for human sudo/auth input."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run in the visible terminal.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory. Defaults to the Gapless Agent Runtime repo root.",
                },
                "title": {
                    "type": "string",
                    "description": "VSCode terminal title.",
                    "default": "Gapless Agent Runtime User Action",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_terminal_status",
        "description": "List Gapless Agent Runtime terminal request status files.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "get_terminal_status",
        "description": "Read one Gapless Agent Runtime terminal request status by id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Terminal request id.",
                }
            },
            "required": ["id"],
        },
    },
]


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            response = handle_request(request)
        except json.JSONDecodeError as exc:
            response = error_response(None, -32700, f"Parse error: {exc.msg}")
        except Exception as exc:  # Keep the MCP process alive on bad input.
            response = error_response(None, -32603, str(exc))

        if response is not None:
            print(json.dumps(response, ensure_ascii=False), flush=True)

    return 0


def handle_request(request: object) -> dict | None:
    if not isinstance(request, dict):
        return error_response(None, -32600, "Request must be a JSON object")

    request_id = request.get("id")
    if request.get("jsonrpc") != "2.0":
        return error_response(request_id, -32600, "jsonrpc must be '2.0'")

    method = request.get("method")
    if not isinstance(method, str) or not method:
        return error_response(request_id, -32600, "method must be a non-empty string")

    raw_params = request.get("params", {})
    if raw_params is None:
        params = {}
    elif isinstance(raw_params, dict):
        params = raw_params
    else:
        return error_response(request_id, -32602, "params must be a JSON object")

    # JSON-RPC notifications deliberately have no response. MCP clients may
    # send initialized, cancellation, progress, and future notifications that
    # this small server does not otherwise need to understand.
    if "id" not in request:
        return None

    if method == "initialize":
        return result_response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "gar-mcp",
                    "version": "0.0.1",
                },
            },
        )

    if method == "tools/list":
        return result_response(request_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return error_response(request_id, -32602, "tools/call requires a tool name")

        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return error_response(request_id, -32602, "tool arguments must be a JSON object")
        return result_response(request_id, call_tool(name, arguments))

    if method == "resources/list":
        return result_response(request_id, {"resources": []})

    if method == "prompts/list":
        return result_response(request_id, {"prompts": []})

    if method == "ping":
        return result_response(request_id, {})

    return error_response(request_id, -32601, f"Unknown method: {method}")


def call_tool(name: str, arguments: dict) -> dict:
    if name == "run_in_visible_terminal":
        return text_result(create_terminal_request(arguments))
    if name == "list_terminal_status":
        return text_result(json.dumps(list_terminal_status(), ensure_ascii=False, indent=2))
    if name == "get_terminal_status":
        return text_result(json.dumps(get_terminal_status(arguments), ensure_ascii=False, indent=2))

    return {
        "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
        "isError": True,
    }


def create_terminal_request(arguments: dict) -> str:
    command = str(arguments.get("command", ""))
    title = str(arguments.get("title") or "Gapless Agent Runtime User Action")
    raw_cwd = arguments.get("cwd")
    cwd = Path(str(raw_cwd)).resolve() if raw_cwd else ROOT
    try:
        cwd.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError(f"cwd must be inside the Gapless Agent Runtime repository ({ROOT}); got {cwd}") from exc

    store = TerminalRequestStore(request_dir=REQUEST_DIR, status_dir=STATUS_DIR)
    request, request_path = store.create_request(
        command=command,
        title=title,
        cwd=cwd,
    )

    return json.dumps(
        {
            "id": request.id,
            "request_path": str(request_path),
            "message": "Terminal request created. The VSCode extension will run it.",
        },
        ensure_ascii=False,
        indent=2,
    )


def list_terminal_status() -> list[dict]:
    store = TerminalRequestStore(request_dir=REQUEST_DIR, status_dir=STATUS_DIR)
    return store.list_statuses()


def get_terminal_status(arguments: dict) -> dict:
    request_id = str(arguments.get("id", "")).strip()
    if not request_id:
        raise ValueError("id is required")

    store = TerminalRequestStore(request_dir=REQUEST_DIR, status_dir=STATUS_DIR)
    return store.read_status(request_id)


def text_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def result_response(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


if __name__ == "__main__":
    raise SystemExit(main())
