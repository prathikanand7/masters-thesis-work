"""
run_c4_guided_only.py — H1 Condition 4: Guided trace (trace_slice.txt), no filter
-----------------------------------------------------------------------------------
Reads each scenario's trace_slice.txt and keeps all cross-component events whose
(ClientComponent, ServerComponent) pair is within the scenario's allowed component
set — no Neo4j reachability filter, no architectural edge filter.

This is the ablation of C5 that removes the scope filter: it shows whether the
guided instrumentation alone (trace_slice.txt) is sufficient to achieve perfect
results, or whether the Neo4j reachability filter is necessary to remove
setup-phase noise.

Expected behaviour:
  - S1a/S1b: FP expected — Aggregator.add fires during test setup (before the
    scenario entry point) and produces Agg→Log:stream events. These are in
    trace_slice.txt because the instrumentation site fires unconditionally,
    but are excluded from the GT by the SCENARIO_ENTRY filter.
    Without a reachability filter, C4 cannot distinguish setup from scenario logic.
  - S2, S3: no setup noise in trace_slice.txt for these scenarios → F1 = 1.000.

Compare with:
  C3: full_trace.txt, no filter         → worst baseline (intra-component FPs too)
  C5: trace_slice.txt + reachability    → F1 = 1.000 everywhere
  C6: full_trace.txt + reachability     → F1 = 1.000 everywhere

Usage:
    python run_c4_guided_only.py --scenario S1a
    python run_c4_guided_only.py --all

Output: experiments/H1/conditions/C4_guided_only/<scenario>/interactions.json
                                                            /sequence.json
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_COMPONENTS,
                    Element, save_elements, save_sequence,
                    interactions_path, sequence_path, load_trace_slice)

LABEL = "C4_guided_only"


def run_scenario(scenario: str) -> None:
    rows    = load_trace_slice(scenario)
    allowed = SCENARIO_COMPONENTS[scenario]
    elements: set[Element] = set()
    ordered_events: list[dict] = []

    for pos, row in enumerate(rows):
        src  = row.get("ClientComponent", "").strip()
        tgt  = row.get("ServerComponent",  "").strip()
        intr = row.get("EventName",        "").strip()
        if src and tgt and intr and src in allowed and tgt in allowed and src != tgt:
            elements.add(Element(src, tgt, intr))
            ordered_events.append({
                "order":       pos,
                "source":      src,
                "target":      tgt,
                "interaction": intr,
            })

    save_elements(elements, interactions_path(LABEL, scenario))
    save_sequence(ordered_events, sequence_path(LABEL, scenario))


def main():
    parser = argparse.ArgumentParser(description="C4 guided-only (no filter)")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--scenario", choices=SCENARIOS)
    grp.add_argument("--all", action="store_true")
    args = parser.parse_args()

    scenarios = SCENARIOS if args.all else [args.scenario]
    for s in scenarios:
        print(f"\n── {s} ──")
        run_scenario(s)


if __name__ == "__main__":
    main()
