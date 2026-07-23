# H1 — Comparing Evidence Sources for Architectural Interaction Recovery

## Research Question

Which evidence source (LLM analysis, static call graph, raw runtime trace, or guided
instrumentation) most accurately recovers the set and execution sequence of
cross-component architectural interactions for a given test scenario?

## Hypothesis

**H1 — Guided instrumentation + runtime reachability filtering achieves the highest
accuracy** because it combines precise instrumentation (targeting architecturally
significant call sites identified by Neo4j) with an automated scope filter that
excludes test-setup boilerplate. Confirmed: C5 macro intr=**1.000**, seq=**1.000**
on all four scenarios.

## Folder structure

```
H1/
├── conditions/
│   ├── C1_llm_only/              LLM two-prompt chain (Azure OpenAI)
│   ├── C2_static_only/           Neo4j CppCalls DFS-ordered traversal
│   ├── C3_dynamic_only/          raw full_trace.txt (no filter)
│   ├── C4_guided_only/           trace_slice.txt, no reachability filter (C5 ablation)
│   ├── C5_guided_reach/          trace_slice.txt + Neo4j reachability  <- perfect
│   ├── C6_full_trace_reach_only/ full_trace.txt + Neo4j reachability (C5 ablation)
│   ├── C7_llm_c2/                LLM + C2 static candidates
│   ├── C8_llm_c3/                LLM + C3 raw trace candidates (denoised)
│   ├── C9_llm_c4/                LLM + C4 guided trace candidates
│   ├── CONDITIONS.md
│   └── _utils.py                 shared helpers
├── scoring/
│   ├── evaluate_all.py           reruns C3-C6, scores all conditions
│   ├── generate_md.py            regenerates results.md from authoritative tables
│   ├── results.csv               scores for all conditions (auto-generated)
│   └── results.md                full tables + shortcoming analysis
└── threats_and_improvements.md   validity threats and design improvements

experiments/scenarios/
├── candidate_scenarios.md        candidate tests for future scenario expansion
└── gt_derivation_arch.md         GT derivation methodology

architectural_diagrams/    (cpscore root - shared across experiments)
├── arch_filters.py           REACHABILITY + SCENARIO_ENTRY filters (excalidraw-derived)
├── cpsCore_packages_annotated.puml
├── S1/ S2/ S3/           excalidraw scenario diagrams
└── instrumentation_sites.txt bijection: excalidraw arrows <-> trace_slice sites
```

## Ground-truth methodology

GT is derived by `experiments/scenarios/derive_gt_arch.py` (Neo4j-free) from:

| Source | Role |
|--------|------|
| `trace_slice.txt` | Runtime events captured at Neo4j-identified instrumentation sites |
| `arch_filters.py` (REACHABILITY + SCENARIO_ENTRY) | Component scope + entry-point scope filter derived from excalidraw diagrams |

Validated at F1 = 1.000 vs the original Neo4j-derived GT on all scenarios.
See `experiments/scenarios/gt_derivation_arch.md` for full methodology.

### Per-scenario ground truth

| Scenario | Test | Components | `gt_interactions` | `gt_sequence` events |
|----------|------|-----------|------------------|---------------------|
| S1a | "Synchronized Runner Test" | Sync, Agg, Log | 2 | 8 |
| S1b | "Synchronized Runner Timeout" | Sync, Agg, Log | 3 | 5 |
| S2 | "Optional test" | Config, Log | 1 | 1 |
| S3 | "MultiThreaded Test 1" | Sync, Agg, Util, Log | 3 | 13 |

## Results

All scores from `evaluate_all.py` rerun — S1a, S1b, S2, S3.
See `scoring/results.md` for full tables, examples, and shortcoming analysis.

### Interactions F1 (set-based, method-level)

| Scenario | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 |
|----------|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1a | **1.000** | 0.667 | 0.444 | 0.800 | **1.000** | **1.000** | **1.000** | **1.000** | 0.800 |
| S1b | **1.000** | 0.857 | 0.545 | 0.857 | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |
| S2 | **1.000** | **1.000** | 0.667 | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |
| S3 | 0.857 | 0.500 | 0.462 | **1.000** | **1.000** | **1.000** | 0.667 | 0.571 | 0.333 |
| **Macro** | 0.964 | 0.756 | 0.530 | 0.914 | **1.000** | **1.000** | 0.917 | 0.893 | 0.783 |

### Sequence LCS F1 (order-preserving)

