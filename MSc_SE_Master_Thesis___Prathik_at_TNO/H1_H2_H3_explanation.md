# H1, H2, H3 Experiments — Detailed Explanation

*Companion notes summarizing the hybrid static + trace analysis pipeline, the three experiments (H1, H2, H3), the formulas used, their basis, and how they support the thesis research questions (RQ1–RQ2).*

---

## The Overall Project: Hybrid Static + Trace Analysis of CPSCore

### What We Did

The thesis developed a **Graph-based Design Intelligence (GDI)** pipeline that automatically reconstructs **SysML v2 Interaction Models** (sequence diagrams) from C++ source code by combining two complementary sources of evidence:

1. **Static analysis** — extracts all *possible* function call relationships from source code (over-approximation: captures everything, including paths never executed in a given scenario)
2. **Runtime tracing** — captures *actual* function calls during test execution (under-approximation: only captures what was instrumented and exercised)

The combination of both produces models that are both **scenario-specific** (from traces) and **complete** (from static analysis filling in gaps the trace missed). The two sources are kept in separate artefacts (the static graph and the trace-derived sequence table) and combined only as a set union of their interaction edges at evaluation time — they are **not** merged into one graph.

### The Target System: CPSCore

CPSCore is an open-source modular C++ framework for cyber-physical systems (~13,000 LOC across 154 files) with 5 modules: **Aggregation**, **Configuration**, **Synchronization**, **Logging**, and **Utilities**. It uses event-driven pub/sub via `boost::signals2` and Redis, making many interactions invisible to raw static call-graph extraction.

**Key structural property:** CPSCore uses template-based static polymorphism extensively (~470 template occurrences) and declares only 32 virtual method signatures, all residing within a single module (Utilities: `INetworkLayer`, `IScheduler`, etc.) or at configuration boundaries. **No cross-module call is dispatched through a virtual table** — inter-module calls resolve statically through concrete class references or `boost::signals2` connections. This means the static call graph is reachability-complete with respect to the trace on the found-in-the-wild scenarios, which directly explains why C4 = C2 on the happy-path scenarios (S1–S3) in the H1 results (the constructed S4 deliberately breaks this, giving C4 > C2).

### Pipeline Stages (How We Did It)

The pipeline is implemented as **12 composable agent skills**, each invocable by natural-language query, backed by a **Neo4j property graph** as the shared knowledge store:

1. **Static Extraction** — Renaissance semantic extraction tool parses C++ source → populates Neo4j graph with 11 node labels and 11 relationship types, all derived from static analysis (runtime traces are **not** ingested into the graph)
2. **Schema Introspection** — dynamically reads graph schema so downstream skills are codebase-agnostic
3. **Interface Dependency Table** — aggregates all relationship types into a compact structural CSV
4. **Sequence Dependency Table** — projects `CppCalls` edges into an ordered sequence table with synthetic timestamps (yielded **2,574 ordered interactions** across **121 components**)
5. **Runtime Instrumentation** — `csp_matcher` (a Clang LibTooling-based tool developed in this thesis) inserts trace probes using AST-level pattern matching
6. **Trace Collection** — runs CPSCore test suite with probes → produces **27 runtime trace events** covering 26 unique interaction pairs
7. **Evidence Combination** — set union of the static edge set (`CppCalls`, queried from the graph) and the trace-derived edge set (from the sequence table CSV), tagged by provenance. This is a set operation over two separate artefacts computed at evaluation time, **not** a merge into Neo4j
8. **Scenario Scoping** — scope-constrained plain Cypher query: retains only edges where caller belongs to the scenario's primary component and callee belongs to a declared participant; the same component filter is applied to the trace-derived sequence table
9. **SysML v2 / Mermaid Generation** — projects the scenario-scoped table into textual notation

### The Key Idea: Combining Evidence and Scenario Scoping

The combined, scenario-scoped edge set:

$$E_\sigma = \{ e \in E_s \cup E_t \mid \text{src}(e) \in \sigma.\text{primary} \land \text{tgt}(e) \in \sigma.\text{targets} \}$$

where $E_s$ is the static interaction edge set (from the `CppCalls` query) and $E_t$ is the trace-derived interaction edge set (from the sequence table). The union $E_s \cup E_t$ is a set operation over two separate artefacts, not a graph merge. The scope constraint is a simple edge filter (linear in $|E|$) that operates identically over both sources because both carry `ClientComponent` and `ServerComponent` metadata.

---

## Research Questions

| RQ | Question | Answered by |
|---|---|---|
| **RQ1** | How does combining static analysis and incomplete runtime traces improve reconstruction accuracy and completeness? | **H1 experiment** |
| **RQ2** | How can scenario-scoped querying of the static call graph focus reconstruction on only scenario-relevant behaviour? | **H2 experiment** |
| *(downstream)* | Do reconstructed models improve agent task performance? | **H3 experiment** |
| *(downstream)* | Do reconstructed models improve agent task performance? | **H3 experiment** |

