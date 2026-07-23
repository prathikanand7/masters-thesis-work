"""
run_c6_full_trace_reach_only.py — H1 Condition 6: Full trace + Neo4j reachability only
----------------------------------------------------------------------------------------
Takes full_trace.txt and applies a single Neo4j reachability filter:

  Reachability filter: keep only events whose ClientFunction is reachable from
  SCENARIO_ENTRY via CppCalls*0..8 in the Renaissance Neo4j graph.
  This removes test-setup/teardown boilerplate.

No architectural edge filter is applied — all component pairs that survive the
reachability filter are kept, regardless of whether the (src, tgt) pair appears
in the static call graph.

Compare with:
  C5: guided trace (trace_slice.txt) + reachability  → F1=1.000
  C4: full trace + reachability + Neo4j arch edges   → S3 FN due to indirect-dispatch gap

Usage:
    python run_c6_full_trace_reach_only.py --scenario S1a
    python run_c6_full_trace_reach_only.py --all

Output: experiments/H1/conditions/C6_full_trace_reach_only/<scenario>/interactions.json
                                                                       /sequence.json
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_COMPONENTS,
                    Element, save_elements, save_sequence,
                    interactions_path, sequence_path,
                    load_full_trace, neo4j_driver)

LABEL = "C6_full_trace_reach_only"

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

CYPHER_REACHABLE = """
MATCH (entry {type:'CppFunctionDefinition'})
WHERE entry.symbol = $method AND entry.name CONTAINS $cls
WITH entry LIMIT 1
MATCH (entry)-[:CppCalls*0..8]->(callee)
RETURN DISTINCT callee.symbol AS sym, callee.name AS callee_path
"""


def _load_reachable(scenario: str) -> set[tuple[str, str]]:
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
        if not _is_client_reachable(client_fn, reachable):
            excluded += 1
            continue
        elements.add(Element(src, tgt, intr))
        ordered_events.append({"order": pos, "source": src, "target": tgt, "interaction": intr})

    print(f"    {len(rows)} raw events → {len(ordered_events)} kept ({excluded} setup-excluded)")
    save_elements(elements, interactions_path(LABEL, scenario))
    save_sequence(ordered_events, sequence_path(LABEL, scenario))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"\nC6 full-trace-reach-only: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
