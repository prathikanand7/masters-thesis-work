---
applyTo: "**"
---

# cpsCore build & test reference

Target repository: `C:\Code\CSP\cpsCore` (Linux path: `/mnt/c/Code/CSP/cpsCore`)

## CMake configure (WSL)

Run once to generate the build system and `compile_commands.json`:

```bash
cmake -S /mnt/c/Code/CSP/cpsCore \
      -B /mnt/c/Code/CSP/cpsCore/bld/release \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

From PowerShell:

```powershell
wsl.exe -e bash -c "cmake -S /mnt/c/Code/CSP/cpsCore -B /mnt/c/Code/CSP/cpsCore/bld/release -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON 2>&1 | tail -6"
```

## Build

```powershell
# All library targets
wsl.exe -e bash -c "cd /mnt/c/Code/CSP/cpsCore/bld/release && make -j4 2>&1 | tail -5"

# Test binary only (not part of ALL target — must be built explicitly)
wsl.exe -e bash -c "cd /mnt/c/Code/CSP/cpsCore/bld/release && make -j4 tests 2>&1 | tail -5"
```

## Run tests

**IMPORTANT**: The test binary must be run from its own directory (`bld/release/tests/`).
It loads config files (e.g. `Utilities/config/agg1.json`) relative to cwd.
Running from the parent directory causes silent failures with zero output.

```powershell
# Run all tests with names and durations
wsl.exe -e bash -c "cd /mnt/c/Code/CSP/cpsCore/bld/release/tests && ./tests -d yes 2>&1"

# Run and capture output to file
wsl.exe -e bash -c "cd /mnt/c/Code/CSP/cpsCore/bld/release/tests && ./tests -d yes 2>&1 | tee /mnt/c/Code/clang-exp/examples/cpscore_tracing/trace_output.txt"
```

## compile_commands.json

Location: `C:\Code\CSP\cpsCore\bld\release\compile_commands.json`

- 87 entries total (42 src/, 19 tests/, rest extern/)
- Each entry has `file` (WSL path), `directory`, and `command` fields
- Used by `apply_tracing.ps1` to enumerate files for csp_matcher
- WSL path conversion: `/mnt/c/` → `C:/`

Parse in PowerShell:

```powershell
$db = Get-Content "C:\Code\CSP\cpsCore\bld\release\compile_commands.json" -Raw | ConvertFrom-Json
$db | Where-Object { $_.file -match '/src/' } | ForEach-Object { $_.file }
```
