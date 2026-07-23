# cpsCore — Agent Instructions

This workspace has **two distinct layers**: a C++ library (`src/`, `include/`, `tests/`) and a
research experiment suite (`experiments/`) that studies LLM-aided architecture reconstruction of
that library. Read both sections before acting.

---

## C++ Library

### Build
```bash
# Requires: Eigen3, Boost (system), submodules (cpp_redis, Catch2)
git submodule update --init --recursive
mkdir -p bld/release && cd bld/release
cmake -DCMAKE_BUILD_TYPE=Release ../../
make -j$(nproc)
```

### Test
```bash
cd bld/release && ctest --output-on-failure
# Or run a single test binary directly, e.g.:
./tests/Synchronization/RunnerTest
```

### Component map
| Directory | Component | Role |
|-----------|-----------|------|
| `src/Aggregation` + `include/cpsCore/Aggregation` | Aggregation | Object graph / observer wiring |
| `src/Configuration` | Configuration | YAML-driven `PropertyMapper` |
| `src/Framework` | Framework | `PluginHelper`, `FrameworkAPI` |
| `src/Logging` | Logging | `CPSLogger` singleton |
| `src/Synchronization` | Synchronization | `RunStage` lifecycle, runners |
| `src/Utilities` | Utilities | Scheduler, IPC, IDC, DataPresentation |

See [README.md](README.md) for component details and reference paper.

### Conventions
- Classes use `AggregatableObject<Params>` mixin + `typeId` static for plugin registry.
- `ConfigurableObject<Params>` uses `PropertyMapper` (`pm.add(key, field)`) for config.
- `RunStage` lifecycle is always `INIT → NORMAL → FINAL`; runners iterate in that order.
- No C++ namespaces — component identity comes from the include path (`cpsCore/Aggregation/…`).
- Runtime instrumentation is injected via the `add-runtime-instrumentation` skill (see
  [`.github/skills/add-runtime-instrumentation/SKILL.md`](.github/skills/add-runtime-instrumentation/SKILL.md)).

---

## Research Experiments

### Shared assets — never duplicate
All three hypotheses use the **same** scenario set, the same Neo4j graph, and the same trace files
already in this workspace. Do **not** create separate clones.

| Shared asset | Location |
|---|---|
| Scenario definitions (authoritative) | [`experiments/scenarios/scenarios.md`](experiments/scenarios/scenarios.md) |
| Runtime traces (full) | [`runtime_traces.txt`](runtime_traces.txt) |
| Hybrid traces | [`runtime_traces_hybrid.txt`](runtime_traces_hybrid.txt) |
| Neo4j schema | [`graph_schema.txt`](graph_schema.txt) |
| Static dependency tables | [`interface_dependency_table.csv`](interface_dependency_table.csv), [`sequence_dependency_table.csv`](sequence_dependency_table.csv) |

### Scenarios (S1a–S3)

| ID | Name | Components | Path type |
|----|------|-----------|----------|
| S1a | Synchronized Runner Test (happy path) | Synchronization, Aggregation, Logging | happy |
| S1b | Synchronized Runner Timeout (failure path) | Synchronization, Aggregation, Logging | failure |
| S2 | Configuration property mapping | Configuration, Logging | happy |
| S3 | Multi-component runner orchestration | Synchronization, Aggregation, Utilities, Logging | happy |

S1a and S1b share entry-point functions (`SynchronizedRunner.runSynchronized`,
`SynchronizedRunnerMaster.runStage`) but exercise different execution paths. S1b is the
failure-path mirror of S1a: logging is suppressed at runtime so the timeout-warning interaction
is static-only visible (a deliberate coverage gap for C2 vs C3 comparison).
See [`experiments/scenarios/scenarios.md`](experiments/scenarios/scenarios.md) for full definitions.

### Hypotheses and blocking order

```
H1 (reference diagrams) → must complete first → gates H2 coverage + H3 ground truth
H2 (guided instrumentation)
H3 (agent task performance)
```

| Hypothesis | Claim | Key result |
|---|---|---|
| H1 | Guided instrumentation + Neo4j reachability filter achieves highest reconstruction accuracy | C5 & C6 macro F1 = 1.000/1.000; C5 ablations confirm both phases are necessary |
| H2 | Guided instrumentation reduces noise | Guided noise=0 vs full noise 0.56–0.89 across S1a–S3 |
| H3 | Reconstructed models improve agent task performance | Source+Trace+Diagram > Source+Trace |

