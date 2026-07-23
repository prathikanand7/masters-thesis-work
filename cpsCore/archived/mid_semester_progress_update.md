# Mid-Semester Progress Update
## Hybrid Static–Trace Analysis for Synthesizing Interaction Diagrams in Event-Driven Systems

**Student:** Prathik Anand Krishnan
**Academic Supervisor:** Dr. L. Thomas van Binsbergen
**Host Supervisor:** Rosilde Corvino, TNO-ESI
**Host Organization:** TNO – PHILLIPS, Eindhoven, High Tech Campus 25

---

## Slide 1 — Title

**Mid-Semester Progress Update**
Hybrid Static–Trace Analysis for Synthesizing Interaction Diagrams in Event-Driven Systems

Student: Prathik Anand Krishnan
Academic Supervisor: Dr. L. Thomas van Binsbergen
Host Supervisor: Rosilde Corvino, TNO-ESI

---

## Slide 2 — Recap: Original 5-Stage Methodology

*(Reproduce the original pipeline diagram from the proposal)*

```
Scenario       Static         Runtime Trace    Hybrid           SysML v2
Definition  →  Analysis    →  Collection    →  Reconstruction → Interaction
                                                                 Diagram
```

**Planned milestone by mid-semester:** Complete static analysis (Weeks 4–7) and begin trace collection & mapping (Weeks 7–10)

**Actual position today:** Static analysis complete + SysML v2 output partially achieved ahead of schedule. Trace collection in active progress.

---

## Slide 3 — Progress Against Original Timeline

| Phase | Planned | Status |
|---|---|---|
| Weeks 1–3: Literature & Scoping | Define problem scope | Done |
| Weeks 4–7: Static Analysis | Dependency-based code slicing | Done (evolved — see next slide) |
| Weeks 7–10: Trace Collection & Mapping | Timestamped runtime events | **In progress** |
| Weeks 10–13: Hybrid Reconstruction | Trace-to-code alignment | Not started |
| Weeks 13–17: Modeling & Evaluation | SysML v2 generation & comparison | Partially ahead — structural SysML already done |
| Weeks 17–21: Writing | — | Planned |

**Overall: On track. One significant architectural evolution in the static analysis approach.**

---

## Slide 4 — What Changed: The Static Analysis Layer Evolved

**Originally proposed:** Scenario-specific dependency-based code slicing directly on C++ source

**What was built instead:**

```
C++ Source Code
      │
      ▼
Neo4j Property Graph (via Renaissance tool)
  - Typed Nodes: Components, Functions, Namespaces
  - Typed Edges: CALLS, INCLUDES, INHERITS, USES
      │
      ▼
LLM Agent Skill Pipeline (Cypher-based queries)
  - Natural language → graph queries
  - Dependency and sequence tables as intermediate output
```

**Why this is better:** The graph representation directly addresses RQ2 ("What intermediate property graph can integrate static call graphs and runtime events?") — it is the unified IR that both static slices and runtime trace events will be merged into. The agent skill layer also makes the pipeline queryable without hardcoding scenario-specific logic.

---

## Slide 5 — What Was Built: Agent Skill Pipeline

Nine modular, composable LLM-invocable skills:

| Skill | Maps to Proposal Stage |
|---|---|
| `get-neo4j-schema` | Static Analysis — graph introspection |
| `text-to-cypher` + `get-cypher` | Static Analysis — scenario-specific query |
| `get-interface-dependency-table` | Static Analysis — dependency aggregation |
| `get-sequence-dependency-table` | Static Analysis — call chain extraction |
| `draw-structural-mermaid` | Modeling — structural visualization |
| `draw-sequential-mermaid-general` | Modeling — behavioral visualization |
| `draw-sysml-structural-model` | SysML v2 Output — BDD/IBD |
| `draw-sysml-sequence-model` | SysML v2 Output — Sequence Diagram |
| `get-runtime-traces` | Trace Collection — in progress |

**Key design property:** Each skill is independently testable. Scenario focus is expressed as a natural language query — this directly enables RQ1 (dependency-based slicing to filter to scenario-relevant behaviour).

---

## Slide 6 — What Was Produced: SysML v2 Artifacts (Ahead of Schedule)

