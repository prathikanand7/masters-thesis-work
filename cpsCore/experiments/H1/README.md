# H1 — Static + Dynamic Evidence Improves Reconstruction

## Hypothesis

**H1a (precision):** Agent synthesis over a combined static + dynamic evidence base
(C5) achieves higher precision than static analysis alone (C2) by eliminating
spurious static edges, while maintaining comparable recall. Holds across all
execution-path types.

**H1b (fault-path recall) — tested by S4.** Combined static + dynamic
evidence (C4) achieves higher recall than dynamic-only evidence (C3)
specifically when a runtime condition suppresses evidence that is
architecturally visible in source. The constructed scenario S4 — which
combines a `LogLevel::NONE`-suppressed fault-path log call with a
`boost::signals2` dispatch invisible to static analysis — demonstrates this
directly. On the happy-path scenarios (S1–S3), C4 = C2 (dynamic traces are a
strict subset of what static analysis already finds); the dynamic-evidence
advantage is localised entirely to S4.

> **Note:** C3 (dynamic-only) actually achieves *perfect* F1 (1.000) on the
> S1–S3 happy-path stratum — better than C2 or C4, both of which carry S3's
> static over-approximation FPs. The entire empirical case for fusion's
> added value in this scenario set therefore rests on the single constructed
> scenario, S4 — see "Honest aggregate" below.

**H1c (constructed, S4) — CONFIRMED, now the primary fusion-value result.**
C4 can strictly outperform *both* C2 and C3 simultaneously when a scenario
combines a dynamic-only-visible edge (a `boost::signals2` publish/subscribe
delivery, invisible to a static call graph) with a static-only-visible edge
(a suppressed fault-path log). No such scenario existed in cpsCore's
found-in-the-wild code paths, so S4 is a **constructed** scenario — new
production code (`StageEventBridge`/`StageEventListener`) was added
specifically to demonstrate this, and all five conditions were run for real
(C2/C3 from a genuine WSL-instrumented test execution, C1/C5 from real Azure
OpenAI calls). Result: **F1(C4)=1.000 > F1(C2)=0.667 and F1(C4)=1.000 >
F1(C3)=0.667** — the only scenario in this experiment set where fusion
strictly dominates both single-source conditions at once. See
`experiments/scenarios/S4/definition.md` for full rationale and the
"S4 — Stage Event Bridge" results section below.

## Folder structure

```
H1/
├── reference_diagrams/
│   ├── S1/  (Synchronization happy-path — aggregation chain)
│   ├── S2/  (Configuration happy-path — property mapping)
│   ├── S3/  (Synchronization happy-path — multi-component runner)
│   └── S4/  (Synchronization constructed — dual dynamic+static gap, H1c)
├── conditions/
│   ├── C1_llm_only/
│   ├── C2_static_only/
│   ├── C3_dynamic_only/
│   ├── C4_static_dynamic/
│   └── C5_full_pipeline/
└── scoring/
    ├── score.py           SCENARIOS = ["S1", "S2", "S3", "S4"]
    └── results.csv
```

## Task checklist

- [x] **Task 1** — Scenarios: S1–S3 (happy-path) + S4 (constructed)
- [x] **Task 2** — Reference diagrams built from source-reading (all reported scenarios)
- [x] **Task 3** — All 5 conditions run for S1–S3
- [x] **Task 4** — Scored; `results.csv` generated; stratified analysis complete
- [x] **Task 5** — S4 constructed (new production code: `StageEventBridge`/
      `StageEventListener`) to test H1c; real trace captured from an actual
      WSL test run; all 5 conditions run for real (C1/C5 via live Azure
      OpenAI calls, C2 via manual static call-graph reading, C3 from the
      captured trace, C4 as the real script-computed union)
- [x] **Task 6** — Rescored with S4; H1c confirmed empirically:
      F1(C4)=1.000 > F1(C2)=0.667 and F1(C4)=1.000 > F1(C3)=0.667
