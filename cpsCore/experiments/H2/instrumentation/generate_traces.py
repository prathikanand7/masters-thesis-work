"""
generate_traces.py — H2 instrumentation trace generator
---------------------------------------------------------
Creates full_trace.txt and guided_trace.txt for each scenario.

  full_trace.txt  = entire runtime_traces.txt (all components, all functions —
                    simulates running with instrumentation on all call sites)
  guided_trace.txt = the scenario's trace_slice.txt (slice-filtered to primary
                    driver → relevant targets, specific client functions only)

This simulates the instrumentation strategy comparison without requiring
re-instrumentation: full = "instrument everything and run", guided = "instrument
only the slice-selected call sites".

S4 is a special case: it is constructed (not found-in-the-wild) production code
added specifically for H1c. Its full_trace.txt is NOT a plain copy of
runtime_traces.txt (which predates S4's code and contains no rows for it).
Instead it is runtime_traces.txt (representing the pre-existing noise a full
instrumentation pass would also capture) with S4's own captured trace row(s)
appended — i.e. what a full-instrumentation run touching every call site,
including the new StageEventBridge/StageEventListener files, would actually
produce. Critically, `stream` is absent from BOTH full and guided traces for
S4: unlike the instrumentation-scope difference that drives full vs. guided,
`stream`'s absence is caused by a runtime CPSLogger::LogLevelScope(NONE) gate
inside publishStage() itself, which suppresses the CPSLOG_ERROR call no
matter how many call sites are instrumented. Only `onStageEvent` (unconditional)
is ever traced, in both variants.

Usage:
    python generate_traces.py
"""
import pathlib
import shutil

ROOT      = pathlib.Path(__file__).parent.parent.parent   # experiments/
INSTR_DIR = pathlib.Path(__file__).parent.parent / "instrumentation"
SCEN_DIR  = ROOT / "scenarios"
FULL_SRC  = ROOT.parent / "runtime_traces.txt"

SCENARIOS = ["S1", "S2", "S3", "S4"]   # H2: happy-path scenarios + constructed S4

for s in SCENARIOS:
    out_dir = INSTR_DIR / s
    out_dir.mkdir(parents=True, exist_ok=True)

    slice_src = SCEN_DIR / s / "trace_slice.txt"
    guided_dst = out_dir / "guided_trace.txt"
    full_dst = out_dir / "full_trace.txt"

    if s == "S4":
        # Full trace = baseline noise (runtime_traces.txt) + S4's own captured
        # row(s), MINUS the header line duplication. `stream` never appears
        # in either variant (runtime log-level suppression, not an
        # instrumentation-scope effect) — see module docstring.
        if not slice_src.exists():
            print(f"{s} guided MISSING — run the S4 test to capture trace_slice.txt first")
        else:
            base_lines = FULL_SRC.read_text().splitlines(keepends=True)
            slice_lines = slice_src.read_text().splitlines(keepends=True)
            header, base_rows = base_lines[0], base_lines[1:]
            slice_rows = slice_lines[1:]  # drop slice's own header, reuse base header
            full_dst.write_text(header + "".join(base_rows) + "".join(slice_rows))
            shutil.copy(slice_src, guided_dst)
            print(f"{s} full    → {full_dst}  ({len(base_rows) + len(slice_rows)} rows, "
                  f"{len(base_rows)} baseline noise + {len(slice_rows)} S4-specific)")
            print(f"{s} guided → {guided_dst}  ({len(slice_rows)} rows)")
        continue

    # Full trace: entire runtime_traces.txt
    shutil.copy(FULL_SRC, full_dst)
    print(f"{s} full    → {full_dst}  ({sum(1 for _ in open(full_dst))-1} rows)")

    # Guided trace: scenario slice
    if slice_src.exists():
        shutil.copy(slice_src, guided_dst)
        rows = sum(1 for _ in open(guided_dst)) - 1
        print(f"{s} guided → {guided_dst}  ({rows} rows)")
    else:
        print(f"{s} guided MISSING — run extract_slices.py --scenario {s} first")

print("\nDone. Run: python metrics/diagram_metrics.py --all")
