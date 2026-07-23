"""
run_c5_guided_reach.py — H1 Condition 5: Guided trace (trace_slice.txt) + Neo4j reachability
-------------------------------------------------------------------------------------------
Reads each scenario's trace_slice.txt (component-level runtime data from
clang-exp guided instrumentation at specific architectural call sites) and
applies a Neo4j reachability filter:

  Reachability filter: keep only events whose ClientFunction is reachable from
  SCENARIO_ENTRY via CppCalls*0..8 in the Renaissance Neo4j graph.
  This removes setup-phase boilerplate (e.g. Aggregator.add) that fires before
  the scenario logic starts.

The instrumentation sites in trace_slice.txt were selected using the Neo4j call
graph (design-time); reachability is also applied at query time to scope events
to scenario logic.

Usage:
    python run_c5_guided_reach.py --scenario S1a
    python run_c5_guided_reach.py --all

Output: experiments/H1/conditions/C5_guided_reach/<scenario>/interactions.json
                                                             /sequence.json
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_COMPONENTS,
                    Element, save_elements, save_sequence,
                    interactions_path, sequence_path, load_trace_slice,
                    neo4j_driver)

LABEL = "C5_guided_reach"

# Entry-point functions per scenario — seed for Neo4j CppCalls* traversal.
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
            ("MultiThreadingScheduler", "runSchedule"),
            ("MultiThreadingScheduler", "stop"),
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


def _load_reachable(scenario: str) -> set[tuple[str, str]]:
    """Return {(symbol, class_or_path)} for all functions reachable from entry points."""
    entries = SCENARIO_ENTRY.get(scenario, [])
    # Seed with entry points themselves (class name as hint).
    reachable: set[tuple[str, str]] = {(method, cls) for cls, method in entries}
    driver = neo4j_driver()
    try:
        with driver.session() as session:
            for cls, method in entries:
                for rec in session.run(CYPHER_REACHABLE, cls=cls, method=method):
                    sym  = (rec["sym"]         or "").strip()
                    path = (rec["callee_path"] or "").strip()
                    if sym:
                        reachable.add((sym, path))
    finally:
        driver.close()
    return reachable


def _is_client_reachable(client_fn: str, reachable: set[tuple[str, str]]) -> bool:
    """Return True if ClientFunction (Class.method) is in the reachable set."""
    if not reachable:
        return True
    if not client_fn or "." not in client_fn:
        return True
    cls, method = client_fn.rsplit(".", 1)
    return any(sym == method and (cls in (hint or "") or cls == hint)
               for sym, hint in reachable)


def run_scenario(scenario: str) -> None:
    print(f"  → Querying Neo4j reachability for {scenario} ...")
    reachable = _load_reachable(scenario)
    print(f"    {len(reachable)} functions reachable from entry points")

    rows = load_trace_slice(scenario)
    elements: set[Element] = set()
    ordered_events: list[dict] = []

    allowed = SCENARIO_COMPONENTS[scenario]
    pos_out = 0
    for row in rows:
        src  = row.get("ClientComponent", "").strip()
        tgt  = row.get("ServerComponent",  "").strip()
        intr = row.get("EventName",        "").strip()
        cf   = row.get("ClientFunction",   "").strip()
        if not (src and tgt and intr) or src == tgt:
            continue
        if src not in allowed or tgt not in allowed:
            continue
        if not _is_client_reachable(cf, reachable):
            continue
        elements.add(Element(src, tgt, intr))
        ordered_events.append({
            "order": pos_out, "source": src, "target": tgt, "interaction": intr
        })
        pos_out += 1

    save_elements(elements, interactions_path(LABEL, scenario))
    save_sequence(ordered_events, sequence_path(LABEL, scenario))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"C5 guided-reach: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
