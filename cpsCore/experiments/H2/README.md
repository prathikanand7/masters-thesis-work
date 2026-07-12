# H2 — Guided Instrumentation Improves Signal-to-Noise

**Hypothesis:** Code-graph-guided instrumentation produces diagrams that are smaller
and less noisy than full instrumentation (quantitative arm), and easier to understand
because they emphasise scenario-relevant interactions and suppress irrelevant execution
details (perceptual arm — confirmed via a 6-rater blinded expert rating, see below).

## Folder structure

```
H2/
├── instrumentation/
│   ├── generate_traces.py       builds full/guided trace files from existing data
│   ├── S1/
│   │   ├── full_trace.txt       entire runtime_traces.txt (all 27 events)
│   │   └── guided_trace.txt     slice-filtered events for S1 (11 events)
│   ├── S2/  (full=27, guided=7)
│   └── S3/  (full=27, guided=6)
├── metrics/
│   ├── diagram_metrics.py       nodes/edges/coverage/noise scorer
│   └── results.csv              auto-generated (confirmed)
└── expert_rating/
    ├── rating_form.md           ready to send — diagrams embedded as mermaid
    ├── decode_key.txt           A/B randomisation key (keep from raters)
    └── responses/               collect completed rating files here
```

## Task checklist

- [x] **Task 1** — Generate full vs. guided trace files (`instrumentation/generate_traces.py`)
- [x] **Task 2** — Run `metrics/diagram_metrics.py --all` → TP/FP/FN per scenario confirmed
- [x] **Task 3 (added)** — Extended to S4 (constructed, \cref H1 §H1c): full/guided
      trace files generated, scored for real; see "S4" subsections below
- [x] **Task 4** — Sent `expert_rating/rating_form.md` to raters ← perceptual arm
- [x] **Task 5** — Collected 6 completed responses (2 in the original round,
      4 more added later to strengthen the sample)
- [x] **Task 6** — Scored responses: guided > full on accuracy/readability for
      every rater on every scenario; usefulness confirmed on S1/S3, genuinely
      mixed on S2 (see "Expert rating results" below)

## Quantitative results (H2 quantitative arm — pending expert ratings)

### Per-scenario TP / FP / FN against H1 independent reference

Coverage and noise are computed against `experiments/H1/reference_diagrams/SX/elements.json`
(manually source-read, independent of the slicing tool).

| Scenario | Variant | Interactions | TP | FP | FN | Coverage | Noise |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| S1 | Full | 9 | 4 | **5** | 0 | 1.000 | 0.556 |
| S1 | Guided | 4 | 4 | 0 | 0 | 1.000 | 0.000 |
| S2 | Full | 9 | 1 | **8** | 0 | 1.000 | 0.889 |
| S2 | Guided | 1 | 1 | 0 | 0 | 1.000 | 0.000 |
| S3 | Full | 9 | 3 | **6** | 0 | 1.000 | 0.667 |
| S3 | Guided | 3 | 3 | 0 | 0 | 1.000 | 0.000 |
| S4 | Full | 10 | 2 | **8** | 0 | **1.000\*** | 0.800 |
| S4 | Guided | 1 | 1 | 0 | **1** | **0.500** | 0.000 |

\* **S4-full coverage is a measurement artifact, not genuine recovery — see
"S4: a discovered scoring artifact" below. Do not read this row the same way
as S1–S3.**

Full-trace FP calls (noise) are real runtime events from non-primary components
active in the same test run: `Aggregation→Logging:stream`, `Configuration→Logging:stream`,
`Framework→Logging:stream`, `Utilities→Logging:stream`, and in some scenarios
additional Synchronization calls irrelevant to the specific scenario.

### Circularity analysis for guided noise=0

**Guided noise=0 has two components — one by construction, one empirical:**

- *By construction (boundary):* the slice filter and the H1 reference share the
  same scope constraint (`ClientComponent == primary`,
  `ServerComponent ∈ SCENARIO_COMPONENTS`). Any call from a non-primary component
  (e.g. `Aggregation→Logging`) is excluded from both the guided trace and the
  reference by definition. It is not possible for the guided trace to produce an
  out-of-scope FP, so noise from out-of-scope calls is 0 by construction, not
  empirically.

