"""Utility functions for extracting and processing Neo4j schema information."""

from __future__ import annotations
import re

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Iterable
from neo4j import GraphDatabase
from neo4j.exceptions import ClientError
import neo4j


def _normalize_type(type_name: str) -> str:
    """
    Map Neo4j-reported types to your desired tokens (STRING, INTEGER, ...).
    If unknown, default to STRING.

    Args:
        type_name: The original type name reported by Neo4j, which may be in various
                     formats (e.g., "String", "LIST OF STRING", "List<String>", etc.).
    Returns:
        A normalized type token as a string (e.g., "STRING", "LIST<STRING>", "INTEGER", etc.).
    """
    t = (type_name or "").strip().lower()

    mapping = {
        "string": "STRING",
        "stringarray": "LIST<STRING>",
        "integer": "INTEGER",
        "int": "INTEGER",
        "long": "INTEGER",
        "float": "FLOAT",
        "double": "FLOAT",
        "boolean": "BOOLEAN",
        "date": "DATE",
        "datetime": "DATETIME",
        "localdatetime": "DATETIME",
        "time": "TIME",
        "localtime": "TIME",
        "duration": "DURATION",
        "point": "POINT",
        # Neo4j sometimes reports "LIST OF STRING" or similar variants:
        "list": "LIST",
    }

    # Handle common list spellings like "List<String>" or "LIST OF STRING"
    if "list" in t and "string" in t:
        return "LIST<STRING>"
    if "list" in t and "integer" in t:
        return "LIST<INTEGER>"
    if "list" in t and ("float" in t or "double" in t):
        return "LIST<FLOAT>"
    if "list" in t and "boolean" in t:
        return "LIST<BOOLEAN>"

    return mapping.get(t, "STRING")


def _strip_node_type(node_type: str) -> str:
    """
    Neo4j schema procedures may return nodeType like ':Label' or ':A:B'.
    For your format, we’ll keep the single-label case as 'Label'.
    For multi-label, we join with '&' to keep it unambiguous (rare in your graphs).

    Args:
        node_type: The original node type string from Neo4j, which may include labels prefixed with colons (e.g., ":Label", ":A:B", etc.).
    Returns:
        A cleaned node type string with colons removed and multi-labels joined by '&' (e.g., "Label", "A&B").
    """
    nt = (node_type or "").strip()
    if nt.startswith(":"):
        nt = nt[1:]
    if nt.startswith("(") and nt.endswith(")"):
        nt = nt[1:-1]
    # ':A:B' -> 'A&B'
    parts = [p for p in nt.split(":") if p]
    return "&".join(parts) if parts else nt


# --- Core extraction -----------------------------------------------------------
def extract_schema_text(
    uri: str,
    username: str,
    password: str,
    database: Optional[str] = None,
    rel_signature_limit: Optional[int] = None,
) -> str:
    """
    Return schema in the exact format:

    Node properties:
      Label {prop: TYPE, ...}
    Relationship properties:
      RELTYPE {prop: TYPE, ...}
    The relationships:
      (:A)-[:R]->(:B)

    Strategy:
      1) Prefer built-in schema procedures:
         - CALL db.schema.nodeTypeProperties()
         - CALL db.schema.relTypeProperties()
      2) Always derive relationship signatures from the graph:
         MATCH (s)-[r]->(t) RETURN DISTINCT type(r), labels(s), labels(t)
      3) If schema procedures are unavailable, fall back to sampling keys and defaulting types to STRING.


    Args:
        uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
        username: Username for Neo4j authentication
        password: Password for Neo4j authentication
        database: Optional database name
        rel_signature_limit: Optional limit for relationship signatures
    Returns:
        A formatted string representing the Neo4j schema.
    """
    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        with driver.session(database=database) as session:
            node_props = _get_node_properties(session)
            rel_props = _get_relationship_properties(session)
            rel_sigs = _get_relationship_signatures(session, limit=rel_signature_limit)

        # Format exactly like your example
        lines: List[str] = []

        lines.append("Node properties:")
        for label in sorted(node_props.keys()):
            props = node_props[label]
            props_str = ", ".join(f"{k}: {v}" for k, v in sorted(props.items()))
            lines.append(f"  {label} {{{props_str}}}")

        lines.append("Relationship properties:")
        for rel_type in sorted(rel_props.keys()):
            props = rel_props[rel_type]
            props_str = ", ".join(f"{k}: {v}" for k, v in sorted(props.items()))
            lines.append(f"  {rel_type} {{{props_str}}}")

        lines.append("The relationships:")
        for (from_label, rel_type, to_label) in sorted(rel_sigs):
            lines.append(f"  (:{from_label})-[:{rel_type}]->(:{to_label})")

        return "\n".join(lines)

    finally:
        driver.close()


