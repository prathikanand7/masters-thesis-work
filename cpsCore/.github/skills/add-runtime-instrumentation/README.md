# Quick Start Guide for add-runtime-instrumentation Skill

## One-Minute Overview

The **add-runtime-instrumentation** skill integrates the renaissance_clang DSL tool into cpsCore to automatically inject runtime tracing into your code. The tool uses pattern matching (via `csp_matcher`) to find specific function calls and wrap them with trace emissions.

**Trace Format:**
```
[TRACE] HH:MM:SS.mmm, caller_func, caller_component, Callee.method, callee_component, caller_class, file:line
```

## Quick Start

### Prerequisites

✅ **Required:**
- `csp_matcher.exe` from compiled renaissance_clang project at: `C:\Code\clang-exp\build_mingw\csp_matcher.exe`
- `compile_commands.json` from cpsCore build directory: `C:\Code\CSP\cpsCore\bld\release\compile_commands.json`
- PowerShell 5.0+
- MSys64/MinGW64 in PATH

### Step 1: Verify Prerequisites

```powershell
# Check csp_matcher
Test-Path "C:\Code\clang-exp\build_mingw\csp_matcher.exe"  # Should return True

# Check compile_commands.json
Test-Path "C:\Code\CSP\cpsCore\bld\release\compile_commands.json"  # Should return True

# If either fails, see Configuration Guide for details
```

### Step 2: Apply Instrumentation

From your cpsCore workspace root:

```powershell
cd C:\Users\prathikak\Documents\cpsCore
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1
```

**Options:**

```powershell
# Skip test files for faster iteration
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 -ExcludeTests

# Specify custom paths
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 `
  -RenaissanceRoot "C:\Your\Path\renaissance_clang" `
  -CpsCoreRoot "C:\Your\Path\cpsCore"
```

**Expected output:**
```
file=src/Synchronization/SimpleRunner.cpp replacements=3
file=src/Aggregation/Aggregator.h replacements=2
Total replacements: 42
file=C:\Code\CSP\cpsCore\include\cpsCore\Logging\CPSLogger.h patched=CPSLOG
```

### Step 3: Rebuild cpsCore

On Linux (or within WSL):

```bash
cd /mnt/c/Users/prathikak/Documents/cpsCore
cmake --build bld/wsl-release --target all -j
```

Or from Windows, via WSL:

```powershell
wsl -e bash -c "cd /mnt/c/Users/prathikak/Documents/cpsCore && cmake --build bld/wsl-release --target all -j"
```

### Step 4: Run Tests and Collect Traces

```bash
cd /mnt/c/Users/prathikak/Documents/cpsCore/bld/wsl-release/tests
./tests -d yes 2>&1 | tee trace_output.txt
```

### Step 5: Analyze Traces

```bash
# View raw trace output
head -20 trace_output.txt

# Extract unique call paths
grep "^\[TRACE\]" trace_output.txt | cut -d',' -f2-5 | sort | uniq -c | sort -rn

# Filter by component
grep "Synchronization" trace_output.txt | head -10

# Parse timestamp
grep "14:23" trace_output.txt
```

### Step 6: Remove Instrumentation (Optional)

```powershell
.\.github\skills\add-runtime-instrumentation\scripts\remove_tracing.ps1
```

This reverts all changes and removes injected trace code.

## What Gets Instrumented?

By default, the skill traces:

1. **`Aggregator::getAll<T>()`** - All aggregator lookups
2. **`CPSLogger::instance()->flush()`** - Logger flush operations
3. **`EnumMap<RunStage>::convert()`** - Stage conversion calls
4. **`CPSLOG(level)`** - All logging statements (macro-patched)

## Customizing Tracing Rules

Edit `.github/skills/add-runtime-instrumentation/scripts/add_tracing.txt`:

```plaintext
find:    MyFunction($arg1, $arg2)
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, MyFunction, Component, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), MyFunction($arg1, $arg2))
```

See [CONFIGURATION.md](CONFIGURATION.md) for advanced customization.

## Understanding Trace Output

**Line example:**
```
[TRACE] 14:23:45.832, runStage, Synchronization, Aggregator.getAll, Aggregation, SimpleRunner, SimpleRunner.cpp:67
```

**Fields:**
- `14:23:45.832` - Wall-clock timestamp (HH:MM:SS.mmm)
- `runStage` - Caller function name
- `Synchronization` - Caller component (directory name)
- `Aggregator.getAll` - Callee (function/method being called)
- `Aggregation` - Callee component
- `SimpleRunner` - Caller class (or "" for free functions)
- `SimpleRunner.cpp:67` - Source file and line number

## Common Issues

### Error: csp_matcher.exe not found

**Solution:**
- Build renaissance_clang: `cd C:\Code\clang-exp && .\setup.ps1`
- Or specify custom path: `.\apply_tracing.ps1 -RenaissanceRoot "C:\Your\Path\renaissance_clang"`

### Error: compile_commands.json not found

**Solution:**
Configure cpsCore first:
```bash
cd C:\Code\CSP\cpsCore
cmake -S . -B bld/release -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

### No traces appearing in output

1. Verify csp_trace.h was injected: `grep "csp_trace.h" src/Synchronization/*.cpp`
2. Check CPSLOG macro was patched: `grep "\[TRACE\]" include/cpsCore/Logging/CPSLogger.h`
3. Rebuild after applying: `cmake --build bld/wsl-release --target all -j`
4. Redirect stderr: `./tests 2>&1 | tee trace.txt`

### Remove instrumentation, rebuild, then re-apply if issues persist

```powershell
.\remove_tracing.ps1
```

Then repeat steps 3-4.

## Next Steps

- **Visualize traces**: Use the `draw-sequential-mermaid-general` skill to generate call diagrams
- **Advanced filtering**: Edit `tracing_filters.cpp` to customize pattern matching
- **Custom metrics**: Parse trace output to measure component interaction frequency
- **Performance analysis**: Correlate trace timestamps with performance profiling data

## More Information

- See [SKILL.md](SKILL.md) for detailed architecture and API documentation
- See [CONFIGURATION.md](CONFIGURATION.md) for advanced customization options
- See renaissance_clang repository: `C:\Code\clang-exp`