---

## H1 — Static + Dynamic Evidence Improves Reconstruction

### What We Did

Compared **5 conditions** across **4 scenarios** (3 happy-path + 1 constructed dual-gap):

| Condition | Evidence |
|---|---|
| C1 | LLM-only (no code context) |
| C2 | Static graph only |
| C3 | Runtime traces only |
| C4 | Static ∪ Dynamic (union) |
| C5 | Full pipeline (C4 + agent synthesis to prune FPs) |

### The Scenarios

- **S1–S3**: Happy-path scenarios occurring naturally in CPSCore (aggregation chain, config mapping, multi-component runner)
- **S4**: *Constructed* dual-gap scenario — a `boost::signals2` publish/subscribe bridge between `StageEventBridge` (Synchronization) and `StageEventListener` (Aggregation). Each single-source condition is blind to a *different* edge: static (C2) sees `stream` but not `onStageEvent` (the slot connection is established via `connect()` at runtime and has no static call expression); dynamic (C3) sees `onStageEvent` but not `stream` (a `LogLevel::NONE` idiom makes `CPSLOG_ERROR` a runtime no-op). Only the union (C4) recovers both.

S4 was added *after* S1–S3 to isolate the one condition under which combining static and dynamic evidence is strictly additive rather than merely protective. It is reported as its own stratum (not blended into S1–S3) because it is constructed rather than found-in-the-wild. **There is no S5.**

### The Formulas (Precision / Recall / F1)

$$P = \frac{|\text{gen} \cap \text{ref}|}{|\text{gen}|}, \quad R = \frac{|\text{gen} \cap \text{ref}|}{|\text{ref}|}, \quad F_1 = \frac{2PR}{P + R}$$

Where:
- $\text{gen}$ = set of interaction edges produced by a condition
- $\text{ref}$ = manually source-read reference edge set (ground truth authored *before* any condition was scored)

**Aggregation**: Macro-F1 (mean of per-scenario F1 scores, weighting each scenario equally) rather than micro-F1, to prevent large scenarios from dominating.

### Basis of the Formulas

Standard information-retrieval metrics applied to *interaction edges* (unique ordered ⟨sender, receiver⟩ pairs). This is the natural way to measure whether a reconstructed model correctly identifies the true cross-component function calls.

### Key Results (Stratified: macro-averaged P / R / F1)

Reported four-scenario set (S1–S4). The constructed scenario S4 is kept as its own stratum rather than folded into the happy-path average.

| Condition | Happy-path (S1–S3) P/R/F1 | Constructed (S4) P/R/F1 | Overall (S1–S4) P/R/F1 |
|---|:---:|:---:|:---:|
| C1 LLM-only | 0.000 / 0.000 / 0.000 | 0.500 / 0.500 / 0.500 | 0.125 / 0.125 / 0.125 |
| C2 Static-only | 0.867 / **1.000** / 0.917 | 1.000 / 0.500 / 0.667 | 0.900 / 0.875 / 0.854 |
| C3 Dynamic-only | **1.000** / **1.000** / **1.000** | 1.000 / 0.500 / 0.667 | **1.000** / 0.875 / 0.917 |
| C4 Static+Dynamic | 0.867 / **1.000** / 0.917 | 1.000 / **1.000** / **1.000** | 0.900 / **1.000** / 0.938 |
| C5 Full pipeline | 0.917 / **1.000** / 0.952 | 1.000 / **1.000** / **1.000** | 0.938 / **1.000** / **0.964** |

Per-scenario F1 detail: on S4, **C4 (1.000) strictly exceeds both C2 (0.667) and C3 (0.667)** — the only scenario where combining sources is additive. C5 matches C4's perfect recall everywhere and posts the highest overall F1 (**0.964**) of any condition.

### Why C4 = C2 on S1–S3 (mechanistic explanation)

On the three found-in-the-wild scenarios (S1–S3), CPSCore (~13 kLOC, 154 files) has **no cross-module virtual dispatch**. All 32 virtual declarations reside within a single module (Utilities: `INetworkLayer`, `IScheduler`, etc.) or at configuration boundaries (`IConfigurableObject`, `IRunnableObject`). Inter-module calls resolve statically through concrete class references or `boost::signals2` slot connections.

Consequence: on S1–S3, every interaction edge the trace discovers is already present in the static call graph. Formally:

$$\text{C3} \subseteq \text{C2} \;\text{(on S1–S3)} \;\Longrightarrow\; \text{C4} = \text{C2} \cup \text{C3} = \text{C2}$$