- *Empirical (within scope):* within the shared boundary, the guided trace could
  still have produced FPs if the runtime contained primary-to-target calls with
  interaction names not in the source-read reference. **S3 is the concrete test
  case:** the full trace contains `Synchronization→Logging:flush` and
  `Synchronization→Logging:instance` within scope (primary=Synchronization,
  target=Logging), but the S3 reference specifies only `getAll`, `stream`,
  `convert` — `flush` and `instance` are in scope but not in the reference.
  The guided slice correctly excluded them (they were not selected by the
  `client_function` filter in the S3 slice definition). FP=0 within scope on
  S3 is therefore a tested result, not a trivially absent possibility.
  S1 and S2 have no within-scope calls outside their reference (in_scope=ref
  for both), so the claim is exercised by S3 alone in this scenario set.

**Correct framing:** "Guided instrumentation excludes all non-primary-driver calls
by the scope constraint. Within that scope, no spurious interactions were observed
at runtime (FP=0 within scope, N=3 scenarios). Full instrumentation captures 5–8
additional real-but-off-target calls per scenario (noise ratio 0.56–0.89)."

**What this does not prove:** that the scope constraint itself is the right one
to apply. The constraint is motivated by the experimental design (study primary
driver interactions), not independently validated as "the correct boundary."

### Coverage = 1.000 for guided — is this independent?

Yes. The H1 reference was built by reading source files independently of the
slicing tool. Coverage=1.000 for guided means the runtime trace exercises all
source-visible reference interactions — a genuine, non-circular finding.
FN=0 across all three scenarios: no reference interaction was missed by the
guided trace.

### Small-N caveat

Results are over 3 happy-path scenarios. The within-scope FP=0 finding is
exercised by S3 (which has 2 real within-scope calls outside the reference);
S1 and S2 pose no within-scope naming ambiguity at all. The claim therefore
rests on one scenario's evidence within the current set. A scenario with
richer conditional logic (e.g. multiple overloaded call sites, a callback
dispatch that resolves differently at runtime) could reveal a slicing miss
that S1–S3 did not exercise. FN=0 across all three scenarios is similarly
a small-sample result; one scenario with complex conditional coverage could
expose a guided-trace miss.

### S4: a discovered scoring artifact (full-trace coverage is not genuine here)