Two SysML v2 models generated from the static graph — **verified manually**:

**Structural Model** (`sysml_structural_model.sysml`)
- `part def` for each C++ component
- `port def` for each interface/dependency type (CppCalls, CppInherits, Include, etc.)
- `connect` statements mapping provider → consumer relationships
- Ready for import into SysON or Jupyter SysML v2 kernel

**Sequence Model** (`sysml_sequence_model.sysml`)
- Runtime interaction flows derived from static call chains
- Represents the static-only baseline interaction diagram (for the comparison from the proposal)

**These form the "Static-Only Approach" baseline** in the planned 3-way evaluation (Trace-Only vs. Static-Only vs. Hybrid).

---

## Slide 7 — Current Work: Runtime Trace Collection (Weeks 7–10)

**Goal:** Capture timestamped runtime events from the `cpsCore` system to enrich the static graph

**Work in progress:**

1. **Generalised Trace Collector** — converting output format to structured `.txt` logs (portable, tool-agnostic)
2. **SysOn Docker Integration** — containerised SysON instance for live SysML visualization and validation
3. **ClangSharp Static Parser** — independent C++17-compatible extractor for benchmarking:
   - Produces GraphML from C++ AST via libclang
   - Will be compared against TNO in-house parser's GraphML as ground truth
   - Validates extraction accuracy of the Neo4j graph before traces are merged in

---

## Slide 8 — Recalibrated Roadmap

```
                [NOW]
                  │
    ┌─────────────┼─────────────┐
    │             │             │
Trace        SysOn Docker  ClangSharp
Collector    Integration  Validation
(format)     (visualize)  (benchmark)
    │
    ▼
Trace Ingestion into Neo4j Graph
(timestamped events → new edge type)
    │
    ▼
Hybrid Reconstruction (Weeks 10–13)
- Trace-to-code alignment
- Static reachability on graph
- Missing interaction inference
    │
    ▼
Scenario-Specific SysML v2 Interaction Diagrams
    │
    ▼
3-Way Evaluation:
Trace-Only | Static-Only | Hybrid
```

**No phase has been dropped. The Neo4j graph is the unified IR that absorbs both static and dynamic data — this makes the hybrid reconstruction cleaner than originally scoped.**

---

## Slide 9 — Research Questions: Where Each Stands

| RQ | Question | Status |
|---|---|---|
| RQ1 | How can dependency-based slicing filter trace events to scenario-relevant behaviour? | Structurally answered via Neo4j graph + agent skill query layer. Needs trace events ingested to fully validate. |
| RQ2 | What intermediate property graph can integrate static call graphs and timestamped runtime events? | **Answered:** Neo4j typed property graph with edge-type separation (structural vs. call vs. runtime). |
| RQ3 | How can combining static + incomplete traces improve accuracy and completeness? | Baseline (static-only) established. Hybrid evaluation planned for Weeks 10–13. |

---

## Slide 10 — Challenges & How They Were Addressed

| Challenge | Solution |
|---|---|
| C++ is context-sensitive — regex/simple parsers fail | Used Renaissance tool → Neo4j for semantic-level extraction; ClangSharp (libclang) for validation |
| Thousands of dependencies crash SysML toolchains | Implemented identifier quoting and relationship deduplication in generation layer |
| Hardcoded scenario slicing is brittle | Agent skill architecture allows scenario definition as a natural language query |
| Traces alone are incomplete (per proposal) | Static reachability in graph will fill unobserved interactions — this is the core hybrid contribution |

---

## Slide 11 — Summary

**What was proposed:** Hybrid static + trace pipeline → scenario-specific SysML v2 interaction diagrams

**What has been delivered at mid-semester:**
- Working Neo4j knowledge graph of `cpsCore` (static layer — complete)
- Modular agent skill pipeline with 9 composable skills (tooling — complete)
- SysML v2 structural + sequence models from static analysis (partial output — ahead of schedule)
- Static-only baseline established for 3-way evaluation

**What is being built now:**
- Runtime trace collector + SysOn visualization + ClangSharp validation

**What remains:**
- Hybrid reconstruction, 3-way evaluation, writing
