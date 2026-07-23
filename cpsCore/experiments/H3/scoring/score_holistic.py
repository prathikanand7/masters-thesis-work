"""
score_holistic.py — H3 holistic 5-condition scorer
-----------------------------------------------------
Scores agent responses against ground truth for the holistic H3 design:

  1. Source only              (C_source_only/)
  2. Trace only                (Aprime_traces_only/)
  3. Diagram only              (D_diagram_only/)
  4. Source + Trace            (A_no_diagrams/)
  5. Source + Trace + Diagram  (B_with_diagrams/)

across S1, S2, S3, S4.

Component matching: case-insensitive substring search for the component name.
Interaction matching: source + target + bare interaction name must all appear
in the response (same convention as H1 and the original H3 scorer).

Usage:
    python score_holistic.py --all
"""
import csv
import json
import pathlib

H3_DIR   = pathlib.Path(__file__).parent.parent
SCEN_DIR = pathlib.Path(__file__).parent.parent.parent / "scenarios"  # experiments/scenarios/
RESP_DIR = H3_DIR / "agent_conditions" / "responses"

SCENARIOS = ["S1a", "S2", "S3", "S4"]  # S1b pending new response collection

CONDITIONS = {
    "source":              "C_source_only",
    "trace":               "Aprime_traces_only",
    "diagram":             "D_diagram_only",
    "source_trace":        "A_no_diagrams",
    "source_trace_diagram":"B_with_diagrams",
}


def _bare(name: str) -> str:
    return name.split(".")[-1]


def load_ground_truth(scenario: str) -> dict:
    path = SCEN_DIR / scenario / "gt_interactions.json"
    with open(path, encoding="utf-8") as f:
        interactions = json.load(f)
    components = sorted({e["source"] for e in interactions} | {e["target"] for e in interactions})
    return {"components": components, "interactions": interactions}


def score_components(response: str, gt_components: list) -> tuple:
    resp_lower = response.lower()
    correct = sum(1 for c in gt_components if c.lower() in resp_lower)
    return correct, len(gt_components)


def score_interactions(response: str, gt_interactions: list) -> tuple:
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
    rows = []
    for condition, subdir in CONDITIONS.items():
        for scenario in SCENARIOS:
            gt = load_ground_truth(scenario)
            resp_path = RESP_DIR / subdir / f"{scenario}_response.txt"
            if not resp_path.exists():
                print(f"[MISSING] {resp_path}")
                continue
            response = resp_path.read_text(encoding="utf-8")

            comp_correct, comp_total = score_components(response, gt.get("components", []))
            intr_correct, intr_total = score_interactions(response, gt.get("interactions", []))

            row = {
                "condition":    condition,
                "scenario":     scenario,
                "comp_correct": comp_correct,
                "comp_total":   comp_total,
                "intr_correct": intr_correct,
                "intr_total":   intr_total,
                "completeness": 0,
            }
            rows.append(row)
            print(f"{condition:22s} x {scenario}  "
                  f"components={comp_correct}/{comp_total}  "
                  f"interactions={intr_correct}/{intr_total}")

    fieldnames = ["condition", "scenario", "comp_correct", "comp_total",
                  "intr_correct", "intr_total", "completeness"]
    out_path = pathlib.Path(__file__).parent / "results_holistic.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written to {out_path}")
    print("Fill in 'completeness' manually using scoring/rubric.md")


if __name__ == "__main__":
    main()