This is a **structural property of CPSCore on those scenarios**, not a pipeline flaw — and it is exactly why S4 was constructed. S4 introduces a runtime-established `connect()` boundary that static analysis cannot resolve, breaking the subset relation: there, C3 ⊄ C2 *and* C2 ⊄ C3, so **C4 > C2 and C4 > C3**. In any system with cross-module virtual dispatch, dynamic plugin loading, or reflection, this additive regime — not the S1–S3 redundant regime — is what materialises.

### Why C2/C4 precision ≠ 1.000

C2/C4 have happy-path macro-P = 0.867 (overall 0.900), not 1.000. The deficit is on S3, where the static graph includes a real Synchronization→Logging call (`flush`) that is a genuine source-level call site but originates from a function outside the S3 scenario scope (per-scenario S3 precision for C2 is 0.60). **Static analysis cannot scope to a single scenario without scenario-scoped querying** — this is the over-approximation problem C5 partially corrects (raising S3 precision to 0.75).

### Why C5 is the best condition (recall parity + partial precision fix)

C5 achieves **perfect recall (R = 1.000) on every one of the four scenarios**, matching C4 — it retains `CPSLogger::instance` on S1 and `stream` on S4 by reasoning over provenance-tagged evidence (each edge labelled with which source observed it). Its only imprecision is on S3, where the same "a suppressed single-source edge is usually real" reasoning that correctly recovers S4's fault-path edge is misapplied to `flush` (a real call, but out of S3's scope). Because C2's element list records source/target/interaction but **not the calling function**, "suppressed-but-in-scope" and "real-but-out-of-scope" are indistinguishable to the agent. Even so, C5 posts the **highest overall F1 of any condition (0.964)** — higher than C4's raw union (0.938) and C3's raw trace (0.917) — because it preserves C4's recall while partially fixing C4's S3 over-approximation (S3 precision 0.60 → 0.75). It is a net improvement over the combined union, not a trade against it.

### How H1 Supports RQ1

- **Combining sources is additive exactly where the sources are blind to different edges**: on S4, C4 (F1 = 1.000) strictly exceeds both C2 (0.667) and C3 (0.667). Static misses the runtime `connect()` edge; dynamic misses the `LogLevel::NONE`-suppressed edge; the union recovers both.
- **Combining sources is protective (redundant) on S1–S3**: C4 = C2 there because C3 ⊆ C2, but C4 ≥ C3 always — the union guarantees a recall floor when traces are incomplete.
- **Agent synthesis (C5) improves on the raw union**: it preserves C4's perfect recall (R = 1.000 on every scenario) while partially correcting C4's S3 over-approximation, giving the highest overall F1 tested (0.964).
- **Value chain**: the union secures the recall floor and adds edges where sources disagree → provenance-aware synthesis then trims over-approximation for the best overall accuracy.

---

## H2 — Guided Instrumentation Improves Signal-to-Noise

### What We Did

Compared **full instrumentation** (probe every cross-component call site, capture entire test run) vs **guided instrumentation** (probe only the scenario-scoped call sites relevant to a specific scenario) on S1–S3.

### The Formulas

$$\text{NodeReduction} = 1 - \frac{|V(G_{\text{guided}})|}{|V(G_{\text{full}})|}, \quad \text{EdgeReduction} = 1 - \frac{|E(G_{\text{guided}})|}{|E(G_{\text{full}})|}$$

$$\text{Noise}(G) = \frac{|V(G) \setminus R|}{|V(G)|}, \quad \text{Coverage}(G) = \frac{|V(G) \cap R|}{|R|}$$

Where:
- $G_\text{full}$ / $G_\text{guided}$ = property-graph subsets from full/guided instrumentation
- $R$ = scenario-relevant reference node set (from H1 reference diagrams)

### Basis

- **Noise** measures the proportion of retained elements that are irrelevant (lower is better)
- **Coverage** measures the proportion of relevant elements actually retained (higher is better, 1.000 = nothing lost)
- Together they prevent the failure mode where noise is reduced by discarding relevant nodes along with irrelevant ones

### Key Results

| Metric | Full | Guided | Improvement |
|---|:---:|:---:|:---:|
| Nodes | 6.0 | 3.0 | −50% |
| Edges | 9.0 | 2.7 | −70% |
| Coverage | 1.000 | 1.000 | 0% loss |
| Noise | 0.704 | 0.000 | −100% |

Plus **blinded expert ratings** (6 raters, A/B randomised — extended from
an initial 2-rater round to strengthen the sample):

| Dimension | Full (mean) | Guided (mean) |
|---|:---:|:---:|
| Accuracy | 2.39 | 4.61 |
| Readability | 2.44 | 4.89 |
| Usefulness | 2.94 | 4.00 |

