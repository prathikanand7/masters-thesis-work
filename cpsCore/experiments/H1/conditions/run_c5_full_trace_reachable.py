"""
run_c5_full_trace_reachable.py — H1 Condition 5: Full trace + arch + reachability (Neo4j)
-------------------------------------------------------------------------------------------
Takes full_trace.txt and applies two Neo4j-derived filters:

  1. Reachability filter: keep only events whose ClientFunction is reachable from
     SCENARIO_ENTRY via CppCalls*0..8 in the Renaissance Neo4j graph.
     This removes test-setup/teardown boilerplate.

  2. Architectural filter: keep only events whose (src, tgt) component pair is
     a confirmed cross-component edge derived from the Neo4j call graph
     (CppCalls*1..8 traversal from entry points, mapped to component names).

Both filters are derived entirely from Neo4j — no puml file is used.
The result is the full trace scoped to scenario logic on Neo4j-validated arch edges.

Usage:
    python run_c5_full_trace_reachable.py --scenario S1a
    python run_c5_full_trace_reachable.py --all

Output: experiments/H1/conditions/C5_full_trace_reachable/<scenario>/interactions.json
                                                                      /sequence.json
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_COMPONENTS,
                    Element, save_elements, save_sequence,
                    interactions_path, sequence_path,
                    load_full_trace, path_to_component, neo4j_driver)

LABEL = "C5_full_trace_reachable"

# Entry points — same seeds as derive_gt.py (extended for std::function dispatch gaps).
SCENARIO_ENTRY: dict[str, list[tuple[str, str]]] = {
    "S1a": [("SynchronizedRunner",      "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S1b": [("SynchronizedRunner",      "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S2":  [("PropertyMapper",          "addOptional"),
            ("PropertyMapper",          "add")],
    "S3":  [("AggregatableRunner",      "runAllStages"),
            ("AggregatableRunner",      "notifyAggregationOnUpdate"),
            ("MultiThreadingScheduler", "schedule"),
            ("MultiThreadingScheduler", "run"),
            # runSchedule/stop called via std::function — Neo4j misses them, seed explicitly
            ("MultiThreadingScheduler", "runSchedule"),
            ("MultiThreadingScheduler", "stop"),
            # ObjectHandleContainer called during aggregation update cycle
            ("ObjectHandleContainer",   "setFromAggregationIfNotSet")],
}

# CppCalls* reachability — all functions reachable from an entry point (depth ≤ 8).
CYPHER_REACHABLE = """
MATCH (entry {type:'CppFunctionDefinition'})
WHERE entry.symbol = $method AND entry.name CONTAINS $cls
WITH entry LIMIT 1
MATCH (entry)-[:CppCalls*0..8]->(callee)
RETURN DISTINCT callee.symbol AS sym, callee.name AS callee_path
"""

# Arch edges — cross-component pairs reachable from entry points (depth 1..8).
# Maps (entry_file, callee_file) → (src_component, tgt_component).
CYPHER_ARCH_EDGES = """
MATCH (entry {type:'CppFunctionDefinition'})
WHERE entry.symbol = $method AND entry.name CONTAINS $cls
WITH entry LIMIT 1
MATCH (entry)-[:Source]->(ef)
MATCH (entry)-[:CppCalls*1..8]->(callee)-[:Source]->(cf)
WHERE ef.name <> cf.name
RETURN DISTINCT ef.name AS entry_file, cf.name AS callee_file
"""


def _load_arch_edges(scenario: str) -> set[tuple[str, str]]:
    """Return {(src_component, tgt_component)} cross-component pairs from Neo4j call graph."""
    entries = SCENARIO_ENTRY.get(scenario, [])
    arch_edges: set[tuple[str, str]] = set()
    try:
        driver = neo4j_driver()
        with driver.session() as session:
            for cls, method in entries:
                for rec in session.run(CYPHER_ARCH_EDGES, cls=cls, method=method):
                    src_comp = path_to_component(rec["entry_file"]  or "")
                    tgt_comp = path_to_component(rec["callee_file"] or "")
                    if src_comp and tgt_comp and src_comp != tgt_comp:
                        arch_edges.add((src_comp, tgt_comp))
        driver.close()
    except Exception as e:
        print(f"  [WARN] Neo4j arch-edges query failed — arch filter skipped: {e}")
    return arch_edges


def _load_reachable(scenario: str) -> set[tuple[str, str]]:
    """Return {(symbol, class_or_path)} for all functions reachable from entry points."""
    entries = SCENARIO_ENTRY.get(scenario, [])
    reachable: set[tuple[str, str]] = {(method, cls) for cls, method in entries}
    try:
        driver = neo4j_driver()
        with driver.session() as session:
            for cls, method in entries:
                for rec in session.run(CYPHER_REACHABLE, cls=cls, method=method):
                    sym  = (rec["sym"]         or "").strip()
                    path = (rec["callee_path"] or "").strip()
                    if sym:
                        reachable.add((sym, path))
        driver.close()
    except Exception as e:
        print(f"  [WARN] Neo4j unavailable — reachability filter skipped: {e}")
    return reachable


def _is_client_reachable(client_fn: str, reachable: set[tuple[str, str]]) -> bool:
    if not reachable:
        return True
    if not client_fn or "." not in client_fn:
        return True
    cls, method = client_fn.rsplit(".", 1)
    return any(sym == method and (cls in (hint or "") or cls == hint)
               for sym, hint in reachable)


def run_scenario(scenario: str) -> None:
    allowed = SCENARIO_COMPONENTS[scenario]

    print(f"  → Querying Neo4j reachability for {scenario} ...")
    reachable = _load_reachable(scenario)
    print(f"    {len(reachable)} functions reachable from entry points")

    print(f"  → Querying Neo4j arch edges for {scenario} ...")
    arch_edges = _load_arch_edges(scenario)
    print(f"    {len(arch_edges)} cross-component arch edges: {sorted(arch_edges)}")

    rows = load_full_trace(scenario)
    elements: set[Element] = set()
    ordered_events: list[dict] = []
    excluded_setup = 0
    excluded_puml  = 0

    for pos, row in enumerate(rows):
        src       = row.get("ClientComponent", "").strip()
        tgt       = row.get("ServerComponent",  "").strip()
        intr      = row.get("EventName",        "").strip()
        client_fn = row.get("ClientFunction",   "").strip()
        if not src or not tgt or not intr or src == tgt:
            continue
        if src not in allowed or tgt not in allowed:
            continue
        if not _is_client_reachable(client_fn, reachable):
            excluded_setup += 1
            continue
        if arch_edges and (src, tgt) not in arch_edges:
            excluded_puml += 1
            continue
        elements.add(Element(src, tgt, intr))
        ordered_events.append({"order": pos, "source": src, "target": tgt, "interaction": intr})

    print(f"    {len(rows)} raw events → {len(ordered_events)} kept "
          f"({excluded_setup} setup-excluded, {excluded_puml} puml-rejected)")
    save_elements(elements, interactions_path(LABEL, scenario))
    save_sequence(ordered_events, sequence_path(LABEL, scenario))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"\nC5 full-trace-reachable: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
