"""File-based requests exchanged with the GAR VS Code terminal bridge.

The CLI, setup handoff, and MCP server all create the same JSON document.  This
module owns that document format and the filesystem safety checks, while each
caller still chooses where its ``.gar`` control directory lives.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_COMMAND_LENGTH = 4000
MAX_TITLE_LENGTH = 200
SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


@dataclass(frozen=True)
class TerminalRequest:
    """One command handed from GAR to a visible VS Code terminal."""

    id: str
    created_at: str
    title: str
    cwd: Path
    command: str
    reason: str | None = None

    @classmethod
    def create(
        cls,
        *,
        command: str,
        title: str,
        cwd: Path,
        reason: str | None = None,
    ) -> TerminalRequest:
        normalized_command = command.strip()
        if not normalized_command:
            raise ValueError("command is required")
        if len(normalized_command) > MAX_COMMAND_LENGTH:
            raise ValueError(f"command exceeds {MAX_COMMAND_LENGTH} character limit")
        if "\x00" in normalized_command:
            raise ValueError("command must not contain NUL bytes")

        normalized_title = title.strip()
        if not normalized_title:
            raise ValueError("title is required")
        if len(normalized_title) > MAX_TITLE_LENGTH:
            raise ValueError(f"title exceeds {MAX_TITLE_LENGTH} character limit")

        created_at = datetime.now(UTC)
        request_id = f"{created_at:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        return cls(
            id=request_id,
            created_at=created_at.isoformat(),
            title=normalized_title,
            cwd=cwd.expanduser().resolve(),
            command=normalized_command,
            reason=reason,
        )

    def to_payload(self) -> dict[str, str]:
        payload = {
            "id": self.id,
            "created_at": self.created_at,
            "title": self.title,
            "cwd": str(self.cwd),
            "command": self.command,
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class TerminalRequestStore:
    """Request and status directories used by one terminal bridge instance."""

    request_dir: Path
    status_dir: Path

    @classmethod
    def under(cls, gar_dir: Path) -> TerminalRequestStore:
        return cls(
            request_dir=gar_dir / "terminal-requests",
            status_dir=gar_dir / "terminal-status",
        )

    def create_request(
        self,
        *,
        command: str,
        title: str,
        cwd: Path,
        reason: str | None = None,
    ) -> tuple[TerminalRequest, Path]:
        request = TerminalRequest.create(
            command=command,
            title=title,
            cwd=cwd,
            reason=reason,
        )
        return request, self.write_request(request)

    def write_request(self, request: TerminalRequest) -> Path:
        """Atomically publish a complete request for the filesystem watcher."""

        self.request_dir.mkdir(parents=True, exist_ok=True)
        request_path = self.request_dir / f"{request.id}.json"
        serialized = json.dumps(request.to_payload(), ensure_ascii=False, indent=2) + "\n"

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{request.id}.",
            suffix=".tmp",
            dir=self.request_dir,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(serialized)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(request_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

        return request_path

    def list_statuses(self) -> list[dict[str, Any]]:
        if not self.status_dir.exists():
            return []

        statuses: list[dict[str, Any]] = []
        for path in sorted(self.status_dir.glob("*.json")):
            try:
                safe_path = self._safe_status_path(path.stem)
            except ValueError:
                statuses.append({"id": path.stem, "status": "invalid-path"})
                continue
            try:
                payload = json.loads(safe_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                statuses.append({"id": path.stem, "status": "invalid-json"})
                continue
            if isinstance(payload, dict):
                statuses.append(payload)
            else:
                statuses.append({"id": path.stem, "status": "invalid-json"})
        return statuses

    def read_status(self, request_id: str) -> dict[str, Any]:
        status_path = self._safe_status_path(request_id)
        if not status_path.exists():
            return {"id": request_id, "status": "unknown"}

        payload = json.loads(status_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"terminal status must be a JSON object: {request_id}")
        return payload

    def _safe_status_path(self, request_id: str) -> Path:
        normalized_id = request_id.strip()
        if not SAFE_REQUEST_ID.fullmatch(normalized_id):
            raise ValueError("id contains unsupported characters")

        status_root = self.status_dir.resolve()
        status_path = (status_root / f"{normalized_id}.json").resolve()
        try:
            status_path.relative_to(status_root)
        except ValueError as exc:  # Defensive check if the ID policy changes later.
            raise ValueError("id must resolve inside terminal-status") from exc
        return status_path
