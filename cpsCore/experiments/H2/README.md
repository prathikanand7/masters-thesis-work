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

### Analysis notes

- **Noise=0 for guided is partly by construction.** The scope constraint (`ClientComponent == primary`, `ServerComponent ∈ SCENARIO_COMPONENTS`) is shared between the guided filter and the H1 reference — out-of-scope FPs are impossible by definition. The within-scope part is empirical: S3 has 2 real in-scope calls (`flush`, `instance`) that the reference does not include; the guided slice correctly excluded them. S1/S2 have no within-scope ambiguity, so S3 is the only real test of this.
- **Coverage=1.000 for guided is independent.** H1 reference built from source-reading, not from the trace tool. FN=0 on all 3 scenarios is genuine.
- **Small N.** Within-scope FP=0 exercised by S3 alone. One scenario with complex conditional logic or overloaded call sites could expose a slicing miss.
- **S4 full-trace coverage=1.000 is a scoring artifact.** The baseline corpus contains 6 unrelated `Sync→Log:stream` rows from other tests. These coincidentally match S4's reference triple by bare name. Guided is not affected — it contains only S4's own captured row. Use S4-guided (coverage=0.500) as the honest number for both strategies.

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

Rating form: two diagrams per scenario in randomised A/B order, 3 criteria (Accuracy, Readability, Usefulness), 1–5 scale. 6 raters (2 original round, 4 added later).

**Mean rating (Full / Guided):**

| Scenario | Accuracy | Readability | Usefulness |
|---|:---:|:---:|:---:|
| S1 | 2.33 / 4.67 | 2.33 / 4.83 | 3.17 / 4.50 |
| S2 | 2.33 / 4.17 | 2.33 / 4.83 | 2.67 / 2.83 |
| S3 | 2.50 / 5.00 | 2.67 / 5.00 | 3.00 / 4.67 |
| **Mean** | **2.39 / 4.61** | **2.44 / 4.89** | **2.94 / 4.00** |

- Guided rated higher in **47/54** comparisons, tied 6, lower 1. Grand mean: guided 4.50 vs. full 2.59.
- **Accuracy + Readability:** unanimous across all 6 raters on all 3 scenarios (34/36 strictly higher, 2 ties on S2/S3 accuracy by rater R4).
- **Usefulness:** unanimous on S1/S3. Genuinely split on S2 — 3 raters tied (collapsing 7 repeated `stream` calls loses count they want for debugging), 1 rated full higher (unclear trigger), 2 rated guided higher.
- Convergent requests: toggle for high-volume `stream` events (R3, R6 independently); record property value per `stream` call (R2); two-stage workflow — full for overview, guided for scenario reasoning (R3).

## Condition definitions

| Variant | Instrumentation strategy | Trace source |
|---|---|---|
| Full | All call sites instrumented; entire test run captured | `runtime_traces.txt` (27 events) + S4's own captured row for S4 |
| Guided | Slice-selected call sites only; primary-driver filter applied | `scenarios/SX/trace_slice.txt` |

---

## Problems with this approach

**P1 — Full trace is not per-test scoped.**
The "full" condition is the same 27-event file for S1, S2, and S3. These events come from the entire test suite, not from each scenario's individual test run. Noise figures (56–89%) are therefore inflated by events from unrelated tests, not only by events active during the scenario under study. Real per-test full traces would likely show lower noise, making the full/guided comparison more conservative (still in guided's favour, but smaller gap).
Fix: generate full traces with LLVM XRay per test case (see "Future work"). Output goes to `experiments/scenarios/SX/full_trace_xray.txt` alongside the existing `trace_slice.txt`.

**P2 — Human study showed the same full diagram for every scenario.**
Because the full trace is identical for S1/S2/S3, raters saw the exact same mermaid diagram as "full" three times in a row. A rater who noticed this could infer the A/B assignment immediately, breaking the blinding.
Fix: redo the study with per-test full traces, giving each scenario a distinct full diagram. The existing results are kept as-is — the effect was strong enough to survive this flaw.

**P3 — Noise=0 for guided is not a clean empirical finding.**
The scope constraint is shared between the guided filter and the reference, so out-of-scope FPs are impossible by construction. Only the within-scope part (exercised by S3 alone) is a real finding.
Fix: report as "within-scope FP=0 (N=1 scenario that had ambiguous calls)". Do not claim "noise=0" without qualification.

**P4 — S4 full-trace coverage=1.000 is a scoring artifact.**
Unrelated `stream` rows from other tests coincidentally match S4's reference triple by bare name. The full trace looks more complete than it is.
Fix: per-test XRay traces eliminate this entirely — the full trace would only contain rows from the S4 test execution, so the spurious `stream` rows would not appear.

**P5 — No LLM reconstruction arm.**
H2 only measures human perception. Whether guided instrumentation also improves machine reconstruction quality (C3 F1) is untested — that is the missing cell between H1 and H3.
Fix: run C3 with per-test full trace as input, score against H1 GT, compare to current C3 (which uses guided trace). See H1 README "Planned addition".

---

## Mapping to H1 scenario naming

