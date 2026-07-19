```skill
---
name: add-runtime-instrumentation
description: Leverage the renaissance_clang DSL tool to apply automated runtime instrumentation and tracing to cpsCore source files using pattern matching and code transformation rules.
user-invocable: true
---

# add-runtime-instrumentation

## Overview

This agent skill integrates the **renaissance_clang DSL tool** (from the `renaissance_clang` repository) into cpsCore to enable **automated runtime instrumentation and tracing** of function calls and logging operations. The tool uses intelligent pattern matching and code transformation to inject trace points into source code without manual modification.

### Key Capabilities

- **Automated code instrumentation**: Match specific function calls or patterns and wrap them with trace emissions
- **Pattern-based transformation**: Define complex matching and replacement rules using a domain-specific language
- **Minimal code coupling**: Instrumentation is injected via preprocessor conditionals, keeping source clean
- **Reversible**: Apply and remove tracing without permanently modifying source files
- **Configurable filters**: Define custom filter logic in C++ to control which matches are transformed

## When to use

- You want to add runtime tracing to track function calls and execution flow in cpsCore
- You need to instrument specific functions or patterns without manual modification
- You want to analyze and visualize the call graph and execution sequences at runtime
- You want to collect timing and component interaction data by tracing key functions
- You need to apply complex, context-aware transformations to source code
- You want to capture logging, aggregation, or utility function calls with detailed metadata

## Architecture

The tool operates in a **two-pronged approach**:

### 1. Pattern-Based Code Matching and Transformation (csp_matcher via Windows)

Uses the `csp_matcher` executable (compiled from the renaissance_clang project) to:

- Parse all source files (.cpp/.hpp) using Clang's compiler frontend
- Match specified patterns (function calls, expressions) using flexible wildcards and type constraints
- Extract metadata ($callerFunc, $callerClass, etc.) from the matching context
- Inject trace calls (via commas operator) wrapping the original expression
- Generate compile_commands.json-driven file enumeration to match exactly what the Linux build compiles

**Files involved:**
- `add_tracing.txt` - Pattern matching rules (find/replace pairs)
- `tracing_filters.cpp` - Custom C++ filter logic for advanced matching
- `.github/skills/add-runtime-instrumentation/scripts/apply_tracing.ps1` - PowerShell orchestration script

### 2. Macro-Level Instrumentation (Post-Processing via CPSLogger.h)

After pattern matching completes, patch the `CPSLOG` macro definition in CPSLogger.h to:

- Emit a [TRACE] line on every logging call without requiring individual file modifications
- Capture detailed metadata (timestamp, caller function, component, location)
- Provide a uniform trace point for all RAIILogStream usage

**Rationale:** Early patching would break the Windows csp_matcher compilation (the preamble includes CPSLogger.h with Linux paths); patching is deferred until after matching completes.

## Inputs

### 1. Tracing Rules File (`add_tracing.txt`)

A simple, line-based domain-specific language with two directives per match:

```
find:    <PATTERN>
replace: <TRANSFORMATION>
```

**Pattern Syntax:**
- Variables: `$agg`, `$stage`, `$T` are wildcards capturing expressions
- Function calls: `Aggregator::getAll<int>()`, `CPSLogger::instance()->flush()`
- Template instances: `EnumMap<RunStage>::convert($x)`
- Metadata: `$callerFunc`, `$callerClass`, `$callerFile`, `$callerLine` are automatically available

**Trace Emission Template in Replacement:**
```cpp
(std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, TARGET.method, COMPONENT, $callerClass, %s\n", 
             cspTraceTimestamp().c_str(), 
             cspTraceCallerComponent(__FILE__).c_str(), 
             cspTraceLocation(__FILE__, __LINE__).c_str()), 
