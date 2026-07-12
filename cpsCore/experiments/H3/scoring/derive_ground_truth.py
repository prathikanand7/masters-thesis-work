"""
derive_ground_truth.py
-----------------------
Converts H1 reference elements.json files into H3 ground-truth JSON files.
Run this once to regenerate all five scenarios.

H1 elements.json format:
  [{"source": "...", "target": "...", "interaction": "..."}]

H3 ground_truth.json format:
  {
    "components": ["ComponentA", "ComponentB", ...],
    "interactions": [{"source": ..., "target": ..., "interaction": ...}, ...],
    "reference_explanation": "<prose written before seeing agent output>"
  }

NOTE: reference_explanation strings are written independently (before any agent
runs) so they are not biased by model output.  They serve as the rubric anchor
for the manual completeness (1-5) scoring step.

Usage:
    python derive_ground_truth.py
"""
import json
import pathlib

H1_REF = pathlib.Path(__file__).parent.parent.parent / "H1" / "reference_diagrams"
GT_DIR = pathlib.Path(__file__).parent / "ground_truth"
GT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = ["S1", "S2", "S3", "S4"]

# Reference explanations written independently before any agent output is seen.
# Each prose string answers: "what components interact, via what methods, and why?"
REFERENCE_EXPLANATIONS = {
    "S1": (
        "SynchronizedRunner.runSynchronized (Synchronization) first fetches all "
        "runnable objects from the Aggregator via Aggregator.getAll (Aggregation). "
        "After executing each run stage it synchronises stdout by calling "
        "CPSLogger::instance() to obtain the logger singleton and then calling "
        "CPSLogger::flush() to flush buffered output (both in Logging). "
        "Progress is additionally logged via RAIILogStream.stream (Logging) through "
        "CPSLOG_DEBUG/CPSLOG_ERROR macros in the surrounding runner chain. "
        "The primary driver is Synchronization; Aggregation provides the object list; "
        "Logging receives all diagnostic output."
    ),
    "S2": (
        "PropertyMapper (Configuration component) validates and maps configuration "
        "properties at startup. Every property-mapping method — add, addEnum, "
        "addEigen, addVector, getChild, and mandatoryCheck — emits a diagnostic "
        "via CPSLOG_TRACE or CPSLOG_ERROR, which expands to a RAIILogStream.stream "
        "call in the Logging component. "
        "The sole cross-component interaction is Configuration → Logging via "
        "RAIILogStream.stream; no other components are involved in this scenario."
    ),
    "S3": (
        "SimpleRunner.runStage (Synchronization) orchestrates a single run stage by "
        "fetching all runnable objects via Aggregator.getAll (Aggregation), converting "
        "the RunStage enum value to a display string via EnumMap.convert (Utilities), "
        "and logging stage entry/exit via CPSLOG_DEBUG which calls RAIILogStream.stream "
        "(Logging). All three interactions occur in a tight per-stage loop; "
        "SimpleRunner.runStages wraps repeated calls and adds error-path logging on "
        "failure. The primary driver is Synchronization."
    ),
    "S4": (
        "StageEventBridge::publishStage (Synchronization) is new, purpose-built "
        "production code that publishes a stage-completion event over a "
        "boost::signals2::signal. If no listener is connected, it emits "
        "CPSLOG_ERROR, calling RAIILogStream.stream (Logging) — a call that is "
        "source-visible but suppressed at runtime by a "
        "CPSLogger::LogLevelScope(LogLevel::NONE) idiom. "
        "When a listener IS connected, publishStage instead invokes the signal "
        "directly, which StageEventListener::onStageEvent (Aggregation) receives "
        "as a connected slot — this dispatch has no static call site anywhere in "
        "the codebase and is only observable via runtime trace. "
        "S4 is therefore the one scenario where static analysis and runtime "
        "tracing are each blind to a different interaction (stream vs. "
        "onStageEvent respectively), rather than one being a strict subset of "
        "the other as in S1–S3. Primary driver: Synchronization."
    ),
}

for scenario in SCENARIOS:
    src = H1_REF / scenario / "elements.json"
    if not src.exists():
        print(f"[SKIP] {src} not found — populate H1 reference_diagrams first")
        continue

    with open(src) as f:
        elements = json.load(f)

    components = sorted({e["source"] for e in elements} | {e["target"] for e in elements})
    gt = {
        "components": components,
        "interactions": elements,
        "reference_explanation": REFERENCE_EXPLANATIONS[scenario],
    }

    out = GT_DIR / f"{scenario}_ground_truth.json"
    with open(out, "w") as f:
        json.dump(gt, f, indent=2)
    print(f"[{scenario}] {len(components)} components, {len(elements)} interactions → {out}")
