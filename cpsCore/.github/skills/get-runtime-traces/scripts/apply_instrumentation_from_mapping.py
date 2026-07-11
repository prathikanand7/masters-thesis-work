from __future__ import annotations

import argparse
import csv
from pathlib import Path

INCLUDE_LINE = '#include "cpsCore/Utilities/Runtime/Instrumentation.hpp"'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply TRACE_FUNCTION_SCOPE from mapping CSV")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--mapping-path", type=Path, required=True)
    return parser.parse_args()


def ensure_include(lines: list[str]) -> list[str]:
    if any(INCLUDE_LINE in line for line in lines):
        return lines

    insert_at = 0
    for index, line in enumerate(lines):
        if line.strip().startswith("#include"):
            insert_at = index + 1

    lines.insert(insert_at, INCLUDE_LINE + "\n")
    return lines


def find_scope_insertion_line(lines: list[str], start_idx: int) -> int | None:
    for index in range(start_idx, min(start_idx + 40, len(lines))):
        if "{" in lines[index]:
            return index + 1
    return None


def already_instrumented(lines: list[str], from_idx: int) -> bool:
    for index in range(from_idx, min(from_idx + 10, len(lines))):
        if "TRACE_FUNCTION_SCOPE(" in lines[index]:
            return True
    return False


def try_find_signature_line(lines: list[str], search_token: str) -> int | None:
    patterns = [
        f"{search_token}(",
        search_token,
    ]

    if "::" in search_token:
        short_name = search_token.split("::")[-1]
        patterns.append(f"::{short_name}(")
        patterns.append(short_name + "(")

    for index, line in enumerate(lines):
        for pattern in patterns:
            if pattern in line:
                return index

    return None


def apply_trace(lines: list[str], search_token: str, component: str, function: str) -> bool:
    signature_idx = try_find_signature_line(lines, search_token)
    if signature_idx is None:
        return False

    insert_idx = find_scope_insertion_line(lines, signature_idx)
    if insert_idx is None:
        return False

    if already_instrumented(lines, insert_idx):
        return False

    indent = "    "
    if insert_idx < len(lines):
        candidate = lines[insert_idx]
        indent = candidate[: len(candidate) - len(candidate.lstrip())] or "    "

    lines.insert(insert_idx, f'{indent}TRACE_FUNCTION_SCOPE("{component}", "{function}");\n')
    return True


def main() -> int:
    args = parse_args()
    workspace_root = args.workspace_root.resolve()

    if not args.mapping_path.exists():
        raise SystemExit(f"Mapping file not found: {args.mapping_path}")

    grouped: dict[Path, list[dict[str, str]]] = {}
    with args.mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            file_path = workspace_root / row["file"]
            grouped.setdefault(file_path, []).append(row)

    updated = 0
    for file_path, rows in grouped.items():
        if not file_path.exists():
            continue

        lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
        original = list(lines)

        lines = ensure_include(lines)
        for row in rows:
            apply_trace(lines, row["search_token"], row["component"], row["function"])

        if lines != original:
            file_path.write_text("".join(lines), encoding="utf-8")
            updated += 1

    print(f"Instrumented files updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