### Conditions (H1)

| ID | Script | Input | Neo4j? | LLM? | Role |
|----|--------|-------|--------|------|----- |
| C1 | `run_c1_llm_only.py` | `source_snippet.txt` | No | Yes | LLM baseline |
| C2 | `run_c2_static_only.py` | Neo4j call graph | Runtime | No | Static baseline |
| C3 | `run_c3_dynamic_only.py` | `full_trace.txt` (unfiltered) | No | No | Dynamic baseline |
| C4 | `run_c4_guided_only.py` | `trace_slice.txt` (no scope filter) | Design-time only | No | C5 ablation: instrumentation |
| C5 | `run_c5_guided_reach.py` | `trace_slice.txt` + reachability | Design-time + Runtime | No | **Best condition — F1=1.000** |
| C6 | `run_c6_full_trace_reach_only.py` | `full_trace.txt` + reachability | Runtime | No | C5 ablation: filter alone sufficient |
| C7 | `run_c7_llm_c2.py` | C2 candidates + `source_snippet.txt` | No | Yes | LLM refines static candidates |
| C8 | `run_c8_llm_c3.py` | C3 candidates + `source_snippet.txt` | No | Yes | LLM denoises raw trace |
| C9 | `run_c9_llm_c4.py` | C4 candidates + `source_snippet.txt` | No | Yes | LLM refines guided trace |

### Running condition scripts (H1)
```bash
# Requires: pip install openai python-dotenv neo4j
# Azure credentials go in .env (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, etc.)

cd experiments/H1/conditions
python run_c1_llm_only.py --all          # LLM — requires Azure .env
python run_c2_static_only.py --all       # requires Neo4j at bolt://127.0.0.1:7688
python run_c3_dynamic_only.py --all
python run_c4_guided_only.py --all
python run_c5_guided_reach.py --all      # requires Neo4j
python run_c6_full_trace_reach_only.py --all  # requires Neo4j
python run_c7_llm_c2.py --all           # LLM — requires C2 output + Azure .env
python run_c8_llm_c3.py --all           # LLM — requires C3 output + Azure .env
python run_c9_llm_c4.py --all           # LLM — requires C4 output + Azure .env
# Output: conditions/CX_<label>/<scenario>/interactions.json
#                                        /sequence.json
```

### Scoring (H1)
```bash
cd experiments/H1/scoring
python evaluate_all.py   # re-runs C3–C6, scores all nine conditions, writes results.csv
python generate_md.py    # regenerates results.md from authoritative tables
```

### H2 instrumentation metrics
```bash
cd experiments/H2/metrics
python diagram_metrics.py --all
```

### H3 agent harness
```bash
cd experiments/H3/agent_conditions
python run_agent.py --condition A_no_diagrams --scenario S1
python run_agent_extra.py --condition C_source_only --scenario S1
```

### Utility helpers
- `experiments/H1/conditions/_utils.py` — shared `SCENARIOS`, `SCENARIO_COMPONENTS`,
  `path_to_component()`, `Element` type; import this instead of duplicating.
- `experiments/scenarios/extract_slices.py` — slice `runtime_traces.txt` per scenario.

---

## Pitfalls

- **Don't re-run C1/C7/C8/C9 carelessly** — those use the Azure OpenAI LLM and consume
  tokens; existing outputs in `C1_llm_only/`, `C7_llm_c2/`, `C8_llm_c3/`, `C9_llm_c4/`
  are the authoritative runs. C3–C6 are deterministic and safe to re-run.
- **Archived condition folders** — `C4_static_dynamic/`, `C5_intersection/` and related
  variants are from an earlier experiment design and are no longer scored. Do not confuse
  them with the current `C4_guided_only/` and `C5_guided_reach/`.
- **Submodules required** — `extern/cpp_redis` and `extern/Catch2` must be initialised
  (`git submodule update --init --recursive`) or the C++ build fails.
- **Azure .env** — The `.env` at repo root holds `AZURE_OPENAI_*` keys needed by all
  LLM condition scripts. Never commit it; it is already in `.gitignore`.
- **Active branch for refactoring:** `feature/refactor` — all new changes go here.
