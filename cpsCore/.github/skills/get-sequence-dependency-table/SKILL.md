````skill
---
name: get-sequence-dependency-table
description: Retrieve an ordered call-dependency table from the Neo4j code graph by executing a read-only Cypher query over CppCalls edges and write the result to a CSV file.
user-invocable: true
---

# get-sequence-dependency-table

## Overview

This agent skill inspects the connected Neo4j code graph and generates a **sequence dependency table** in CSV format: one row per static `CppCalls` edge, with the caller's and callee's file paths standing in for components.

This is the **static ground truth** call table — it comes from the property graph via Cypher, not from any runtime trace. It is consumed by `run_c2_static_only.py` (H1's static-only condition) and by `draw-sysml-sequence-model` and similar sequence-model generators, which map file paths to component names downstream.

The skill is read-only and does not modify the database.

## When to use

- User wants an ordered call-dependency table derived from the static code graph.
- User wants static sequence-modeling input from the connected Neo4j database.
- User wants every `CppCalls` edge in the graph flattened into a CSV, one row per edge.

## Output files

- `sequence_dependency_table.csv` at the repository root
- `.github/skills/get-sequence-dependency-table/cypher_query.txt` containing the Cypher query executed by this skill

## CSV format

The CSV file uses these columns:

- `Sequence` — a 1-based row counter (extraction order, not execution order)
- `EventName` — the callee's bare function/symbol name
- `ClientComponent` — the file path of the caller (declaration or definition)
- `ClientFunction` — the caller's bare function/symbol name
- `ServerComponent` — the file path of the callee
- `ServerFunction` — the callee's bare function/symbol name (same as `EventName`)
- `RelationshipType` — always `Command` (a static call, not a reply)
- `EventTimestamp` — a synthetic, strictly-increasing per-row timestamp kept only for
  schema compatibility with trace-derived CSVs; it does **not** represent a real
  captured execution time, since no code actually ran to produce this table

## Semantics

- Each row represents one `CppCalls` edge in the property graph — no execution ever happens.
- Node ids in the graph are composite strings of the form
  `cpp_funcdec//include/cpsCore/Aggregation/Aggregator.h/Aggregator.getAll`
  (kind, then file path, then qualified symbol). The skill strips the kind prefix and
  trailing symbol segment to recover the bare file path for `ClientComponent` /
  `ServerComponent`.
- No component-name mapping or scenario filtering happens here — file paths are
  written as-is. Downstream consumers (e.g. `run_c2_static_only.py`'s
  `path_to_component()`) map paths to component names and filter to a scenario's
  component set.
- Duplicate edges are not de-duplicated by this skill; `MATCH ... RETURN DISTINCT`
  is intentionally not used, so multiple identical static edges collapse only if
  Neo4j itself stores a single relationship for them.

## Execution

1. Load Neo4j connection settings from the repository `.env` file.
2. Run the read-only Cypher query in `cypher_query.txt` against the connected Neo4j database.
3. For each `CppCalls` edge returned, extract the caller/callee file paths and bare symbol names.
4. Write one row per edge to `sequence_dependency_table.csv`, numbered by extraction order.
5. Write the Cypher query used by this skill to `.github/skills/get-sequence-dependency-table/cypher_query.txt`.

## Example

A row such as:

- `EventName = getAll`
- `ClientComponent = /src/Synchronization/SimpleRunner.cpp`
- `ClientFunction = runStage`
- `ServerComponent = /include/cpsCore/Aggregation/Aggregator.h`
- `ServerFunction = getAll`

means `SimpleRunner.cpp`'s `runStage` statically calls `Aggregator.h`'s `getAll` —
a real, source-confirmed call site, independent of whether any test ever exercises it.
````