| Scenario | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | C9 |
|----------|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S1a | **1.000** | 0.333 | 0.340 | 0.800 | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |
| S1b | **1.000** | 0.667 | 0.304 | 0.715 | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |
| S2 | **1.000** | **1.000** | 0.667 | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |
| S3 | 0.740 | 0.143 | 0.400 | 0.867 | **1.000** | **1.000** | 0.645 | 0.615 | 0.560 |
| **Macro** | 0.935 | 0.536 | 0.428 | 0.846 | **1.000** | **1.000** | 0.911 | 0.904 | 0.890 |

### Condition summary

| Condition | intr macro | seq macro | Role |
|---|:---:|:---:|---|
| C1 - LLM source-only | 0.964 | 0.935 | S3 FP: stop() teardown call in snippet |
| C2 - Neo4j static (entry-pt ordered) | 0.756 | 0.536 | misses indirect-dispatch; ordering is approximate |
| C3 - unfiltered raw trace | 0.530 | 0.428 | worst dynamic: intra-component FPs inflate both metrics |
| C4 - guided only (no filter) | 0.914 | 0.846 | best Neo4j-free baseline; only setup FPs remain |
| **C5 - guided + reachability** | **1.000** | **1.000** | perfect; two-phase Neo4j use |
| **C6 - full trace + reachability** | **1.000** | **1.000** | C5 ablation: filter sufficient regardless of instrumentation |
| C7 - LLM + C2 candidates | 0.917 | 0.911 | LLM recovers C2 precision gaps; fails on S3 (added static FPs) |
| C8 - LLM + C3 candidates | 0.893 | 0.904 | LLM denoises raw trace; S3 hardest (diverse intra-component noise) |
| C9 - LLM + C4 candidates | 0.783 | 0.890 | LLM over-filters a good prior; C4 alone is better |

## Key findings

1. **C5 achieves perfect scores** via two independent Neo4j uses: design-time site selection
   and runtime reachability filtering. Cross-validated against human architectural
   analysis (excalidraw diagrams) independently.

2. **C6 = C5 on all metrics**: the reachability filter is sufficient regardless of
   instrumentation strategy. Guided vs full trace does not matter once the scope filter
   is applied.

3. **Guided instrumentation (C4, 0.914/0.846) substantially outperforms unfiltered trace (C3, 0.530/0.428)**
   because `trace_slice.txt` only fires at cross-component arch sites — intra-component
   call sites are never instrumented. C3's low score is entirely due to intra-component
   FPs. The reachability filter (C5 vs C4, C6 vs C3) then eliminates the remaining
   setup-phase FPs, bringing both to 1.000. C4 is the strongest Neo4j-free baseline.

4. **C1 (LLM source-only)** reaches macro intr=0.964, seq=0.935 with natural snippets.
   Fails only on S3: 1 FP (`CPSLogger.flush` from `stop()`, called by test teardown
   but present in the snippet).

5. **C2 (static analysis) is structurally limited by indirect dispatch.** Neo4j cannot
   follow `std::function`-dispatched calls — the `Utilities→Logging` interaction in S3
   has no static call site visible to `CppCalls`. This is a structural ceiling, not a
   tuning issue: no refinement of the Cypher query recovers it.

6. **LLM with evidence prior (C7/C8/C9) shows diminishing returns as the prior gets cleaner.**
   C7 (LLM+C2) significantly recovers C2's recall, matching C1 on 3/4 scenarios.
   C8 (LLM+C3) nearly eliminates C3's FP inflation. C9 (LLM+C4) actually hurts
   (0.783 vs C4's 0.914) because LLM over-filters a prior that's already precise.

## Condition definitions

| ID | Script | Input | Neo4j? | Purpose |
|----|--------|-------|--------|---------|
| C1 | `run_c1_llm_only.py` | `source_snippet.txt` | No | LLM baseline |
| C2 | `run_c2_static_only.py` | Neo4j call graph (entry-pt ordered) | Runtime | Static baseline |
| C3 | `run_c3_dynamic_only.py` | `full_trace.txt` | No | Dynamic baseline |
| C4 | `run_c4_guided_only.py` | `trace_slice.txt` (no reachability filter) | Design-time only | C5 ablation: instrumentation |
| C5 | `run_c5_guided_reach.py` | `trace_slice.txt` + reachability | Design-time + Runtime | Best condition |
| C6 | `run_c6_full_trace_reach_only.py` | `full_trace.txt` + reachability | Runtime | C4 ablation: instrumentation |
| C7 | `run_c7_llm_c2.py` | C2 candidates + `source_snippet.txt` | No | LLM refines static candidates |
| C8 | `run_c8_llm_c3.py` | C3 candidates + `source_snippet.txt` | No | LLM denoises raw trace |
| C9 | `run_c9_llm_c4.py` | C4 candidates + `source_snippet.txt` | No | LLM refines guided trace |
