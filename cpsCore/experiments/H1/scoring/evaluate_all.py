"""
evaluate_all.py — Full H1 evaluation pipeline
=============================================
1. Re-runs C3, C4, C5, and C6 for all scenarios (C1, C2, C7, C8, C9 results are read as-is).
2. Scores all nine conditions (C1–C9) against ground truth from derive_gt_arch.py.
3. Writes results to results.csv and prints a summary table.

Ground truth methodology
------------------------
GT is produced by experiments/scenarios/derive_gt_arch.py (Neo4j-free).
Two sources are combined:

  1. trace_slice.txt — runtime events captured at Neo4j-identified instrumentation
     sites (guided instrumentation via clang-exp; one site per excalidraw arrow).
  2. arch_filters.py — two filters derived from the excalidraw architectural diagrams:
       REACHABILITY:    allowed (ClientComponent, ServerComponent) component pairs
       SCENARIO_ENTRY:  allowed ClientFunction names (scenario entry-point callers only)

Algorithm: keep trace_slice.txt rows where
  (ClientComponent, ServerComponent) ∈ REACHABILITY
  AND ClientFunction ∈ SCENARIO_ENTRY[scenario]
then deduplicate to unique (source, target, interaction) triples.

Validated at F1 = 1.000 vs the original Neo4j-derived GT (derive_gt.py) on all scenarios.

Per-scenario ground truth (from gt_interactions.json, gt_sequence.json):

  S1a ("Synchronized Runner Test")           — 2 interactions, 8 sequence events
      Sync→Agg:getAll  (×2, SynchronizedRunner.runSynchronized)
      Sync→Log:flush   (×6, SynchronizedRunner.runSynchronized)
      GT: {Sync→Agg:getAll, Sync→Log:flush}
      NOTE: Agg→Log:stream events from Aggregator.add are EXCLUDED — they fire during
            test setup before any SCENARIO_ENTRY function, so SCENARIO_ENTRY filter drops them.

  S1b ("Synchronized Runner Timeout")        — 3 interactions, 5 sequence events
      Sync→Agg:getAll        (×2, SynchronizedRunner.runSynchronized)
      Sync→Log:flush         (×2, SynchronizedRunner.runSynchronized)
      Sync→Log:RAIILogStream.stream (×1, SynchronizedRunnerMaster.runStage — timeout warning)
      GT: {Sync→Agg:getAll, Sync→Log:flush, Sync→Log:stream}
      NOTE: this interaction IS captured in trace_slice.txt at the probe site even though
            full_trace.txt may not record it at all log levels.

  S2  ("Optional test")                      — 1 interaction, 1 sequence event
      Config→Log:stream (×1, PropertyMapper.add)
      GT: {Config→Log:stream}

  S3  ("MultiThreaded Test 1")               — 3 interactions, 13 sequence events
      Sync→Agg:getAll  (×2, AggregatableRunner.notifyAggregationOnUpdate)
      Agg→Log:stream   (×2, ObjectHandleContainer.setFromAggregationIfNotSet)
      Util→Log:stream  (×9, MultiThreadingScheduler.schedule/run/runSchedule/stop)
      GT: {Sync→Agg:getAll, Agg→Log:stream, Util→Log:stream}

Scoring
-------
Match rule:
  TP = ground-truth edge (src, tgt, bare_method) also in generated set
  FP = generated edge not in ground truth
  FN = ground-truth edge missing from generated set
  bare_method = interaction.split(".")[-1].lower()   e.g. "Aggregator.getAll" → "getall"

Metrics:
  Precision = TP / (TP + FP)
  Recall    = TP / (TP + FN)
  F1        = 2 * P * R / (P + R)  (0 if denominator is 0)
"""

import csv
import json
import pathlib
import re
import subprocess
import sys

ROOT      = pathlib.Path(__file__).parent.parent.parent.parent  # cpsCore/
SCEN_DIR  = ROOT / "experiments" / "scenarios"
H1_DIR    = ROOT / "experiments" / "H1"
COND_DIR  = H1_DIR / "conditions"
SCORE_DIR = pathlib.Path(__file__).parent

PYTHON    = sys.executable
CONDITION_LABELS = {
    "C1_llm_only":               "C1",
    "C2_static_only":            "C2",
    "C3_dynamic_only":           "C3",
    "C4_guided_only":            "C4",
    "C5_guided_reach":           "C5",
    "C6_full_trace_reach_only":  "C6",
    "C7_llm_c2":                 "C7",
    "C8_llm_c3":                 "C8",
    "C9_llm_c4":                 "C9",
}

