"""
run_full_trace_experiment.py — one-off full-trace run for C3/C4
================================================================
Runs C3f / C4f (full_trace.txt instead of trace_slice.txt) in-process,
scores all four conditions (C3/C4 guided + C3f/C4f full), and prints
a side-by-side comparison table.

Output folders:
  experiments/H1/conditions/C3_dynamic_full/
  experiments/H1/conditions/C4_static_dynamic_full/
"""
import json
import pathlib
import shutil
import sys

# ── Bootstrap path ────────────────────────────────────────────────────────
SCRIPT_DIR = pathlib.Path(__file__).parent
COND_DIR   = SCRIPT_DIR.parent / "conditions"
sys.path.insert(0, str(COND_DIR))

from _utils import (
    SCENARIOS, SCENARIO_COMPONENTS,
    Element, save_elements, save_sequence,
    interactions_path, sequence_path,
    load_full_trace, load_elements,
)

# ── Labels ────────────────────────────────────────────────────────────────
C3F = "C3_dynamic_full"
C4F = "C4_static_dynamic_full"


# ── C3f — dynamic-only, full trace ───────────────────────────────────────

def run_c3f(scenario: str) -> None:
    rows    = load_full_trace(scenario)
    allowed = SCENARIO_COMPONENTS[scenario]
    elements: set[Element] = set()
    ordered_events: list[dict] = []

    for pos, row in enumerate(rows):
        src  = row.get("ClientComponent", "").strip()
        tgt  = row.get("ServerComponent",  "").strip()
        intr = row.get("EventName",        "").strip()
        if src and tgt and intr and src in allowed and tgt in allowed and src != tgt:
            elements.add(Element(src, tgt, intr))
            ordered_events.append({"order": pos, "source": src, "target": tgt, "interaction": intr})

    save_elements(elements, interactions_path(C3F, scenario))
    save_sequence(ordered_events, sequence_path(C3F, scenario))


# ── C4f — static ∪ full-trace ────────────────────────────────────────────

def _normalize(elements: set) -> set:
    return {Element(e.source, e.target, e.interaction.split(".")[-1]) for e in elements}


def run_c4f(scenario: str) -> None:
    c2  = _normalize(load_elements(interactions_path("C2_static_only", scenario)))
    c3f = _normalize(load_elements(interactions_path(C3F,              scenario)))
    if not c2:
        print(f"  [WARN] C2 missing for {scenario}")
    merged = c2 | c3f
    save_elements(merged, interactions_path(C4F, scenario))

    c3f_seq = sequence_path(C3F, scenario)
    c4f_seq = sequence_path(C4F, scenario)
    c4f_seq.parent.mkdir(parents=True, exist_ok=True)
    if c3f_seq.exists():
        shutil.copy2(c3f_seq, c4f_seq)
    else:
        c4f_seq.write_text("[]")
    print(f"  C2={len(c2)}  C3f={len(c3f)}  merged={len(merged)}")


# ── Scoring helpers ───────────────────────────────────────────────────────

ROOT     = COND_DIR.parent.parent.parent
SCEN_DIR = ROOT / "experiments" / "scenarios"


def bare_str(s: str) -> str:
    return s.split(".")[-1].strip().lower()


def load_gt_set(scenario: str) -> set[tuple]:
    p = SCEN_DIR / scenario / "gt_interactions.json"
    if not p.exists():
        return set()
    data = json.loads(p.read_text())
    return {(d["source"].lower(), d["target"].lower(), bare_str(d["interaction"])) for d in data}


def load_generated_set(label: str, scenario: str) -> set[tuple]:
    p = interactions_path(label, scenario)
    if not p.exists():
        return set()
    data = json.loads(p.read_text())
    return {(d["source"].lower(), d["target"].lower(), bare_str(d["interaction"])) for d in data}


def load_gt_seq(scenario: str) -> list[tuple]:
    p = SCEN_DIR / scenario / "gt_sequence.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [(d["source"].lower(), d["target"].lower(), bare_str(d["interaction"])) for d in data]


def load_gen_seq(label: str, scenario: str) -> list[tuple]:
    p = sequence_path(label, scenario)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [(d["source"].lower(), d["target"].lower(), bare_str(d["interaction"])) for d in data]


def f1(tp: int, fp: int, fn: int) -> float:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * p * r / (p + r) if (p + r) else 0.0


def lcs_length(a: list, b: list) -> int:
    m, n = len(a), len(b)
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


def score_intr(label: str, scenario: str) -> float:
    gt  = load_gt_set(scenario)
    gen = load_generated_set(label, scenario)
    tp  = len(gt & gen)
    fp  = len(gen - gt)
    fn  = len(gt - gen)
    return f1(tp, fp, fn)


def score_seq(label: str, scenario: str) -> float:
    gt  = load_gt_seq(scenario)
    gen = load_gen_seq(label, scenario)
    if not gt and not gen:
        return 1.0
    if not gen:
        return 0.0
    lcs = lcs_length(gt, gen)
    p = lcs / len(gen)
    r = lcs / len(gt) if gt else 1.0
    return 2 * p * r / (p + r) if (p + r) else 0.0


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("Running full-trace variants: C3f / C4f")
    print("=" * 70)

    for scenario in SCENARIOS:
        print(f"\n── {scenario} ──")
        print(f"  C3f (dynamic full):"); run_c3f(scenario)
        print(f"  C4f (union full):"); run_c4f(scenario)

    print("\n\n" + "=" * 70)
    print("RESULTS: Guided (trace_slice.txt) vs Full (full_trace.txt)")
    print("=" * 70)

    guided_labels = {"C3": "C3_dynamic_only",
                     "C4": "C4_guided_trace"}
    full_labels   = {"C3f": C3F, "C4f": C4F}

    # Build score table
    for metric, score_fn in [("Interactions F1", score_intr), ("Sequence F1", score_seq)]:
        print(f"\n{metric}")
        header = f"{'Scenario':<8}" + "".join(
            f" {'C3':>6} {'C3f':>6} {'C4':>6} {'C4f':>6}"
        )
        print(header)
        print("-" * len(header))

        g_sums = {k: 0.0 for k in guided_labels}
        f_sums = {k: 0.0 for k in full_labels}

        for scenario in SCENARIOS:
            row = f"{scenario:<8}"
            for (gname, glabel), (fname, flabel) in zip(
                    guided_labels.items(), full_labels.items()):
                g = score_fn(glabel, scenario)
                f = score_fn(flabel, scenario)
                row += f" {g:>6.3f} {f:>6.3f}"
                g_sums[gname] += g
                f_sums[fname] += f
            print(row)

        n = len(SCENARIOS)
        macro_row = f"{'Macro':<8}"
        for gname, fname in zip(guided_labels, full_labels):
            g = g_sums[gname] / n
            f = f_sums[fname] / n
            macro_row += f" {g:>6.3f} {f:>6.3f}"
        print("-" * len(header))
        print(macro_row)

    print()


if __name__ == "__main__":
    main()
