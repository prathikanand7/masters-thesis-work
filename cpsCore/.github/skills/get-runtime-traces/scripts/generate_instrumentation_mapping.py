from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, Query


SKILL_DIR = Path(__file__).resolve().parents[1]


def normalize_repo_path(path_value: str) -> str | None:
    normalized = path_value.replace("\\", "/")
    match = re.search(r"(src/.+)$", normalized)
    if not match:
        return None
    return match.group(1)


def function_search_token(qualified_name: str) -> tuple[str, str]:
    name = qualified_name.split("/")[-1].strip()
    name = name.split("(")[0].strip()
    if not name:
        return qualified_name, "unknown"

    if "::" in name:
        function_label = name.split("::")[-1]
        if function_label.startswith("~"):
            function_label = "dtor"
        elif function_label and function_label == name.split("::")[-2]:
            function_label = "ctor"
        return name, function_label

    return name, name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate instrumentation mapping from Neo4j CppCalls graph")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--mapping-path", type=Path, required=True)
    parser.add_argument("--query-log-path", type=Path, default=SKILL_DIR / "cypher_query.txt")
    return parser.parse_args()


def load_query(path: Path) -> str:
    if not path.exists():
        raise SystemExit(f"Cypher query file not found: {path}")
    query = path.read_text(encoding="utf-8").strip()
    if not query:
        raise SystemExit(f"Cypher query file is empty: {path}")
    return query


def main() -> int:
    args = parse_args()
    workspace_root = args.workspace_root.resolve()

    load_dotenv(workspace_root / ".env")

    uri = os.getenv("NEO4J_URI", os.getenv("NEO4J_BOLT_URI", "bolt://localhost:7687"))
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise SystemExit("NEO4J_PASSWORD is not set in .env")

    query = load_query(args.query_log_path)

    query_obj = Query(query)  # pyright: ignore[reportArgumentType]

    rows: list[dict[str, object]] = []
    active_uri = uri
    uris_to_try = [uri]
    if uri.startswith("neo4j://"):
        uris_to_try.append("bolt://" + uri[len("neo4j://") :])

    last_error: Exception | None = None
    for candidate_uri in uris_to_try:
        driver = GraphDatabase.driver(candidate_uri, auth=(user, password))
        try:
            with driver.session(database="neo4j") as session:
                rows = [record.data() for record in session.run(query_obj)]
            active_uri = candidate_uri
            break
        except Exception as exc:
            last_error = exc
        finally:
            driver.close()

    if not rows and last_error is not None:
        raise SystemExit(str(last_error))

    required_columns = {"callerFile", "callerComponent", "callerFunctionQualified"}
    if rows:
        available = set(rows[0].keys())
        missing = required_columns - available
        if missing:
            raise SystemExit(
                "Cypher query output missing required columns for mapping generation: "
                f"{sorted(missing)}. Available columns: {sorted(available)}"
            )

    mapping_rows: list[dict[str, str]] = []
    for row in rows:
        caller_file = row.get("callerFile")
        component = row.get("callerComponent")
        qualified = row.get("callerFunctionQualified")

        if not caller_file or not component or not qualified:
            continue

        rel_path = normalize_repo_path(str(caller_file))
        if not rel_path:
            continue

        abs_path = workspace_root / rel_path
        if not abs_path.exists():
            continue

        search_token, function_label = function_search_token(str(qualified))
        mapping_rows.append(
            {
                "file": rel_path,
                "search_token": search_token,
                "component": str(component),
                "function": function_label,
            }
        )

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in mapping_rows:
        key = (item["file"], item["search_token"], item["component"], item["function"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    args.mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with args.mapping_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "search_token", "component", "function"])
        writer.writeheader()
        writer.writerows(deduped)

    print(f"Connected to: {active_uri} as {user}")
    print(f"Instrumentation mapping rows: {len(deduped)}")
    print(f"Mapping file: {args.mapping_path}")
    print(f"Cypher query source: {args.query_log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