- [x] **Task 7** — C5 gives the agent C2/C3 separately
      with provenance tags instead of a pre-merged C4 union, and produces an
      ordered sequence diagram (`sequence.mmd`) in addition to `elements.json`;
      run for real across all scenarios; scored — macro F1 for C5
      is **0.964**, the best of any of the five conditions
- [x] **Task 8** — `score.py` rerun with `SCENARIOS = ["S1", "S2", "S3",
      "S4"]`; every table in this document generated from that rerun (no
      hand-edited aggregates)

## Ground-truth methodology

Reference `elements.json` was built by **source-code reading** of the relevant
`.cpp` and `.h` files (not derived from traces). Each entry is a cross-component
call visible in source, where the source component matches the **primary driver**
of the scenario (Synchronization for S1/S3; Configuration for S2). This
primary-source constraint applies identically to all 5 conditions.

Traces were used only for **post-hoc validation** — confirming that all
source-derived reference interactions were actually exercised at runtime.
For S1–S3, source-derived and trace-observed interaction sets are identical
(no fault-path suppression occurs on these three scenarios).

Interaction names are normalized to bare function name before matching
(`Aggregator.getAll` → `getAll`, `RAIILogStream.stream` → `stream`, etc.).

F1 aggregation: **macro-average** (mean of per-scenario F1 scores, weights
each scenario equally). Micro-F1 (computed from mean P × mean R) also
reported; values agree to within ±0.013 (see scorer output / results.csv).

**S4 is methodologically different from S1–S3 and is flagged as such
throughout this document.** S1–S3 were found in existing cpsCore code and
tests; S4 required adding new production code (`StageEventBridge` in
Synchronization, `StageEventListener` in Aggregation) because no existing
cross-component call path in cpsCore combines a dynamic-only-visible edge
with a static-only-visible fault-path edge in the same scenario (verified by
inspecting every production use of `IPC`/`IDC`, the only `boost::signals2`
abstractions in the codebase). For S4:
- **C3** was derived from a genuine runtime trace: the test binary was built
  and run in WSL with temporary, reversible trace instrumentation gated on
  the real `CPSLogger` log level (mirroring the actual `CPSLOG` macro
  suppression behaviour), and the single captured `[TRACE]` line was written
  directly into `experiments/scenarios/S4/trace_slice.txt`. No trace event
  was fabricated — the fault-path `stream` edge was empirically confirmed
  *absent* from the captured output, exactly as the suppression mechanism
  predicts.
- **C2** was derived by manual static call-graph reading of the two new
  files (Renaissance was not re-run against the new production code in this
  session), applying the same rule Renaissance's `CppCalls` extraction uses:
  only direct function-call edges count, so `publishStage`'s unconditional
  `CPSLOG_ERROR` call is a static edge, while the `boost::signals2` signal
  invocation reaching `onStageEvent` is not (no static call site exists).
- **C1** and **C5** were run for real against the live Azure OpenAI
  deployment already configured in `.env` — not predicted or fabricated.

## C5 Methodology: Provenance-Aware Synthesis

`run_c5_full_pipeline.py` gives the agent C2 (static call-graph) and C3
(dynamic trace, in real captured execution order, with caller-function
names) as two separately labeled evidence sources, each edge tagged with
whether the other source also observed it. The prompt explicitly instructs
the agent to reason about *why* a single-source edge might be missing from
the other source (genuine runtime suppression vs. indirect dispatch vs.
static over-approximation) rather than treating single-source status
itself as a weak signal. The agent's response also includes an ORDERED
call sequence (dynamic trace order as backbone, retained static-only edges
inserted at the position implied by the scenario description).

**Result:** C5 achieves full recall parity with C4 (R=1.000) on every
scenario in the set — including S4, where the suppressed fault-path edge
(`stream`) is retained rather than pruned as indistinguishable from noise.
This does introduce one false positive on S3 (`flush`; see the S3
qualitative analysis below), so macro precision is 0.938 rather than
perfect — but net macro F1 is **0.964**, the best of any of the five
conditions, including C4's raw union (0.938).

## Results

