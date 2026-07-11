# CSP Matcher

AST-pattern search and replace tool for C++. Parses a CSP pattern into a Clang AST (via LibTooling), emits ASTMatcher DSL, runs it against target files, and optionally rewrites matched code.

## Prerequisites

This project builds with MSYS2/MinGW64 (Clang and LLVM from MSYS2 packages).

### Quick setup (recommended)

Run the setup script from the repo root in PowerShell. It installs the required MSYS2 packages, fixes `PATH`, configures CMake, builds the binary, and runs a smoke test — all in one step:

```powershell
.\setup.ps1
```

Optional parameters:

| Parameter | Default | Description |
|---|---|---|
| `-MingwRoot` | `C:\msys64\mingw64` | Path to your MSYS2 mingw64 directory |
| `-BuildDir` | `build_mingw` | CMake build output directory |
| `-SkipBuild` | off | Fix PATH only; skip cmake/build |

If MSYS2 is not at the default path:

```powershell
.\setup.ps1 -MingwRoot "D:\msys64\mingw64"
```

### Manual setup

**Dependencies:**

| Package | Purpose |
|---|---|
| [MSYS2](https://www.msys2.org/) | Provides the MinGW64 toolchain and runtime |
| `mingw-w64-x86_64-clang` | Clang/LLVM compiler (builds the tool and is used as the C++ API) |
| `mingw-w64-x86_64-llvm` | LLVM libraries required by Clang |
| `mingw-w64-x86_64-ninja` | Ninja build system (used by CMake) |

#### 1. Install MSYS2

Download and install MSYS2 from https://www.msys2.org/ (default location: `C:\msys64`).

#### 2. Install required packages

Open a **MSYS2 MinGW64** shell and run:

```shell
pacman -S mingw-w64-x86_64-clang mingw-w64-x86_64-llvm mingw-w64-x86_64-ninja
```

#### 3. Add MinGW to PATH

The runtime DLLs must be on `PATH` for the binary to run. In PowerShell:

```powershell
# Current session only
$env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH

# Permanently (restart PowerShell after)
[System.Environment]::SetEnvironmentVariable(
    "PATH",
    "C:\msys64\mingw64\bin;" + [System.Environment]::GetEnvironmentVariable("PATH", "User"),
    "User"
)
```

If MSYS2 is installed elsewhere, substitute its `mingw64\bin` path.

## Build

```powershell
cmake -S . -B build_mingw -G Ninja `
  -DCMAKE_BUILD_TYPE=Release `
  -DCMAKE_CXX_COMPILER=C:/msys64/mingw64/bin/clang++.exe
cmake --build build_mingw
```

The executable is at `build_mingw/csp_matcher.exe`.

If MSYS2 is not at the default path, also pass `-DMINGW_ROOT=<path>`.

## Run

> **Target file**: the examples below use `tests/find_fixture.cpp`, which ships with the repo and contains if-statements that the default pattern matches.
> Substitute any `.cpp` file of your own.
> `$p` must be assigned in the same PowerShell session before the commands that reference it.

### Find matches in a file

```powershell
$p = 'if ( $cond ) { $$body }'
./build_mingw/csp_matcher.exe --csp $p --find tests/find_fixture.cpp
```

Multiple files:

```powershell
./build_mingw/csp_matcher.exe --csp $p --find tests/find_fixture.cpp --find src/main.cpp
```

From a `compile_commands.json`:

```powershell
./build_mingw/csp_matcher.exe --csp $p --db compile_commands.json
```

### Output modes

```powershell
# byte offsets only (default with count)
./build_mingw/csp_matcher.exe --csp $p --find tests/find_fixture.cpp --output offset

# raw matched text
./build_mingw/csp_matcher.exe --csp $p --find tests/find_fixture.cpp --output raw

# count + offsets + raw text
./build_mingw/csp_matcher.exe --csp $p --find tests/find_fixture.cpp --output count,offset,raw

# limit displayed rows (counts are always complete)
./build_mingw/csp_matcher.exe --csp $p --find tests/find_fixture.cpp --output count,offset,raw --max-matches 5
```

Example output:

```
file=tests/find_fixture.cpp matches=2
match[0] start=28 end=43
match[1] start=46 end=64
```

### Replace matched code

```powershell
$t = 'if ( !($cond) ) { $$body }'
./build_mingw/csp_matcher.exe --csp $p --replace $t --find tests/find_fixture.cpp
```

All `$hole` and `$$hole` references in the template are substituted with the text captured from the pattern.

### Remove matched code

```powershell
./build_mingw/csp_matcher.exe --csp $p --remove --find tests/find_fixture.cpp
```

`--remove` deletes each match from the file. It cannot be combined with `--replace` for the same pattern.

### Multiple patterns

Patterns are evaluated independently; all matches are reported in source order:

```powershell
./build_mingw/csp_matcher.exe `
  --csp 'if ( $cond ) { $$body }' `
  --csp 'return $x;' `
  --find tests/find_fixture.cpp --output count
```

### Rules files

A rules file batches one or more `find`/`replace`/`filter` triples:

```text
# my_rules.txt
find: if ( $cond ) { $$body }
replace: if ( !($cond) ) { $$body }
filter: my_filter

find: return $x;
```

```powershell
./build_mingw/csp_matcher.exe --rules my_rules.txt --find tests/find_fixture.cpp
```

Multiple rules files and inline `--csp` patterns can be mixed freely.

Rules file format:
- `find: <pattern>` — pattern to match (required; starts a new pair)
- `replace: <tmpl>` — replacement template for the preceding `find:` (optional)
- `remove:` — remove each match of the preceding `find:` (optional; mutually exclusive with `replace:`)
- `filter: <call>` — filter function call for the preceding `find:` (optional; see Filters)
- Lines starting with `#` and blank lines are ignored

### Pattern syntax

Patterns are written as near-normal C++ code with **hole variables** prefixed with `$`:

| Syntax | Matches | Use in `replace:` |
|---|---|---|
| `$name` | Any single expression or identifier | Substituted with the captured text |
| `$$name` | A statement or parameter list (multi-element) | Substituted with the captured list |
| `$T` | An unbound template type argument | Round-tripped verbatim into the replacement |

The same hole name used in `find:` is substituted into `replace:` wherever it appears.

Two **special variables** are automatically injected for every match and can be used in `replace:` templates:

| Variable | Value |
|---|---|
| `$callerFunc` | Name of the function that encloses the match |
| `$callerClass` | Name of the class that encloses the match (empty string at file scope) |

Example — wrap a call with a trace `fprintf`, using injected context:

```text
find:    $agg.getAll<$T>()
replace: (std::fprintf(stderr, "[TRACE] %s %s::%s\n", cspTraceTimestamp().c_str(), "$callerClass", "$callerFunc"), $agg.getAll<$T>())
```

### Filters

Filters let you accept or reject matches based on the captured hole values.
Filter functions are written in plain C++ (no Clang/LLVM headers required) and compiled at runtime into a shared library.

**1. Write a filter definitions file** (`my_filters.cpp`):

```cpp
#include <string.h>  // strcmp, strlen — no Clang headers needed

// Return true to accept the match, false to reject it.
// 'count' is the number of captured holes; 'names'/'values' are parallel C-string arrays.
bool only_short_cond(int count, const char * const *names, const char * const *values) {
    for (int i = 0; i < count; i++)
        if (strcmp(names[i], "cond") == 0)
            return strlen(values[i]) < 10;
    return false;
}

// Extra parameters are passed from the filter call expression.
bool cond_equals(int count, const char * const *names, const char * const *values,
                 const char* expected) {
    for (int i = 0; i < count; i++)
        if (strcmp(names[i], "cond") == 0)
            return strcmp(values[i], expected) == 0;
    return false;
}
```

**2. Invoke with `--filter` and `--filter-defs`**:

```powershell
./build_mingw/csp_matcher.exe `
  --csp 'if ( $cond ) { $$body }' `
  --filter 'only_short_cond' `
  --filter-defs my_filters.cpp `
  --find tests/find_fixture.cpp --output count

# With extra arguments:
./build_mingw/csp_matcher.exe `
  --csp 'if ( $cond ) { $$body }' `
  --filter 'cond_equals("x")' `
  --filter-defs my_filters.cpp `
  --find tests/find_fixture.cpp --output count
```

Or in a rules file:

```text
find: if ( $cond ) { $$body }
filter: only_short_cond
```

```powershell
./build_mingw/csp_matcher.exe --rules my_rules.txt --filter-defs my_filters.cpp --find tests/find_fixture.cpp
```

**Compiler requirements**: MSYS2 `g++` is used to compile the filter DLL for ABI compatibility with the main binary.
The tool looks for it at `MINGW_ROOT/bin/g++` (default `C:/msys64/mingw64`).
Set the `MINGW_ROOT` environment variable to override the MSYS2 root.

### Strict mode

```powershell
./build_mingw/csp_matcher.exe --csp $p --strict
```

Treats Clang parse errors in the pattern as a hard failure (exit code 6) instead of proceeding with whatever roots were extracted.

### Advanced flags

| Flag | Description |
|---|---|
| `--pattern-preamble <code>` | Prepend code to every pattern translation unit (e.g. to bring types into scope). |
| `--pattern-flags <flag>` | Add a compiler flag when parsing patterns (repeatable). |
| `--find-flags <flag>` | Add a compiler flag when parsing target files (repeatable). |

## Robustness test suite

Run the full suite (130 cases across 7 suites):

```powershell
cmake --build build_mingw
./tests/run_csp_suite.ps1 -ExePath ./build_mingw/csp_matcher.exe
```

The script writes a Markdown report to `tests/csp_suite_report.md` and case artifacts under `tests/generated/case_artifacts/`.

Suites covered: pattern parse, configuration/find, replacement, generated replacement, compilation database, rules file, filter.

Filter tests require MSYS2 `g++` to be available (the tool uses `MINGW_ROOT/bin/g++`; set `MINGW_ROOT` if MSYS2 is not at the default path).

## Design

1. Hole rewrite to valid C++ placeholders:
- $name -> context-aware placeholder (expression/type/function name)
- \$\$name -> list placeholder (statement list or parameter list)

2. Parse strategy:
- first parse as a statement pattern in a synthetic function body
- if no statement roots are extracted, parse as a declaration pattern

3. Emitter strategy:
- registry handlers for common cursor kinds (if, compound, operators, decl refs, params, function decls, literals, calls)
- fallback matcher name from cursor-kind spelling plus hasDescendant(...) constraints for children

4. Hole binding behavior:
- expression holes bind as expr().bind("...")
- statement-list holes in blocks bind as stmt().bind("...") with hasAnySubstatement(...)
- parameter-list holes bind as parmVarDecl().bind("...") via hasAnyParameter(...)
- function-name holes bind on functionDecl(...).bind("...")

5. Descendant directives (comment-based):
- start: // <...
- end: // ...>
- statements inside the active region emit as hasDescendant(...)
- statements outside emit as hasSubstatement(...)

6. Parse error forwarding:
- on overall parse failure, diagnostics from statement and declaration attempts are printed

Example:

```text
if ($cond) {
  // <desc
  return $x;
  $$body
  // desc>
  $x = 1;
}
```

Expected structure:
- return and $$body are emitted under hasDescendant(...)
- $x = 1 is emitted under hasSubstatement(...)

## Example output

Input:

```text
if ( $cond0 || $cond1 ) { $$body1 }
```

Output:

```text
pattern[0] DSL: ifStmt(hasCondition(binaryOperator(hasOperatorName("||"), hasLHS(expr().bind("cond0")), hasRHS(expr().bind("cond1")))), hasThen(compoundStmt().bind("__cs__body1"))).bind("__csp_root__")
```