CONDITIONS = ["C1_llm_only", "C2_static_only", "C3_dynamic_only",
              "C4_guided_only", "C5_guided_reach", "C6_full_trace_reach_only",
              "C7_llm_c2", "C8_llm_c3", "C9_llm_c4"]
SCENARIOS  = ["S1a", "S1b", "S2", "S3"]

# Path to the clang-uml annotated package diagram (static architecture reference)
ANNOTATED_PUML = ROOT / "architectural_diagrams" / "cpsCore_packages_annotated.puml"


# ── 0. Parse annotated diagram → valid (src, tgt) architectural edges ──────

def load_valid_edges(puml_path: pathlib.Path) -> set[tuple[str, str]]:
    """Parse cpsCore_packages_annotated.puml and return the set of valid
    (source_pkg, target_pkg) directed edges confirmed by clang-uml static analysis."""
    if not puml_path.exists():
        print(f"  [WARN] Annotated diagram not found: {puml_path} — skipping validation")
        return set()
    edges: set[tuple[str, str]] = set()
    for line in puml_path.read_text().splitlines():
        m = re.match(r'^(\w+)\s+\.\.[>|]\s+(\w+)', line.strip())
        if m:
            edges.add((m.group(1).lower(), m.group(2).lower()))
    return edges

VALID_EDGES = load_valid_edges(ANNOTATED_PUML)


# ── 1. Re-run conditions that depend on trace_slice.txt ────────────────────

def run_conditions():
    """Re-run C3, C4, C5, and C6 to pick up updated trace files."""
    for script in ["run_c3_dynamic_only.py", "run_c4_guided_only.py",
                   "run_c5_guided_reach.py", "run_c6_full_trace_reach_only.py"]:
        path = H1_DIR / "conditions" / script
        print(f"\n→ Running {script} --all ...")
        result = subprocess.run(
            [PYTHON, str(path), "--all"],
            cwd=str(H1_DIR / "conditions"),
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"  [WARN] {script} exited {result.returncode}: {result.stderr[:300]}")


# ── 2. Scoring helpers ─────────────────────────────────────────────────────

def bare(interaction: str) -> str:
    """Normalize to bare method name: 'Aggregator.getAll' → 'getall'."""
    return interaction.split(".")[-1].strip().lower()


def class_name(interaction: str) -> str:
    """Normalize to bare class name: 'Aggregator.getAll' → 'aggregator'."""
    return interaction.split(".")[0].strip().lower()


def load_raw(path: pathlib.Path) -> list[dict]:
    """Load elements.json without normalisation."""
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [d for d in data if d.get("source") and d.get("target") and d.get("interaction")]


def load_set(path: pathlib.Path, normalise=bare, validate_edges: bool = False) -> set[tuple]:
    result = set()
    for d in load_raw(path):
        src  = d["source"].strip().lower()
        tgt  = d["target"].strip().lower()
        intr = normalise(d["interaction"])
        if src and tgt and intr:
            if validate_edges and VALID_EDGES and (src, tgt) not in VALID_EDGES:
                continue  # trace event on an edge not confirmed by clang-uml diagram
            result.add((src, tgt, intr))
    return result


def load_edges(path: pathlib.Path) -> set[tuple]:
    """Load as (src, tgt) pairs — for structural edge-presence scoring."""
    result = set()
    for d in load_raw(path):
        src = d["source"].strip().lower()
        tgt = d["target"].strip().lower()
        if src and tgt:
            result.add((src, tgt))
    return result


def lcs_length(a: list, b: list) -> int:
    """Length of Longest Common Subsequence of two lists (element equality)."""
    m, n = len(a), len(b)
    # Use two-row DP to save memory
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr
    return prev[n]


def load_sequence_list(path: pathlib.Path) -> list[tuple]:
    """Load ordered sequence as list of (src, tgt, bare_method) tuples."""
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    result = []
    for d in data:
        src  = (d.get("source") or "").strip().lower()
        tgt  = (d.get("target") or "").strip().lower()
        intr = bare((d.get("interaction") or ""))
        if src and tgt and intr:
            result.append((src, tgt, intr))
    return result


def lcs_recall(ref: list, gen: list) -> float:
    """LCS recall = |LCS(gen, ref)| / |ref|. 0.0 if ref is empty."""
    if not ref:
        return 0.0
    return round(lcs_length(ref, gen) / len(ref), 3)


