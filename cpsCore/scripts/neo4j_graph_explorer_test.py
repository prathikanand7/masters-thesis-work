from __future__ import annotations

import html
import os
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase
from pyvis.network import Network


DB_PATH = Path(r"C:/Users/prathikak/.Neo4jDesktop2/Data/dbmss/dbms-53ca4fd9-2306-4c45-a7bd-a4188d584db2")
BOLT_URI = os.getenv("NEO4J_BOLT_URI", "bolt://localhost:7687")
USERNAME = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j")


def run_table_query(driver, cypher: str, params: dict | None = None) -> pd.DataFrame:
    params = params or {}
    with driver.session(database="neo4j") as session:
        rows = [record.data() for record in session.run(cypher, params)]
    return pd.DataFrame(rows)


def run_graph_query(driver, cypher: str, params: dict | None = None):
    params = params or {}
    with driver.session(database="neo4j") as session:
        return list(session.run(cypher, params))


def node_caption(node) -> str:
    for key in ["name", "title", "label", "id", "uuid", "code"]:
        if key in node and node[key] not in (None, ""):
            return str(node[key])
    return node.element_id


def build_html(records, output_path: Path) -> None:
    palette = ["#38bdf8", "#f0abfc", "#6ee7b7", "#f59e0b", "#fb7185", "#a78bfa"]
    color_map: dict[str, str] = {}
    net = Network(height="780px", width="100%", bgcolor="#ffffff", font_color="#1f2937", notebook=False, cdn_resources="in_line")
    seen = set()

    for record in records:
        n = record["n"]
        r = record["r"]
        m = record["m"]
        for node in (n, m):
            node_id = node.element_id
            if node_id in seen:
                continue
            labels = list(node.labels)
            primary_label = labels[0] if labels else "Node"
            color_map.setdefault(primary_label, palette[len(color_map) % len(palette)])
            caption = html.escape(node_caption(node))
            props = "<br>".join(f"{html.escape(str(k))}: {html.escape(str(v))}" for k, v in node.items())
            title = f"<b>{html.escape(primary_label)}</b><br>{caption}" + (f"<br>{props}" if props else "")
            net.add_node(
                node_id,
                label=caption,
                title=title,
                group=primary_label,
                color=color_map[primary_label],
                value=max(len(node), 1),
                shape="dot",
            )
            seen.add(node_id)
        net.add_edge(n.element_id, m.element_id, label=r.type, title=r.type)

    net.toggle_physics(True)
    output_path.write_text(net.generate_html(), encoding="utf-8")


def main() -> int:
    print(f"DB path: {DB_PATH}")
    print(f"Bolt URI: {BOLT_URI}")
    print(f"User: {USERNAME}")

    driver = GraphDatabase.driver(BOLT_URI, auth=(USERNAME, PASSWORD))
    try:
        driver.verify_connectivity()
        print("Connectivity check: OK")

        labels = run_table_query(driver, "CALL db.labels() YIELD label RETURN label ORDER BY label")
        rel_types = run_table_query(driver, "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType ORDER BY relationshipType")
        print(f"Labels: {labels['label'].tolist() if not labels.empty else []}")
        print(f"Relationship types: {rel_types['relationshipType'].tolist() if not rel_types.empty else []}")

        records = run_graph_query(driver, "MATCH (n)-[r]-(m) RETURN n, r, m LIMIT 25")
        print(f"Graph rows returned: {len(records)}")

        output_path = Path(__file__).with_name("neo4j_graph_explorer_test.html")
        build_html(records, output_path)
        print(f"Wrote visualization to: {output_path}")

        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())