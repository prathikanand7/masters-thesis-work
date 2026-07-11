---
description: "Sync add_tracing.txt with tracing_spec.csv. Use when tracing_spec.csv has changed and add_tracing.txt needs to be updated."
name: "Sync tracing rules from spec"
agent: "agent"
---

Sync [add_tracing.txt](../../examples/cpscore_tracing/add_tracing.txt) with the callee functions listed in [tracing_spec.csv](../../examples/cpscore_tracing/tracing_spec.csv).

## Steps

### 1 — Read the spec

Read `examples/cpscore_tracing/tracing_spec.csv`.

Each data row has 4 columns (comma-separated, quoted). The third column is the callee.
The callee field has the form `cpp_funcdef//path/ClassName.methodName` or `cpp_funcdec//path/ClassName.methodName`.
Extract the final segment after the last `/` — that is the logical callee name, e.g. `Aggregator.getAll`.

Collect the **unique** callee names from the entire file.

### 2 — Compare to existing rules

Read `examples/cpscore_tracing/add_tracing.txt`.

The file contains `find:/replace:` pairs. Each `replace:` line contains the callee label in the format
`[TRACE] ... ClassName.methodName, FolderName, ...`.

Identify which callees from step 1 are **not yet covered** by any rule.

### 3 — Skip callees that need no csp_matcher rule

The following callees are handled by other mechanisms and must NOT get a csp_matcher rule:

| Callee | Why skipped |
|---|---|
| `RAIILogStream.stream` | Covered by the CPSLogger.h macro patch in apply_tracing.ps1 |
| `CPSLogger.instance` | Always co-occurs with `CPSLogger.flush` or `CPSLogger.setLogLevel`; no standalone rule needed |

### 4 — For each uncovered callee, find the call pattern

For any callee not in the skip list and not yet in add_tracing.txt:

1. Search the cpsCore source tree (`C:\Code\CSP\cpsCore\src` and `include`) for actual call sites.
2. Read the relevant source files to understand the exact C++ call syntax.
3. Determine:
   - The `find:` pattern (C++ expression using `$hole` names matching the existing preamble holes or new ones).
   - Whether new hole declarations are needed in the apply_tracing.ps1 preamble.

### 5 — Known callee registry (use these patterns verbatim)

| Callee | find: pattern | Notes |
|---|---|---|
| `Aggregator.getAll` | `$agg.getAll<$T>()` | $agg=Aggregator, $T=IAggregatableObject |
| `CPSLogger.flush` | `CPSLogger::instance()->flush()` | no holes |
| `EnumMap.convert` | `EnumMap<RunStage>::convert($stage)` | $stage=RunStage; needs IRunnableObject.h + EnumMap.hpp in preamble |

For any callee **not** in this table, read the source to derive the pattern.

### 6 — Write new rules

For each uncovered callee (not in skip list), append to `add_tracing.txt` a `find:/replace:` pair following this exact template:

```
find:    <pattern>
replace: (std::fprintf(stderr, "[TRACE] %s, %s, %s, <ClassName.methodName>, <FolderName>, %s, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerFunc(__PRETTY_FUNCTION__).c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceCallerClass(__PRETTY_FUNCTION__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), <pattern>)
```

Where `<ClassName.methodName>` and `<FolderName>` match exactly the values in the callee column of the spec CSV.

### 7 — Update apply_tracing.ps1 preamble if needed

Read the `--pattern-preamble` argument in [apply_tracing.ps1](../../examples/cpscore_tracing/apply_tracing.ps1).

If any new rule requires a hole type not yet declared in the preamble (e.g. a new `static SomeType csp_hole_x = ...;` or a new `#include`), add it.

The preamble already declares:
- `#include <cpsCore/Logging/CPSLogger.h>`
- `#include <cpsCore/Aggregation/Aggregator.h>`
- `#include <cpsCore/Utilities/EnumMap.hpp>`
- `#include <cpsCore/Synchronization/IRunnableObject.h>`
- `static Aggregator csp_hole_agg;`
- `using csp_type_hole_T = IAggregatableObject;`
- `static RunStage csp_hole_stage = RunStage::INIT;`

### 8 — Report

Summarise:
- Callees newly added to add_tracing.txt
- Callees already covered (no change needed)
- Callees skipped (handled by macro patch or co-occurrence)
- Any preamble changes made