def _get_node_properties(session: "neo4j.Session") -> Dict[str, Dict[str, str]]:
    """
    Returns a dictionary mapping node labels to their properties and types.

    Args:
        session: An active Neo4j session object used to execute queries against the database.
    Returns:
        A dictionary where each key is a node label and the value is another dictionary mapping property names to their normalized type tokens.
    """
    # Preferred: built-in schema procedure (Neo4j 4.2+/5+ typically)
    cypher = """
    CALL db.schema.nodeTypeProperties()
    YIELD nodeType, propertyName, propertyTypes
    RETURN nodeType, propertyName, propertyTypes
    """
    try:
        records = session.execute_read(lambda tx: [r.data() for r in tx.run(cypher)])
        out: Dict[str, Dict[str, str]] = {}
        for r in records:
            label = _strip_node_type(r.get("nodeType", ""))
            prop = r.get("propertyName")
            ptypes = r.get("propertyTypes") or []
            if not label or not prop:
                continue
            # pick first type; if multiple, prefer STRING-ish mapping fallback
            chosen = _normalize_type(ptypes[0]) if ptypes else "STRING"
            out.setdefault(label, {})[prop] = chosen
        if out:
            return out
    except ClientError:
        pass  # fall back below

    # Fallback: sample keys per label, types default to STRING
    labels = session.execute_read(lambda tx: [r["label"] for r in tx.run("CALL db.labels() YIELD label RETURN label")])
    out: Dict[str, Dict[str, str]] = {}
    for label in labels:
        q = f"""
        MATCH (n:`{label}`)
        WITH n LIMIT 200
        UNWIND keys(n) AS k
        RETURN DISTINCT k AS propertyName
        """
        keys_ = session.execute_read(lambda tx: [r["propertyName"] for r in tx.run(q)])
        if keys_:
            out[label] = {k: "STRING" for k in keys_}
    return out


def _get_relationship_properties(session: "neo4j.Session") -> Dict[str, Dict[str, str]]:
    """
    Returns a dictionary mapping relationship types to their properties and types.

    Args:
        session: An active Neo4j session object used to execute queries against the database.
    Returns:
        A dictionary where each key is a relationship type and the value is another dictionary mapping property names to their normalized type tokens.
    """
    cypher = """
    CALL db.schema.relTypeProperties()
    YIELD relType, propertyName, propertyTypes
    RETURN relType, propertyName, propertyTypes
    """
    try:
        records = session.execute_read(lambda tx: [r.data() for r in tx.run(cypher)])
        out: Dict[str, Dict[str, str]] = {}
        for r in records:
            rel_type = (r.get("relType") or "").strip()
            prop = r.get("propertyName")
            ptypes = r.get("propertyTypes") or []
            if not rel_type or not prop:
                continue
            chosen = _normalize_type(ptypes[0]) if ptypes else "STRING"
            out.setdefault(rel_type, {})[prop] = chosen
        if out:
            return out
    except ClientError:
        pass

    # Fallback: sample keys per relationship type, types default to STRING
    rel_types = session.execute_read(
        lambda tx: [r["relationshipType"] for r in tx.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")]
    )
    out: Dict[str, Dict[str, str]] = {}
    for rt in rel_types:
        q = f"""
        MATCH ()-[r:`{rt}`]->()
        WITH r LIMIT 200
        UNWIND keys(r) AS k
        RETURN DISTINCT k AS propertyName
        """
        keys_ = session.execute_read(lambda tx: [r["propertyName"] for r in tx.run(q)])
        if keys_:
            out[rt] = {k: "STRING" for k in keys_}
    return out


def _get_relationship_signatures(session: "neo4j.Session", limit: Optional[int] = None) -> List[Tuple[str, str, str]]:
    """
    Returns a list of relationship signatures in the form of (from_label, rel_type, to_label).

    Args:
        session: An active Neo4j session object used to execute queries against the database.
        limit: Optional limit on the number of relationship signatures to retrieve, which can help reduce output size for large schemas.
    Returns:
        A list of tuples, where each tuple contains the from node label, relationship type, and to node label representing the relationships in the graph schema.
    """
    lim = f"LIMIT {int(limit)}" if limit else ""
    cypher = f"""
    MATCH (s)-[r]->(t)
    RETURN DISTINCT labels(s) AS fromLabels, type(r) AS relType, labels(t) AS toLabels
    {lim}
    """
    records = session.execute_read(lambda tx: [r.data() for r in tx.run(cypher)])

    triples: List[Tuple[str, str, str]] = []
    for r in records:
        rel_type = r.get("relType")
        from_labels = r.get("fromLabels") or []
        to_labels = r.get("toLabels") or []
        # Expand multi-label nodes into all combinations (usually single-label in your graphs)
        for fl in from_labels:
            for tl in to_labels:
                if fl and tl and rel_type:
                    triples.append((fl, rel_type, tl))
    return triples