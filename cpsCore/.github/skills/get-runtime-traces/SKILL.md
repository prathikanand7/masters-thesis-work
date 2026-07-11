````skill
---
name: get-runtime-traces
description: Neo4j-driven instrumentation and runtime trace collection workflow with mapping generation, code instrumentation, and trace log export.
user-invocable: true
---

# get-runtime-traces

## Overview

This agent skill provides an end-to-end, Neo4j-driven instrumentation workflow:

1. Extract instrumentation targets from the Neo4j code graph.
2. Generate a reusable instrumentation mapping CSV.
3. Apply `TRACE_FUNCTION_SCOPE` instrumentation automatically to mapped C++ functions.
4. Export runtime-style traces from Neo4j and optionally collect live runtime traces from program execution.

This skill standardizes an agnostic instrumentation approach for repeatable trace collection.

## When to use

- User wants instrumentation targets determined from graph relationships (instead of manual edits).
- User wants reproducible mapping-driven instrumentation updates.
- User wants both graph-derived trace logs and optional runtime stderr traces.

## Scripts

- `.github/skills/get-runtime-traces/scripts/generate_instrumentation_mapping.py`
- `.github/skills/get-runtime-traces/scripts/apply_instrumentation_from_mapping.py`
- `.github/skills/get-runtime-traces/scripts/get_runtime_traces.py`
- `.github/skills/get-runtime-traces/scripts/neo4j_instrument_and_collect.py`

## Query source of truth

- Mapping generation reads Cypher directly from `.github/skills/get-runtime-traces/cypher_query.txt`.
- To change instrumentation target selection, edit that query file.
- The mapping generator expects the query to return these columns:
	- `callerFile`
	- `callerComponent`
	- `callerFunctionQualified`

## Output files

- `.github/skills/get-runtime-traces/instrumentation_mapping.csv`
- `.github/skills/get-runtime-traces/cypher_query.txt`
- `runtime_traces.txt`
- `runtime_traces_hybrid.txt` (only when a runtime trace command is provided)

## Execution

Run from workspace root:

```bash
python .github/skills/get-runtime-traces/scripts/neo4j_instrument_and_collect.py
```

Optional runtime trace collection (stderr capture from a runnable target):

```bash
python .github/skills/get-runtime-traces/scripts/neo4j_instrument_and_collect.py --trace-command "wsl -d Ubuntu -- bash -lc 'cd /mnt/c/Users/prathikak/Documents/cpsCore && ./bld/wsl-release/tests/tests'"
```

## Notes

- Neo4j credentials are loaded from repository `.env`.
- Instrumentation uses `TRACE_FUNCTION_SCOPE` from `include/cpsCore/Utilities/Runtime/Instrumentation.hpp`.
- The mapping file is intended to be committed/iterated, enabling deterministic instrumentation updates.
````