ORIGINAL_CALL)
```

**Example:**
```
find:    $agg.getAll<$T>()
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, Aggregator.getAll, Aggregation, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), $agg.getAll<$T>())
```

### 2. Filter Rules File (`tracing_filters.cpp`) [Optional]

Advanced C++ code that defines custom filter functions to select/reject matches:

```cpp
extern "C" {
bool is_trace_remove(int n, const char* const* ns, const char* const* vs) {
    // ns: array of variable names ($callerFunc, $callerClass, etc.)
    // vs: array of their captured values
    const char* text = get_hole(n, ns, vs, "any");
    return text != NULL && strstr(text, "[TRACE]") != NULL;  // Match if already traced
}
}
```

Used by csp_matcher with `--filter-defs` flag.

### 3. Trace Header (`csp_trace.h`)

A single header file containing inline helper functions:

| Function | Purpose | Example Output |
|----------|---------|-----------------|
| `cspTraceTimestamp()` | Wall-clock time as "HH:MM:SS.mmm" | "14:23:45.832" |
| `cspTraceLocation(file, line)` | "filename.ext:lineno" | "Aggregator.cpp:123" |
| `cspTraceCallerFunc(pretty_func)` | Extract method name from `__PRETTY_FUNCTION__` | "notifyAggregationOnUpdate" |
| `cspTraceCallerClass(pretty_func)` | Extract class name from `__PRETTY_FUNCTION__` | "AggregatableRunner" |
| `cspTraceCallerComponent(filepath)` | Extract component from path (/src/X/, /include/cpsCore/X/) | "Synchronization" |

**Trace Line Format (stderr):**
```
[TRACE] HH:MM:SS.mmm, callerFunc, callerComponent, Callee.method, calleeComponent, callerClass, file:line
```

Example:
```
[TRACE] 14:23:45.832, runStage, Synchronization, Aggregator.getAll, Aggregation, SimpleRunner, SimpleRunner.cpp:67
```

## Execution Flow

### Step 1: Prepare Tracing Rules

Define or customize `add_tracing.txt` with pattern matching rules:

```
find:    Aggregator::getAll<$T>()
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, Aggregator.getAll, Aggregation, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), Aggregator::getAll<$T>())
```

### Step 2: Run the Skill

Execute the skill to apply instrumentation:

```
agent invoke add-runtime-instrumentation --action apply [--exclude-tests]
```

**Options:**
- `--action apply` - Apply instrumentation rules (default)
- `--action remove` - Remove previously applied instrumentation
- `--exclude-tests` - Skip files under `/tests/` (faster iteration)

### Step 3: Rebuild and Run

Rebuild cpsCore with instrumentation:

```bash
cmake --build bld/wsl-release --target all -j
./bld/wsl-release/tests/tests -d yes 2>&1 | tee trace_output.txt
```

**Output:** Trace lines appear on stderr, ready for analysis:

**Automated alternative:** `scripts/collect_traces.py` does the rebuild, the run,
and converts the captured `[TRACE]` lines directly into `runtime_traces.txt`
(the pipe-delimited `EventTimestamp|EventName|ClientComponent|ClientFunction|
ServerComponent|ServerFunction|RelationshipType|InterfaceNames` schema used
elsewhere in this repo), instead of leaving you with a raw `trace_output.txt`
to parse by hand. It assumes Step 2 has already been applied; see its own
docstring and the "Automated: Steps 3-4 in one script" section below.

```
[TRACE] 14:23:45.832, runStage, Synchronization, Aggregator.getAll, Aggregation, SimpleRunner, SimpleRunner.cpp:67
[TRACE] 14:23:45.834, notifyAggregationOnUpdate, Synchronization, Aggregator.getAll, Aggregation, AggregatableRunner, AggregatableRunner.cpp:45
```

## Customization Guide

### Adding New Trace Points

Edit `.github/skills/add-runtime-instrumentation/scripts/add_tracing.txt`:

1. Identify the target function or pattern you want to trace
2. Write a precise pattern using variables and template syntax
3. Construct a replacement that calls `cspTraceTimestamp()`, `cspTraceCallerComponent()`, etc.
4. Test with a subset: specify `--exclude-tests` for faster iteration

### Advanced: Custom Filters

If you want to skip certain matches (e.g., already-traced code, specific namespaces):

1. Edit `.github/skills/add-runtime-instrumentation/scripts/tracing_filters.cpp`
2. Implement a filter function following the `is_trace_remove()` pattern
3. Rebuild the renaissance_clang project to regenerate `csp_matcher.exe`
4. The skill will use it via `--filter-defs` flag

### Removing Instrumentation

To revert all changes without rebuilds:

```
agent invoke add-runtime-instrumentation --action remove
```

This pattern-matches trace wrappers (identified by `[TRACE]` marker) and replaces `($any, $orig)` with just `$orig`.

## Prerequisites

### Windows Machine

- **cmake 3.31+**: For building and rule processing
- **csp_matcher.exe**: Pre-built from the renaissance_clang project
  - Location: `C:\Code\clang-exp\build_mingw\csp_matcher.exe`
  - Used via PowerShell with full path
- **compile_commands.json**: Must be generated from CMake configuration
  - Location: `C:\Code\CSP\cpsCore\bld\release\compile_commands.json`
  - Generate with:
    ```bash
    cmake -S /mnt/c/Code/CSP/cpsCore \
          -B /mnt/c/Code/CSP/cpsCore/bld/release \
          -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    ```

### Linux Machine (for rebuild after instrumentation)

- **CMake 3.15+**
- **Ninja or Make**
- **GCC/Clang** with standard C++17 support

### Configuration

Paths are configured in the skill's PowerShell scripts:

```powershell
$compdbPath   = "C:\Code\CSP\cpsCore\bld\release\compile_commands.json"
$exePath      = "C:\Code\clang-exp\build_mingw\csp_matcher.exe"
$cpsCorePath  = "C:\Code\CSP\cpsCore"
```

Update these if your repository layout differs.

## Step-by-Step Example

### 1. Define Tracing Rules

Create or update `.github/skills/add-runtime-instrumentation/scripts/add_tracing.txt`:

```
find:    $agg.getAll<$T>()
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, Aggregator.getAll, Aggregation, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), $agg.getAll<$T>())