Across all 6×9=54 rater×scenario×dimension comparisons: guided rated
strictly higher in **47**, tied in **6**, and rated strictly lower in
exactly **1**. Accuracy/readability: guided never rated below full by any
rater on any scenario (34/36 strictly higher, 2 ties). Usefulness:
unanimous in favor of guided on S1/S3, but a genuine 3-way split on S2 (3
raters tied, 1 rated full higher, 2 preferred guided) — all four groups
independently cited the same cause: collapsing 7 repeated
Configuration→Logging property-read calls into 1 edge loses a count some
raters consider useful for debugging.

### How H2 Supports RQ2

H2 demonstrates that applying the scenario scope *before* instrumentation (guided) rather than filtering *after* (full) produces diagrams that are:
- Structurally smaller (50–70% reduction)
- Zero noise while maintaining full coverage
- Judged more accurate and readable by domain experts — confirmed by a 6-rater blinded panel, not just the original 2 raters

This answers RQ2: scenario-scoped querying effectively constrains both trace events and static interactions to only scenario-relevant behaviour.

---

## H3 — Reconstructed Models Improve Agent Task Performance

### What We Did

Tested whether giving an LLM agent the pipeline's output (C5 interaction list) helps it perform a Scenario Comprehension task, relative to source code and/or execution traces. A single **holistic experiment with five conditions** was run across the same four scenarios (S1–S4), isolating source, trace, and the reconstructed diagram both alone and in combination.

### Metrics

- **Component recall**: fraction of ground-truth components identified
- **Interaction recall**: fraction of ground-truth interactions identified
- **Completeness** (1–5): rubric-scored (blind-rated for the three reused conditions; the two newly collected conditions — source only, diagram only — rated non-blind by the same rater, disclosed as a limitation)

### Key Results

| Condition | Component recall | Interaction recall | Completeness (1–5) |
|---|:---:|:---:|:---:|
| Source only | 0.917 | 0.800 | 4.25 |
| Trace only | 0.917 | 0.900 | 4.25 |
| **Diagram only** | **1.000** | **1.000** | **5.00** |
| Source + Trace | 0.917 | 0.900 | 4.25 |
| **Source + Trace + Diagram** | **1.000** | **1.000** | **5.00** |

**The standout result: `Diagram only` and `Source+Trace+Diagram` are identical and perfect on every measure.** With *no* source and *no* trace — only the C5 interaction list — the agent reaches perfect component recall (12/12), perfect interaction recall (10/10), and perfect completeness (5.00) on every scenario, including the constructed S4. Adding source and traces on top neither helps nor hurts, because the diagram alone already saturates every metric.

`Source only` has the weakest interaction recall (0.800): source-grounded narration foregrounds the main control-flow path and omits secondary log-only branches (`RAIILogStream.stream`) on S1 and S4, even though the snippets contain explicit comments identifying them. `Trace only` avoids this on S1 (it observes the log event firing) but repeats it on S4, where the trace never captures the `LogLevel::NONE`-suppressed edge. `Diagram only` avoids it everywhere, because C5 surfaces the interaction as an explicit labelled edge regardless of whether it was exercised at runtime.

### How H3 Supports the Thesis

H3 shows the reconstructed diagram is not merely a helpful supplement but can be a **sufficient** basis for scenario comprehension — it matches the full-context condition exactly while carrying the combined static+dynamic evidence (the set union of the two edge sets) that raw source or traces alone under-report, most visibly on the constructed fault-path scenario S4 where runtime evidence is suppressed.

---

## Summary: How Everything Connects

```
Static Analysis (Renaissance → Neo4j)
         │
         ├──► Property Graph (static call graph only)
         │         │
         │         ├──► Sequence Dep. Table (2,574 interactions)
         │         │
Runtime Tracing (csp_matcher probes → 27 trace events)
         │         │
         └────┬────┘
              │
    Evidence Combination (C4 = static ∪ dynamic; set union of two
                          separate edge sets at evaluation time)
              │
    Scenario Scoping (scope-constrained plain Cypher query;
                      same filter applied to the trace table)
              │
         Agent Synthesis (C5 = combined + LLM pruning)
              │
         SysML v2 / Mermaid Diagrams
              │
    ┌─────────┼──────────┐
    H1        H2         H3
 (accuracy) (focus)   (utility)
```

The thesis sentence:
> "Combining static and dynamic evidence (as a set union at evaluation time) is strictly additive exactly where the two sources are blind to different edges (on the constructed scenario S4, C4 F1 1.000 vs C2 0.667 and C3 0.667), and redundant elsewhere. Provenance-aware agent synthesis then preserves that perfect recall while partially correcting static over-approximation, for the highest overall reconstruction accuracy of any condition tested (C5 macro-F1 0.964). Guided instrumentation reduces diagram noise by 100% while preserving full coverage, confirmed by a blinded six-rater expert panel; and the reconstructed diagram alone is a sufficient basis for scenario comprehension (perfect component and interaction recall)."
