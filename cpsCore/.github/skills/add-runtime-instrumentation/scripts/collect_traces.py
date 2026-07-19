"""
collect_traces.py -- Steps 3-4 of add-runtime-instrumentation:
rebuild the instrumented binary, run it, and convert the captured
"[TRACE] ..." stderr lines into runtime_traces.txt.

PREREQUISITE: instrumentation must already be applied to the source via
apply_tracing.ps1 (Step 2, Windows-only, uses csp_matcher). This script does
NOT apply instrumentation itself -- if you run it against a clean checkout,
the rebuilt binary won't print anything and the output will be empty.

Run this from within WSL (or any Linux shell) -- the test binary is a Linux
ELF built via the WSL/Linux build directory; it cannot be invoked directly
from a Windows Python interpreter.

Raw trace line format (see SKILL.md / README.md):
    [TRACE] HH:MM:SS.mmm, callerFunc, callerComponent, Callee.method, calleeComponent, callerClass, file:line

Usage:
    python3 collect_traces.py
    python3 collect_traces.py --cpscore-root /mnt/c/Users/prathikak/Documents/cpsCore
    python3 collect_traces.py --build-dir bld/wsl-release --skip-build

Output:
    <cpscore-root>/runtime_traces.txt, overwritten, pipe-delimited:
    EventTimestamp|EventName|ClientComponent|ClientFunction|ServerComponent|ServerFunction|RelationshipType|InterfaceNames
"""
from __future__ import annotations

import argparse
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Groups: 1=HH:MM:SS.mmm 2=callerFunc 3=callerComponent 4=Callee.method
#         5=calleeComponent 6=callerClass 7=file:line
_TRACE_RE = re.compile(
    r"^\[TRACE\]\s*([^,]+),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*([^,]*),\s*(.*)$"
)

FIELDNAMES = [
    "EventTimestamp",
    "EventName",
    "ClientComponent",
    "ClientFunction",
    "ServerComponent",
    "ServerFunction",
    "RelationshipType",
    "InterfaceNames",
]


def _iso_timestamp(hms: str, on_date: datetime) -> str:
    """Convert the trace's 'HH:MM:SS.mmm' wall-clock time into a full
    ISO-8601 UTC timestamp on `on_date`, padded from millisecond to
    microsecond precision."""
    hh, mm, rest = hms.strip().split(":")
    ss, ms = rest.split(".")
    dt = on_date.replace(hour=int(hh), minute=int(mm), second=int(ss),
                          microsecond=int(ms) * 1000)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def parse_trace_line(line: str, on_date: datetime) -> dict | None:
    m = _TRACE_RE.match(line.strip())
    if not m:
        return None
    hms, caller_func, caller_component, callee_method, callee_component, caller_class, _file_line = (
        g.strip() for g in m.groups()
    )
    client_function = f"{caller_class}.{caller_func}" if caller_class else caller_func
    return {
        "EventTimestamp": _iso_timestamp(hms, on_date),
        "EventName": callee_method,
        "ClientComponent": caller_component,
        "ClientFunction": client_function,
        "ServerComponent": callee_component,
        "ServerFunction": callee_method,
        # Not encoded anywhere in the [TRACE] format -- every emitted trace
        # point is a plain call, so this is fixed rather than derived.
        "RelationshipType": "Command",
        "InterfaceNames": callee_method.split(".")[0] if "." in callee_method else callee_method,
    }


def rebuild(cpscore_root: Path, build_dir: str) -> None:
    subprocess.run(
        ["cmake", "--build", build_dir, "--target", "tests", "-j"],
        cwd=cpscore_root, check=True,
    )


def run_tests_and_capture(cpscore_root: Path, build_dir: str) -> str:
    test_binary = cpscore_root / build_dir / "tests" / "tests"
    if not test_binary.exists():
        raise SystemExit(f"Test binary not found: {test_binary} (build it first, or check --build-dir)")
    result = subprocess.run(
        [str(test_binary), "-d", "yes"],
        cwd=test_binary.parent, capture_output=True, text=True,
    )
    # Trace lines are written to stderr; stdout carries the normal Catch2 report.
    return result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--cpscore-root", default=str(Path(__file__).resolve().parents[4]),
        help="Path to the cpsCore checkout to build/run -- must be the same "
             "checkout that apply_tracing.ps1 (Step 2) was applied to.",
    )
    parser.add_argument("--build-dir", default="bld/wsl-release",
                         help="Build directory relative to --cpscore-root")
    parser.add_argument("--skip-build", action="store_true",
                         help="Skip the rebuild step (binary already up to date)")
    args = parser.parse_args()

    cpscore_root = Path(args.cpscore_root)
    out_path = cpscore_root / "runtime_traces.txt"

    if not args.skip_build:
        print(f"Rebuilding 'tests' target in {cpscore_root / args.build_dir} ...")
        rebuild(cpscore_root, args.build_dir)
    else:
        print("Skipping rebuild (--skip-build)")

    print("Running instrumented test binary and capturing stderr ...")
    raw_stderr = run_tests_and_capture(cpscore_root, args.build_dir)

    on_date = datetime.now(timezone.utc)
    rows = []
    for line in raw_stderr.splitlines():
        row = parse_trace_line(line, on_date)
        if row:
            rows.append(row)

    if not rows:
        print("WARNING: no [TRACE] lines found in the captured output.")
        print("Did you run apply_tracing.ps1 (Step 2) on this checkout before rebuilding?")

    with out_path.open("w", encoding="utf-8", newline="") as f:
        f.write("|".join(FIELDNAMES) + "\n")
        for row in rows:
            f.write("|".join(row[k] for k in FIELDNAMES) + "\n")

    print(f"Trace rows captured: {len(rows)}")
    print(f"Written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
