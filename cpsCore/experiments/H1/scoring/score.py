"""
score.py — H1 precision / recall / F1 scorer
----------------------------------------------
Compares pipeline-generated diagram elements against the reference diagrams
for each condition × scenario pair.

A "match" is defined as:
  - Same source component + same target component + same interaction name
    (case-insensitive, prefix-stripped to bare function name) = TRUE POSITIVE
  - Generated element not in reference = FALSE POSITIVE
  - Reference element not in generated = FALSE NEGATIVE

F1 AGGREGATION — two variants are reported to avoid reviewer confusion:
  - macro_f1   : mean of per-scenario F1 scores  (= what most papers report;
                 weights each scenario equally regardless of size)
  - micro_f1   : F1 computed from mean(P) and mean(R)  (= what a reader gets
                 if they recompute F1 from the P/R means in the table)
  These can differ. Both are reported; macro_f1 is the thesis figure.

Usage:
    python score.py --condition C1 --scenario S1
    python score.py --all          # runs all 5 conditions × 3 scenarios

Output:
    Prints per-scenario rows + per-condition summary, writes results.csv
"""
import argparse
import csv
import json
import pathlib
from itertools import product
from typing import NamedTuple

H1_DIR = pathlib.Path(__file__).parent.parent          # experiments/H1/
REFERENCE_DIR = H1_DIR / "reference_diagrams"
CONDITIONS_DIR = H1_DIR / "conditions"
RESULTS_CSV = pathlib.Path(__file__).parent / "results.csv"

CONDITIONS = ["C1_llm_only", "C2_static_only", "C3_dynamic_only",
              "C4_static_dynamic", "C5_full_pipeline"]
# S4/S5 (fault-path found-in-the-wild scenarios) were removed from the
# reported scenario set; S4 (constructed) now carries the fault-path /
# dual-gap demonstration on its own. See experiments/H1/README.md.
SCENARIOS = ["S1", "S2", "S3", "S4"]


class DiagramElement(NamedTuple):
    source: str
    target: str
    interaction: str

    @classmethod
    def from_dict(cls, d: dict) -> "DiagramElement":
        # Normalize interaction to bare function name (strip ClassName. prefix)
        # e.g. "Aggregator.getAll" → "getAll", "stream" → "stream"
        raw_interaction = d["interaction"].strip().lower()
        interaction = raw_interaction.split(".")[-1]
        return cls(
            source=d["source"].strip().lower(),
            target=d["target"].strip().lower(),
            interaction=interaction,
        )


def load_elements(path: pathlib.Path) -> set[DiagramElement]:
    if not path.exists():
        return set()
    with open(path) as f:
        data = json.load(f)
    return {DiagramElement.from_dict(e) for e in data}


def score(reference: set, generated: set) -> dict:
    tp = len(reference & generated)
    fp = len(generated - reference)
    fn = len(reference - generated)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3),
            "recall":    round(recall, 3),
            "f1":        round(f1, 3)}


def _micro_f1(mean_p: float, mean_r: float) -> float:
    """F1 computed from mean P and mean R (what a reader gets when they
    recompute from the table means). Different from macro_f1 when per-scenario
    P and R vary."""
    return round(2 * mean_p * mean_r / (mean_p + mean_r), 3) if (mean_p + mean_r) > 0 else 0.0


def run_all() -> list[dict]:
    rows = []
    print(f"\n{'Condition':30s} {'Scen':4s}  {'P':6s} {'R':6s} {'F1':6s}  TP FP FN")
    print("-" * 70)
    for condition, scenario in product(CONDITIONS, SCENARIOS):
        ref_path = REFERENCE_DIR / scenario / "elements.json"
        gen_path = CONDITIONS_DIR / condition / scenario / "elements.json"
        ref = load_elements(ref_path)
        gen = load_elements(gen_path)
        metrics = score(ref, gen)
        row = {"condition": condition, "scenario": scenario, **metrics}
        rows.append(row)
        print(f"{condition:30s} {scenario}  "
              f"P={metrics['precision']:.3f}  "
              f"R={metrics['recall']:.3f}  "
              f"F1={metrics['f1']:.3f}  "
              f"({metrics['tp']} {metrics['fp']} {metrics['fn']})")
    return rows


def print_summary(rows: list[dict]) -> None:
    """Print per-condition summary with BOTH macro_f1 and micro_f1."""
    print(f"\n{'':=<70}")
    print("SUMMARY (mean ± range across scenarios)")
    print(f"{'':=<70}")
    hdr = f"{'Condition':30s}  {'mean_P':6s}  {'mean_R':6s}  {'macro_F1':8s}  {'micro_F1':8s}  note"
    print(hdr)
    print("-" * len(hdr))

    for condition in CONDITIONS:
        crows = [r for r in rows if r["condition"] == condition]
        ps = [r["precision"] for r in crows]
        rs = [r["recall"]    for r in crows]
        f1s = [r["f1"]       for r in crows]

        mean_p   = round(sum(ps) / len(ps), 3)
        mean_r   = round(sum(rs) / len(rs), 3)
        macro_f1 = round(sum(f1s) / len(f1s), 3)
        micro_f1 = _micro_f1(mean_p, mean_r)

        # Range: max - min per metric
        rng_p  = round(max(ps)  - min(ps),  3)
        rng_r  = round(max(rs)  - min(rs),  3)
        rng_f1 = round(max(f1s) - min(f1s), 3)

        differ = " ← P≠R" if abs(macro_f1 - micro_f1) >= 0.02 else ""
        print(f"{condition:30s}  "
              f"{mean_p:.3f}±{rng_p:.2f}  "
              f"{mean_r:.3f}±{rng_r:.2f}  "
              f"{macro_f1:.3f}±{rng_f1:.2f}  "
              f"{micro_f1:.3f}      {differ}")

    print()
    print("Note: macro_F1 = mean of per-scenario F1 scores (thesis figure).")
    print("      micro_F1 = 2*mean_P*mean_R/(mean_P+mean_R) (reader's recomputed value).")
    print("      They differ when per-scenario P and R are not proportional.")
    print("      Ground truth: source-derived (primary-component edges only),")
    print("      independently validated against runtime traces.")
    print("      C3 constraint: only edges FROM the primary component are scored;")
    print("      this makes C3 non-trivially fallible (side-channel edges excluded).")


def write_csv(rows: list[dict]) -> None:
    fieldnames = ["condition", "scenario", "tp", "fp", "fn",
                  "precision", "recall", "f1"]
    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to {RESULTS_CSV}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=CONDITIONS)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all or (not args.condition and not args.scenario):
        rows = run_all()
        print_summary(rows)
        write_csv(rows)
    else:
        condition = args.condition or CONDITIONS[0]
        scenario  = args.scenario  or SCENARIOS[0]
        ref = load_elements(REFERENCE_DIR / scenario / "elements.json")
        gen = load_elements(CONDITIONS_DIR / condition / scenario / "elements.json")
        m = score(ref, gen)
        print(f"{condition} × {scenario}: P={m['precision']} R={m['recall']} F1={m['f1']}")


if __name__ == "__main__":
    main()
