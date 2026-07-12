# H1 Reference Diagrams

One subfolder per scenario.  Each subfolder must contain:

| File | Description |
|---|---|
| `elements.json` | Machine-readable list of diagram elements used by `scoring/score.py` |
| `structural.sysml` | Ground-truth structural diagram (SysML v2 text) |
| `sequence.sysml` | Ground-truth sequence diagram (SysML v2 text) |

## elements.json schema

```json
[
  {
    "source": "ComponentA",
    "target": "ComponentB",
    "interaction": "MethodName.operation"
  }
]
```

`source` and `target` are CPSCore module names (e.g. `Synchronization`, `Aggregation`).  
`interaction` is the function/method call name as it appears in the trace header
(`ClientFunction` / `EventName` column).

## Construction procedure

Ground truth was derived by **source-code reading**, not by inspecting traces.
The exact steps followed:

1. Identified the primary-driver component for each scenario
   (Synchronization for S1/S3; Configuration for S2).
2. Read the relevant `.cpp` files directly:
   - S1: `src/Synchronization/{AggregatableRunner,SimpleRunner,SynchronizedRunner,SynchronizedRunnerMaster}.cpp`
   - S2: `src/Configuration/PropertyMapper.cpp`
   - S3: `src/Synchronization/{SimpleRunner,SynchronizedRunnerMaster}.cpp`
3. Recorded every cross-component call **from the primary component** to any
   other scenario component, including both happy-path and error-path calls
   (e.g. `CPSLOG_ERROR` in `SynchronizedRunnerMaster.runStage` on timeout).
4. Normalized interaction names to bare function names (`Aggregator.getAll` → `getAll`).
5. **Validated** by checking that all recorded interactions appear in
   `runtime_traces.txt` — confirming the test suite exercises them.
   For these 3 scenarios, source-derived = trace-observed (complete coverage).
   Error-path interactions not in traces (`CPSLOG_WARN` on shm exception,
   `CPSLOG_ERROR` on stage timeout) collapse to the same `stream` triple
   already present, so the reference set is unchanged.

**Independence guarantee:** the reference was constructed before running any
pipeline condition. The traces were used only for validation, not derivation.

**Known limitation:** because test coverage is complete for S1/S2/S3, C3
(dynamic-only) trivially scores 1.0. The constructed scenario S4 (see
`H1/reference_diagrams/S4/` and `H1/README.md`) breaks this by combining a
suppressed fault-path log call with a static-blind indirect dispatch.

## Status

| Scenario | elements.json | structural.sysml | sequence.sysml | Validated |
|----------|:---:|:---:|:---:|:---:|
| S1 | ✓ | ✓ | ✓ | source-confirmed |
| S2 | ✓ | ✓ | ✓ | source-confirmed |
| S3 | ✓ | ✓ | ✓ | source-confirmed |
| S4 | ✓ | ✓ | ✓ | source-confirmed (constructed) |
