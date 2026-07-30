#!/usr/bin/env python3
"""gar_lib の module 依存 DSM と公開メンバ参照状況を再生成するツール。

Usage:
    .venv/bin/python3 tools/gen_gar_lib_dsm.py
    .venv/bin/python3 tools/gen_gar_lib_dsm.py --check

以下の3ファイルを repo ルートに (再)生成します:
  - GAR_LIB_DSM.md               package粒度のDSM表とサマリ
  - GAR_LIB_DSM_file_level.csv    file粒度の依存matrix (要素数は自動算出)
  - GAR_LIB_PUBLIC_API_USAGE.md   公開メンバ(top-level関数/class/定数)の参照元一覧

解析は import 文の静的解析のみで行うため、`getattr`/動的import/文字列参照
(`mock.patch("scripts.gar_lib....")` 等) 経由の参照は数え漏れる場合があります。
"""

from __future__ import annotations

import argparse
import ast
import csv
import io
import math
import sys
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCAN_ROOTS = [REPO / "scripts", REPO / "tests"]
GAR_LIB_PREFIX = "scripts.gar_lib"


@dataclass(frozen=True)
class ModuleInfo:
    """One parsed Python module and the public definitions declared in it."""

    path: Path
    tree: ast.Module
    public_definitions: dict[str, int]


@dataclass(frozen=True)
class ImportBinding:
    """A local import name and the module/member to which it resolves."""

    local_name: str
    target_module: str
    target_member: str | None


def iter_py_files() -> Iterator[Path]:
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.py")):
            if "__pycache__" in p.parts or ".venv" in p.parts:
                continue
            yield p
    gar_script = REPO / "scripts" / "gar"
    if gar_script.exists():
        yield gar_script


def module_name(path: Path) -> str:
    rel = path.relative_to(REPO)
    if rel.name == "gar" and rel.parent.name == "scripts":
        return "scripts.gar(entrypoint)"
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def is_public(name: str) -> bool:
    return not name.startswith("_")


def short_name(mod: str) -> str:
    if mod.startswith(GAR_LIB_PREFIX + "."):
        return mod[len(GAR_LIB_PREFIX) + 1 :]
    if mod == GAR_LIB_PREFIX:
        return "(top-level __init__)"
    return mod


def package_of(mod: str) -> str:
    if mod == "scripts.gar(entrypoint)":
        return "scripts.gar(entrypoint)"
    if mod.startswith("tests."):
        return "tests"
    parts = mod.split(".")
    if len(parts) <= 3:
        return "gar_lib(top-level)"
    return short_name(".".join(parts[:3]))


def file_tree_distance(left: Path, right: Path) -> int:
    """Return the number of tree edges between two repository files."""

    left_parts = left.relative_to(REPO / "scripts" / "gar_lib").parts
    right_parts = right.relative_to(REPO / "scripts" / "gar_lib").parts
    common = 0
    for left_part, right_part in zip(left_parts, right_parts, strict=False):
        if left_part != right_part:
            break
        common += 1
    return len(left_parts) + len(right_parts) - (2 * common)


def resolve_relative(current_mod: str, is_package: bool, level: int, module: str | None) -> list[str]:
    parts = current_mod.split(".")
    base_parts = parts if is_package else parts[:-1]
    if level > 1:
        base_parts = base_parts[: len(base_parts) - (level - 1)]
    if module:
        base_parts = base_parts + module.split(".")
    return base_parts


def sync_generated_file(path: Path, contents: str, *, check: bool) -> bool:
    """Write one generated file, or report whether its checked-in copy matches."""

    if check:
        try:
            with path.open("r", encoding="utf-8", newline="") as current_file:
                current_contents = current_file.read()
        except OSError:
            print(f"out of date: {path} does not exist", file=sys.stderr)
            return False
        if current_contents != contents:
            print(f"out of date: {path}", file=sys.stderr)
            return False
        print(f"up to date: {path}")
        return True

    path.write_text(contents, encoding="utf-8", newline="")
    print(f"wrote {path}")
    return True


