"""
run_c3_dynamic_only.py — H1 Condition 3: Runtime traces only
-------------------------------------------------------------
Reads each scenario's pre-extracted trace_slice.txt (component-level runtime data).
Converts rows directly to elements.json.
No Neo4j static graph is used.

Usage:
    python run_c3_dynamic_only.py --scenario S1
    python run_c3_dynamic_only.py --all

Output: experiments/H1/conditions/C3_dynamic_only/<scenario>/elements.json
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, SCENARIO_PRIMARY, SCENARIO_COMPONENTS,
                    Element, save_elements, elements_path, load_trace_slice)

LABEL = "C3_dynamic_only"


def run_scenario(scenario: str) -> None:
    rows = load_trace_slice(scenario)
    elements: set[Element] = set()

    primary = SCENARIO_PRIMARY[scenario]
    allowed = SCENARIO_COMPONENTS[scenario]
    for row in rows:
        src  = row.get("ClientComponent", "").strip()
        tgt  = row.get("ServerComponent",  "").strip()
        intr = row.get("EventName",        "").strip()
        if src and tgt and intr and src == primary and tgt in allowed and src != tgt:
            elements.add(Element(src, tgt, intr))

    save_elements(elements, elements_path(LABEL, scenario))


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
