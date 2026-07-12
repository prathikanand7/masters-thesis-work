"""
extract_slices.py
-----------------
Extract trace rows from runtime_traces.txt (synthetic) or
runtime_traces_hybrid.txt (real execution) into per-scenario slice files.

S1/S2/S3 use the synthetic runtime_traces.txt (pipe-delimited, component names).
S4 uses runtime_traces_hybrid.txt (real test-binary output) if available; if not,
a stub file is written as a reminder to run scenarios/S4/run_s4_test.sh first.

Usage:
    python extract_slices.py --scenario S1
    python extract_slices.py --all
"""
import argparse
import csv
import re
import pathlib
from datetime import datetime

ROOT = pathlib.Path(__file__).parent.parent.parent  # cpsCore/
TRACE_FILE        = ROOT / "runtime_traces.txt"
HYBRID_TRACE_FILE = ROOT / "runtime_traces_hybrid.txt"
SCENARIOS_DIR = pathlib.Path(__file__).parent

# Scenario filter definitions — mirror scenarios.md
SCENARIO_FILTERS = {
    "S1": {
        "client_components": {"Synchronization"},
        "server_components": {"Aggregation", "Logging"},
        "client_functions": None,
    },
    "S2": {
        "client_components": {"Configuration"},
        "server_components": {"Logging"},
        "client_functions": None,
    },
    "S3": {
        "client_components": {"Synchronization"},
        "server_components": {"Aggregation", "Utilities", "Logging"},
        "client_functions": {
            "SimpleRunner.runStage",
            "SimpleRunner.runStages",
            "SynchronizedRunnerMaster.runAllStages",
        },
    },
    # S4 uses the real (hybrid) trace format (constructed StageEventBridge
    # pub-sub scenario). ClientFunction filter covers the publishing call:
    #   - StageEventBridge.publishStage (Synchronization)
    # The CPSLOG_ERROR fired when publishing with no listener attached is
    # suppressed with LogLevel::NONE in the test — so real traces will NOT
    # contain Synchronization→Logging:stream, even though source shows it.
    # See experiments/scenarios/S4/definition.md and run_s4_test.sh.
    "S4": {
        "client_components": {"Synchronization"},
        "server_components": {"Aggregation", "Logging"},
        "client_functions": {
            "publishStage",
        },
        "use_hybrid": True,  # read from runtime_traces_hybrid.txt
    },
}

# ── Hybrid trace format parser ───────────────────────────────────────────────
# [TRACE] HH:MM:SS.mmm, ClientFunction, ClientComponent, EventName,
#         ServerComponent, ClassName, SourceFile:Line
_HYBRID_RE = re.compile(
    r"^\[TRACE\]\s+(\S+),\s+(\S+),\s+(\S+),\s+(\S+),\s+(\S+),",
)

def parse_hybrid_line(line: str) -> dict | None:
    m = _HYBRID_RE.match(line.strip())
    if not m:
        return None
    time_str, client_fn, client_comp, event_name, server_comp = m.groups()
    # Convert to the same dict shape extract_trace_slice expects
    return {
        "EventTimestamp": f"2000-01-01T{time_str}Z",
        "EventName":      event_name,
        "ClientComponent": client_comp,
        "ClientFunction":  client_fn,
        "ServerComponent": server_comp,
        "ServerFunction":  event_name,
        "RelationshipType": "Command",
        "InterfaceNames":  event_name.split(".")[0] if "." in event_name else event_name,
    }


def extract_trace_slice(scenario_id: str) -> None:
    f = SCENARIO_FILTERS[scenario_id]
    out_path = SCENARIOS_DIR / scenario_id / "trace_slice.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    use_hybrid = f.get("use_hybrid", False)

    if use_hybrid:
        if not HYBRID_TRACE_FILE.exists():
            print(f"[{scenario_id}] STUB — {HYBRID_TRACE_FILE.name} not found.")
            print(f"  Run experiments/scenarios/S4/run_s4_test.sh first.")
            # Write an empty-but-valid stub so downstream scripts don't crash
            with open(out_path, "w") as fh:
                fh.write("EventTimestamp|EventName|ClientComponent|ClientFunction"
                         "|ServerComponent|ServerFunction|RelationshipType|InterfaceNames\n")
            return
        all_rows = []
        with open(HYBRID_TRACE_FILE) as fh:
            for line in fh:
                row = parse_hybrid_line(line)
                if row:
                    all_rows.append(row)
    else:
        all_rows = []
        with open(TRACE_FILE, newline="") as fh:
            reader = csv.DictReader(fh, delimiter="|")
            for row in reader:
                all_rows.append(row)

    fieldnames = ["EventTimestamp", "EventName", "ClientComponent", "ClientFunction",
                  "ServerComponent", "ServerFunction", "RelationshipType", "InterfaceNames"]
    rows = []
    for row in all_rows:
        client_ok = row["ClientComponent"] in f["client_components"]
        server_ok = row["ServerComponent"] in f["server_components"]
        func_ok = (
            f["client_functions"] is None
            or row["ClientFunction"] in f["client_functions"]
            # hybrid traces use bare function names; also match Class.method
            or any(row["ClientFunction"].endswith(fn.split(".")[-1])
                   for fn in (f["client_functions"] or []))
        )
        if client_ok and server_ok and func_ok:
            rows.append({k: row.get(k, "") for k in fieldnames})

    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="|")
        writer.writeheader()
        writer.writerows(rows)

    src = "hybrid" if use_hybrid else "synthetic"
    print(f"[{scenario_id}] {len(rows)} trace rows ({src}) → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=list(SCENARIO_FILTERS.keys()))
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    targets = list(SCENARIO_FILTERS.keys()) if args.all else [args.scenario]
    for sid in targets:
        extract_trace_slice(sid)


if __name__ == "__main__":
    main()
