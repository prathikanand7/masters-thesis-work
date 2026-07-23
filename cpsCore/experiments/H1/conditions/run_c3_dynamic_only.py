"""run_c3_dynamic_only.py — H1 Condition 3: Full runtime trace only (unfiltered)
---------------------------------------------------------------------------
Reads each scenario's full_trace.txt with NO filtering whatsoever.
All events — including intra-component (src==tgt), setup-phase boilerplate,
and events from any component — are passed through directly.
No Neo4j static graph is used.

This is the true raw-trace baseline. Compare with:
  C4: trace_slice.txt, no filter (guided instrumentation only)
  C5: trace_slice.txt + Neo4j reachability filter (guided reach)
  C6: full_trace.txt + Neo4j reachability filter

Usage:
    python run_c3_dynamic_only.py --scenario S1
    python run_c3_dynamic_only.py --all

Output: experiments/H1/conditions/C3_dynamic_only/<scenario>/elements.json
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS,
                    Element, save_elements, save_sequence,
                    interactions_path, sequence_path, load_full_trace)

LABEL = "C3_dynamic_only"


def run_scenario(scenario: str) -> None:
    rows = load_full_trace(scenario)
    elements: set[Element] = set()
    ordered_events: list[dict] = []

    for pos, row in enumerate(rows):
        src  = row.get("ClientComponent", "").strip()
        tgt  = row.get("ServerComponent",  "").strip()
        intr = row.get("EventName",        "").strip()
        if src and tgt and intr:
            elements.add(Element(src, tgt, intr))
            ordered_events.append({
                "order": pos, "source": src, "target": tgt, "interaction": intr
            })

    save_elements(elements, interactions_path(LABEL, scenario))
    save_sequence(ordered_events, sequence_path(LABEL, scenario))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"C3 dynamic-only: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
