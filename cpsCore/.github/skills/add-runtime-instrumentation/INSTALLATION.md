# Installation and Setup Guide

## Overview

The **add-runtime-instrumentation** skill is now integrated into cpsCore at:

```
cpsCore/.github/skills/add-runtime-instrumentation/
├── SKILL.md                    # Comprehensive skill documentation
├── README.md                   # Quick start guide
├── CONFIGURATION.md            # Configuration and customization
├── EXAMPLES.md                 # Practical usage examples
├── INSTALLATION.md             # This file
├── package.json                # Metadata
└── scripts/
    ├── apply_tracing.ps1       # Apply instrumentation (PowerShell)
    ├── remove_tracing.ps1      # Remove instrumentation (PowerShell)
    ├── invoke_instrumentation.py # Python wrapper for agent invocation
    ├── add_tracing.txt         # Default pattern matching rules
    ├── remove_tracing.txt      # Pattern for removing traces
    ├── tracing_filters.cpp     # Custom filter logic (C++)
    └── csp_trace.h             # Trace helper functions (header)
```

## Prerequisites

Before using the skill, ensure you have:

### 1. Renaissance Clang Project (with csp_matcher)

**Location:** `C:\Code\clang-exp` (or custom path)

**Verification:**
```powershell
Test-Path "C:\Code\clang-exp\build_mingw\csp_matcher.exe"
```

**If not found:**
```powershell
cd C:\Code\clang-exp
.\setup.ps1
```

### 2. cpsCore CMake Configuration

**Location:** `C:\Code\CSP\cpsCore\bld\release\compile_commands.json`

**Verification:**
```powershell
Test-Path "C:\Code\CSP\cpsCore\bld\release\compile_commands.json"
```

**If not found:**
```bash
# On Windows, in PowerShell:
wsl -e bash -c "cd /mnt/c/Code/CSP/cpsCore && cmake -S . -B bld/release -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON"

# Or directly in WSL:
cmake -S /mnt/c/Code/CSP/cpsCore \
      -B /mnt/c/Code/CSP/cpsCore/bld/release \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
```

### 3. Dependencies

