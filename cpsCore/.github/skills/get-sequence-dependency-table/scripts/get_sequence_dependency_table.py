from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[4]
CSV_PATH = ROOT / "sequence_dependency_table.csv"
QUERY_LOG_PATH = Path(__file__).resolve().parents[1] / "cypher_query.txt"

DEPENDENCY_QUERY = """
MATCH (caller)-[:CppCalls]->(callee)
RETURN
    caller.name   AS callerName,
    caller.symbol AS callerSymbol,
    callee.name   AS calleeName,
    callee.symbol AS calleeSymbol
ORDER BY callerName, calleeName
""".strip()


def _path_of(name: str) -> str:
    """Extract the file path from a composite node id string.

    Node ids look like `cpp_funcdec//include/cpsCore/Aggregation/Aggregator.h/Aggregator.getAll`
    (kind, then path, then the qualified symbol as the final segment). Strip the
    kind prefix and the trailing symbol segment, leaving the file path.
    """
    if "//" not in name:
        return name
    _, rest = name.split("//", 1)
    if "/" not in rest:
        return "/" + rest
    path, _symbol = rest.rsplit("/", 1)
    return "/" + path


def _run_query(driver, cypher: str):
    with driver.session(database="neo4j") as session:
        return [record.data() for record in session.run(cypher)]


def main() -> int:
    load_dotenv()

    uri = os.getenv("NEO4J_URI", os.getenv("NEO4J_BOLT_URI", "bolt://localhost:7687"))
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise SystemExit("NEO4J_PASSWORD is not set in the environment")

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()

        rows = _run_query(driver, DEPENDENCY_QUERY)

        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        # No execution actually happened -- this is the static call graph, not a
        # runtime capture. EventTimestamp is a synthetic, strictly-increasing
        # per-row counter kept only so the CSV satisfies the schema consumed by
        # run_c2_static_only.py; it carries no real timing information.
        base_time = datetime(2000, 1, 1)
        with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "Sequence",
                    "EventName",
                    "ClientComponent",
                    "ClientFunction",
                    "ServerComponent",
                    "ServerFunction",
                    "RelationshipType",
                    "EventTimestamp",
                ],
            )
            writer.writeheader()
            for index, row in enumerate(rows, start=1):
                caller_symbol = row.get("callerSymbol") or ""
                callee_symbol = row.get("calleeSymbol") or ""
                writer.writerow(
                    {
                        "Sequence": index,
                        "EventName": callee_symbol,
                        "ClientComponent": _path_of(row.get("callerName") or ""),
                        "ClientFunction": caller_symbol,
                        "ServerComponent": _path_of(row.get("calleeName") or ""),
                        "ServerFunction": callee_symbol,
                        "RelationshipType": "Command",
                        "EventTimestamp": (base_time + timedelta(milliseconds=index)).isoformat() + "Z",
                    }
                )

        QUERY_LOG_PATH.write_text(DEPENDENCY_QUERY + "\n", encoding="utf-8")

        print(f"Connected to: {uri} as {username}")
        print(f"CppCalls edges found: {len(rows)}")
        print(f"CSV written to: {CSV_PATH}")
        print(f"Query log written to: {QUERY_LOG_PATH}")
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
