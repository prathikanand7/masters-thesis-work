# Examples: Using add-runtime-instrumentation Skill

This document provides practical examples of using the instrumentation skill.

## Example 1: Basic Instrumentation

Apply default tracing rules to track key cpsCore operations:

```powershell
cd C:\Users\prathikak\Documents\cpsCore
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1
```

This instruments:
- `Aggregator::getAll<T>()`
- `CPSLogger::instance()->flush()`
- `EnumMap<RunStage>::convert()`
- All `CPSLOG(...)` macro calls

**Rebuild and run:**
```bash
cd /mnt/c/Users/prathikak/Documents/cpsCore
cmake --build bld/wsl-release --target tests -j
./bld/wsl-release/tests/tests -d yes 2>&1 | head -50
```

**Sample output:**
```
[TRACE] 14:23:45.001, SimpleRunner::runAllStages, Synchronization, Aggregator.getAll, Aggregation, SimpleRunner, SimpleRunner.cpp:89
[TRACE] 14:23:45.002, AggregatableRunner::notifyAggregationOnUpdate, Synchronization, Aggregator.getAll, Aggregation, AggregatableRunner, AggregatableRunner.cpp:45
[TRACE] 14:23:45.005, SynchronizedRunner::runSynchronized, Synchronization, CPSLogger.flush, Logging, SynchronizedRunner, SynchronizedRunner.cpp:123
```

## Example 2: Fast Iteration (Exclude Tests)

During development, avoid instrumenting test files for faster feedback:

```powershell
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 -ExcludeTests
```

This only instruments files under `src/`, speeding up pattern matching significantly.

## Example 3: Custom Tracing Rule

Add instrumentation for a custom function. Edit `.github/skills/add-runtime-instrumentation/scripts/add_tracing.txt`:

```plaintext
# Original rules (keep these)
find:    $agg.getAll<$T>()
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, Aggregator.getAll, Aggregation, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), $agg.getAll<$T>())

# Add a new custom rule
find:    PropertyMapper<$T>::add($key, $val)
replace: (std::fprintf(stderr, "[TRACE] %s, $callerFunc, %s, PropertyMapper.add, Configuration, $callerClass, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), PropertyMapper<$T>::add($key, $val))
```

Then apply:
```powershell
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 -ExcludeTests
```

## Example 4: Trace Analysis

Collect traces and analyze call patterns:

```bash
cd /mnt/c/Users/prathikak/Documents/cpsCore/bld/wsl-release/tests
./tests -d yes 2>&1 > /tmp/full_trace.txt

# Extract unique caller-callee pairs
grep "^\[TRACE\]" /tmp/full_trace.txt | cut -d',' -f2-5 | sort | uniq -c | sort -rn | head -20

# Count calls per component
grep "^\[TRACE\]" /tmp/full_trace.txt | cut -d',' -f4 | sort | uniq -c

# Timeline view (unique times)
grep "^\[TRACE\]" /tmp/full_trace.txt | cut -d',' -f1 | sort | uniq
```

**Sample analysis output:**
```
     42 Synchronization , Aggregator.getAll, Aggregation
     35 Synchronization , CPSLogger.flush, Logging
     20 Configuration , PropertyMapper.add, Configuration
     18 Utilities , EnumMap.convert, Utilities
```

## Example 5: Generate Mermaid Sequence Diagram

Use trace output with the `draw-sequential-mermaid-general` skill:

```bash
# Collect traces
cd /mnt/c/Users/prathikak/Documents/cpsCore/bld/wsl-release/tests
./tests -d yes 2>&1 | grep "^\[TRACE\]" > /tmp/traces.txt

# Copy to cpsCore root for processing by skill
cp /tmp/traces.txt /mnt/c/Users/prathikak/Documents/cpsCore/runtime_traces.txt
```

Then invoke the `draw-sequential-mermaid-general` skill to generate a visual sequence diagram.

## Example 6: Performance Analysis

Correlate trace timestamps with execution time:

```bash
# Extract time deltas between consecutive traces
grep "^\[TRACE\]" /tmp/full_trace.txt | \
  awk -F',' '{
    if (NR > 1) {
      cmd = "date -d \""$1\" 00:00:00\" +%s"
      cmd | getline ts
      close(cmd)
      print (ts - prev_ts) "ms: " $2 " -> " $3 " -> " $4
    }
    cmd = "date -d \""$1\" 00:00:00\" +%s"
    cmd | getline prev_ts
    close(cmd)
  }'
```

This helps identify performance bottlenecks.

## Example 7: Component Interaction Matrix

Build a matrix of which components interact:

```bash
grep "^\[TRACE\]" /tmp/full_trace.txt | \
  awk -F',' '{
    caller=$3; callee=$4;
    pair = caller " -> " callee;
    count[pair]++;
  } END {
    for (p in count) print count[p], p;
  }' | sort -rn | column -t
```

**Sample output:**
```
42 Synchronization -> Aggregation
35 Synchronization -> Logging
20 Configuration -> Configuration
18 Utilities -> Utilities
```

## Example 8: Filtering Traces by Component

Extract only traces involving the Synchronization component:

```bash
grep "^\[TRACE\]" /tmp/full_trace.txt | grep "Synchronization" > /tmp/sync_traces.txt
wc -l /tmp/sync_traces.txt

# Or with specific function
grep "runSynchronized" /tmp/full_trace.txt
```

## Example 9: Custom Filter (Advanced)

Create a custom filter to trace only specific code paths. Edit `.github/skills/add-runtime-instrumentation/scripts/tracing_filters.cpp`:

```cpp
// Only trace if caller is in Synchronization component
bool sync_only(int n, const char* const* ns, const char* const* vs) {
    const char* component = get_hole(n, ns, vs, "callerComponent");
    return component != NULL && strcmp(component, "Synchronization") == 0;
}
```

Then in `add_tracing.txt`:

```plaintext
find:    PropertyMapper<$T>::add($key, $val)
filter:  sync_only
replace: (std::fprintf(...), PropertyMapper<$T>::add($key, $val))
```

This rule only matches when called from the Synchronization component.

## Example 10: Remove and Reapply

Test different tracing configurations:

```powershell
# Try first configuration
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 -ExcludeTests

# ... Test and analyze ...

# Remove
.\.github\skills\add-runtime-instrumentation\scripts\remove_tracing.ps1

# Edit add_tracing.txt with different rules

# Try again
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 -ExcludeTests
```

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# Example GitHub Actions
- name: Apply instrumentation
  run: |
    cd cpsCore
    .\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 -ExcludeTests

- name: Build with instrumentation
  run: |
    cmake --build cpsCore/bld/wsl-release --target all -j

- name: Run tests and collect traces
  run: |
    cd cpsCore/bld/wsl-release/tests
    ./tests -d yes 2>&1 | tee trace_output.txt

- name: Analyze traces
  run: |
    grep "^\[TRACE\]" cpsCore/bld/wsl-release/tests/trace_output.txt | \
      wc -l
```

## Troubleshooting Examples

### No matches found

**Check 1: Pattern syntax**
```powershell
# Test with a simpler pattern first
# find:    EnumMap<RunStage>::convert($stage)
# Check that variable names match what's captured
```

**Check 2: Include paths**
```powershell
# Verify files are properly parsed
# Add -v flag to csp_matcher (requires modification to script)
```

**Check 3: File enumeration**
```powershell
# Check which files were processed
Get-Content ".\.github\skills\add-runtime-instrumentation\scripts\apply_log.txt"
```

### Rebuild fails after instrumentation

Clear build cache and retry:

```bash
cd /mnt/c/Users/prathikak/Documents/cpsCore
rm -rf bld/wsl-release/CMakeFiles
cmake --build bld/wsl-release --target all -j
```

### Trace output file is empty

```bash
# Verify stderr redirection
./tests -d yes 2>&1  # Must include "2>&1"

# Check that traces are actually being hit
./tests 2>&1 | grep TRACE | head -5
```

