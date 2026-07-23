"""
run_c2_static_only.py — H1 Condition 2: Static call-graph (Neo4j, test-scoped)
-------------------------------------------------------------------------------
Queries the Renaissance Neo4j graph for cross-component CppCalls edges
reachable from each scenario's entry-point function via forward call-graph
traversal (CppCalls*). This scopes static analysis to the specific test path
rather than the whole codebase.

Ordering: calls are collected in SCENARIO_ENTRY order — each entry point's
cross-component callees are appended in the order they appear in the query
result.  Full call-graph DFS is not feasible here because the Neo4j schema
separates function declarations from definitions (CppCalls → declaration,
CppImplements ← definition), making multi-hop traversal non-trivial with a
single Cypher query.

Usage:
    python run_c2_static_only.py --scenario S1a
    python run_c2_static_only.py --all

Output: experiments/H1/conditions/C2_static_only/<scenario>/interactions.json
                                                              sequence.json
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (ROOT, SCENARIOS, SCENARIO_COMPONENTS,
                    Element, save_elements, interactions_path, sequence_path,
                    path_to_component, neo4j_driver)

LABEL = "C2_static_only"

# Entry-point functions for each scenario (class, method).
# Multiple entries per scenario capture all production functions called by the test.
# C2 traverses CppCalls*[def→decl] + reverse CppImplements[decl←def] from each.
SCENARIO_ENTRY = {
    "S1a": [("SynchronizedRunner",   "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S1b": [("SynchronizedRunner",   "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S2":  [("PropertyMapper",       "addOptional"),
            ("PropertyMapper",       "add")],
    "S3":  [("AggregatableRunner",   "runAllStages"),
            ("AggregatableRunner",   "notifyAggregationOnUpdate"),
            ("MultiThreadingScheduler", "schedule"),
            ("MultiThreadingScheduler", "run")],
}

# Interactions to exclude per scenario (implementation details that are
# real calls but not architecturally significant for the scenario).
# getLogLevel: only present due to temporary trace instrumentation in publishStage.
SCENARIO_EXCLUDE: dict[str, set[str]] = {
}

# Cypher: forward call-graph traversal from entry point, collect cross-component edges
CYPHER = """
MATCH (entry {type:'CppFunctionDefinition'})
WHERE entry.symbol = $method AND entry.name CONTAINS $cls
WITH entry LIMIT 1
MATCH (entry)-[:Source]->(ef)
WITH entry, ef
CALL {
  WITH entry, ef
  MATCH (entry)-[:CppCalls]->(decl)<-[:CppImplements]-(step_def)-[:CppCalls]->(callee)
  MATCH (callee)-[:Source]->(cf)
  WHERE ef.name <> cf.name
  RETURN callee.symbol AS sym, cf.name AS callee_file
  UNION
  WITH entry, ef
  MATCH (entry)-[:CppCalls]->(callee)
  MATCH (callee)-[:Source]->(cf)
  WHERE ef.name <> cf.name
  RETURN callee.symbol AS sym, cf.name AS callee_file
}
RETURN DISTINCT sym, callee_file, ef.name AS entry_file
"""

def load_from_neo4j(scenario: str) -> set[Element]:
    allowed  = SCENARIO_COMPONENTS[scenario]
    elements: set[Element] = set()
    entries  = SCENARIO_ENTRY.get(scenario, [])
    if not entries:
        print(f"  [SKIP] No entry points defined for {scenario}")
        return elements

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            for cls, method in entries:
                for record in session.run(CYPHER, cls=cls, method=method):
                    src_comp = path_to_component(record["entry_file"] or "")
                    tgt_comp = path_to_component(record["callee_file"] or "")
                    if not src_comp or not tgt_comp or src_comp == tgt_comp:
                        continue
                    if src_comp not in allowed or tgt_comp not in allowed:
                        continue
                    interaction = (record["sym"] or "").strip()
                    if interaction and interaction not in SCENARIO_EXCLUDE.get(scenario, set()):
                        elements.add(Element(src_comp, tgt_comp, interaction))
    finally:
        driver.close()
    return elements


def load_ordered_from_neo4j(scenario: str) -> list[dict]:
    """Return cross-component calls ordered by SCENARIO_ENTRY traversal order.

    For each entry point (in SCENARIO_ENTRY order), runs the same CYPHER used
    by load_from_neo4j and appends new cross-component calls to a list.  The
    first time a (src, tgt, interaction) triple is seen it is recorded; later
    duplicates are skipped.  This gives a deterministic sequence that reflects
    the entry-point structure without requiring a full call-graph traversal
    (which is non-trivial due to the CppCalls/CppImplements split in the schema).
    """
    allowed = SCENARIO_COMPONENTS[scenario]
    exclude = SCENARIO_EXCLUDE.get(scenario, set())
    entries = SCENARIO_ENTRY.get(scenario, [])

    results: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    driver = neo4j_driver()
    try:
        with driver.session() as session:
            for cls, method in entries:
                for record in session.run(CYPHER, cls=cls, method=method):
                    src_comp = path_to_component(record["entry_file"] or "")
                    tgt_comp = path_to_component(record["callee_file"] or "")
                    if not src_comp or not tgt_comp or src_comp == tgt_comp:
                        continue
                    if src_comp not in allowed or tgt_comp not in allowed:
                        continue
                    interaction = (record["sym"] or "").strip()
                    if not interaction or interaction in exclude:
                        continue
                    key = (src_comp, tgt_comp, interaction)
                    if key not in seen:
                        seen.add(key)
                        results.append(key)
    finally:
        driver.close()

    return [
        {"order": i, "source": s, "target": t, "interaction": intr,
         "evidence": "static", "method": "entry_order"}
        for i, (s, t, intr) in enumerate(results)
    ]


def run_scenario(scenario: str) -> None:
    elements = load_from_neo4j(scenario)
    entries = SCENARIO_ENTRY.get(scenario, [])
    print(f"  Source: Neo4j ({len(entries)} entry points, interactions)")
    save_elements(elements, interactions_path(LABEL, scenario))

    ordered = load_ordered_from_neo4j(scenario)
    sequence_path(LABEL, scenario).parent.mkdir(parents=True, exist_ok=True)
    sequence_path(LABEL, scenario).write_text(json.dumps(ordered, indent=2))
    print(f"  Source: Neo4j DFS-ordered → {len(ordered)} sequence steps")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"C2 static-only: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
