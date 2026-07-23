"""
_utils.py — shared helpers for H1 condition scripts
"""
import csv
import json
import pathlib
import re
from typing import NamedTuple

ROOT      = pathlib.Path(__file__).parent.parent.parent.parent  # cpsCore/
H1_DIR    = pathlib.Path(__file__).parent.parent                # experiments/H1/
COND_DIR  = H1_DIR / "conditions"
SCEN_DIR  = ROOT / "experiments" / "scenarios"
SCENARIOS = ["S1a", "S1b", "S2", "S3"]

# ── Component name detection ────────────────────────────────────────────────
# Maps a file path fragment to a CPSCore top-level component name.
# Order matters: more-specific patterns first.
_PATH_COMPONENT_MAP = [
    (re.compile(r"/(src|include/cpsCore)/Aggregation/",   re.I), "Aggregation"),
    (re.compile(r"/(src|include/cpsCore)/Configuration/", re.I), "Configuration"),
    (re.compile(r"/(src|include/cpsCore)/Framework/",     re.I), "Framework"),
    (re.compile(r"/(src|include/cpsCore)/Logging/",       re.I), "Logging"),
    (re.compile(r"/(src|include/cpsCore)/Synchronization/",re.I),"Synchronization"),
    (re.compile(r"/(src|include/cpsCore)/Utilities/",     re.I), "Utilities"),
]

def path_to_component(path: str) -> str | None:
    for pattern, name in _PATH_COMPONENT_MAP:
        if pattern.search(path):
            return name
    return None

# ── Scenario component sets ──────────────────────────────────────────────────
# All components that appear in the scenario (used to bound the search space)
SCENARIO_COMPONENTS = {
    "S1a": {"Synchronization", "Aggregation", "Logging"},  # happy path
    "S1b": {"Synchronization", "Aggregation", "Logging"},  # timeout path (Aggregation.add() events also captured)
    "S2":  {"Configuration", "Logging"},
    "S3":  {"Synchronization", "Aggregation", "Utilities", "Logging"},
}

# The single component that DRIVES each scenario.
# Only edges where source == primary are counted across all conditions.
# This ensures ground truth is defined by the scenario narrative (source-derived),
# not by what runtime traces happen to record — making C3 non-trivially fallible.
SCENARIO_PRIMARY = {
    "S1a": "Synchronization",
    "S1b": "Synchronization",
    "S2":  "Configuration",
    "S3":  "Synchronization",

}

# ── Element I/O ──────────────────────────────────────────────────────────────
class Element(NamedTuple):
    source:      str
    target:      str
    interaction: str

    def to_dict(self) -> dict:
        return {"source": self.source, "target": self.target,
                "interaction": self.interaction}

def load_elements(path: pathlib.Path) -> set[Element]:
    if not path.exists():
        return set()
    with open(path) as f:
        data = json.load(f)
    return {Element(d["source"], d["target"], d["interaction"]) for d in data}

def save_elements(elements: set[Element], path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump([e.to_dict() for e in sorted(elements)], f, indent=2)
    print(f"  Saved {len(elements)} elements → {path.relative_to(ROOT)}")

def save_sequence(events: list[dict], path: pathlib.Path) -> None:
    """Save an ordered list of events (with 'order', 'source', 'target', 'interaction')."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(events, f, indent=2)
    print(f"  Saved {len(events)} sequence events → {path.relative_to(ROOT)}")

def interactions_path(condition_label: str, scenario: str) -> pathlib.Path:
    return COND_DIR / condition_label / scenario / "interactions.json"

def sequence_path(condition_label: str, scenario: str) -> pathlib.Path:
    return COND_DIR / condition_label / scenario / "sequence.json"

# Legacy alias — kept so any external callers still work during transition
def elements_path(condition_label: str, scenario: str) -> pathlib.Path:
    return interactions_path(condition_label, scenario)

# ── Trace slice loader ───────────────────────────────────────────────────────
def load_trace_slice(scenario: str) -> list[dict]:
    path = SCEN_DIR / scenario / "trace_slice.txt"
    if not path.exists():
        return []
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            rows.append(row)
    return rows


def load_full_trace(scenario: str) -> list[dict]:
    path = SCEN_DIR / scenario / "full_trace.txt"
    if not path.exists():
        return []
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            rows.append(row)
    return rows

# ── Neo4j connection ─────────────────────────────────────────────────────────
def neo4j_driver():
    """Return an authenticated Neo4j driver using cpsCore/.env settings."""
    try:
        from neo4j import GraphDatabase
        from dotenv import load_dotenv
        import os
        load_dotenv(ROOT / ".env")
        uri      = os.environ.get("NEO4J_URI",      "bolt://localhost:7687")
        user     = os.environ.get("NEO4J_USER",      "neo4j")
        password = os.environ.get("NEO4J_PASSWORD",  "password")
        return GraphDatabase.driver(uri, auth=(user, password))
    except ImportError as e:
        raise SystemExit(f"Missing dependency: {e}\nRun: pip install neo4j python-dotenv")