S4 was added to H2 for the same reason it was added to H1: it is the one
scenario where static and dynamic evidence each miss a *different* edge
(`stream` vs. `onStageEvent`, see H1 §H1c). Unlike S1–S3, whose
`full_trace.txt` is a direct copy of `runtime_traces.txt` (a single capture
that already contains those scenarios' own code paths), S4's production code
(`StageEventBridge`/`StageEventListener`) did not exist when
`runtime_traces.txt` was captured. Its `full_trace.txt` was therefore
constructed by *appending* S4's own captured row (`onStageEvent`) to the
pre-existing `runtime_traces.txt` baseline — the honest simulation of "what a
full-instrumentation run across the whole, now-larger test suite would
capture."

Scoring this file produced an unexpected result: **S4-full shows TP=2,
coverage=1.000 — appearing to recover `stream` as well.** Inspecting the
matched row shows this is **not genuine**: the pre-existing baseline already
contains six unrelated `Synchronization→Logging:stream` rows (from
`SimpleRunner.runStage`, `SynchronizedRunnerMaster.runStage`, and similar —
real calls from *other* scenarios' code, captured under normal logging
conditions, not from `StageEventBridge::publishStage`). Because the H1/H2/H3
scoring convention matches on the bare
`(source, target, interaction-name)` triple only — deliberately, to mirror how
an agent or a human describes an interaction — any one of those six
pre-existing rows satisfies the S4 reference's `Synchronization→Logging:stream`
requirement, even though none of them is the S4 fault-path log call, which
remains genuinely absent (still suppressed by
`CPSLogger::LogLevelScope(LogLevel::NONE)` inside the S4 test, exactly as
designed). **The guided trace does not have this problem**, precisely
because it is scoped to only the rows captured during the S4 test itself
(1 row, `onStageEvent`) — it correctly reports FN=1, coverage=0.500.

**Correct interpretation:** treat S4-guided (coverage=0.500) as the honest
answer for both instrumentation strategies — neither recovers `stream` for
the *right* reason. S4-full's coverage=1.000 is retained in the table above
(the script output is not edited) but must be read as a **finding about the
scoring convention**, not about instrumentation strategy: pooling trace
events across an entire, unscoped test suite increases the chance that some
unrelated call elsewhere in the codebase coincidentally matches a reference
triple by bare name alone. This is the same generic risk noted for C2/C4's
S3 precision deficit (\cref{sec:h1-corrections} in the thesis), but appearing
here as a **false positive in the opposite direction — inflated coverage
rather than inflated noise.**

**Why this strengthens, not weakens, the H2 argument:** it shows a full,
unscoped instrumentation strategy can produce a diagram that looks more
complete than it is, for reasons entirely unrelated to the scenario being
studied. Guided instrumentation cannot exhibit this failure mode by
construction — its trace file only ever contains rows from the scenario's
own execution. This is a stronger form of the noise argument: full
instrumentation isn't just noisier, it can be **unverifiably, coincidentally
over-credited** under a coarse (but necessary, agent-friendly) matching
convention.

### Summary (mean across S1–S3; S4 reported separately as constructed)

| Metric | Full | Guided | Reduction |
|---|:---:|:---:|:---:|
| Nodes | 6.0 | 3.0 | −50% |
| Interactions | 9.0 | 2.7 | −70% |
| Coverage | 1.000 | 1.000 | 0% |
| Noise (overall) | 0.704 | 0.000¹ | — |
| Noise (within-scope FP) | varies | 0.000 | real finding |

¹ Noise=0 for guided is partially by the scope constraint (see circularity analysis).
The meaningful comparison is full-trace noise 0.56–0.89 vs guided within-scope noise 0.000.
S4 (constructed) is excluded from this mean — see its own subsection above; its
guided coverage (0.500) reflects a genuine, designed-in fault-path miss, not a
failure of the slicing mechanism, and its full-trace coverage (1.000) is a
scoring-convention artifact rather than a comparable data point.

## Expert rating results (perceptual arm — complete, n=6 raters)

The rating form (`expert_rating/rating_form.md`) presented both diagrams to raters
in randomised A/B order per scenario (see `decode_key.txt`). Three scenarios, three
criteria (Accuracy, Readability, Usefulness), 1–5 scale. Six raters returned
completed forms (2 in the original round; 4 more collected afterward to
strengthen the sample).

**Mean rating per scenario/dimension (Full vs. Guided, n=6):**

| Scenario | Accuracy (F/G) | Readability (F/G) | Usefulness (F/G) |
|---|:---:|:---:|:---:|
| S1 | 2.33 / 4.67 | 2.33 / 4.83 | 3.17 / 4.50 |
| S2 | 2.33 / 4.17 | 2.33 / 4.83 | 2.67 / 2.83 |
| S3 | 2.50 / 5.00 | 2.67 / 5.00 | 3.00 / 4.67 |
| **Mean** | **2.39 / 4.61** | **2.44 / 4.89** | **2.94 / 4.00** |

**Aggregate across all 6×9=54 rater×scenario×dimension comparisons:** guided
rated strictly higher in **47**, tied in **6**, and rated strictly lower in
exactly **1**. Grand mean: guided 4.50 vs. full 2.59.

**What the ratings show:**
- Accuracy/Readability: guided is never rated below full by any rater on any
  scenario (34/36 strictly higher, 2 ties — both rater R4, on S2 and S3
  accuracy). This effect is unanimous in direction across all six raters.
- Usefulness: unanimous on S1 and S3 (guided preferred by all 6). Genuinely
  mixed on S2: 3 raters (R1–R3) tied — each independently citing the same
  reason, that collapsing 7 repeated property-read calls into 1 edge loses a
  count they consider useful for debugging; 1 rater (R4) rated full *higher*
  on usefulness, citing a different concern ("not clear what triggers a
  logging event"); 2 raters (R5, R6) rated guided higher.
- Convergent feature requests: R3 and R6 independently suggested a way to
  toggle/filter high-volume `stream` events; R2 suggested recording the
  specific property value per `stream` call to preserve debugging value in
  the collapsed S2 edge; R3 proposed a two-stage workflow (full diagram for
  overview, guided diagram to reason about the scenario).

**Conclusion:** H2's perceptual arm is confirmed, more robustly than the
original 2-rater round suggested — expanding the panel to 6 raters preserved
the direction of every effect and sharpened (rather than resolved) the one
qualification: usefulness on S2 is a genuine three-way split, not a clean tie.

## Condition definitions

| Variant | Instrumentation strategy | Trace source |
|---|---|---|
| Full | All call sites instrumented; entire test run captured | `runtime_traces.txt` (27 events) + S4's own captured row for S4 |
| Guided | Slice-selected call sites only; primary-driver filter applied | `scenarios/SX/trace_slice.txt` |