def generate(*, check: bool = False) -> int:
    files = list(iter_py_files())
    modules: dict[str, ModuleInfo] = {}
    syntax_errors: list[str] = []

    for path in files:
        mod = module_name(path)
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as exc:
            syntax_errors.append(f"SYNTAX ERROR in {path}: {exc}")
            continue
        public_definitions: dict[str, int] = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if is_public(node.name):
                    public_definitions[node.name] = node.lineno
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and is_public(t.id) and t.id.isupper():
                        public_definitions[t.id] = node.lineno
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and is_public(node.target.id) and node.target.id.isupper():
                    public_definitions[node.target.id] = node.lineno
        modules[mod] = ModuleInfo(
            path=path,
            tree=tree,
            public_definitions=public_definitions,
        )

    if syntax_errors:
        for message in syntax_errors:
            print(message, file=sys.stderr)
        print("Generation aborted; existing DSM files were not changed.", file=sys.stderr)
        return 1

    module_set = set(modules.keys())
    local_bindings: dict[str, list[ImportBinding]] = defaultdict(list)

    for mod, module in modules.items():
        is_package = module.path.name == "__init__.py"
        for node in ast.walk(module.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    bound = alias.asname or alias.name.split(".")[0]
                    local_bindings[mod].append(ImportBinding(bound, target, None))
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    base_parts = resolve_relative(mod, is_package, node.level, node.module)
                else:
                    base_parts = (node.module or "").split(".")
                target_module = ".".join(base_parts)
                for alias in node.names:
                    bound = alias.asname or alias.name
                    candidate_submodule = f"{target_module}.{alias.name}" if target_module else alias.name
                    if candidate_submodule in module_set:
                        local_bindings[mod].append(ImportBinding(bound, candidate_submodule, None))
                    else:
                        local_bindings[mod].append(ImportBinding(bound, target_module, alias.name))

    dep_edges: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for mod, bindings in local_bindings.items():
        for binding in bindings:
            if binding.target_module.startswith(GAR_LIB_PREFIX) and binding.target_module != mod:
                dep_edges[mod][binding.target_module] += 1

    usage: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for mod, module in modules.items():
        bindings = local_bindings.get(mod, [])
        name_map: dict[str, tuple[str, str]] = {}
        module_alias_map: dict[str, str] = {}
        for binding in bindings:
            if binding.target_member is not None:
                name_map[binding.local_name] = (binding.target_module, binding.target_member)
            else:
                module_alias_map[binding.local_name] = binding.target_module

        for node in ast.walk(module.tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in name_map:
                    def_mod, symbol = name_map[node.id]
                    usage[(def_mod, symbol)][mod] += 1
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id in module_alias_map:
                    def_mod = module_alias_map[node.value.id]
                    usage[(def_mod, node.attr)][mod] += 1

    gar_lib_modules = sorted(m for m in modules if m.startswith(GAR_LIB_PREFIX))

    # --- file_level_dsm.csv ---
    csv_path = REPO / "GAR_LIB_DSM_file_level.csv"
    csv_buffer = io.StringIO(newline="")
    csv_writer = csv.writer(csv_buffer)
    header = [short_name(m) for m in gar_lib_modules]
    csv_writer.writerow(["consumer \\ provider"] + header)
    for consumer in gar_lib_modules:
        row = [short_name(consumer)]
        for provider in gar_lib_modules:
            row.append(dep_edges.get(consumer, {}).get(provider, 0))
        csv_writer.writerow(row)
    csv_contents = csv_buffer.getvalue()

    # --- package-level DSM ---
    packages = sorted(set(package_of(m) for m in modules))
    pkg_edges: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for mod, targets in dep_edges.items():
        for target_module, count in targets.items():
            pkg_edges[package_of(mod)][package_of(target_module)] += count

    lines = []
    lines.append("# gar_lib 依存関係 DSM (Design Structure Matrix)")
    lines.append("")
    lines.append(
        "`tools/gen_gar_lib_dsm.py` により import 文の静的解析から自動生成。"
        " 再生成: `.venv/bin/python3 tools/gen_gar_lib_dsm.py`"
    )
    lines.append("")
    lines.append(
        "読み方: **行 (consumer)** が **列 (provider)** を import している数。"
        " 空欄 = 依存なし。対角線 (同一package内) は集計から除外。"
    )
    lines.append("")
    lines.append("## package粒度 DSM")
    lines.append("")
    lines.append("| consumer \\\\ provider | " + " | ".join(packages) + " |")
    lines.append("|---|" + "---|" * len(packages))
    for consumer in packages:
        cells = []
        for provider in packages:
            v = pkg_edges.get(consumer, {}).get(provider, 0)
            cells.append(str(v) if v else "")
        lines.append(f"| **{consumer}** | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        f"file粒度 ({len(gar_lib_modules)}x{len(gar_lib_modules)}) の完全なmatrixは"
        " `GAR_LIB_DSM_file_level.csv` を参照 (Excel/sheetsで開くと見やすい)。"
    )
    lines.append("")
    file_edges = [
        (consumer, provider, count)
        for consumer, providers in dep_edges.items()
        if consumer in gar_lib_modules
        for provider, count in providers.items()
        if provider in gar_lib_modules
    ]
    distances = sorted(
        file_tree_distance(modules[consumer].path, modules[provider].path) for consumer, provider, _count in file_edges
    )
    weighted_distance_sum = sum(
        file_tree_distance(modules[consumer].path, modules[provider].path) * count
        for consumer, provider, count in file_edges
    )
    binding_count = sum(count for _consumer, _provider, count in file_edges)
    mean_distance = sum(distances) / len(distances) if distances else 0.0
    weighted_mean_distance = weighted_distance_sum / binding_count if binding_count else 0.0
    p95_distance = distances[math.ceil(len(distances) * 0.95) - 1] if distances else 0
    max_distance = distances[-1] if distances else 0
    lines.append("## file配置距離")
    lines.append("")
    lines.append(
        "各Pythonファイルをtreeのleaf、import元→import先の一意な組を1 edgeとして、"
        "最短pathに含まれるtree edge数を測定。平均だけでなく外れ値も確認できるよう"
        "p95と最大値を併記する。"
    )
    lines.append("")
    lines.append(f"- 一意なfile依存edge数: {len(file_edges)}")
    lines.append(f"- 平均path長: {mean_distance:.3f}")
    lines.append(f"- import binding数による加重平均path長: {weighted_mean_distance:.3f}")
    lines.append(f"- p95 / 最大path長: {p95_distance} / {max_distance}")
    lines.append("")
    lines.append("## 公開メンバの参照状況サマリ")
    lines.append("")
    total_members = sum(len(modules[m].public_definitions) for m in gar_lib_modules)
    unused = [
        (m, n)
        for m in gar_lib_modules
        for n in modules[m].public_definitions
        if sum(v for k, v in usage.get((m, n), {}).items() if k != m) == 0
    ]
    lines.append(f"- 対象module数: {len(gar_lib_modules)}")
    lines.append(f"- 公開メンバ(top-level関数/class/UPPER定数)総数: {total_members}")
    lines.append(
        f"- 他moduleから一度も参照されていないメンバ: {len(unused)}"
        "  (詳細は `GAR_LIB_PUBLIC_API_USAGE.md` の「外部未参照」表)"
    )
    lines.append("")
    lines.append("詳細な「メンバ単位でどこから参照されているか」は" " `GAR_LIB_PUBLIC_API_USAGE.md` を参照。")
    lines.append("")
    dsm_contents = "\n".join(lines) + "\n"

    # --- public API usage ---
    lines2 = []
    lines2.append("# gar_lib 公開メンバ参照一覧")
    lines2.append("")
    lines2.append(
        "`tools/gen_gar_lib_dsm.py` により自動生成。"
        " 各moduleのtop-level公開関数/class/UPPER定数が、どのmoduleから参照されているかを一覧化。"
    )
    lines2.append("")
    lines2.append(
        '注意: 静的なimport解析のみのため、`mock.patch("...")` の文字列指定や'
        " `getattr` 経由の参照は数え漏れることがあります。"
    )
    lines2.append("")

    for mod in gar_lib_modules:
        defs = modules[mod].public_definitions
        if not defs:
            continue
        lines2.append(f"## `{short_name(mod)}` ({modules[mod].path.relative_to(REPO)})")
        lines2.append("")
        lines2.append("| メンバ | 行 | 参照元module (回数) |")
        lines2.append("|---|---:|---|")
        for name in sorted(defs, key=lambda n: defs[n]):
            refs = usage.get((mod, name), {})
            external = {k: v for k, v in refs.items() if k != mod}
            if external:
                refs_str = ", ".join(f"{short_name(k)}({v})" for k, v in sorted(external.items()))
            else:
                refs_str = "_(外部参照なし)_"
            lines2.append(f"| `{name}` | {defs[name]} | {refs_str} |")
        lines2.append("")

    lines2.append("## 外部未参照の公開メンバ一覧")
    lines2.append("")
    lines2.append(
        "同一module内でしか使われていない (または全く未使用の) 公開メンバ。" " private化 (`_`prefix) や整理の候補。"
    )
    lines2.append("")
    lines2.append("| module | メンバ | 行 |")
    lines2.append("|---|---|---:|")
    for mod, name in sorted(unused):
        lines2.append(f"| `{short_name(mod)}` | `{name}` | {modules[mod].public_definitions[name]} |")

    public_api_contents = "\n".join(lines2) + "\n"
    generated_files = (
        (csv_path, csv_contents),
        (REPO / "GAR_LIB_DSM.md", dsm_contents),
        (REPO / "GAR_LIB_PUBLIC_API_USAGE.md", public_api_contents),
    )
    file_results = [sync_generated_file(path, contents, check=check) for path, contents in generated_files]
    files_match = all(file_results)
    print(f"modules={len(gar_lib_modules)} public_members={total_members} unused={len(unused)}")
    return 0 if files_match else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="generated filesを変更せず、checked-in内容が最新か確認します",
    )
    args = parser.parse_args(argv)
    return generate(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
