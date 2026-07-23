from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, Query


ROOT = Path(__file__).resolve().parents[4]
TRACE_PATH = ROOT / "runtime_traces.txt"
QUERY_LOG_PATH = Path(__file__).resolve().parents[1] / "cypher_query.txt"


def _display_name(node, fallback: str) -> str:
    if node is None:
        return fallback
    for key in ("symbol", "name", "labelV"):
        value = node.get(key)
        if value not in (None, ""):
            return str(value)
    labels = list(node.labels) if hasattr(node, "labels") else []
    if labels:
        return labels[0]
    return fallback


def _component_name(node, fallback: str) -> str:
    if node is None:
        return fallback
    for key in ("name", "labelV"):
        value = node.get(key)
        if value not in (None, ""):
            return str(value)
    labels = list(node.labels) if hasattr(node, "labels") else []
    if labels:
        return labels[0]
    return fallback


def main() -> int:
    load_dotenv()

    uri = os.getenv("NEO4J_URI", os.getenv("NEO4J_BOLT_URI", "bolt://localhost:7687"))
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise SystemExit("NEO4J_PASSWORD is not set in the environment")

    if not QUERY_LOG_PATH.exists():
        raise SystemExit(f"Cypher query file not found: {QUERY_LOG_PATH}")
    query = QUERY_LOG_PATH.read_text(encoding="utf-8").strip()
    if not query:
        raise SystemExit(f"Cypher query file is empty: {QUERY_LOG_PATH}")

    query_obj = Query(query)  # pyright: ignore[reportArgumentType]

    rows: list[dict[str, object]] = []
    active_uri = uri
    uris_to_try = [uri]
    if uri.startswith("neo4j://"):
        uris_to_try.append("bolt://" + uri[len("neo4j://") :])

    last_error: Exception | None = None

    for candidate_uri in uris_to_try:
        driver = GraphDatabase.driver(candidate_uri, auth=(username, password))
        try:
            driver.verify_connectivity()
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

    try:

        required_columns = {"callerFunction", "client", "calleeFunction", "server", "interfaceName"}
        if rows:
            available = set(rows[0].keys())
            missing = required_columns - available
            if missing:
                raise SystemExit(
                    "Cypher query output missing required columns for runtime traces: "
                    f"{sorted(missing)}. Available columns: {sorted(available)}"
                )

        base_time = datetime.now(timezone.utc)
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="|", lineterminator="\n")
            writer.writerow(
                [
                    "EventTimestamp",
                    "EventName",
                    "ClientComponent",
                    "ClientFunction",
                    "ServerComponent",
                    "ServerFunction",
                    "RelationshipType",
                    "InterfaceNames",
                ]
            )
            for index, row in enumerate(rows):
                client_function = str(row.get("callerFunction", "UnknownClientFunction"))
                server_function = str(row.get("calleeFunction", "UnknownServerFunction"))
                client_component = str(row.get("client", "UnknownClientComponent"))
                server_component = str(row.get("server", "UnknownServerComponent"))
                timestamp = (base_time + timedelta(milliseconds=index)).isoformat().replace("+00:00", "Z")
                writer.writerow(
                    [
                        timestamp,
                        server_function,
                        client_component,
                        client_function,
                        server_component,
                        server_function,
                        "Command",
                        row.get("interfaceName", "CppCalls"),
                    ]
                )

        print(f"Connected to: {active_uri} as {username}")
        print(f"Trace rows written: {len(rows)}")
        print(f"Trace log written to: {TRACE_PATH}")
        print(f"Query source: {QUERY_LOG_PATH}")
        return 0
    finally:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