def lcs_f1(ref: list, gen: list) -> tuple[float, float, float]:
    """LCS-based P, R, F1.
    P = |LCS| / |generated|  (penalises over-generation)
    R = |LCS| / |GT|         (penalises missed elements)
    """
    if not ref:
        return 0.0, 0.0, 0.0
    lcs = lcs_length(ref, gen)
    p = round(lcs / len(gen), 3) if gen else 0.0
    r = round(lcs / len(ref), 3)
    f = round(2 * p * r / (p + r), 3) if (p + r) > 0 else 0.0
    return p, r, f


def f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def score_one(ref: set, gen: set) -> dict:
    tp = len(ref & gen)
    fp = len(gen - ref)
    fn = len(ref - gen)
    p, r, f = f1(tp, fp, fn)
    return {"TP": tp, "FP": fp, "FN": fn, "P": p, "R": r, "F1": f}


# ── 3. Main evaluation loop ────────────────────────────────────────────────

def evaluate() -> list[dict]:
    rows = []
    for scenario in SCENARIOS:
        ref_intr_path = SCEN_DIR / scenario / "gt_interactions.json"
        ref_seq_path  = SCEN_DIR / scenario / "gt_sequence.json"
        # Interactions GT: deduplicated set, validated against puml
        ref_intr = load_set(ref_intr_path, bare, validate_edges=True)
        if not ref_intr:
            print(f"  [SKIP] No gt_interactions.json for {scenario}")
            continue
        # Sequence GT: full ordered list from trace
        ref_seq_list = load_sequence_list(ref_seq_path)
        for condition in CONDITIONS:
            cond_dir = COND_DIR / condition / scenario
            # ── Interactions scoring (set F1) ──
            gen_intr = load_set(cond_dir / "interactions.json", bare)
            intr_scores = score_one(ref_intr, gen_intr)
            # ── Sequence scoring (LCS F1) ──
            gen_seq_list = load_sequence_list(cond_dir / "sequence.json")
            seq_p, seq_r, seq_f1 = lcs_f1(ref_seq_list, gen_seq_list)
            row = {
                "scenario": scenario, "condition": condition,
                "intr_TP": intr_scores["TP"], "intr_FP": intr_scores["FP"],
                "intr_FN": intr_scores["FN"], "intr_P":  intr_scores["P"],
                "intr_R":  intr_scores["R"],  "intr_F1": intr_scores["F1"],
                "seq_GT_len": len(ref_seq_list),
                "seq_gen_len": len(gen_seq_list),
                "seq_P": seq_p, "seq_R": seq_r, "seq_F1": seq_f1,
            }
            rows.append(row)
    return rows


# ── 4. Reporting ───────────────────────────────────────────────────────────

def print_table(rows: list[dict]):
    hdr = f"{'Scenario':<8} {'Condition':<22}  {'intr_TP':>7} {'intr_FP':>7} {'intr_FN':>7} {'intr_F1':>8}  {'seq_GT':>6} {'seq_gen':>7} {'seq_P':>7} {'seq_R':>7} {'seq_F1':>8}"
    print("\n" + hdr)
    print("-" * len(hdr))
    cur_scen = None
    for r in rows:
        if r["scenario"] != cur_scen:
            if cur_scen is not None:
                print()
            cur_scen = r["scenario"]
        print(f"{r['scenario']:<8} {CONDITION_LABELS.get(r['condition'], r['condition']):<6} "
              f" {r['intr_TP']:>7} {r['intr_FP']:>7} {r['intr_FN']:>7} {r['intr_F1']:>8.3f} "
              f" {r['seq_GT_len']:>6} {r['seq_gen_len']:>7} {r['seq_P']:>7.3f} {r['seq_R']:>7.3f} {r['seq_F1']:>8.3f}")

    print("\n\u2500\u2500 Macro per condition \u2500\u2500\u2500")
    print(f"  {'Condition':<22}  {'intr_macro':>11} {'seq_macro':>10}")
    for cond in CONDITIONS:
        cond_rows = [r for r in rows if r["condition"] == cond]
        if cond_rows:
            intr_macro = round(sum(r["intr_F1"] for r in cond_rows) / len(cond_rows), 3)
            seq_macro  = round(sum(r["seq_F1"]  for r in cond_rows) / len(cond_rows), 3)
            print(f"  {cond:<22}  {intr_macro:>11.3f} {seq_macro:>10.3f}")


def write_csv(rows: list[dict]):
    out = SCORE_DIR / "results.csv"
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["scenario","condition",
                                               "intr_TP","intr_FP","intr_FN","intr_P","intr_R","intr_F1",
                                               "seq_GT_len","seq_gen_len","seq_P","seq_R","seq_F1"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nResults written → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    skip_rerun = "--no-rerun" in sys.argv
    if not skip_rerun:
        run_conditions()
    rows = evaluate()
    print_table(rows)
    write_csv(rows)
