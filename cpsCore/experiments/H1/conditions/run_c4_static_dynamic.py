"""
run_c4_static_dynamic.py — H1 Condition 4: Static + Dynamic (no agent synthesis)
----------------------------------------------------------------------------------
Merges C2 (static call-graph) and C3 (dynamic trace) elements.
This is the raw union before any agent reasoning layer is applied.

Requires C2 and C3 outputs to exist first. Run:
    python run_c2_static_only.py --all
    python run_c3_dynamic_only.py --all
Then run this script.

Usage:
    python run_c4_static_dynamic.py --scenario S1
    python run_c4_static_dynamic.py --all

Output: experiments/H1/conditions/C4_static_dynamic/<scenario>/elements.json
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _utils import (SCENARIOS, Element, load_elements,
                    save_elements, elements_path)  # Element used in _normalize

LABEL = "C4_static_dynamic"


def _normalize(elements: set) -> set:
    """Normalize interaction names to bare function name (split on '.')."""
    return {Element(e.source, e.target, e.interaction.split(".")[-1])
            for e in elements}


def run_scenario(scenario: str) -> None:
    c2 = _normalize(load_elements(elements_path("C2_static_only",  scenario)))
    c3 = _normalize(load_elements(elements_path("C3_dynamic_only", scenario)))

    if not c2:
        print(f"  [WARN] C2 elements missing for {scenario} — run run_c2_static_only.py first")
    if not c3:
        print(f"  [WARN] C3 elements missing for {scenario} — run run_c3_dynamic_only.py first")

    merged = c2 | c3
    save_elements(merged, elements_path(LABEL, scenario))
    print(f"  C2={len(c2)}  C3={len(c3)}  merged={len(merged)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    targets = SCENARIOS if args.all else [args.scenario]
    for s in targets:
        print(f"C4 static+dynamic: {s}")
        run_scenario(s)


if __name__ == "__main__":
    main()
