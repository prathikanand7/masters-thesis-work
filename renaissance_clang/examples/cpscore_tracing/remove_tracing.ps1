# Remove tracing instrumentation from cpsCore.
# Mirrors apply_tracing.ps1 in reverse:
#   1. Reverts CPSLogger.h's CPSLOG macro to its original form.
#   2. Uses csp_matcher to strip (std::fprintf([TRACE]...), expr) wrappers from .cpp files.
#
# Run from the clang-exp repository root:
#   cd C:\Code\clang-exp
#   .\examples\cpscore_tracing\remove_tracing.ps1

$env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)

# ── 1. Revert CPSLogger.h ──────────────────────────────────────────────────
$cpslHeader = "C:\Code\CSP\cpsCore\include\cpsCore\Logging\CPSLogger.h"
$hContent = Get-Content $cpslHeader -Raw
if ($hContent -match 'csp_trace\.h') {
    $hContent = $hContent.Replace(
        "#include `"/mnt/c/Code/clang-exp/examples/cpscore_tracing/csp_trace.h`"`n",
        "")
    $tracedMacro = '#define CPSLOG(level) (std::fprintf(stderr, "[TRACE] %s, %s, %s, RAIILogStream.stream, Logging, %s, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerFunc(__PRETTY_FUNCTION__).c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceCallerClass(__PRETTY_FUNCTION__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), RAIILogStream(level).stream())'
    $origMacro   = '#define CPSLOG(level) (RAIILogStream(level).stream())'
    $hContent = $hContent.Replace($tracedMacro, $origMacro)
    [System.IO.File]::WriteAllText($cpslHeader, $hContent)
    Write-Host "file=$cpslHeader reverted=CPSLOG"
}

# ── 2. Strip [TRACE] wrappers from .cpp files ──────────────────────────────
$files = @(Get-ChildItem -Recurse C:/Code/CSP/cpsCore/src -Filter *.cpp) +
         @(Get-ChildItem -Recurse C:/Code/CSP/cpsCore/tests -Filter *.cpp) |
         Where-Object { $_.Name -ne "CPSLogger.cpp" }

$counts = $files | ForEach-Object {
    $exe    = "$root\build_mingw\csp_matcher.exe"
    $script = $scriptDir

    $result = & $exe `
        --pattern-preamble "#include <cstdio>" `
        --pattern-flags "-IC:/Code/CSP/cpsCore/include" `
        --pattern-flags "-IC:/msys64/mingw64/include" `
        --pattern-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --find-flags "-IC:/Code/CSP/cpsCore/include" `
        --find-flags "-IC:/msys64/mingw64/include" `
        --find-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --find-flags "-IC:/Code/clang-exp/examples/cpscore_tracing" `
        --filter-defs "$script\tracing_filters.cpp" `
        --rules "$script\remove_tracing.txt" `
        --find $_.FullName 2>&1 | Where-Object { $_ -match "replacements=" }

    if ($result) {
        Write-Host $result
        $content = Get-Content $_.FullName -Raw
        # Strip the cross-platform ifdef block injected by apply_tracing.ps1
        $content = $content -replace '#ifdef __linux__\r?\n#  include "[^"]+"\r?\n#else\r?\n#  include "csp_trace\.h"\r?\n#endif\r?\n', ''
        [System.IO.File]::WriteAllText($_.FullName, $content)
        [int]($result -replace '.*replacements=(\d+).*', '$1')
    }
}

Write-Host "Total replacements: $([int](($counts | Measure-Object -Sum).Sum))"

