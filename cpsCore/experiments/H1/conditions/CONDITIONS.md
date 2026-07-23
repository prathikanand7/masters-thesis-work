# H1 Experimental Conditions

## Condition Overview

| ID | Script | Method | Data Source | Neo4j? | LLM? |
|---|---|---|---|---|---|
| **C1** | `run_c1_llm_only.py` | Two-prompt LLM chain: call 1 identifies unique interactions, call 2 orders the sequence | `source_snippet.txt` | ❌ | ✅ |
| **C2** | `run_c2_static_only.py` | Forward `CppCalls*0..8` traversal from entry points; cross-component edges collected in SCENARIO_ENTRY order (full call-graph DFS not feasible due to CppCalls/CppImplements split in the schema) | Neo4j call graph | ✅ runtime | ❌ |
| **C3** | `run_c3_dynamic_only.py` | Unfiltered full trace — no component scope filter, no src==tgt filter, no reachability filter. All events from `full_trace.txt` pass through including intra-component calls. | `full_trace.txt` (all events, unfiltered) | ❌ | ❌ |
| **C4** | `run_c4_guided_only.py` | Guided instrumentation trace (probes at Neo4j-identified arch call sites) with no reachability filter — ablation of C5 that removes the runtime scope filter | `trace_slice.txt` (no filter) | ✅ design-time only | ❌ |
| **C5** | `run_c5_guided_reach.py` | Guided instrumentation trace filtered by Neo4j `CppCalls*0..8` reachability from entry points | `trace_slice.txt` + Neo4j reachability | ✅ design-time + runtime | ❌ |
| **C6** | `run_c6_full_trace_reach_only.py` | Full trace filtered by Neo4j `CppCalls*0..8` reachability only — ablation of C5 that replaces guided instrumentation with the full trace | `full_trace.txt` + Neo4j reachability | ✅ runtime | ❌ |
| **C7** | `run_c7_llm_c2.py` | Two-prompt LLM chain seeded with C2 static candidates: call 1 filters static over-approximations and adds dynamically-dispatched calls, call 2 orders the sequence | `C2_static_only/<scenario>/interactions.json` + `source_snippet.txt` | ❌ | ✅ |
| **C8** | `run_c8_llm_c3.py` | Two-prompt LLM chain seeded with C3 raw-trace candidates: call 1 removes intra-component and setup events and adds missed calls, call 2 orders the sequence | `C3_dynamic_only/<scenario>/interactions.json` + `source_snippet.txt` | ❌ | ✅ |
| **C9** | `run_c9_llm_c4.py` | Two-prompt LLM chain seeded with C4 guided-trace candidates: call 1 removes setup-phase FPs and adds missed calls, call 2 orders the sequence | `C4_guided_only/<scenario>/interactions.json` + `source_snippet.txt` | ❌ | ✅ |

## Known Blind Spots

| Condition | Over-generates (FP risk) | Under-generates (FN risk) |
|---|---|---|
| C1 | Hallucinated calls; wrong multiplicity | Missed indirect dispatch |
| C2 | Static over-approximation (dead code paths) | Indirect dispatch (`std::function`, threads) |
| C3 | Setup-phase boilerplate (e.g. `Aggregator.add`) | — |
| C4 | Setup-phase boilerplate (instrumentation sites fire in setup; no filter to exclude them) | — |
| C5 | — | — |
| C6 | — | — |
| C7 | LLM may hallucinate additions; accepts static FPs it can't disprove | LLM may drop correct static edges it considers unlikely |
| C8 | LLM may retain some FPs from the noisy C3 input | — |
| C9 | — | LLM may incorrectly classify a real interaction as setup-phase |

## Ground Truth

GT is derived by `derive_gt_arch.py` using:
1. `trace_slice.txt` filtered by component-level `REACHABILITY` (from excalidraw diagrams)
2. `SCENARIO_ENTRY` entry-point scope filter (excludes setup-phase boilerplate)

The derivation is Neo4j-free and directly traceable to the hand-drawn Excalidraw reference diagrams.
See [`experiments/scenarios/gt_derivation_arch.md`](../../scenarios/gt_derivation_arch.md) for full methodology.