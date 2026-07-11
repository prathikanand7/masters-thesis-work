# Remove runtime instrumentation from cpsCore.
# Mirrors apply_tracing.ps1 in reverse:
#   1. Reverts CPSLogger.h's CPSLOG macro to its original form.
#   2. Uses csp_matcher to strip (std::fprintf([TRACE]...), expr) wrappers from .cpp files.
#
# Usage:
#   .\remove_tracing.ps1
#
param(
    [string]$RenaissanceRoot = "C:\Code\clang-exp",
    [string]$CpsCoreRoot = "C:\Code\CSP\cpsCore"
)

# Ensure paths are valid
if (-not (Test-Path "$RenaissanceRoot\build_mingw\csp_matcher.exe")) {
    Write-Error "csp_matcher.exe not found at $RenaissanceRoot\build_mingw\csp_matcher.exe"
    exit 1
}

$env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = "$RenaissanceRoot\build_mingw\csp_matcher.exe"

# Compute WSL-form of the skill scripts dir (matches the path injected by apply_tracing.ps1)
$wslScriptDir = ($scriptDir -replace '^([A-Za-z]):\\', { '/mnt/' + $_.Groups[1].Value.ToLower() + '/' }) -replace '\\', '/'

# ── 1. Revert CPSLogger.h ──────────────────────────────────────────────────
$cpslHeader = "$CpsCoreRoot\include\cpsCore\Logging\CPSLogger.h"
$hContent = Get-Content $cpslHeader -Raw
if ($hContent -match 'csp_trace\.h') {
    # Remove the csp_trace.h include line (whatever path was injected)
    $hContent = $hContent -replace '#include "[^"]+/csp_trace\.h"\r?\n', ''
    $tracedMacro = '#define CPSLOG(level) (std::fprintf(stderr, "[TRACE] %s, %s, %s, RAIILogStream.stream, Logging, %s, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerFunc(__PRETTY_FUNCTION__).c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceCallerClass(__PRETTY_FUNCTION__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), RAIILogStream(level).stream())'
    $origMacro   = '#define CPSLOG(level) (RAIILogStream(level).stream())'
    $hContent = $hContent.Replace($tracedMacro, $origMacro)
    [System.IO.File]::WriteAllText($cpslHeader, $hContent)
    Write-Host "file=$cpslHeader reverted=CPSLOG"
}

# ── 2. Strip [TRACE] wrappers from .cpp files ──────────────────────────────
$files = @(Get-ChildItem -Recurse $CpsCoreRoot/src -Filter *.cpp -ErrorAction SilentlyContinue) +
         @(Get-ChildItem -Recurse $CpsCoreRoot/tests -Filter *.cpp -ErrorAction SilentlyContinue) |
         Where-Object { $_.Name -ne "CPSLogger.cpp" }

$counts = $files | ForEach-Object {
    $result = & $exe `
        --pattern-preamble "#include <cstdio>" `
        --pattern-flags "-I$CpsCoreRoot/include" `
        --pattern-flags "-IC:/msys64/mingw64/include" `
        --pattern-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --find-flags "-I$CpsCoreRoot/include" `
        --find-flags "-IC:/msys64/mingw64/include" `
        --find-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --find-flags "-I$scriptDir" `
        --filter-defs "$scriptDir\tracing_filters.cpp" `
        --rules "$scriptDir\remove_tracing.txt" `
        --find $_.FullName 2>&1 | Where-Object { $_ -match "replacements=" }

    if ($result) {
        Write-Host $result
        $content = Get-Content $_.FullName -Raw
        # Strip the cross-platform ifdef block
        $content = $content -replace '#ifdef __linux__\r?\n#  include "[^"]+"\r?\n#else\r?\n#  include "csp_trace\.h"\r?\n#endif\r?\n', ''
        [System.IO.File]::WriteAllText($_.FullName, $content)
        [int]($result -replace '.*replacements=(\d+).*', '$1')
    }
}

$total = "Total replacements: $([int](($counts | Measure-Object -Sum).Sum))"
Write-Host $total

Write-Host ""
Write-Host "=== Instrumentation removed successfully ==="
Write-Host "You may need to rebuild: cmake --build $CpsCoreRoot\bld\release --target all -j"
