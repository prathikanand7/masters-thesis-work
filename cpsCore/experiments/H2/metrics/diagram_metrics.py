"""
diagram_metrics.py — H2 diagram size + coverage scorer
--------------------------------------------------------
For each scenario, compares full vs. guided diagram on:
  1. Node count (distinct component names)
  2. Edge count (distinct source→target pairs)
  3. Relevant-edge count (distinct source→target→interaction triples)
  4. Coverage: recall of guided diagram against H1 reference elements
  5. Noise ratio: (edges not in H1 reference) / total edges

Interaction names are normalized to bare function name (split on ".")
to match the H1 reference scoring convention.

Usage:
    python diagram_metrics.py --scenario S1
    python diagram_metrics.py --all

Depends on:
  - H1 reference elements:   ../H1/reference_diagrams/SX/elements.json
  - H2 trace files:          ../H2/instrumentation/SX/{full,guided}_trace.txt
    (traces are parsed to extract component-level elements in the same format
    as H1 elements.json for direct comparison)

Output: prints table + writes results.csv
"""
import argparse
import csv
import json
import pathlib
from typing import NamedTuple

H2_DIR    = pathlib.Path(__file__).parent.parent          # experiments/H2/
H1_REF    = H2_DIR.parent / "H1" / "reference_diagrams"
INSTR_DIR = H2_DIR / "instrumentation"
RESULTS   = pathlib.Path(__file__).parent / "results.csv"
SCENARIOS = ["S1", "S2", "S3", "S4"]  # H2: happy-path scenarios + constructed S4


class DiagramElement(NamedTuple):
    source: str
    target: str
    interaction: str  # bare function name (normalized)


def _bare(name: str) -> str:
    """Normalize interaction to bare function name (strip class prefix)."""
    return name.strip().split(".")[-1].lower()


def load_trace_elements(trace_path: pathlib.Path) -> set[DiagramElement]:
    """Parse a pipe-delimited trace file into DiagramElement objects."""
    elements = set()
    if not trace_path.exists():
        return elements
    with open(trace_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            src  = row.get("ClientComponent", "").strip().lower()
            tgt  = row.get("ServerComponent",  "").strip().lower()
            intr = _bare(row.get("EventName", ""))
            if src and tgt and intr and src != tgt:
                elements.add(DiagramElement(src, tgt, intr))
    return elements


def load_reference_elements(scenario: str) -> set[DiagramElement]:
    ref_path = H1_REF / scenario / "elements.json"
    if not ref_path.exists():
        return set()
    with open(ref_path) as f:
        data = json.load(f)
    return {DiagramElement(
        source=d["source"].strip().lower(),
        target=d["target"].strip().lower(),
        interaction=_bare(d["interaction"]),
    ) for d in data}


def count_nodes(elements: set[DiagramElement]) -> int:
    return len({e.source for e in elements} | {e.target for e in elements})


def count_edges(elements: set[DiagramElement]) -> int:
    """Distinct source→target component pairs."""
    return len({(e.source, e.target) for e in elements})


def coverage(generated: set, reference: set) -> float:
    """Recall: fraction of reference elements found in generated."""
    if not reference:
        return 0.0
    return round(len(reference & generated) / len(reference), 3)


def noise_ratio(generated: set, reference: set) -> float:
    """Fraction of generated elements NOT in the reference."""
    if not generated:
        return 0.0
    return round(len(generated - reference) / len(generated), 3)


def score_scenario(scenario: str) -> list[dict]:
    full_trace   = INSTR_DIR / scenario / "full_trace.txt"
    guided_trace = INSTR_DIR / scenario / "guided_trace.txt"
    reference    = load_reference_elements(scenario)
    full_elems   = load_trace_elements(full_trace)
    guided_elems = load_trace_elements(guided_trace)

    rows = []
    for label, elems in [("full", full_elems), ("guided", guided_elems)]:
        tp = elems & reference
        fp = elems - reference
        fn = reference - elems
        r = {
            "scenario":     scenario,
            "variant":      label,
            "nodes":        count_nodes(elems),
            "edges":        count_edges(elems),
            "interactions": len(elems),
            "TP": len(tp), "FP": len(fp), "FN": len(fn),
            "coverage":     coverage(elems, reference),
            "noise":        noise_ratio(elems, reference),
        }
        rows.append(r)
        print(f"{scenario} {label:6s}  "
              f"nodes={r['nodes']:2d}  interactions={r['interactions']:2d}  "
              f"TP={r['TP']}  FP={r['FP']}  FN={r['FN']}  "
              f"coverage={r['coverage']:.3f}  noise={r['noise']:.3f}")
        if fp:
            print(f"         FP(noise): {sorted(str(e) for e in fp)}")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    targets = SCENARIOS if args.all else [args.scenario]
    all_rows = []
    for s in targets:
        all_rows.extend(score_scenario(s))

    with open(RESULTS, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario", "variant", "nodes",
                                               "edges", "interactions",
                                               "TP", "FP", "FN",
                                               "coverage", "noise"])
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"\nResults written to {RESULTS}")


if __name__ == "__main__":
    main()
