"""
score_agent.py — H3 agent response scorer
-------------------------------------------
Scores agent responses against ground truth on three measures:
  1. Components correct   (count of ground-truth components mentioned)
  2. Interactions correct (count of ground-truth interactions mentioned)
  3. Completeness         (1-5 rubric score — apply manually, see rubric.md)

Component matching: case-insensitive substring search for the component name.

Interaction matching: all three fields (source, target, interaction) must appear
in the response.  The interaction field is matched by its **bare name** (the part
after the last "."), e.g. "Aggregator.getAll" → matched as "getAll".  This
mirrors the convention used in H1 scoring and handles the fact that agents
typically write bare method names rather than fully-qualified "Class.method"
strings.

Usage:
    python score_agent.py --all        # auto-scores components + interactions
    python score_agent.py --condition A --scenario S1
    python score_agent.py --all
    python score_agent.py --all --no-source   # score Experiment 2 (traces-only)

The completeness score column is left 0 (placeholder) until manually filled in.
Edit results.csv (or results_exp2.csv) after running to add completeness scores.
"""
import argparse
import csv
import json
import pathlib

H3_DIR      = pathlib.Path(__file__).parent.parent          # experiments/H3/
SCEN_DIR    = pathlib.Path(__file__).parent.parent.parent / "scenarios"  # experiments/scenarios/
RESP_DIR    = H3_DIR / "agent_conditions" / "responses"

CONDITIONS_EXP1 = {"A": "A_no_diagrams",       "B": "B_with_diagrams"}
CONDITIONS_EXP2 = {"A": "Aprime_traces_only",  "B": "Bprime_traces_diagram"}
# S4/S5 (fault-path found-in-the-wild scenarios) were removed from the
# reported scenario set; S4 (constructed) now carries the fault-path /
# dual-gap demonstration on its own. See experiments/H3/README.md and
# experiments/H1/README.md.
SCENARIOS  = ["S1a", "S2", "S3", "S4"]  # S1b pending new response collection


def _bare(name: str) -> str:
    """Return the bare method name: 'Aggregator.getAll' → 'getAll'."""
    return name.split(".")[-1]


def load_ground_truth(scenario: str) -> dict:
    path = SCEN_DIR / scenario / "gt_interactions.json"
    if not path.exists():
        return {"components": [], "interactions": []}
    with open(path, encoding="utf-8") as f:
        interactions = json.load(f)
    components = sorted({e["source"] for e in interactions} | {e["target"] for e in interactions})
    return {"components": components, "interactions": interactions}


def score_components(response: str, gt_components: list[str]) -> tuple[int, int]:
    """Returns (correct, total) — case-insensitive substring match."""
    resp_lower = response.lower()
    correct = sum(1 for c in gt_components if c.lower() in resp_lower)
    return correct, len(gt_components)


def score_interactions(response: str, gt_interactions: list[dict]) -> tuple[int, int]:
    """
    Each ground-truth interaction is {"source": ..., "target": ..., "interaction": ...}.
    A response matches an interaction if it contains:
      - the source component name (case-insensitive)
      - the target component name (case-insensitive)
      - the bare interaction name, i.e. the part after the last "." (case-insensitive)
        e.g. "Aggregator.getAll" → check for "getAll"
    All three must appear somewhere in the response.
    """
    resp_lower = response.lower()
    correct = 0
    for item in gt_interactions:
        src  = item["source"].lower()
        tgt  = item["target"].lower()
        intr = _bare(item["interaction"]).lower()
        if src in resp_lower and tgt in resp_lower and intr in resp_lower:
            correct += 1
    return correct, len(gt_interactions)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=["A", "B"])
    parser.add_argument("--scenario",  choices=SCENARIOS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-source", dest="no_source", action="store_true",
                        help="Score Experiment 2 responses (traces-only conditions)")
    args = parser.parse_args()

    conditions = CONDITIONS_EXP2 if args.no_source else CONDITIONS_EXP1
    results_csv = pathlib.Path(__file__).parent / ("results_exp2.csv" if args.no_source else "results.csv")
    # Condition label suffix for CSV clarity
    cond_suffix = "'" if args.no_source else ""

    if args.all:
        pairs = [(c, s) for c in conditions for s in SCENARIOS]
    elif args.condition and args.scenario:
        pairs = [(args.condition, args.scenario)]
    else:
        parser.error("Provide --all or both --condition and --scenario")

    rows = []
    for condition, scenario in pairs:
        gt = load_ground_truth(scenario)
        resp_path = RESP_DIR / conditions[condition] / f"{scenario}_response.txt"
        if not resp_path.exists():
            print(f"[MISSING] {resp_path}")
            continue
        response = resp_path.read_text(encoding="utf-8")

        comp_correct, comp_total = score_components(response, gt.get("components", []))
        intr_correct, intr_total = score_interactions(response, gt.get("interactions", []))

        row = {
            "condition":    f"{condition}{cond_suffix}",
            "scenario":     scenario,
            "comp_correct": comp_correct,
            "comp_total":   comp_total,
            "intr_correct": intr_correct,
            "intr_total":   intr_total,
            "completeness": 0,   # fill in manually from rubric.md
        }
        rows.append(row)
        print(f"{condition}{cond_suffix} × {scenario}  "
              f"components={comp_correct}/{comp_total}  "
              f"interactions={intr_correct}/{intr_total}  "
              f"completeness=<manual>")

    if not rows:
        print("No responses found to score.")
        return

    fieldnames = ["condition", "scenario",
                  "comp_correct", "comp_total",
                  "intr_correct", "intr_total",
                  "completeness"]
    with open(results_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to {results_csv}")
    print("Fill in the 'completeness' column manually using scoring/rubric.md")


if __name__ == "__main__":
    main()
