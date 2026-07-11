from __future__ import annotations

import csv
import os
from collections import OrderedDict
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


ROOT = Path(__file__).resolve().parents[4]
CSV_PATH = ROOT / "interface_dependency_table.csv"
QUERY_LOG_PATH = Path(__file__).resolve().parents[1] / "cypher_query.txt"


def _component_expr(alias: str) -> str:
    return f"coalesce({alias}.labelV, head(labels({alias})), {alias}.name, toString(id({alias})))"


def _clean_list(values: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return sorted(cleaned, key=str.lower)


def _join_list(values: list[str]) -> str:
    return "; ".join(_clean_list(values))


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

    query_log = []
    inventory_query = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType"
    dependency_query = f"""
    MATCH (client)-[r]->(server)
    WITH
        type(r) AS InterfaceName,
        collect(DISTINCT {_component_expr('server')}) AS Servers,
        collect(DISTINCT {_component_expr('client')}) AS Clients
    RETURN InterfaceName, Servers, Clients
    ORDER BY InterfaceName
    """.strip()

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()

        inventory_rows = _run_query(driver, inventory_query)
        dependency_rows = _run_query(driver, dependency_query)

        query_log.extend(
            [
                "1. CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType",
                dependency_query,
            ]
        )

        CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CSV_PATH.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=["InterfaceName", "Server", "Client"])
            writer.writeheader()
            for row in dependency_rows:
                writer.writerow(
                    {
                        "InterfaceName": row.get("InterfaceName", ""),
                        "Server": _join_list(row.get("Servers") or []),
                        "Client": _join_list(row.get("Clients") or []),
                    }
                )

        QUERY_LOG_PATH.write_text("\n\n".join(query_log) + "\n", encoding="utf-8")

        print(f"Connected to: {uri} as {username}")
        print(f"Relationship types discovered: {len(inventory_rows)}")
        print(f"Interface rows written: {len(dependency_rows)}")
        print(f"CSV written to: {CSV_PATH}")
        print(f"Query log written to: {QUERY_LOG_PATH}")
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
