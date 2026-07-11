# Configuration Guide for add-runtime-instrumentation Skill

This document provides configuration options for the instrumentation skill.

## Path Configuration

The PowerShell scripts support parameterized paths so you can customize execution:

```powershell
# Apply with custom renaissance_clang root
.\scripts\apply_tracing.ps1 -RenaissanceRoot "C:\Your\Path\renaissance_clang" `
                            -CpsCoreRoot "C:\Your\Path\cpsCore"

# Remove instrumentation
.\scripts\remove_tracing.ps1 -RenaissanceRoot "C:\Your\Path\renaissance_clang" `
                             -CpsCoreRoot "C:\Your\Path\cpsCore"
```

**Default Paths:**
- Renaissance Root: `C:\Code\clang-exp`
- cpsCore Root: `C:\Code\CSP\cpsCore`

## Tracing Rules Customization

Edit `scripts/add_tracing.txt` to define custom patterns:

### Basic Pattern Format

```
find:    <PATTERN_WITH_VARIABLES>
replace: <TRANSFORMATION_WITH_METADATA>
```

### Variables and Metadata

- **Capture Variables**: `$var`, `$agg`, `$stage`, `$T` (template parameter)
- **Metadata Functions**:
  - `$callerFunc` - Function name from call site
  - `$callerClass` - Class name from call site
  - `cspTraceTimestamp()` - Wall-clock time
  - `cspTraceCallerComponent(__FILE__)` - Component directory
  - `cspTraceLocation(__FILE__, __LINE__)` - File and line number

### Example: Trace a Custom Function

To add tracing for `MyClass::myFunction()`:

```
find:    MyClass::myFunction<$T>($arg)
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, MyClass.myFunction, MyComponent, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), MyClass::myFunction<$T>($arg))
```

## Advanced: Custom Filter Logic

Edit `scripts/tracing_filters.cpp` to implement custom filter functions:

```cpp
extern "C" {

// Example: Only match if caller is in specific namespace
bool my_custom_filter(int n, const char* const* ns, const char* const* vs) {
    const char* caller = get_hole(n, ns, vs, "callerFunc");
    // Return true if this match should be accepted
    return caller != NULL && strstr(caller, "Specific") != NULL;
}

}
```

Then reference in `add_tracing.txt`:

```
find:    SomePattern
filter:  my_custom_filter
replace: ...
```

## Trace Output Format

All traces are written to stderr in the format:

```
[TRACE] HH:MM:SS.mmm, caller_func, caller_component, Callee.method, callee_component, caller_class, file:line
```

**Example:**
```
[TRACE] 14:23:45.832, runStage, Synchronization, Aggregator.getAll, Aggregation, SimpleRunner, SimpleRunner.cpp:67
```

## Excluding Tests

During development, skip test files for faster iteration:

```powershell
.\scripts\apply_tracing.ps1 -ExcludeTests
```

This speeds up pattern matching by skipping all files under `/tests/`.

## Log File

After execution, check `scripts/apply_log.txt` for:
- Number of replacements per file
- Files modified
- Errors or warnings

## Prerequisites Checklist

- [ ] csp_matcher.exe built from renaissance_clang project
- [ ] compile_commands.json generated from CMake
- [ ] MSys64/MinGW64 in PATH (for tools)
- [ ] PowerShell 5.0+ (to run .ps1 scripts)
- [ ] CPSLogger.h in unpatched state (before applying)

## Troubleshooting Configuration

### Pattern Matches Not Found

1. Check pattern syntax in `add_tracing.txt`
2. Verify `--pattern-flags` includes all necessary include paths
3. Test on a single file first: manual csp_matcher invocation

### Path Issues on Different Systems

Update the hardcoded paths in scripts if your environment differs:

```powershell
# In apply_tracing.ps1 and remove_tracing.ps1
$RenaissanceRoot = "C:\Your\Custom\Path\renaissance_clang"
$CpsCoreRoot = "C:\Your\Custom\Path\cpsCore"
```

Or pass them as parameters to avoid editing files.

## Integration with Build System

After applying instrumentation, rebuild cpsCore:

```bash
cd /path/to/cpsCore
cmake --build bld/wsl-release --target all -j
cmake --build bld/wsl-release --target tests -j
cd bld/wsl-release/tests
./tests -d yes 2>&1 | tee trace_output.txt
```

Parse trace_output.txt for analysis.
