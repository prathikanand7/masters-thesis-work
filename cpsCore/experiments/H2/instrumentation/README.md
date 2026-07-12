# H2 Instrumentation Traces

One subfolder per scenario, containing:

| File | Description |
|---|---|
| `full_trace.txt` | All events from running the scenario with full instrumentation (no filter) |
| `guided_trace.txt` | Events after applying dependence-based slicing to scenario-relevant components |

## How to populate these

**Full instrumentation:**  
Run the CPSCore test suite (or scenario harness) with all `TRACE_FUNCTION_SCOPE` macros
active. Copy/filter the relevant rows from `../../runtime_traces.txt` using the scenario
component set (no function restriction).

**Guided instrumentation:**  
Apply your H2/RQ3 slicing mechanism to restrict instrumentation to the scenario's
entry-point component and its transitive dependents only.  
The resulting trace should be a strict subset of the full trace.

## Status

| Scenario | full_trace.txt | guided_trace.txt |
|----------|:---:|:---:|
| S1 | ✗ | ✗ |
| S2 | ✗ | ✗ |
| S3 | ✗ | ✗ |
