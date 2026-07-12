# S4 — Stage Event Bridge Pub-Sub Routing (constructed scenario)

## Status: constructed, not found in existing code

**Unlike S1-S3, this scenario required adding new production code**
(`StageEventBridge` in Synchronization, `StageEventListener` in Aggregation).
No existing cpsCore call path exhibited both properties needed to make
C4 (static+dynamic) strictly beat *both* C2 (static-only) and C3
(dynamic-only) in the same scenario — this was verified by inspecting every
production use of `IPC`/`IDC` (the only `boost::signals2` pub-sub
abstractions in the codebase) and finding they are only ever invoked from
tests, never from another architectural component in `src/`.

This is flagged explicitly per the thesis's own methodological standard
(`H1 Methodological Corrections` — ground-truth circularity, scope
definition timing): S4 is a **synthetic, purpose-built scenario**, not a
scenario "found in the wild" like S1-S3. It should be reported and
interpreted as such.

## Scenario

**Primary component:** Synchronization
**Involved components:** Synchronization, Aggregation, Logging
**Production code:**
- `include/cpsCore/Synchronization/StageEventBridge.h` / `src/Synchronization/StageEventBridge.cpp`
- `include/cpsCore/Aggregation/StageEventListener.h` / `src/Aggregation/StageEventListener.cpp`

**Test file:** `tests/Synchronization/StageEventBridgeTest.cpp`
**Test case:** `TEST_CASE("Stage Event Bridge Pub-Sub Routing")`

## Mechanism — two independent evidence gaps in one scenario

### Gap 1 — dynamic-only-visible (static analysis structurally cannot find it)

`StageEventBridge::publishStage()` invokes its own `boost::signals2::signal`
object (`stageComplete_(stage)`). `StageEventListener::attachTo()` connects
`onStageEvent()` as a slot via `bridge.subscribeStage(...)`. A static call
graph sees:
- `publishStage()` → `stageComplete_.operator()` (a signal invocation, not a
  call to any subscriber)
- `attachTo()` → `subscribeStage()` (a connect call, not a call to the
  bridge's emission logic)

**No static edge connects `publishStage()` to `onStageEvent()`.** The only
way to observe `Synchronization → Aggregation : onStageEvent` is to run the
code and see the slot actually execute after the signal fires. This is the
same class of indirection as the IDC/Redis publish-subscribe layer discussed
in the thesis ("Macro Resolution for Publish-Subscribe Systems"), reproduced
here in a minimal, deterministic, non-Redis-dependent form.

### Gap 2 — static-only-visible (`LogLevel::NONE` suppression)

`StageEventBridge::publishStage()` is called once **before** any listener is
attached, wrapped in `CPSLogger::LogLevelScope(LogLevel::NONE)`. This
triggers the `CPSLOG_ERROR` "no listener connected" branch — source-visible
unconditionally — but the log is suppressed at runtime, so
`Synchronization → Logging : stream` is present in static analysis and
absent from a runtime trace of this test.

## Reference elements (source + behavior derived)

```json
[
  {"source": "Synchronization", "target": "Logging",     "interaction": "RAIILogStream.stream"},
  {"source": "Synchronization", "target": "Aggregation", "interaction": "StageEventListener.onStageEvent"}
]
```

## Expected scores

| Condition | TP | FP | FN | F1 | Note |
|---|---:|---:|---:|---:|---|
| C2 Static-only | 1 | 0 | 1 | 0.667 | Finds `stream` (source-visible); misses `onStageEvent` (no static edge exists — signal indirection) |
| C3 Dynamic-only | 1 | 0 | 1 | 0.667 | Finds `onStageEvent` (observed firing); misses `stream` (suppressed by `LogLevel::NONE`) |
| C4 Static+Dynamic | 2 | 0 | 0 | **1.000** | Recovers both — **F1(C4) > F1(C2) AND F1(C4) > F1(C3)** |

This is the property no other scenario (S1–S3) in this experiment set
demonstrates: in all of them, the dynamic trace is a strict *subset* of what
static analysis already finds, so `C4 = C2` always. Here, `C2` and `C3` each
miss a *different* element, so their union (`C4`) strictly dominates both.

## Why this required new production code, not just a new test

Every existing pub-sub-shaped call path in cpsCore (`IPC`, `IDC`) is:
- only ever invoked from test files (never from another `src/` component), and
- resolved via a plain string `id` matched inside the class's own internal
  map — which is a real design pattern, but no *existing* production caller
  in a different component exercises it.

Constructing S4 therefore required a minimal, self-contained bridge between
two production components (Synchronization, Aggregation) that reproduces the
signal-indirection property without needing a live Redis/IPC transport,
keeping the scenario deterministic and reviewable.

## Trace filter

```
ClientComponent == Synchronization
ServerComponent in {Aggregation, Logging}
ClientFunction in {publishStage}
```

## Status

- [x] Production code added and compiled (WSL build, `tests` target)
- [x] Test passes in isolation (`1 assertion in 1 test case`)
- [x] Full suite: 61/62 test cases pass; 1 pre-existing, unrelated timing
      flake in `SchedulerTest.cpp` ("Scheduler Period Change") — not caused
      by this change
- [ ] Real traces: run instrumented test binary, capture `[TRACE]` output
- [ ] Extract slice: add S4 to `extract_slices.py`
- [ ] Run conditions C1–C5 for S4 through the standard H1 pipeline
- [ ] Score with `experiments/H1/scoring/score.py` and confirm the
      predicted C4 > C2, C4 > C3 result empirically