find:    CPSLogger::instance()->flush()
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, CPSLogger.flush, Logging, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), CPSLogger::instance()->flush())
```

### 2. Apply Instrumentation

```powershell
# From the cpsCore workspace root
agent invoke add-runtime-instrumentation --action apply --exclude-tests
```

**Expected output:**
- Modified `.cpp` files with injected `#include csp_trace.h` (conditional)
- Modified CPSLogger.h with updated CPSLOG macro
- Log file: `.github/skills/add-runtime-instrumentation/scripts/apply_log.txt`

### 3. Rebuild

```bash
# WSL
cd /mnt/c/Users/prathikak/Documents/cpsCore
cmake --build bld/wsl-release --target all -j
cmake --build bld/wsl-release --target tests -j
```

### 4. Collect Traces

```bash
cd bld/wsl-release/tests
./tests -d yes 2>&1 | tee trace_output.txt
```

### 5. Analyze

Parse `trace_output.txt` with your analysis tool:

```bash
# Extract unique call paths
grep "^\[TRACE\]" trace_output.txt | cut -d',' -f2-5 | sort | uniq -c | sort -rn

# Filter by component
grep "Synchronization" trace_output.txt
```

## Automated: Steps 3-4 in one script

`scripts/collect_traces.py` runs the rebuild, runs the (already-instrumented)
test binary, and converts the captured `[TRACE]` lines straight into
`runtime_traces.txt` in the repo root -- skipping the manual
`trace_output.txt` + `grep`/`cut` steps above.

```bash
# from WSL (or any Linux shell) -- the test binary is a Linux ELF, so this
# script must run under a Linux Python, not from Windows directly
python3 .github/skills/add-runtime-instrumentation/scripts/collect_traces.py
```

