"""
evaluate_all_h3.py — Full H3 evaluation pipeline
==================================================
1. Re-derives H3 ground truth from updated H1 reference_sequence.json files.
2. Re-collects responses for updated conditions (S3 scenario changed; condition B
   uses improved C5 diagram).
3. Scores all conditions and writes results.

Usage:
    # Full pipeline (re-collects S3 + condition B responses):
    python3 evaluate_all_h3.py

    # Score only (skip API calls):
    python3 evaluate_all_h3.py --no-rerun

Output:
    experiments/H3/scoring/results_h3.csv
    experiments/H3/scoring/results_h3.md  (summary table)

Conditions evaluated (Experiment 1 = with source, Experiment 2 = traces only):
    A  = source + trace       (no diagram)
    B  = source + trace + C5  (with diagram)

Scenarios: S1a, S2, S3, S4  (S1b pending new response collection)
"""

import argparse
import csv
import json
import pathlib
import subprocess
import sys

ROOT         = pathlib.Path(__file__).parent.parent.parent.parent  # cpsCore/
SCEN_DIR     = ROOT / "experiments" / "scenarios"
H3_DIR       = ROOT / "experiments" / "H3"
SCORING_DIR  = H3_DIR / "scoring"
AGENT_DIR    = H3_DIR / "agent_conditions"
RESPONSES    = AGENT_DIR / "responses"
PYTHON       = "/root/miniforge3/envs/llm4legacy/bin/python3"

SCENARIOS   = ["S1a", "S2", "S3", "S4"]
CONDITIONS  = {"A": "A_no_diagrams", "B": "B_with_diagrams"}
RESULTS_CSV = SCORING_DIR / "results_h3.csv"


# ── 1. Ground truth ────────────────────────────────────────────────────────
# Ground truth is now read directly from scenarios/SX/gt_interactions.json.
# derive_ground_truth.py has been removed — no pre-step needed.


# ── 2. Re-collect stale responses ─────────────────────────────────────────

def recollect_responses():
    """Re-collect S3 (scenario changed) and all condition B (improved C5 diagram)."""
    print("\n→ Re-collecting stale responses ...")
    tasks = [
        # S3 changed to MultiThreaded Test 1 — both conditions need refresh
        ("A", "S3"), ("B", "S3"),
        # All condition B responses benefit from improved C5 diagram
        ("B", "S1a"), ("B", "S2"), ("B", "S4"),
    ]
    script = str(AGENT_DIR / "run_agent.py")
    for cond, scen in tasks:
        print(f"  Collecting {cond} × {scen} ...")
        r = subprocess.run([PYTHON, script, "--condition", cond, "--scenario", scen],
                           cwd=str(AGENT_DIR), capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [WARN] {cond}×{scen}: {r.stderr[:150]}")
        else:
            print(f"  ✓ {cond} × {scen}")


# ── 3. Score ───────────────────────────────────────────────────────────────

def load_gt(scenario: str) -> dict:
    path = SCEN_DIR / scenario / "ground_truth.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def load_response(condition_dir: str, scenario: str) -> str:
    path = RESPONSES / condition_dir / f"{scenario}_response.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def score_components(gt_comps: list, response: str) -> tuple[int, int]:
    found = sum(1 for c in gt_comps if c.lower() in response.lower())
    return found, len(gt_comps)


def score_interactions(gt_interactions: list, response: str) -> tuple[int, int]:
    resp_lower = response.lower()
    found = 0
    for e in gt_interactions:
        method = e["interaction"].split(".")[-1].lower()
        src    = e["source"].lower()
        tgt    = e["target"].lower()
        if method in resp_lower and src in resp_lower and tgt in resp_lower:
            found += 1
    return found, len(gt_interactions)


def run_scoring() -> list[dict]:
    rows = []
    for cond_key, cond_dir in CONDITIONS.items():
        for scenario in SCENARIOS:
            gt = load_gt(scenario)
            if not gt:
                print(f"  [SKIP] No GT for {scenario}")
                continue
            response = load_response(cond_dir, scenario)
            if not response:
                print(f"  [SKIP] No response for {cond_key}×{scenario}")
                continue
            comp_found, comp_total = score_components(gt.get("components", []), response)
            intr_found, intr_total = score_interactions(gt.get("interactions", []), response)
            rows.append({
                "condition": cond_key, "scenario": scenario,
                "comp_found": comp_found, "comp_total": comp_total,
                "comp_recall": round(comp_found / comp_total, 3) if comp_total else 0,
                "intr_found": intr_found, "intr_total": intr_total,
                "intr_recall": round(intr_found / intr_total, 3) if intr_total else 0,
                "completeness": "<manual>",
            })
            print(f"  {cond_key} × {scenario}  "
                  f"components={comp_found}/{comp_total}  "
                  f"interactions={intr_found}/{intr_total}")
    return rows


# ── 4. Write outputs ───────────────────────────────────────────────────────

def write_csv(rows: list[dict]):
    fields = ["condition","scenario","comp_found","comp_total","comp_recall",
              "intr_found","intr_total","intr_recall","completeness"]
    with open(RESULTS_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"\nResults → {RESULTS_CSV.relative_to(ROOT)}")


def print_table(rows: list[dict]):
    print(f"\n{'Cond':<5} {'Scenario':<8} {'Components':>12} {'Interactions':>14} {'Completeness':>14}")
    print("-" * 60)
    for r in sorted(rows, key=lambda x: (x["condition"], x["scenario"])):
        print(f"{r['condition']:<5} {r['scenario']:<8} "
              f"  {r['comp_found']}/{r['comp_total']} ({r['comp_recall']:.2f})  "
              f"  {r['intr_found']}/{r['intr_total']} ({r['intr_recall']:.2f})  "
              f"  {r['completeness']}")
    # Macro recall per condition
    print("\n── Macro recall per condition ──")
    for cond in CONDITIONS:
        cond_rows = [r for r in rows if r["condition"] == cond]
        if cond_rows:
            comp_macro = round(sum(r["comp_recall"] for r in cond_rows) / len(cond_rows), 3)
            intr_macro = round(sum(r["intr_recall"] for r in cond_rows) / len(cond_rows), 3)
            print(f"  {cond}: comp_recall={comp_macro:.3f}  intr_recall={intr_macro:.3f}")


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-rerun", action="store_true",
                        help="Skip re-deriving GT and re-collecting responses")
    args = parser.parse_args()

    if not args.no_rerun:
        recollect_responses()

    print("\n→ Scoring ...")
    rows = run_scoring()
    print_table(rows)
    write_csv(rows)