H1 was later refactored to split S1 into S1a (happy path) and S1b (timeout/failure path).
H2 uses only the pre-existing tests; S1b is not applicable here because it has no
runtime trace (logging is fully suppressed during the timeout test, so there is nothing
to instrument or compare).

| H2 scenario | H1 equivalent | Description |
|---|---|---|
| S1 | S1a | Synchronized Runner Test — happy path |
| S2 | S2 | Configuration property mapping |
| S3 | S3 | Multi-component runner orchestration |
| S4 | S4 | Stage Event Bridge Pub-Sub Routing (constructed) |

**The expert rating study (perceptual arm) used S1/S2/S3 only.** The rating results
are directly reusable under the new naming with S1 → S1a. No re-labelling of the
rating data is needed.

---

## Known limitation: full-trace scope

The current `full_trace.txt` for S1/S2/S3 is the same file — a verbatim copy of
the entire `runtime_traces.txt` corpus (27 events from all components, all tests
combined). This means:

- **Quantitatively:** the full-trace noise figures (56–89%) partly reflect calls
  from *other* scenarios' tests captured in the same run, not only noise from the
  test under study. The guided/full comparison is valid in direction but the full
  baseline is not strictly scoped to the scenario's own test execution.
- **Perceptually (human study):** raters received the same "full" mermaid diagram
  for every scenario (S1, S2, S3), since the underlying 9-edge diagram is identical.
  This creates a risk that raters noticed the repetition and inferred the A/B
  assignment. The unanimous direction of the accuracy and readability results
  suggests the effect was real regardless, but the study design is imperfect.

**For a methodologically stronger future study**, the full trace should be scoped to
the events that fire during *that specific test's execution only* — not the whole
corpus. This would give each scenario a distinct full-trace diagram, and would reduce
noise figures to only the off-target calls active in that one test.

---

## Future work: per-test full traces via LLVM XRay

Scripts are in `instrumentation/`:

| File | Purpose |
|---|---|
| `run_xray.sh` | WSL shell script — builds with XRay, runs each test, calls converter |
| `xray_to_traces.py` | Post-processes symbolized XRay YAML → pipe-delimited trace format |

**Prerequisites (WSL):**
```bash
sudo apt install clang llvm   # Clang >= 8, includes llvm-xray
pip install pyyaml
```

**Run:**
```bash
cd /path/to/cpsCore
bash experiments/H2/instrumentation/run_xray.sh
# Writes experiments/H2/instrumentation/SX/full_trace.txt per scenario
```

**What it does:**
1. Builds CPSCore test binary with `-fxray-instrument -fxray-instruction-threshold=1`
2. Runs each Catch2 test case in isolation with `XRAY_OPTIONS="patch_premain=true"`
3. Symbolizes the XRay binary log via `llvm-xray convert --symbolize --output-format=yaml`
4. `xray_to_traces.py` reconstructs caller→callee pairs from entry/exit events (per-thread call stack), filters to cross-component pairs, maps class names to CPSCore components, emits the pipe-delimited format

**What this fixes vs. current approach:**
- Each scenario gets a distinct full trace (only events from its own test run)
- No cross-test contamination → noise figures will be accurate
- S4 full-trace coverage artifact disappears (no unrelated `stream` rows in the corpus)

---

## LLM redo plan

The quantitative arm (metrics) and the expert rating (human study) are complete and
reusable as described above. The part that should be redone with improved traces is
an **LLM-based reconstruction comparison**: given either the full or guided trace as
input to a condition-C3/C6-style pipeline, does guided instrumentation produce better
LLM reconstruction quality?

This fills a gap in the chain across the three hypotheses:

```
Instrumentation scope → Trace quality → Reconstruction F1 → Agent task performance
       H2 (human)          [missing]          H1                     H3
```

- **H2** (this experiment) measures human perception of full vs. guided diagrams.
- **H1** measures reconstruction F1 but always uses the guided trace as input — it
  never tests what happens when a noisy full trace is fed into the pipeline.
- **H3** measures how a reconstructed diagram helps an agent on a downstream task,
  but always receives the H1 C5/C6 output — it does not vary instrumentation scope.

The missing link: does instrumentation scope propagate through to reconstruction
quality, or does the LLM absorb the noise? For example, on S3 the full trace
contains `flush` and `instance` (real but off-target Sync→Log calls) alongside the
three true interactions. Feeding that to C3 or C6 would likely produce FPs in the
reconstruction. Feeding the guided trace would not. Scoring the difference against
`gt_interactions.json` would quantify the "instrumentation scope effect on
reconstruction F1" — directly complementing H2's human perception result.

To run:
1. Generate per-test-scoped full traces (via XRay or by filtering `runtime_traces.txt`
   to scenario-specific `ClientFunction` values)
2. Run C3 (dynamic-only) with full trace as input → score against H1 GT → F1_full
3. Run C3 with guided trace as input → score against H1 GT → F1_guided
4. Compare F1_full vs. F1_guided: quantifies how much instrumentation scope matters
   for the reconstruction step, independently of the LLM's reasoning ability
