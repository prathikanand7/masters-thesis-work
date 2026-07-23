"""
derive_gt_arch.py — Neo4j-free GT derivation from excalidraw arch filter + trace_slice.txt
===========================================================================================
Replaces derive_gt.py for scenarios where Neo4j is unavailable.

Algorithm
---------
1. Load trace_slice.txt for each scenario.
2. Keep only rows where:
   a. (ClientComponent, ServerComponent) ∈ REACHABILITY  (from excalidraw diagram)
   b. ClientFunction ∈ SCENARIO_ENTRY[scenario]          (entry-point scope filter)
3. Deduplicate to unique (source, target, interaction) triples.
4. Write gt_interactions.json.

Validation: F1 = 1.000 vs existing Neo4j-derived GT on all 4 scenarios (S1a, S1b, S2, S3).

Usage
  python derive_gt_arch.py                  # all scenarios, write files
  python derive_gt_arch.py --scenario S1a  # single scenario
  python derive_gt_arch.py --dry-run       # print only, do not write
"""

import argparse
import csv
import json
import pathlib

ROOT     = pathlib.Path(__file__).parent.parent.parent   # cpsCore/
SCEN_DIR = pathlib.Path(__file__).parent                 # experiments/scenarios/

SCENARIOS = ["S1a", "S1b", "S2", "S3"]

SCENARIO_COMPONENTS: dict[str, set[str]] = {
    "S1a": {"Synchronization", "Aggregation", "Logging"},
    "S1b": {"Synchronization", "Aggregation", "Logging"},
    "S2":  {"Configuration",   "Logging"},
    "S3":  {"Synchronization", "Aggregation", "Utilities", "Logging"},
}

# Component-level reachability derived from excalidraw arch diagrams.
# An edge (A, B) means component A calls into component B in at least one scenario.
REACHABILITY: set[tuple[str, str]] = {
    ("Aggregation",     "Logging"),
    ("Configuration",   "Logging"),
    ("Synchronization", "Aggregation"),
    ("Synchronization", "Logging"),
    ("Utilities",       "Logging"),
}

# Entry-point functions per scenario.
# Only trace events whose ClientFunction matches one of these (Class.method) are kept.
# This excludes setup-phase calls (e.g. Aggregator.add) that fire before the scenario.
SCENARIO_ENTRY: dict[str, list[tuple[str, str]]] = {
    "S1a": [("SynchronizedRunner",      "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S1b": [("SynchronizedRunner",      "runSynchronized"),
            ("SynchronizedRunnerMaster", "runStage")],
    "S2":  [("PropertyMapper",          "addOptional"),
            ("PropertyMapper",          "add")],
    "S3":  [("AggregatableRunner",      "runAllStages"),
            ("AggregatableRunner",      "notifyAggregationOnUpdate"),
            ("MultiThreadingScheduler", "schedule"),
            ("MultiThreadingScheduler", "run"),
            ("MultiThreadingScheduler", "runSchedule"),
            ("MultiThreadingScheduler", "stop"),
            ("ObjectHandleContainer",   "setFromAggregationIfNotSet")],
}


def is_entry(client_function: str, entries: list[tuple[str, str]]) -> bool:
    for cls, method in entries:
        if client_function == cls + "." + method:
            return True
    return False


def derive_gt(scenario: str) -> list[dict]:
    """Return sorted list of {source, target, interaction} dicts for one scenario."""
    slice_path = SCEN_DIR / scenario / "trace_slice.txt"
    if not slice_path.exists():
        raise FileNotFoundError(f"trace_slice.txt not found: {slice_path}")

    allowed = SCENARIO_COMPONENTS[scenario]
    entries = SCENARIO_ENTRY[scenario]
    seen: set[tuple[str, str, str]] = set()

    with open(slice_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            src = (row.get("ClientComponent") or "").strip()
            tgt = (row.get("ServerComponent")  or "").strip()
            evt = (row.get("EventName")        or "").strip()
            cf  = (row.get("ClientFunction")   or "").strip()

            if not src or not tgt or not evt or src == tgt:
                continue
            if src not in allowed or tgt not in allowed:
                continue
            if (src, tgt) not in REACHABILITY:
                continue
            if not is_entry(cf, entries):
                continue

            seen.add((src, tgt, evt))

    return sorted(
        [{"source": s, "target": t, "interaction": i} for s, t, i in seen],
        key=lambda d: (d["source"], d["target"], d["interaction"])
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS,
                        help="Process a single scenario (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print report only; do not write GT files")
    args = parser.parse_args()

    targets = [args.scenario] if args.scenario else SCENARIOS
    for scenario in targets:
        print(f"\n{'='*60}")
        print(f"  Scenario: {scenario}")
        print(f"{'='*60}")

        try:
            gt = derive_gt(scenario)
        except FileNotFoundError as e:
            print(f"  [SKIP] {e}")
            continue

        print(f"\n  GT interactions ({len(gt)} elements):")
        for d in gt:
            print(f"    {d['source']} → {d['target']} : {d['interaction']}")

        if not args.dry_run:
            out = SCEN_DIR / scenario / "gt_interactions.json"
            out.write_text(json.dumps(gt, indent=2))
            print(f"\n  Written: {out.relative_to(ROOT)}")
        else:
            print("\n  [dry-run] File not written.")


if __name__ == "__main__":
    main()
