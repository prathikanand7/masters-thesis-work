# Experiments

All hypotheses share the **same scenario set, the same Neo4j graph, and the
same CPSCore trace files** in this workspace.

## Folder structure

```
experiments/
├── scenarios/              ← shared GT derivation + scenario definitions
│   ├── derive_gt_arch.py   Neo4j-free GT: trace_slice.txt + arch_filters.py
│   ├── arch_filters.py     REACHABILITY + SCENARIO_ENTRY filters (excalidraw-derived)
│   ├── gt_derivation_arch.md  full GT methodology + validation
│   ├── candidate_scenarios.md  candidate tests for future scenario expansion
│   └── S1a/ S1b/ S2/ S3/  (gt_interactions.json + gt_sequence.json per scenario)
├── H1/                     ← evidence source comparison study (complete)
│   ├── conditions/         C1–C9 condition scripts + outputs, per scenario
│   ├── scoring/            evaluate_all.py + generate_md.py + results.csv + results.md
│   └── threats_and_improvements.md
└── H2/                     ← guided vs. full instrumentation study (complete)
    ├── instrumentation/    full_trace.txt + trace_slice.txt per scenario (S1–S4)
    ├── metrics/            diagram_metrics.py + results.csv
    └── expert_rating/      rating_form.md + 6 collected responses

architectural_diagrams/  ← at cpscore root, shared across all experiments
    arch_filters.py                    REACHABILITY + SCENARIO_ENTRY filters
    cpsCore_packages_annotated.puml    architectural edge map (clang-uml output)
    S1/ S2/ S3/                    per-scenario excalidraw reference diagrams
```

## Scenarios

All scenarios are drawn from the existing cpsCore test suite.
GT is derived by `scenarios/derive_gt_arch.py` (Neo4j-free: `trace_slice.txt` filtered
by `arch_filters.py`). Validated at F1=1.000 vs. the original Neo4j-derived GT.
See `scenarios/gt_derivation_arch.md` for methodology.

| ID | Test name | Components | GT interactions | GT seq events |
|----|-----------|-----------|:---:|:---:|
| S1a | "Synchronized Runner Test" | Sync, Agg, Log | 2 | 8 |
| S1b | "Synchronized Runner Timeout" | Sync, Agg, Log | 3 | 5 |
| S2 | "Optional test" | Config, Log | 1 | 1 |
| S3 | "MultiThreaded Test 1" | Sync, Agg, Util, Log | 3 | 13 |

H1 uses S1a–S3.

## Dependency flow

```
scenarios/derive_gt_arch.py  ──►  H1 condition scoring (GT source)
                              ──►  H3 ground truth (component/interaction reference)

architectural_diagrams/  ──►  arch_filters.py (SCENARIO_ENTRY filter)
                          ──►  H1/C2 (Neo4j static graph)
                          ──►  H1/C4, C6 (Neo4j reachability filter)
```

## Status

| Hypothesis | Question | Status | Key result |
|---|---|---|---|
| **H1** | Which evidence source best recovers architectural interactions? | ✅ Complete | C5/C6=**1.000/1.000** (reach filter → perfect); C1=0.964/0.935 (LLM source); C7=0.917/0.911 (LLM+static); C8=0.893/0.904 (LLM+raw trace); C4=0.914/0.846 (best Neo4j-free non-LLM); C9=0.783/0.890 (LLM over-filters C4); C2=0.756/0.536 (static; `std::function` gap is structural ceiling); C3=0.530/0.428 (unfiltered trace; intra-component FPs) |
| **H2** | Does guided instrumentation improve signal-to-noise? | ✅ Complete | Guided diagrams smaller and higher coverage; guided > full for all 6 raters on accuracy + readability |
| **H3** | Do reconstructed diagrams improve agent task performance? | 🔄 In progress | — |

## Running the full pipeline

```bash
# 1. (Optional) Re-derive GT for all scenarios — Neo4j-free
conda run -n llm4legacy python experiments/scenarios/derive_gt_arch.py --all

# 2. Rerun H1 dynamic/guided conditions and score (C1 needs Azure OpenAI; C2/C4/C6 need Neo4j)
cd experiments/H1/conditions
conda run -n llm4legacy python run_c1_llm_only.py --all         # Azure OpenAI
conda run -n llm4legacy python run_c2_static_only.py --all      # Neo4j
conda run -n llm4legacy python run_c3_dynamic_only.py --all     # no external deps
conda run -n llm4legacy python run_c4_guided_only.py --all      # no external deps
conda run -n llm4legacy python run_c5_guided_reach.py --all     # Neo4j
conda run -n llm4legacy python run_c6_full_trace_reach_only.py --all  # Neo4j
conda run -n llm4legacy python run_c7_llm_c2.py --all           # Azure OpenAI (run after C2)
conda run -n llm4legacy python run_c8_llm_c3.py --all           # Azure OpenAI (run after C3)
conda run -n llm4legacy python run_c9_llm_c4.py --all           # Azure OpenAI (run after C4)

# 3. Score and generate report
cd experiments/H1/scoring
conda run -n llm4legacy python evaluate_all.py   # reruns C3-C6, scores all conditions
python generate_md.py                            # regenerates results.md

# 4. H2 metrics
conda run -n llm4legacy python experiments/H2/metrics/diagram_metrics.py --all
```

Neo4j: `bolt://127.0.0.1:7688`, credentials in `.env` at cpscore root.