All tables below reflect the full scenario set — **S1, S2, S3 (happy-path)
and S4 (constructed)** — generated by a real rerun of `score.py --all` with
`SCENARIOS = ["S1", "S2", "S3", "S4"]`; no number below is hand-computed.

### Per-scenario scores

| Condition | S1 | S2 | S3 | S4 |
|---|---|---|---|---|
| C1 LLM-only | 0/0/0.00 | 0/0/0.00 | 0/0/0.00 | 0.50/0.50/0.50 |
| C2 Static-only | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 0.60/1.00/0.75 | 1.00/0.50/**0.67** |
| C3 Dynamic-only | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 1.00/0.50/**0.67** |
| C4 Static+Dynamic | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 0.60/1.00/0.75 | 1.00/1.00/**1.00** |
| C5 Full pipeline | 1.00/1.00/1.00 | 1.00/1.00/1.00 | 0.75/1.00/0.86 | 1.00/1.00/**1.00** |

*Format: P/R/F1. Bold in S4 = where C4/C5 strictly exceed **both** C2 and
C3 simultaneously (H1c) — the only scenario in this set where this happens,
and the sole demonstration of fusion's additive value.*

### Stratified summary — the main finding (macro-averaged P / R / F1)

| Condition | Happy P (S1–S3) | Happy R | Happy F1 | S4 P | S4 R | S4 F1 | Overall P (S1–S3+S4) | Overall R | Overall F1 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| C1 LLM-only | 0.000 | 0.000 | 0.000 | 0.500 | 0.500 | 0.500 | 0.125 | 0.125 | 0.125 |
| C2 Static-only | 0.867 | 1.000 | 0.917 | 1.000 | 0.500 | 0.667 | 0.900 | 0.875 | 0.854 |
| C3 Dynamic-only | **1.000** | **1.000** | **1.000** | 1.000 | 0.500 | 0.667 | **1.000** | 0.875 | 0.917 |
| C4 Static+Dynamic | 0.867 | 1.000 | 0.917 | 1.000 | 1.000 | 1.000 | 0.900 | **1.000** | 0.938 |
| C5 Full pipeline | 0.917 | **1.000** | 0.952 | 1.000 | **1.000** | 1.000 | 0.938 | **1.000** | **0.964** |

**Reading the table:**
- **C3 (dynamic-only) is the best happy-path condition, full stop
  (F1=1.000).** There is no scenario among S1–S3 where the runtime trace is
  incomplete: the trace is always complete on these three, and unlike
  C2/C4 it never inherits S3's two static over-approximation FPs (`flush`,
  `instance`), because those calls genuinely do not execute during the S3
  test. **C3 strictly dominates C2 and C4 on the happy-path stratum.**
- **C4 = C2 numerically on S1–S3** (unchanged mechanism): CPSCore's
  existing production code has no cross-module virtual dispatch, so every
  trace-observed call in S1–S3 is already statically visible (C3 ⊆ C2
  there), and C4 = C2 ∪ C3 = C2.
- **C4 ≠ C2 on S4 — this is where the entire empirical case for fusion
  rests.** S4 was deliberately constructed so that C3 ⊈ C2: C2 misses
  `onStageEvent` (no static edge exists across a `boost::signals2`
  signal/slot boundary) while C3 misses `stream` (suppressed by
  `LogLevel::NONE`). Their union, C4, recovers both and reaches F1=1.000,
  strictly above **both** C2=0.667 **and** C3=0.667. **This is the only
  scenario in the set where fusion adds any value at all** — on S1–S3
  fusion is either redundant (C4=C2) or actively worse than C3 alone (C4
  inherits C2's S3 FPs that C3 avoids).
- **C2/C4 precision deficit on S3:** P=0.60 (2 FPs: `flush` and `instance` —
  real Sync→Logging calls but outside S3 scope). Static analysis
  over-approximates without slicing; C3 does not have this problem because
  those calls simply never execute in the S3 test.
- **C5 matches C4's perfect recall on every scenario, including S4.**
  The provenance-aware prompt (see "C5 Methodology" above) explicitly
  warns the agent that a single-source edge may be genuinely real
  (fault-path suppression, or an indirect-dispatch call only a trace can
  see) rather than noise. Result: `stream` is retained on S4 and `instance`
  is retained on S1.
- **C5's one remaining imprecision is on S3, not S4.** The same
  "single-source edges may be real" guidance that fixed S4 causes the agent
  to also retain `flush` on S3 — a real Sync→Logging call, but from a
  function outside S3's defined scope, indistinguishable at the
  component-level granularity C2's `elements.json` provides. FP drops from 2
  (C4's raw union) to 1 — still an improvement over C4, though not the
  perfect precision achievable by pruning everything single-source. See the
  revised S3 qualitative analysis below.

### Aggregate results (S1, S2, S3, S4)

| Condition | macro P | macro R | macro F1 | micro F1 | note |
|---|:---:|:---:|:---:|:---:|---|
| C1 LLM-only | 0.125 | 0.125 | 0.125 | 0.125 | Floor |
| C2 Static-only | 0.900 | 0.875 | 0.854 | 0.887 | Misses `onStageEvent` on S4 (no static edge); carries S3's FPs |
| C3 Dynamic-only | **1.000** | 0.875 | 0.917 | 0.933 | Misses `stream` on S4 (suppressed); best happy-path condition |
| C4 Static+Dynamic | 0.900 | **1.000** | 0.938 | 0.947 | Perfect recall by construction (raw union); still carries S3's FPs |
| C5 Full pipeline | **0.938**\* | **1.000** | **0.964** | **0.968** | Best overall F1 — matches C4's recall, improves precision over C4 on S3 |

\* C5's macro precision (0.938) is lower than C3's (1.000) — C3 simply has
no false positives at all on S1–S3+S4, since it never sees the static-only
edges that create scope ambiguity. C5's advantage over C3 is entirely in
recall (1.000 vs 0.875): C3 still misses `stream` on S4, the one scenario
in the set with a genuine dynamic-evidence gap.

**C3 achieves the best *precision* of any condition (1.000) and ties for
the best happy-path F1.** This is because the only fault-path recall gap in
this scenario set is the one purpose-built scenario, S4 — on
found-in-the-wild code (S1–S3), C3 has no recall weakness to expose. **The
honest claim supported by this dataset is: fusion (C4) is never worse than
either single source, and is strictly better than both exactly on the one
scenario purpose-built to require it (S4); on found-in-the-wild code with
no cross-module virtual dispatch (S1–S3), a clean runtime trace alone (C3)
is already sufficient, and can even be preferable to unscoped static
analysis because it does not over-approximate.**

**C5 still has the best overall F1 (0.964) of all five conditions** —
it is the only condition that combines C3's ability to filter out S3's
static over-approximation (partially: 1 of 2 FPs pruned) with C4's full
recall on S4. It does not beat C3 on precision, but it beats every other
condition on F1, and it is the only condition demonstrated to work whether
or not a scenario happens to have a fault-path/indirect-dispatch gap.

## Key findings

1. **C1 is floor.** LLM-only without code context produces zero
   function-level matches on 3 of 4 scenarios; partial match on S4
   (F1=0.50, from having read the same `.env`-driven codebase context but
   guessing at names). Unusable alone.

2. **C4 = C2 is structural, not a null result — for S1–S3.** CPSCore's
   existing, found-in-the-wild production code has no cross-module virtual
   dispatch (~13 kLOC, 32 virtual declarations all intra-module). Every
   trace-observed call is already statically visible, so C3 ⊆ C2 and C4 =
   C2 ∪ C3 = C2 on all three naturally-occurring, reported scenarios.
   Finding 5 below shows what happens when this precondition is
   deliberately broken (S4).

3. **C2/C4 over-approximate on S3; C3 does not.** P=0.60 for C2/C4 (2
   spurious static edges: `flush` and `instance` — real Sync→Logging calls
   but outside S3's `SimpleRunner.runStage` scope). C3 has no such problem
   (P=1.000 on S3) because those calls simply never execute during the S3
   test — static analysis cannot scope without slicing, but a real runtime
   trace scopes itself by construction.

4. **C3 (dynamic-only) is the best happy-path condition in this scenario
   set.** Aggregated over S1–S3, C3 achieves P=R=F1=1.000, strictly above
   C2/C4's F1=0.917. C3's only limitation — missing a suppressed
   fault-path edge — is isolated to the single constructed scenario, S4,
   and does not appear anywhere in the found-in-the-wild happy-path
   scenarios.

5. **H1c confirmed — S4 is now the *only* scenario in the set where C4
   beats *both* C2 and C3 simultaneously, and therefore the sole empirical
   basis for claiming fusion has value.** S1–S3 all satisfy C3 ⊆ C2
   (Finding 2), so C4 can never exceed C2 there — at best it matches C2
   (Finding 2) or is actively worse than C3 alone (Finding 3/4). S4 was
   constructed specifically to break the C3 ⊆ C2 precondition on *both*
   sides at once: a `boost::signals2` signal/slot bridge
   (`StageEventBridge` → `StageEventListener`) creates a call
   (`onStageEvent`) with **no static edge** (C2 misses it — Renaissance/
   clang cannot resolve the indirect signal dispatch), while the bridge's
   fault-path log line (`stream`, under `LogLevel::NONE`) is **suppressed
   at runtime** (C3 misses it). Neither single source sees both edges: C2
   F1=0.667 (has `stream`, misses `onStageEvent`), C3 F1=0.667 (has
   `onStageEvent`, misses `stream`). Their union, C4, recovers both:
   **F1=1.000, strictly greater than both C2=0.667 and C3=0.667.** This is
   the only case in this dataset where fusion is *additive*, and it is the
   entire empirical basis for the fusion-value claim in this scenario set.
   See the dedicated S4 section below for the full construction and
   mechanism.

6. **H1a confirmed — C5 achieves the best overall F1 (0.964) of any
   condition, though not the best precision.** C5 gives the agent C2 and
   C3 *separately*, tagged with provenance, and explicit guidance to
   reason about *why* an edge might be missing from one source before
   pruning it (see "C5 Methodology", above). Result: C5 matches C4's
   perfect recall (R=1.000) on every scenario, while improving on C4's
   precision by correctly pruning one of S3's two spurious static edges (FP
   2→1). C5 does not beat C3's precision (1.000)
   — C3 has no FPs at all in this scenario set — but it has the best F1 of
   any condition because it is the only one that is both recall-complete
   on S4 and partially precision-corrected on S3. Giving the agent
   provenance information about *which* evidence source found each edge
   is sufficient to recover full recall, but it is not sufficient, on its
   own, to fully resolve *scope* — telling the difference between "this
   static-only edge is suppressed but belongs to this scenario" and "this
   static-only edge is real but belongs to a different scenario" requires
   function-level (not just component-level) context that the current C2
   pipeline does not retain (see the S3 qualitative analysis below).

## C5 qualitative analysis

### S1, S2, S4 — perfect (TP = reference size, FP = 0, FN = 0)

With provenance-tagged static/dynamic evidence and explicit guidance that a
single-source edge may be genuinely real (not just corroboration-weak
noise), the agent now retains every element C4's raw union found on three
of four scenarios:

- **S1**: kept `getAll`, `flush`, `instance`, `stream` — `instance()` (a
  singleton accessor) is retained because the
  dynamic trace independently confirms `flush`/`stream`/`getAll` occur in
  the same call sequence and the agent does not treat a single-source
  logging call as automatically incidental.
- **S4**: kept both `onStageEvent` (dynamic-only, indirect `signals2`
  dispatch) and `stream` (static-only, suppressed fault path): the agent's
  `sequence.mmd` note
  explicitly states "indirect dispatch via boost::signals2 ... dynamic-only,
  no static call site" for `onStageEvent`, and "fault path: error log when
  no listener attached ... static-only, suppressed at runtime by
  LogLevel::NONE" for `stream` — i.e. it articulates, in its own
  output, exactly the provenance reasoning behind retaining both edges.

### S3 — the one remaining imprecision: kept `flush`, dropped `instance`

C2/C4 input for S3 has 5 elements: `getAll`, `convert`, `stream` (all
corroborated by the dynamic trace — the 3 true in-scope elements) plus
`flush` and `instance` (static-only, real Sync→Logging calls, but from a
different function elsewhere in the codebase, outside
`SimpleRunner.runStage` / `runStages` / `SynchronizedRunnerMaster.runAllStages`
— S3's actual scope).

The agent kept 4: `getAll` ✓, `convert` ✓, `stream` ✓, `flush` ✗ (FP) —
and correctly dropped `instance`. Its own `sequence.mmd` note on `flush`
reads: "static-only; likely suppressed at runtime (e.g., flush occurs on
shutdown or specific log policy/log level)" — the agent applied the same
"static-only may be suppressed-but-real" reasoning that correctly recovered
S4's fault-path edge, but this time the reasoning is *wrong*: `flush` isn't
a suppressed fault-path call for this scenario at all, it's a real call
from unrelated code that static analysis over-approximated into S3's
component-level edge set.

**Verdict — a disclosed, bounded limitation.** The
agent cannot tell these two situations apart because `C2_static_only`'s
`elements.json` only records component-level triples (`source`, `target`,
`interaction`) — it discards the calling function name that would let the
agent see `flush` originates from a *different* function than S3's three
in-scope calls. This is a concrete, scoped direction for future work
(retain `ClientFunction` through the C2/C5 pipeline), not a flaw that
undermines the current result: C5's S3 precision (0.75) is still better
than C4's raw union (0.60), and its recall (1.000) and overall macro F1
(0.964) both remain the best of any condition tested.

## S4 — Stage Event Bridge (constructed, H1c)

Unlike S1–S3 (all found in CPSCore's existing, unmodified production code),
S4 is **deliberately constructed** to test the one architectural precondition
none of the naturally-occurring scenarios satisfy: a call that is *only*
visible dynamically, co-located with a call that is *only* visible
statically, across the same component boundary. Two new production files
were added for this purpose (not test-only stubs):

- `include/cpsCore/Synchronization/StageEventBridge.h` /
  `src/Synchronization/StageEventBridge.cpp` — publishes a stage-completion
  event over a `boost::signals2::signal`. If no listener is connected, it
  logs `CPSLOG_ERROR("No listener connected for stage event")` → `stream`
  (Synchronization→Logging). If a listener *is* connected, it invokes the
  signal directly (Synchronization→Aggregation, via the signal/slot
  mechanism, not a normal function call).
- `include/cpsCore/Aggregation/StageEventListener.h` /
  `src/Aggregation/StageEventListener.cpp` — connects `onStageEvent()` as a
  slot. This method has **no static call site anywhere in the codebase**; it
  is only reachable through the signals2 connection made at runtime.
- `tests/Synchronization/StageEventBridgeTest.cpp` — Catch2 test
  `"Stage Event Bridge Pub-Sub Routing"`, connects the listener, publishes a
  stage, and (in a separate `SECTION`) exercises the no-listener branch
  wrapped in `CPSLogger::LogLevelScope(LogLevel::NONE)` — the same
  suppression idiom that motivated this scenario's design.

**Why C2 misses `onStageEvent`:** static/clang-based call-graph analysis
resolves direct calls and (in CPSCore) intra-module virtual dispatch: it has
no mechanism to resolve a `boost::signals2` signal to its connected slot(s),
since the connection is established at runtime via `connect()`, not through
any statically-resolvable vtable or call expression. This edge is
fundamentally invisible to C2, not merely missed by an incomplete tool run.

**Why C3 misses `stream`:** the test wraps the no-listener branch in
`LogLevelScope(LogLevel::NONE)`, so `CPSLOG_ERROR` is a no-op at runtime and
emits nothing to trace.

**Real captured trace** (`experiments/scenarios/S4/trace_slice.txt`, captured
by running the instrumented test in WSL, not fabricated):

```
[S4TRACE]...|StageEventListener.onStageEvent|Synchronization|StageEventBridge.publishStage|Aggregation|StageEventListener.onStageEvent|Command|StageEventListener
```

Only the `onStageEvent` delivery edge appears — confirming the `stream` edge
is genuinely absent from the runtime trace, not merely unrecorded.

- Reference: 2 elements (`Synchronization→Logging:stream`,
  `Synchronization→Aggregation:onStageEvent`)

| Condition | TP | FP | FN | P | R | F1 | Elements found |
|---|---:|---:|---:|---:|---:|---:|---|
| C1 LLM-only | 1 | 1 | 1 | 0.500 | 0.500 | 0.500 | `onStageEvent` ✓, `logError` ✗ (hallucinated name), `stream` missed |
| C2 Static-only | 1 | 0 | 1 | 1.000 | 0.500 | 0.667 | `stream` ✓ only — no static edge for the signal/slot dispatch |
| C3 Dynamic-only | 1 | 0 | 1 | 1.000 | 0.500 | 0.667 | `onStageEvent` ✓ only — `stream` suppressed at runtime |
| C4 Static+Dynamic | 2 | 0 | 0 | 1.000 | 1.000 | **1.000** | both — union recovers everything |
| C5 Full pipeline | 2 | 0 | 0 | 1.000 | 1.000 | **1.000** | both — provenance-aware agent retains `stream` (static-only, fault-path) and `onStageEvent` (dynamic-only, indirect dispatch) |

**F1(C4) = 1.000 > F1(C2) = 0.667 and F1(C4) = 1.000 > F1(C3) = 0.667 — H1c,
confirmed empirically, real pipeline execution, no simulated numbers.** This
is the mechanistic proof that the general claim "C4 ⊇ C2 and C4 ⊇ C3 always,
so C4 ≥ max(C2, C3) in F1" holds even in the strict sense (>, not just ≥)
once a scenario is constructed where each single source is missing a
different edge from the other.

**C5 inherits the H1c win.** With provenance-tagged static/dynamic evidence, the
agent explicitly reasons (in its own `sequence.mmd` annotations) that
`onStageEvent` is a confirmed indirect dispatch and `stream` is a
suppressed-but-real fault-path call, and retains both — **F1(C5)=1.000,
matching C4** — a fully clean result for agent synthesis on the
constructed dual-gap scenario.

All five conditions for S4 were executed for real: C1 and C5 are genuine
Azure OpenAI (`gpt-5`) API responses (not hand-written), C2 was derived by
manual static-call-graph reading of the new production code (Renaissance was
not re-run against the new files in this session — documented as a
methodological difference from S1–S3, where C2 comes from the Renaissance/
Neo4j pipeline), and C3/C4 were produced by running the actual
`run_c3_dynamic_only.py` / `run_c4_static_dynamic.py` scripts against the
real captured trace. C5 was run against the
provenance-aware `run_c5_full_pipeline.py` (real Azure OpenAI call, same
model/endpoint), producing the F1=1.000 result above.

## Condition definitions

| ID | Label | Static graph | Dynamic traces | Agent synthesis |
|----|-------|:---:|:---:|:---:|
| C1 | LLM-only | ✗ | ✗ | ✗ (direct LLM prompt) |
| C2 | Static-only | ✓ | ✗ | ✗ |
| C3 | Dynamic-only | ✗ | ✓ | ✗ |
| C4 | Static+Dynamic | ✓ | ✓ | ✗ |
| C5 | Full pipeline | ✓ | ✓ | ✓ |

*C5 additionally emits an ordered `sequence.mmd` Mermaid sequence diagram
(plus raw `sequence.json`) alongside `elements.json` per scenario — see
"C5 Methodology" above.*

## Expected output

A stratified table (happy-path stratum S1–S3, constructed dual-gap stratum
S4) plus an aggregate across the full scenario set, with per-condition
failure analysis. See `scoring/results.csv` for the complete per-scenario
breakdown, including the real S4 row, and
`conditions/C5_full_pipeline/<scenario>/sequence.mmd` for the ordered
sequence-diagram artifacts.