**Prerequisite:** Step 2 (`apply_tracing.ps1`) must already have been applied
to this checkout -- the script only rebuilds and runs, it does not inject
instrumentation. If Step 2 was skipped, the rebuilt binary won't emit
`[TRACE]` lines and the script will warn about an empty result.

Options:

```bash
python3 collect_traces.py --cpscore-root /mnt/c/Users/prathikak/Documents/cpsCore
python3 collect_traces.py --build-dir bld/wsl-release --skip-build
```

Output columns match the schema already used elsewhere in this repo:
`EventTimestamp|EventName|ClientComponent|ClientFunction|ServerComponent|ServerFunction|RelationshipType|InterfaceNames`.
`RelationshipType` is always written as `Command` (the `[TRACE]` format itself
doesn't encode Command/Reply/Notification), and `EventTimestamp` is the real
captured wall-clock time from the trace line, reformatted to ISO-8601.

### 6. Clean Up (Optional)

```powershell
agent invoke add-runtime-instrumentation --action remove
```

## Output Files

After execution, the skill generates:

| File | Purpose |
|------|---------|
| `apply_log.txt` | Records every file modification and pattern match count |
| `*.cpp` (modified) | Instrumented source files with trace injections |
| `CPSLogger.h` (modified) | Updated CPSLOG macro with trace emission |
| `apply_tracing_remove_backup.txt` | Backup of remove script for reverting changes |
| `runtime_traces.txt` (repo root) | Written by `scripts/collect_traces.py` (Steps 3-4) -- rebuilt binary's `[TRACE]` output, converted to the pipe-delimited schema |

## Troubleshooting

### csp_matcher.exe not found
- Check path: `C:\Code\clang-exp\build_mingw\csp_matcher.exe`
- Rebuild renaissance_clang project: `cd C:\Code\clang-exp && .\setup.ps1`

### No matches found (replacements=0)

**Possible causes:**
1. Pattern syntax mismatch (use `::` for member functions, not `.`)
2. Template syntax incorrect (use angle brackets precisely)
3. Include paths in `--pattern-flags` incomplete
4. File not in compile_commands.json

**Debug steps:**
1. Check `add_tracing.txt` syntax: each `find` followed immediately by `replace`
2. Verify file appears in compile_commands.json: `grep TargetFile compile_commands.json`
3. Run csp_matcher manually on a single file with `-v` flag

### Trace Output Not Appearing

1. Verify csp_trace.h is included (check `.cpp` file headers)
2. Verify CPSLOG macro was patched (check CPSLogger.h)
3. Make sure to redirect stderr: `./tests 2>&1 | tee trace_output.txt`
4. Check application is actually reaching instrumented code paths

### Windows vs. Linux Path Issues

- csp_matcher runs on Windows; paths are converted from WSL format (`/mnt/c/...`) to Windows (`C:/...`)
- csp_trace.h include uses directive to switch between Windows (`csp_trace.h`) and Linux (`/mnt/c/Code/clang-exp/examples/cpscore_tracing/csp_trace.h`) paths
- If conditionals fail, check that the header is copied to the correct location in both build environments

## Integration with Other Skills

This skill pairs well with:

- **draw-sequential-mermaid-general**: Process trace output to generate call sequence diagrams
- **get-interface-dependency-table**: Document which components interact at runtime
- **draw-sysml-sequence-model**: Generate formal SysML models from captured traces

## See Also

- **Renaissance Clang Repository**: `C:\Code\clang-exp`
- **csp_matcher Tool**: Pattern matching compiler frontend (uses Clang libtooling)
- **Trace Format Specification**: See `csp_trace.h` for detailed trace line format
- **Steps 3-4 automation**: `scripts/collect_traces.py` (rebuild + run + convert to `runtime_traces.txt`)
- **cpsCore Build Instructions**: [README.md](../../../README.md)
```
