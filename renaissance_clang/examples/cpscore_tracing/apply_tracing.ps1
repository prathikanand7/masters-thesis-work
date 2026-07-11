# Apply tracing instrumentation to cpsCore.
# Two-pronged approach:
#   1. Use csp_matcher to wrap Aggregator.getAll, CPSLogger.flush, and EnumMap.convert
#      call sites with (std::fprintf([TRACE]...), original_call).
#      CPSLogger.h must be CLEAN (unpatched) when the matcher runs — the preamble
#      includes it, and the Linux-only /mnt/c/... path we inject would break the
#      Windows-side Clang compilation if it were already there.
#   2. Patch CPSLogger.h's CPSLOG(level) macro LAST to emit a [TRACE] line on every
#      logging call (covers all RAIILogStream.stream call sites regardless of TU).
#
# Run from the clang-exp repository root:
#   cd C:\Code\clang-exp
#   .\examples\cpscore_tracing\apply_tracing.ps1
#   .\examples\cpscore_tracing\apply_tracing.ps1 -ExcludeTests
param(
    [switch]$ExcludeTests   # Skip files under .../tests/ in compile_commands.json
)

$env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)

# Log file — records every replacement and patch action for review.
$logFile = "$scriptDir\apply_log.txt"
"=== apply_tracing $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')$(if ($ExcludeTests) { ' [ExcludeTests]' }) ===" | Set-Content $logFile

# ── 1. Run csp_matcher on all .cpp files (CPSLogger.h must be clean here) ──
# Derive the file list from compile_commands.json so the set exactly matches
# what the Linux build compiles (src/ + tests/, no extern/).
$compdbPath = "C:\Code\CSP\cpsCore\bld\release\compile_commands.json"
$compdb = Get-Content $compdbPath -Raw | ConvertFrom-Json
$files = $compdb |
    Where-Object { $_.file -notmatch 'CPSLogger\.cpp' } |
    Where-Object { -not ($ExcludeTests -and $_.file -match '/tests/') } |
    ForEach-Object {
        # Convert WSL path /mnt/c/... to Windows path C:/...
        $winPath = $_.file
        if ($winPath -match '^/mnt/([a-zA-Z])/(.+)$') {
            $winPath = "$($matches[1].ToUpper()):/$($matches[2])"
        }
        [PSCustomObject]@{ FullName = $winPath; Name = (Split-Path $winPath -Leaf) }
    }
$counts = $files | ForEach-Object {
    $exe    = "$root\build_mingw\csp_matcher.exe"
    $script = $scriptDir

    $result = & $exe `
        --pattern-preamble "#include <cpsCore/Logging/CPSLogger.h>`n#include <cpsCore/Aggregation/Aggregator.h>`n#include <cpsCore/Utilities/EnumMap.hpp>`n#include <cpsCore/Synchronization/IRunnableObject.h>`nstatic Aggregator csp_hole_agg;`nusing csp_type_hole_T = IAggregatableObject;`nstatic RunStage csp_hole_stage = RunStage::INIT;" `
        --pattern-flags "-IC:/Code/CSP/cpsCore/include" `
        --pattern-flags "-IC:/msys64/mingw64/include" `
        --pattern-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --find-flags "-IC:/Code/CSP/cpsCore/include" `
        --find-flags "-IC:/msys64/mingw64/include" `
        --find-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --filter-defs "$script\tracing_filters.cpp" `
        --rules "$script\add_tracing.txt" `
        --find $_.FullName 2>&1 | Where-Object { $_ -match "replacements=" }

    if ($result) {
        Write-Host $result
        $result | Add-Content $logFile
        $n = [int]($result -replace '.*replacements=(\d+).*', '$1')
        # Inject csp_trace.h (WSL path — valid at WSL build time) before the first #include.
        $content = Get-Content $_.FullName -Raw
        if ($content -notmatch 'csp_trace\.h') {
            $firstInc = $content.IndexOf('#include')
            if ($firstInc -ge 0) {
                # Use a conditional include so the Windows-side csp_matcher remove
                # pass can find csp_trace.h via -IC:/Code/clang-exp/examples/cpscore_tracing,
                # while the WSL build uses the absolute /mnt/c/... path.
                $content = $content.Substring(0, $firstInc) +
                           "#ifdef __linux__`n#  include `"/mnt/c/Code/clang-exp/examples/cpscore_tracing/csp_trace.h`"`n#else`n#  include `"csp_trace.h`"`n#endif`n" +
                           $content.Substring($firstInc)
            }
            [System.IO.File]::WriteAllText($_.FullName, $content)
        }
        $n
    }
}

$total = "Total replacements: $([int](($counts | Measure-Object -Sum).Sum))"
Write-Host $total
$total | Add-Content $logFile

# ── 2. Patch CPSLogger.h LAST (after csp_matcher has finished) ─────────────
# Patching early would inject a Linux-only path into CPSLogger.h; csp_matcher's
# preamble includes that header, causing a compilation failure on Windows that
# drops type constraints and produces thousands of spurious matches.
$cpslHeader = "C:\Code\CSP\cpsCore\include\cpsCore\Logging\CPSLogger.h"
$hContent = Get-Content $cpslHeader -Raw
if ($hContent -notmatch 'csp_trace\.h') {
    # Inject csp_trace.h include right after the header-guard #define line.
    $guardDef = "#define UAVAP_CORE_LOGGING_CPSLOGGER_H_"
    $pos = $hContent.IndexOf($guardDef)
    if ($pos -ge 0) {
        $after = $pos + $guardDef.Length
        $eol   = $hContent.IndexOf("`n", $after)
        if ($eol -ge 0) {
            $hContent = $hContent.Substring(0, $eol + 1) +
                        "#include `"/mnt/c/Code/clang-exp/examples/cpscore_tracing/csp_trace.h`"`n" +
                        $hContent.Substring($eol + 1)
        }
    }
    # Replace the CPSLOG macro to emit a [TRACE] line before the stream() call.
    $origMacro   = '#define CPSLOG(level) (RAIILogStream(level).stream())'
    $tracedMacro = '#define CPSLOG(level) (std::fprintf(stderr, "[TRACE] %s, %s, %s, RAIILogStream.stream, Logging, %s, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerFunc(__PRETTY_FUNCTION__).c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceCallerClass(__PRETTY_FUNCTION__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), RAIILogStream(level).stream())'
    $hContent = $hContent.Replace($origMacro, $tracedMacro)
    [System.IO.File]::WriteAllText($cpslHeader, $hContent)
    $msg = "file=$cpslHeader patched=CPSLOG"
    Write-Host $msg
    $msg | Add-Content $logFile
}
