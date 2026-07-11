# Apply runtime instrumentation to cpsCore using the renaissance_clang DSL tool.
#
# Two-pronged approach:
#   1. Use csp_matcher to wrap function call sites with trace emissions
#      (std::fprintf([TRACE]...), original_call).
#      CPSLogger.h must be CLEAN (unpatched) when the matcher runs.
#   2. Patch CPSLogger.h's CPSLOG(level) macro LAST to emit a [TRACE] line on every
#      logging call (covers all RAIILogStream.stream call sites).
#
# Usage:
#   .\apply_tracing.ps1
#   .\apply_tracing.ps1 -ExcludeTests
#
param(
    [string]$RenaissanceRoot = "C:\Code\clang-exp",
    [string]$CpsCoreRoot = "C:\Code\CSP\cpsCore",
    [string]$BuildSubdir = "bld\release",   # subdir containing compile_commands.json
    [switch]$ExcludeTests
)

# Ensure paths are valid
if (-not (Test-Path "$RenaissanceRoot\build_mingw\csp_matcher.exe")) {
    Write-Error "csp_matcher.exe not found at $RenaissanceRoot\build_mingw\csp_matcher.exe"
    Write-Error "Ensure renaissance_clang project is built. Run: cd $RenaissanceRoot && .\setup.ps1"
    exit 1
}

if (-not (Test-Path "$CpsCoreRoot\$BuildSubdir\compile_commands.json")) {
    Write-Error "compile_commands.json not found. Configure cpsCore first:"
    Write-Error "  cmake -S $CpsCoreRoot -B $CpsCoreRoot\$BuildSubdir -DCMAKE_BUILD_TYPE=Release -DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
    exit 1
}

$env:PATH = "C:\msys64\mingw64\bin;" + $env:PATH
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = "$RenaissanceRoot\build_mingw\csp_matcher.exe"

# Compute WSL-form of the skill scripts dir (csp_trace.h lives there)
$wslScriptDir = ($scriptDir -replace '^([A-Za-z]):\\', { '/mnt/' + $_.Groups[1].Value.ToLower() + '/' }) -replace '\\', '/'

# Log file
$logFile = "$scriptDir\apply_log.txt"
"=== apply_tracing $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')$(if ($ExcludeTests) { ' [ExcludeTests]' }) ===" | Set-Content $logFile

# ── 1. Run csp_matcher on all .cpp files (CPSLogger.h must be clean here) ──
$compdbPath = "$CpsCoreRoot\$BuildSubdir\compile_commands.json"
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
    $result = & $exe `
        --pattern-preamble "#include <cpsCore/Logging/CPSLogger.h>`n#include <cpsCore/Aggregation/Aggregator.h>`n#include <cpsCore/Utilities/EnumMap.hpp>`n#include <cpsCore/Synchronization/IRunnableObject.h>`nstatic Aggregator csp_hole_agg;`nusing csp_type_hole_T = IAggregatableObject;`nstatic RunStage csp_hole_stage = RunStage::INIT;" `
        --pattern-flags "-I$CpsCoreRoot/include" `
        --pattern-flags "-IC:/msys64/mingw64/include" `
        --pattern-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --find-flags "-I$CpsCoreRoot/include" `
        --find-flags "-IC:/msys64/mingw64/include" `
        --find-flags "-IC:/msys64/mingw64/lib/gcc/x86_64-w64-mingw32/16.1.0/include" `
        --filter-defs "$scriptDir\tracing_filters.cpp" `
        --rules "$scriptDir\add_tracing.txt" `
        --find $_.FullName 2>&1 | Where-Object { $_ -match "replacements=" }

    if ($result) {
        Write-Host $result
        $result | Add-Content $logFile
        $n = [int]($result -replace '.*replacements=(\d+).*', '$1')
        
        # Inject csp_trace.h before the first #include
        $content = Get-Content $_.FullName -Raw
        if ($content -notmatch 'csp_trace\.h') {
            $firstInc = $content.IndexOf('#include')
            if ($firstInc -ge 0) {
                $content = $content.Substring(0, $firstInc) +
                           "#ifdef __linux__`n#  include `"$wslScriptDir/csp_trace.h`"`n#else`n#  include `"csp_trace.h`"`n#endif`n" +
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

# ── 2. Patch CPSLogger.h LAST ──────────────────────────────────────────────
$cpslHeader = "$CpsCoreRoot\include\cpsCore\Logging\CPSLogger.h"
$hContent = Get-Content $cpslHeader -Raw
if ($hContent -notmatch 'csp_trace\.h') {
    $guardDef = "#define UAVAP_CORE_LOGGING_CPSLOGGER_H_"
    $pos = $hContent.IndexOf($guardDef)
    if ($pos -ge 0) {
        $after = $pos + $guardDef.Length
        $eol   = $hContent.IndexOf("`n", $after)
        if ($eol -ge 0) {
            $hContent = $hContent.Substring(0, $eol + 1) +
                        "#include `"$wslScriptDir/csp_trace.h`"`n" +
                        $hContent.Substring($eol + 1)
        }
    }
    
    # Replace the CPSLOG macro
    $origMacro   = '#define CPSLOG(level) (RAIILogStream(level).stream())'
    $tracedMacro = '#define CPSLOG(level) (std::fprintf(stderr, "[TRACE] %s, %s, %s, RAIILogStream.stream, Logging, %s, %s\n", cspTraceTimestamp().c_str(), cspTraceCallerFunc(__PRETTY_FUNCTION__).c_str(), cspTraceCallerComponent(__FILE__).c_str(), cspTraceCallerClass(__PRETTY_FUNCTION__).c_str(), cspTraceLocation(__FILE__, __LINE__).c_str()), RAIILogStream(level).stream())'
    $hContent = $hContent.Replace($origMacro, $tracedMacro)
    [System.IO.File]::WriteAllText($cpslHeader, $hContent)
    
    $msg = "file=$cpslHeader patched=CPSLOG"
    Write-Host $msg
    $msg | Add-Content $logFile
}

Write-Host "=== Instrumentation applied successfully ==="
Write-Host "Next steps:"
Write-Host "  1. Rebuild cpsCore: cmake --build $CpsCoreRoot\bld\release --target all -j"
Write-Host "  2. Run tests:       cd $CpsCoreRoot\bld\release\tests && .\tests"
Write-Host "  3. Trace output will be written to stderr"
Write-Host ""
Write-Host "To remove instrumentation: .\remove_tracing.ps1 -RenaissanceRoot $RenaissanceRoot -CpsCoreRoot $CpsCoreRoot"
