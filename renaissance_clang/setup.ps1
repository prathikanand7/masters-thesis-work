# setup.ps1 — one-shot setup for csp_matcher on Windows
# Run from the repo root:  .\setup.ps1
# Optional parameters:
#   -MingwRoot  path to your MSYS2 mingw64 directory (default C:\msys64\mingw64)
#   -BuildDir   build output directory                (default build_mingw)
#   -SkipBuild  only fix PATH and install packages; do not run cmake/build
param(
    [string] $MingwRoot = "C:\msys64\mingw64",
    [string] $BuildDir  = "build_mingw",
    [switch] $SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── helpers ───────────────────────────────────────────────────────────────────
function Write-Step([string]$msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "    WARN: $msg" -ForegroundColor Yellow }

# ── 1. Verify MSYS2 exists ────────────────────────────────────────────────────
Write-Step "Checking MSYS2 at $MingwRoot"
if (-not (Test-Path $MingwRoot)) {
    Write-Host @"
ERROR: MSYS2 mingw64 directory not found at: $MingwRoot

Install MSYS2 from https://www.msys2.org/ (default: C:\msys64), then re-run this script.
If MSYS2 is installed elsewhere, pass -MingwRoot to this script:
  .\setup.ps1 -MingwRoot "D:\msys64\mingw64"
"@ -ForegroundColor Red
    exit 1
}
Write-Ok "Found $MingwRoot"

# ── 2. Install required MSYS2 packages ───────────────────────────────────────
Write-Step "Installing MSYS2 packages (clang, llvm, ninja)"
$pacman = "$MingwRoot\..\usr\bin\pacman.exe"
if (-not (Test-Path $pacman)) {
    $pacman = "C:\msys64\usr\bin\pacman.exe"
}
if (Test-Path $pacman) {
    $packages = @(
        "mingw-w64-x86_64-clang",
        "mingw-w64-x86_64-llvm",
        "mingw-w64-x86_64-ninja"
    )
    & $pacman -S --needed --noconfirm @packages
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "pacman reported errors — packages may already be up to date."
    } else {
        Write-Ok "Packages installed"
    }
} else {
    Write-Warn "pacman not found at $pacman — skipping package install."
    Write-Warn "Make sure these are installed manually in MSYS2 MinGW64:"
    Write-Warn "  pacman -S mingw-w64-x86_64-clang mingw-w64-x86_64-llvm mingw-w64-x86_64-ninja"
}

# ── 3. Add MinGW bin to PATH for this session ─────────────────────────────────
Write-Step "Updating PATH for this session"
$mingwBin = "$MingwRoot\bin"
if ($env:PATH -notlike "*$mingwBin*") {
    $env:PATH = "$mingwBin;" + $env:PATH
    Write-Ok "Added $mingwBin to PATH (this session)"
} else {
    Write-Ok "$mingwBin already in PATH"
}

# ── 4. Offer to persist PATH permanently ─────────────────────────────────────
$userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$mingwBin*") {
    Write-Host ""
    $answer = Read-Host "Add $mingwBin to your permanent user PATH? [y/N]"
    if ($answer -match '^[Yy]') {
        [System.Environment]::SetEnvironmentVariable(
            "PATH",
            "$mingwBin;" + $userPath,
            "User"
        )
        Write-Ok "Permanent PATH updated. Restart PowerShell to pick it up in new sessions."
    } else {
        Write-Warn "Skipped permanent PATH update. You will need to re-run this script (or set PATH manually) in new sessions."
    }
} else {
    Write-Ok "$mingwBin already in permanent user PATH"
}

# ── 5. Configure and build ────────────────────────────────────────────────────
if (-not $SkipBuild) {
    Write-Step "Configuring with CMake (output: $BuildDir)"
    $repoRoot   = $PSScriptRoot
    $compiler   = "$MingwRoot\bin\clang++.exe"
    $mingwRootF = $MingwRoot -replace '\\', '/'

    cmake -S $repoRoot -B "$repoRoot\$BuildDir" -G Ninja `
        -DCMAKE_BUILD_TYPE=Release `
        "-DCMAKE_CXX_COMPILER=$compiler" `
        "-DMINGW_ROOT=$mingwRootF"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: CMake configure failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Ok "CMake configure succeeded"

    Write-Step "Building"
    cmake --build "$repoRoot\$BuildDir"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Build failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Ok "Build succeeded"
} else {
    Write-Warn "Skipping build (-SkipBuild was set)"
}

# ── 6. Smoke test ─────────────────────────────────────────────────────────────
Write-Step "Smoke test"
$exe = "$PSScriptRoot\$BuildDir\csp_matcher.exe"
if (Test-Path $exe) {
    $p = 'if ( $cond ) { $$body }'
    & $exe --csp $p --find "$PSScriptRoot\tests\find_fixture.cpp"
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "csp_matcher ran successfully"
    } else {
        Write-Warn "csp_matcher exited with code $LASTEXITCODE"
    }
} else {
    Write-Warn "Executable not found at $exe — run without -SkipBuild to build it."
}

Write-Host "`nSetup complete." -ForegroundColor Green