- **PowerShell 5.0+** (for executing .ps1 scripts)
- **Python 3.6+** (optional, for Python wrapper invocation)
- **MSys64/MinGW64** (for build tools)
  - Should be in PATH, or scripts will add it: `C:\msys64\mingw64\bin\`
- **cpsCore source code** in expected location

## Installation Steps

### Step 1: Clone/Download the Skill

The skill files are now part of cpsCore repository at:
```
.github/skills/add-runtime-instrumentation/
```

No separate installation needed—the files are already in place.

### Step 2: Set File Permissions (Linux/WSL)

If running on Linux or from within WSL, ensure scripts are executable:

```bash
chmod +x /mnt/c/Users/prathikak/Documents/cpsCore/.github/skills/add-runtime-instrumentation/scripts/*.ps1
chmod +x /mnt/c/Users/prathikak/Documents/cpsCore/.github/skills/add-runtime-instrumentation/scripts/*.py
```

### Step 3: Verify Paths in Scripts

Check that hardcoded paths in scripts match your environment:

**In `apply_tracing.ps1` and `remove_tracing.ps1`:**

```powershell
# Default paths (configurable via parameters)
$RenaissanceRoot = "C:\Code\clang-exp"
$CpsCoreRoot = "C:\Code\CSP\cpsCore"
```

If your paths differ, either:
1. Edit the defaults in the scripts, OR
2. Pass custom paths as parameters when invoking

### Step 4: Create Workspace Alias (Optional)

For convenience, create a PowerShell alias in your profile:

```powershell
# Open PowerShell profile
notepad $PROFILE

# Add this line:
Set-Alias -Name applyTracing -Value "C:\Users\prathikak\Documents\cpsCore\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1"
Set-Alias -Name removeTracing -Value "C:\Users\prathikak\Documents\cpsCore\.github\skills\add-runtime-instrumentation\scripts\remove_tracing.ps1"

# Save and reload profile
. $PROFILE
```

Then use:
```powershell
applyTracing
removeTracing -ExcludeTests
```

## Quick Verification

Run these steps to verify everything is set up correctly:

```powershell
# 1. Check prerequisites
$prereqs = @{
    "csp_matcher.exe"        = "C:\Code\clang-exp\build_mingw\csp_matcher.exe"
    "compile_commands.json"  = "C:\Code\CSP\cpsCore\bld\release\compile_commands.json"
    "apply_tracing.ps1"      = ".\scripts\apply_tracing.ps1"
    "remove_tracing.ps1"     = ".\scripts\remove_tracing.ps1"
    "add_tracing.txt"        = ".\scripts\add_tracing.txt"
    "csp_trace.h"            = ".\scripts\csp_trace.h"
}

# Navigate to skill root
cd "C:\Users\prathikak\Documents\cpsCore\.github\skills\add-runtime-instrumentation"

# Verify files
foreach ($name in $prereqs.Keys) {
    $path = $prereqs[$name]
    $exists = Test-Path $path
    Write-Host "$name : $(if ($exists) { 'OK' } else { 'MISSING' })"
}

# 2. Test with --ExcludeTests (faster)
Write-Host ""
Write-Host "Ready to apply instrumentation!"
Write-Host "Run: .\scripts\apply_tracing.ps1 -ExcludeTests"
```

## Usage

Once installed, using the skill is straightforward:

### From PowerShell

```powershell
cd C:\Users\prathikak\Documents\cpsCore

# Apply default instrumentation
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1

# Or with options
.\.github\skills\add-runtime-instrumentation\scripts\apply_tracing.ps1 -ExcludeTests

# Remove instrumentation
.\.github\skills\add-runtime-instrumentation\scripts\remove_tracing.ps1
```

### From Python (Agent Invocation)

```bash
cd cpsCore/.github/skills/add-runtime-instrumentation

# Apply instrumentation
python scripts/invoke_instrumentation.py apply

# Apply excluding tests
python scripts/invoke_instrumentation.py apply --exclude-tests

# Remove instrumentation
python scripts/invoke_instrumentation.py remove
```

### From VS Code Task

Create a VS Code task in `.vscode/tasks.json`:

```json
{
    "label": "Apply Runtime Instrumentation",
    "type": "shell",
    "command": "powershell",
    "args": [
        "-NoProfile",
        "-File",
        ".github/skills/add-runtime-instrumentation/scripts/apply_tracing.ps1"
    ],
    "group": "build",
    "presentation": {
        "reveal": "always"
    }
}
```

Then run via `Ctrl+Shift+B` → "Apply Runtime Instrumentation"

## Configuration

Before applying instrumentation, consider customizing:

### 1. Tracing Rules

Edit `.github/skills/add-runtime-instrumentation/scripts/add_tracing.txt` to add/modify patterns.

See [CONFIGURATION.md](CONFIGURATION.md) for syntax and examples.

### 2. Custom Filters

Edit `.github/skills/add-runtime-instrumentation/scripts/tracing_filters.cpp` for advanced matching logic.

Requires rebuilding renaissance_clang if you modify filters.

### 3. Paths

Update default paths in PowerShell scripts if your setup differs from standard locations.

## First Run Checklist

Before your first instrumentation:

- [ ] csp_matcher.exe is built and accessible
- [ ] compile_commands.json exists in cpsCore build directory
- [ ] Your cpsCore source files are unmodified (clean git state recommended)
- [ ] MSys64/MinGW64 tools are in PATH
- [ ] PowerShell 5.0+ available
- [ ] You have read access to cpsCore source files
- [ ] You have write permissions to modify cpsCore files (can be reverted with remove_tracing.ps1)

## Troubleshooting Installation

### PowerShell execution policy error

**Error:** `cannot be loaded because running scripts is disabled on this system`

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### csp_matcher.exe not found

**Solution:**
```powershell
# Build renaissance_clang
cd C:\Code\clang-exp
.\setup.ps1
```

### compile_commands.json not found

**Solution:**
Follow the CMake configuration steps above.

### Path not found errors

**Solution:**
Check that default paths in scripts match your environment, or pass custom paths:
```powershell
.\scripts\apply_tracing.ps1 -RenaissanceRoot "YOUR_PATH\renaissance_clang" -CpsCoreRoot "YOUR_PATH\cpsCore"
```

## Next Steps

1. Read [README.md](README.md) for quick start
2. Try [EXAMPLES.md](EXAMPLES.md) for practical usage patterns
3. Review [CONFIGURATION.md](CONFIGURATION.md) for customization
4. See [SKILL.md](SKILL.md) for comprehensive documentation

## Support

For issues or questions:

1. Check the **Troubleshooting** sections in relevant documentation
2. Verify prerequisites are correctly installed
3. Review apply_log.txt after running for diagnostic information
4. Ensure cpsCore source files are in a clean state (commit changes first)

## Integration with cpsCore Workflow

### Recommended Workflow

```
1. Modify cpsCore source → commit changes
2. Apply instrumentation → rebuild → test → analyze
3. Remove instrumentation → rebuild → verify (optional)
4. Continue with next development cycle
```

### Keeping Changes Reversible

All changes made by the skill are fully reversible:

```powershell
# Apply
.\scripts\apply_tracing.ps1

# ... test, analyze ...

# Remove (completely reversible)
.\scripts\remove_tracing.ps1

# Files return to original state
```

## Advanced Integration

The PowerShell scripts support parameterized paths and can be integrated into:

- CI/CD pipelines (GitHub Actions, Jenkins, etc.)
- Custom build scripts
- Agent-based automation
- Development workflows

See [EXAMPLES.md](EXAMPLES.md) for CI/CD integration examples.
