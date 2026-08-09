"""Run a Target-owned one-time recipe over SSH."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from uuid import uuid4

from scripts.gar_lib.access.ssh import SSH_CONNECTION_OPTIONS
from scripts.gar_lib.core.errors import GarDomainError


def prepare_ssh_target(host: str, recipe: Path, *, config_path: Path | None = None) -> None:
    """Stage and run a validated Target recipe, asking for sudo when it needs it."""
    config = config_path or Path.home() / ".ssh" / "config"
    prepare_script = recipe / "prepare.sh"
    installer = recipe / "gar-target-install"
    service_template = recipe / "gar-app@.service"
    payloads = (prepare_script, installer, service_template)
    for payload in payloads:
        if payload.is_symlink() or not payload.is_file():
            raise GarDomainError(f"target prepare recipeの必須fileがありません: {payload}")
    user_result = subprocess.run(
        ("ssh", "-F", str(config), *SSH_CONNECTION_OPTIONS, "-o", f"HostKeyAlias={host}", host, "id -un"),
        check=False,
        capture_output=True,
        text=True,
    )
    if user_result.returncode != 0:
        detail = user_result.stderr.strip() or "SSH接続に失敗しました"
        raise GarDomainError(f"target prepare: {detail}")
    remote_user = user_result.stdout.strip()
    if not remote_user or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in remote_user
    ):
        raise GarDomainError("target prepare: SSH接続ユーザー名を安全に取得できません")

    stage = f"/tmp/gar-prepare-{uuid4().hex}"
    create = subprocess.run(
        (
            "ssh",
            "-F",
            str(config),
            *SSH_CONNECTION_OPTIONS,
            "-o",
            f"HostKeyAlias={host}",
            host,
            f"mkdir -m 0700 {shlex.quote(stage)}",
        ),
        check=False,
        capture_output=True,
        text=True,
    )
    if create.returncode != 0:
        detail = create.stderr.strip() or "一時directoryを作成できません"
        raise GarDomainError(f"target prepare: {detail}")

    try:
        copied = subprocess.run(
            (
                "scp",
                "-F",
                str(config),
                *SSH_CONNECTION_OPTIONS,
                "-o",
                f"HostKeyAlias={host}",
                *(str(payload) for payload in payloads),
                f"{host}:{stage}/",
            ),
            check=False,
            capture_output=True,
            text=True,
        )
        if copied.returncode != 0:
            detail = copied.stderr.strip() or "recipeを転送できません"
            raise GarDomainError(f"target prepare: {detail}")

        remote = (
            f"/bin/sh {shlex.quote(stage + '/prepare.sh')} "
            f"{shlex.quote(remote_user)} {shlex.quote(stage + '/gar-target-install')} "
            f"{shlex.quote(stage + '/gar-app@.service')}"
        )
        result = subprocess.run(
            (
                "ssh",
                "-tt",
                "-F",
                str(config),
                *SSH_CONNECTION_OPTIONS,
                "-o",
                f"HostKeyAlias={host}",
                host,
                remote,
            ),
            check=False,
        )
        if result.returncode != 0:
            raise GarDomainError("target prepare: Target recipeの実行に失敗しました")
    finally:
        subprocess.run(
            (
                "ssh",
                "-F",
                str(config),
                *SSH_CONNECTION_OPTIONS,
                "-o",
                f"HostKeyAlias={host}",
                host,
                f"rm -rf -- {shlex.quote(stage)}",
            ),
            check=False,
            capture_output=True,
            text=True,
        )
