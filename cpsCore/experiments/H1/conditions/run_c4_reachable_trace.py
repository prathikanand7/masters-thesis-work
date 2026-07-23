"""
run_c4_reachable_trace.py — H1 Condition 4: Full trace + reachability filter + puml
-------------------------------------------------------------------------------------
Takes full_trace.txt and applies two filters:

  1. Reachability filter: keep only events whose ClientFunction is reachable from
     SCENARIO_ENTRY via CppCalls*0..8 in the Renaissance Neo4j graph.
     This removes test-setup/teardown boilerplate.

  2. Architectural filter: keep only events whose (src, tgt) component pair is
     a confirmed directed edge in cpsCore_packages_annotated.puml.

The result is the full trace scoped to scenario logic on valid architectural edges.

Usage:
    python run_c5_reachable_trace.py --scenario S1a
    python run_c5_reachable_trace.py --all

Output: experiments/H1/conditions/C4_reachable_trace/<scenario>/interactions.json
                                                                  /sequence.json
"""
import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (ROOT, SCENARIOS, SCENARIO_COMPONENTS,
                    Element, save_elements, save_sequence,
                    interactions_path, sequence_path,
                    load_full_trace, neo4j_driver)

LABEL = "C4_reachable_trace"

# Entry points — same as derive_gt.py (extended seeds for std::function dispatch gaps)
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
            ("ObjectHandleContainer",   "setFromAggregationIfNotSet"),
           ],
}

# CppCalls* reachability — returns all functions reachable from an entry point (depth ≤8)
CYPHER_REACHABLE = """
MATCH (entry {type:'CppFunctionDefinition'})
WHERE entry.symbol = $method AND entry.name CONTAINS $cls
WITH entry LIMIT 1
MATCH (entry)-[:CppCalls*0..8]->(callee)
RETURN DISTINCT callee.symbol AS sym, callee.name AS callee_path
"""

ANNOTATED_PUML = ROOT / "architectural_diagrams" / "cpsCore_packages_annotated.puml"


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_puml_edges(puml_path: pathlib.Path) -> set[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    if not puml_path.exists():
        return edges
    for m in re.finditer(r"^\s*(\w+)\s+\.\.>\s+(\w+)", puml_path.read_text(), re.MULTILINE):
        edges.add((m.group(1).lower(), m.group(2).lower()))
    return edges


def load_reachable(scenario: str) -> set[tuple[str, str]]:
    """Return (symbol, hint_or_path) for all functions reachable from entry points."""
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


def is_client_reachable(client_fn: str, reachable: set[tuple[str, str]]) -> bool:
    if not reachable:
        return True
    if not client_fn or "." not in client_fn:
        return True
    parts = client_fn.rsplit(".", 1)
    cls, method = parts[0], parts[1]
    return any(sym == method and (cls in (hint or "") or cls == hint)
               for sym, hint in reachable)


# ── Main condition logic ─────────────────────────────────────────────────────

def run_scenario(scenario: str, puml_edges: set[tuple[str, str]]) -> None:
    allowed   = SCENARIO_COMPONENTS[scenario]
    reachable = load_reachable(scenario)
    print(f"  {len(reachable)} functions reachable from entry points")

    rows = load_full_trace(scenario)
    elements: set[Element] = set()
    ordered_events: list[dict] = []
    excluded = 0

    for pos, row in enumerate(rows):
        src       = row.get("ClientComponent", "").strip()
        tgt       = row.get("ServerComponent",  "").strip()
        intr      = row.get("EventName",        "").strip()
        client_fn = row.get("ClientFunction",   "").strip()
        if not src or not tgt or not intr or src == tgt:
            continue
        if src not in allowed or tgt not in allowed:
            continue
        if not is_client_reachable(client_fn, reachable):
            print(f"    [SETUP] excluded {src}→{tgt}:{intr} (caller={client_fn})")
            excluded += 1
            continue
        if puml_edges and (src.lower(), tgt.lower()) not in puml_edges:
            print(f"    [PUML]  rejected  {src}→{tgt}:{intr}")
            continue
        elements.add(Element(src, tgt, intr))
        ordered_events.append({"order": pos, "source": src, "target": tgt, "interaction": intr})

    print(f"  {len(rows)} raw events → {len(ordered_events)} kept, {excluded} setup-excluded")
    save_elements(elements, interactions_path(LABEL, scenario))
    save_sequence(ordered_events, sequence_path(LABEL, scenario))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    puml_edges = load_puml_edges(ANNOTATED_PUML)
    print(f"Loaded {len(puml_edges)} puml edges")

    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"\nC4 reachable-trace: {s}")
        run_scenario(s, puml_edges)


if __name__ == "__main__":
    main()
