param(
  [string]$ExePath = "./build_mingw/csp_matcher.exe",
  [string]$ReportPath = "./tests/csp_suite_report.md",
  [switch]$StrictAll
)

if (-not (Test-Path $ExePath)) {
  Write-Error "Generator not found at $ExePath. Build first."
  exit 2
}

function Get-FirstNonEmptyLine {
  param([string]$Text)

  $firstLine = ($Text -split "`r?`n" | Where-Object { $_.Trim().Length -gt 0 } | Select-Object -First 1)
  if (-not $firstLine) {
    return "<no output>"
  }
  return $firstLine.Trim()
}

function Get-PreviewLine {
  param(
    [string]$Text,
    [string[]]$ArgList
  )

  $lines = $Text -split "`r?`n"
  $skipMetadata = ($ArgList -contains "--replace")
  foreach ($line in $lines) {
    $trimmed = $line.Trim()
    if ($trimmed.Length -eq 0) {
      continue
    }
    if ($skipMetadata -and $trimmed.StartsWith("file=")) {
      continue
    }
    return $trimmed
  }

  return Get-FirstNonEmptyLine -Text $Text
}

function Escape-MarkdownCell {
  param([string]$Text)

  if ($null -eq $Text) {
    return ""
  }

  $escaped = $Text
  $escaped = $escaped.Replace("\\", "\\\\")
  $escaped = $escaped.Replace("|", "\\|")
  $escaped = $escaped.Replace("`r", "")
  $escaped = $escaped.Replace("`n", " <br> ")
  $escaped = $escaped.Replace('$', '\$')
  return $escaped
}

function ConvertTo-SafePathPart {
  param([string]$Text)

  if ([string]::IsNullOrWhiteSpace($Text)) {
    return "unnamed"
  }

  return ([regex]::Replace($Text, '[^A-Za-z0-9._-]+', '_')).Trim('_')
}

function Write-CaseArtifact {
  param(
    [string]$SuiteName,
    [string]$CaseName,
    [string]$Output,
    [string[]]$ArgList = @(),
    [string]$CommandText = "",
    [string]$InputText = "",
    [string]$InputFileName = "input.txt"
  )

  $suiteDir = Join-Path $artifactRoot (ConvertTo-SafePathPart -Text $SuiteName)
  $caseDir = Join-Path $suiteDir (ConvertTo-SafePathPart -Text $CaseName)
  if (-not (Test-Path $caseDir)) {
    New-Item -ItemType Directory -Path $caseDir -Force | Out-Null
  }

  if (-not [string]::IsNullOrEmpty($CommandText)) {
    Set-Content -Path (Join-Path $caseDir "command.txt") -Encoding ascii -Value $CommandText
  }

  Set-Content -Path (Join-Path $caseDir "output.txt") -Encoding ascii -Value $Output

  if (-not [string]::IsNullOrEmpty($InputText)) {
    Set-Content -Path (Join-Path $caseDir $InputFileName) -Encoding ascii -Value $InputText
  }

  $findPaths = Get-FindPathsFromArgs -ArgList $ArgList
  if ($findPaths.Count -gt 0) {
    $inputsDir = Join-Path $caseDir "inputs"
    if (-not (Test-Path $inputsDir)) {
      New-Item -ItemType Directory -Path $inputsDir -Force | Out-Null
    }

    for ($index = 0; $index -lt $findPaths.Count; ++$index) {
      $findPath = $findPaths[$index]
      if (-not (Test-Path $findPath)) {
        continue
      }

      $leaf = Split-Path -Path $findPath -Leaf
      $safeLeaf = ConvertTo-SafePathPart -Text $leaf
      $targetName = "{0:D2}_{1}" -f ($index + 1), $safeLeaf
      $sourceText = Get-Content -Path $findPath -Raw
      Set-Content -Path (Join-Path $inputsDir $targetName) -Encoding ascii -Value $sourceText
      Set-Content -Path (Join-Path $inputsDir ("{0:D2}_source_path.txt" -f ($index + 1))) -Encoding ascii -Value $findPath
    }
  }
}

function Get-FindPathsFromArgs {
  param([string[]]$ArgList)

  $paths = @()
  for ($i = 0; $i -lt $ArgList.Count; ++$i) {
    if ($ArgList[$i] -eq "--find" -and ($i + 1) -lt $ArgList.Count) {
      $paths += $ArgList[$i + 1]
      ++$i
    }
  }
  return ,@($paths)
}

function Get-DbPaths {
  param([string[]]$ArgList)

  $paths = @()
  for ($i = 0; $i -lt $ArgList.Count; ++$i) {
    if ($ArgList[$i] -eq "--db" -and ($i + 1) -lt $ArgList.Count) {
      $dbPath = $ArgList[$i + 1]
      if (Test-Path $dbPath) {
        try {
          $entries = Get-Content -Path $dbPath -Raw | ConvertFrom-Json
          foreach ($entry in $entries) {
            if ($null -ne $entry.file) { $paths += $entry.file }
          }
        } catch { }
      }
      ++$i
    }
  }
  return ,@($paths)
}

function Invoke-GeneratorCase {
  param(
    [string]$SuiteName,
    [string]$Name,
    [string[]]$ArgList,
    [int]$ExpectedExit,
    [string[]]$MustContain = @(),
    [string[]]$MustNotContain = @(),
    [switch]$HasReplacement
  )

  $isReplacement = ($ArgList -contains "--replace") -or $HasReplacement
  # For replacement: snapshot originals so we can restore them after the run,
  # keeping every fixture file pristine for subsequent tests.
  $findPaths = @()
  $snapshots = [ordered]@{}
  if ($isReplacement) {
    $fpFind = Get-FindPathsFromArgs -ArgList $ArgList
    $fpDb   = Get-DbPaths -ArgList $ArgList
    $findPaths = @($fpFind) + @($fpDb)
    foreach ($fp in $findPaths) {
      if (Test-Path $fp) {
        $snapshots[$fp] = Get-Content -Path $fp -Raw
      }
    }
  }

  $output   = & $ExePath @ArgList 2>&1 | Out-String
  $exitCode = $LASTEXITCODE

  if ($isReplacement) {
    # Append the (now in-place-modified) file content so MustContain checks work.
    foreach ($fp in $snapshots.Keys) {
      if (Test-Path $fp) {
        $output += (Get-Content -Path $fp -Raw)
      }
    }
    # Save pre-run snapshots as artifacts, then restore each file.
    $suiteDir  = Join-Path $artifactRoot (ConvertTo-SafePathPart -Text $SuiteName)
    $caseDir   = Join-Path $suiteDir     (ConvertTo-SafePathPart -Text $Name)
    $inputsDir = Join-Path $caseDir "inputs"
    New-Item -ItemType Directory -Path $inputsDir -Force | Out-Null
    $idx = 0
    foreach ($fp in $snapshots.Keys) {
      ++$idx
      $leaf = Split-Path $fp -Leaf
      $saveName = "{0:D2}_{1}" -f $idx, (ConvertTo-SafePathPart -Text $leaf)
      Set-Content -Path (Join-Path $inputsDir $saveName) -Encoding ascii -Value $snapshots[$fp]
      Set-Content -Path (Join-Path $inputsDir ("{0:D2}_source_path.txt" -f $idx)) -Encoding ascii -Value $fp
      Set-Content -Path $fp -Encoding ascii -Value $snapshots[$fp]
    }
  }

  $pass = ($exitCode -eq $ExpectedExit)
  foreach ($needle in $MustContain) {
    if (-not $output.Contains($needle)) {
      $pass = $false
      break
    }
  }

  if ($pass) {
    foreach ($needle in $MustNotContain) {
      if ($output.Contains($needle)) {
        $pass = $false
        break
      }
    }
  }

  $argsText = ($ArgList -join " ")
  $artifactArgList = if ($isReplacement) { @() } else { $ArgList }
  Write-CaseArtifact -SuiteName $SuiteName `
    -CaseName $Name `
    -Output $output `
    -ArgList $artifactArgList `
    -CommandText "$ExePath $argsText"

  return [pscustomobject]@{
    Name       = $Name
    Command    = "$ExePath $argsText"
    ExpectExit = $ExpectedExit
    ActualExit = $exitCode
    Pass       = if ($pass) { "PASS" } else { "FAIL" }
    FirstLine  = (Get-PreviewLine -Text $output -ArgList $ArgList)
  }
}

$generatedDir = "tests/generated"
if (-not (Test-Path $generatedDir)) {
  New-Item -ItemType Directory -Path $generatedDir | Out-Null
}

$artifactRoot = "$generatedDir/case_artifacts"
if (Test-Path $artifactRoot) {
  Remove-Item -Path $artifactRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $artifactRoot | Out-Null

$generatedDescPath = "$generatedDir/replace_desc_input.cpp"
$generatedExprPath = "$generatedDir/replace_expr_input.cpp"
$generatedFuncPath = "$generatedDir/replace_func_input.cpp"
$generatedSamplePath = "$generatedDir/replace_sample_input.cpp"

Set-Content -Path $generatedDescPath -Encoding ascii -Value @'
int run_desc(int x, int y) {
  if (x) {
    if (y) {
      x += 3;
    }
    x = 1;
  }

  if (x) {
    x = 1;
  }

  return x;
}
'@

Set-Content -Path $generatedExprPath -Encoding ascii -Value @'
int run_expr(int a, int b) {
  if (a && b) {
    a += b;
  }

  if (a) {
    a++;
  }

  return a;
}
'@

Set-Content -Path $generatedFuncPath -Encoding ascii -Value @'
int foo(int p) {
  return p + 1;
}

int bar(int q) {
  return q + 2;
}
'@

Set-Content -Path $generatedSamplePath -Encoding ascii -Value @'
int main() {
  int x = 0;
  if (x) { x++; }
  if (x) { x += 2; }
  return x;
}
'@

# ── Compilation-database fixtures ────────────────────────────────────────────
# Use absolute forward-slash paths so the C++ parser resolves them on all hosts.
$generatedCompdbPath      = "$generatedDir/test_compdb.json"
$generatedCompdbDedupPath = "$generatedDir/test_compdb_dedup.json"

$absSamplePath  = (Resolve-Path $generatedSamplePath).Path  -replace '\\', '/'
$absFixturePath = (Resolve-Path "tests/find_fixture.cpp").Path -replace '\\', '/'

# Two-file compdb: replace_sample_input.cpp + find_fixture.cpp
Set-Content -Path $generatedCompdbPath -Encoding ascii -Value @"
[
  {"directory": ".", "command": "clang++ -std=c++17 -c", "file": "$absSamplePath"},
  {"directory": ".", "command": "clang++ -std=c++17 -c", "file": "$absFixturePath"}
]
"@

# Dedup compdb: replace_sample_input.cpp listed twice (different flags)
Set-Content -Path $generatedCompdbDedupPath -Encoding ascii -Value @"
[
  {"directory": ".", "command": "clang++ -std=c++17 -c",    "file": "$absSamplePath"},
  {"directory": ".", "command": "clang++ -std=c++17 -O2 -c", "file": "$absSamplePath"}
]
"@

# ── Rules-file fixtures ───────────────────────────────────────────────────────
$rulesPathSingleFind      = "$generatedDir/test_rules_single_find.txt"
$rulesPathFindReplace     = "$generatedDir/test_rules_find_replace.txt"
$rulesPathMulti           = "$generatedDir/test_rules_multi.txt"
$rulesPathMultiReplace    = "$generatedDir/test_rules_multi_replace.txt"
$rulesPathWithComments    = "$generatedDir/test_rules_with_comments.txt"
$rulesPathEmpty           = "$generatedDir/test_rules_empty.txt"
$rulesPathBadReplaceOrder = "$generatedDir/test_rules_bad_replace_order.txt"
$rulesPathBadLine         = "$generatedDir/test_rules_bad_line.txt"
$rulesPathEmptyPattern    = "$generatedDir/test_rules_empty_pattern.txt"
$rulesPathSecond          = "$generatedDir/test_rules_second.txt"

Set-Content -Path $rulesPathSingleFind -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
'@

Set-Content -Path $rulesPathFindReplace -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
replace: if ( !($cond) ) { $$body }
'@

Set-Content -Path $rulesPathMulti -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
find: return $x;
'@

Set-Content -Path $rulesPathMultiReplace -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
replace: if ( !($cond) ) { $$body }
find: return $x;
'@

Set-Content -Path $rulesPathWithComments -Encoding ascii -Value @'
# This is a comment
find: if ( $cond ) { $$body }

# Replacement follows
replace: if ( !($cond) ) { $$body }
'@

Set-Content -Path $rulesPathEmpty -Encoding ascii -Value @'
# No patterns defined here
# Just comments and blank lines
'@

Set-Content -Path $rulesPathBadReplaceOrder -Encoding ascii -Value @'
replace: if ( !($cond) ) { $$body }
find: if ( $cond ) { $$body }
'@

Set-Content -Path $rulesPathBadLine -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
unrecognised garbage line
'@

Set-Content -Path $rulesPathEmptyPattern -Encoding ascii -Value @'
find:
'@

Set-Content -Path $rulesPathSecond -Encoding ascii -Value @'
find: return $x;
'@

# ── Filter-related rules-file fixtures ───────────────────────────────────────
$rulesPathWithFilter       = "$generatedDir/test_rules_with_filter.txt"
$rulesPathWithFilterReject = "$generatedDir/test_rules_with_filter_reject.txt"
$rulesPathFilterBeforeFind = "$generatedDir/test_rules_filter_before_find.txt"
$rulesPathFilterEmpty      = "$generatedDir/test_rules_filter_empty_expr.txt"

# ── Remove-related rules-file fixtures ───────────────────────────────────────
$rulesPathWithRemove = "$generatedDir/test_rules_with_remove.txt"
$removeInputPath     = "$generatedDir/remove_input.cpp"
$removeInputPath2    = "$generatedDir/remove_input2.cpp"

Set-Content -Path $rulesPathWithRemove -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
remove:
'@

Set-Content -Path $removeInputPath -Encoding ascii -Value @'
int main() { int x = 0; if (x) { x++; } if (x) { x += 2; } return x; }
'@

Set-Content -Path $removeInputPath2 -Encoding ascii -Value @'
int main() { int x = 0; if (x) { x++; } if (x) { x += 2; } return x; }
'@

Set-Content -Path $rulesPathWithFilter -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
filter: accept_all
'@

Set-Content -Path $rulesPathWithFilterReject -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
filter: reject_all
'@

Set-Content -Path $rulesPathFilterBeforeFind -Encoding ascii -Value @'
filter: accept_all
find: if ( $cond ) { $$body }
'@

Set-Content -Path $rulesPathFilterEmpty -Encoding ascii -Value @'
find: if ( $cond ) { $$body }
filter:
'@

$cases = @(
  @{ Name = "if_or_two_expr_holes"; Csp = 'if ( $cond0 || $cond1 ) { $$body1 }'; ExpectSuccess = $true },
  @{ Name = "decl_function_template_like"; Csp = '$type $function ( $$params ) { $$body }'; ExpectSuccess = $true },
  @{ Name = "simple_assignment"; Csp = '$lhs = $rhs;'; ExpectSuccess = $true },
  @{ Name = "nested_if_else"; Csp = 'if ($c0) { if ($c1) { $$body } } else { $$elseBody }'; ExpectSuccess = $true },
  @{ Name = "while_loop"; Csp = 'while ($cond) { $$body }'; ExpectSuccess = $true },
  @{ Name = "for_loop"; Csp = 'for ($i; $c; $u) { $$body }'; ExpectSuccess = $true },
  @{ Name = "do_while_loop"; Csp = 'do { $$body } while ($cond);'; ExpectSuccess = $true },
  @{ Name = "switch_case_like"; Csp = 'switch ($x) { case 1: $$body break; default: $$def }'; ExpectSuccess = $true },
  @{ Name = "return_stmt"; Csp = 'return $x;'; ExpectSuccess = $true },
  @{ Name = "call_expr"; Csp = '$f($a, $b);'; ExpectSuccess = $true },
  @{ Name = "unary_not"; Csp = 'if (!$c) { $$body }'; ExpectSuccess = $true },
  @{ Name = "binary_chain"; Csp = 'if (($a + $b) > $c) { $$body }'; ExpectSuccess = $true },
  @{ Name = "compound_with_list_hole_only"; Csp = '{ $$body }'; ExpectSuccess = $true },
  @{ Name = "param_list_hole_only"; Csp = 'void f($$params) { $$body }'; ExpectSuccess = $true },
  @{ Name = "type_and_name_holes"; Csp = '$ret $fn($$params) { return $v; }'; ExpectSuccess = $true },
  @{ Name = "desc_region_multiline"; Csp = @'
if ($cond) {
  // <desc
  return $x;
  $$body
  // desc>
  $x = 1;
}
'@; ExpectSuccess = $true },
  @{ Name = "desc_region_inline_open"; Csp = @'
if ($cond) { // <desc
  return $x;
  $$body // desc>
}
'@; ExpectSuccess = $true },
  @{ Name = "desc_region_nested_blocks"; Csp = @'
if ($cond) {
  // <desc
  if ($inner) { $$body }
  // desc>
}
'@; ExpectSuccess = $true },
  @{ Name = "function_decl_with_desc_in_body"; Csp = @'
$type $function($$params) {
  // <desc
  return $x;
  // desc>
}
'@; ExpectSuccess = $true },
  @{ Name = "multiple_statements"; Csp = '$a = $b; $c = $d;'; ExpectSuccess = $true },
  @{ Name = "empty_body_function"; Csp = 'void f() { }'; ExpectSuccess = $true },
  @{ Name = "integer_literal_use"; Csp = 'if ($x == 42) { $$body }'; ExpectSuccess = $true },
  @{ Name = "float_literal_use"; Csp = 'if ($x < 3.14) { $$body }'; ExpectSuccess = $true },
  @{ Name = "invalid_symbol_only"; Csp = '@'; ExpectSuccess = $false },
  @{ Name = "invalid_unclosed_block"; Csp = 'if ($c) {'; ExpectSuccess = $false },
  @{ Name = "invalid_broken_if"; Csp = 'if ( ) { $$body }'; ExpectSuccess = $true },
  @{ Name = "invalid_decl_fragment"; Csp = '$type ('; ExpectSuccess = $false },
  @{ Name = "comment_directive_without_close"; Csp = @'
if ($cond) {
  // <desc
  return $x;
}
'@; ExpectSuccess = $true },
  @{ Name = "comment_directive_close_only"; Csp = @'
if ($cond) {
  // desc>
  return $x;
}
'@; ExpectSuccess = $true },
  @{ Name = "template_like_shift_tokens"; Csp = 'if (($a >> $b) > 0) { $$body }'; ExpectSuccess = $true }
)

$results = @()

foreach ($case in $cases) {
  $cmdArgs = @("--csp", $case.Csp)
  $usedStrict = $false
  if ($StrictAll -or (-not $case.ExpectSuccess)) {
    $cmdArgs += "--strict"
    $usedStrict = $true
  }

  $output = & $ExePath @cmdArgs 2>&1 | Out-String
  $exitCode = $LASTEXITCODE
  $actualSuccess = ($exitCode -eq 0)
  $pass = (($case.ExpectSuccess -and $actualSuccess) -or ((-not $case.ExpectSuccess) -and (-not $actualSuccess)))
  Write-CaseArtifact -SuiteName "pattern_parse" `
    -CaseName $case.Name `
    -Output $output `
    -ArgList $cmdArgs `
    -CommandText "$ExePath $($cmdArgs -join ' ')" `
    -InputText $case.Csp `
    -InputFileName "input.csp"

  $results += [pscustomobject]@{
    Name = $case.Name
    Csp = $case.Csp
    Mode = if ($usedStrict) { "strict" } else { "default" }
    Expect = if ($case.ExpectSuccess) { "success" } else { "failure" }
    Actual = if ($actualSuccess) { "success" } else { "failure" }
    ExitCode = $exitCode
    Pass = if ($pass) { "PASS" } else { "FAIL" }
    FirstLine = (Get-FirstNonEmptyLine -Text $output)
  }
}

$findPattern = 'if ( $cond ) { $$body }'
$configCases = @(
  @{ Name = "cfg_default_find_count_offset"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", "match[0] start=30 end=45", "match[1] start=49 end=67") },
  @{ Name = "cfg_output_count_only"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2"); MustNotContain = @("match[0]") },
  @{ Name = "cfg_output_offset_only"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "offset"); ExpectedExit = 0; MustContain = @("match[0] start=30 end=45", "match[1] start=49 end=67"); MustNotContain = @("file=$generatedSamplePath matches=") },
  @{ Name = "cfg_output_offsets_alias"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "offsets"); ExpectedExit = 0; MustContain = @("match[0] start=30 end=45", "match[1] start=49 end=67") },
  @{ Name = "cfg_output_raw_only"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "raw"); ExpectedExit = 0; MustContain = @('match[0] raw="if (x) { x++; }"', 'match[1] raw="if (x) { x += 2; }"'); MustNotContain = @("start=") },
  @{ Name = "cfg_output_signature_alias"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "signature"); ExpectedExit = 0; MustContain = @('match[0] raw="if (x) { x++; }"') },
  @{ Name = "cfg_output_count_offset_raw"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "count,offset,raw"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", 'match[0] start=30 end=45 raw="if (x) { x++; }"') },
  @{ Name = "cfg_output_pipe_separator"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "count|offset"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", "match[0] start=30 end=45") },
  @{ Name = "cfg_multi_file_count_total"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", "file=tests/find_fixture.cpp matches=2", "total_matches=4") },
  @{ Name = "cfg_multi_file_count_offset"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count,offset"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", "file=tests/find_fixture.cpp matches=2", "total_matches=4") },
  @{ Name = "cfg_multi_file_raw_newline_escape"; Args = @("--csp", $findPattern, "--find", "tests/find_fixture.cpp", "--output", "raw"); ExpectedExit = 0; MustContain = @('raw="if (y) {', 'y -= 2;', '\n') },
  @{ Name = "cfg_max_matches_one"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "count,offset", "--max-matches", "1"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", "match[0] start=30 end=45", "file=$generatedSamplePath printed=1 of 2 matches"); MustNotContain = @("match[1]") },
  @{ Name = "cfg_max_matches_zero"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "count,offset", "--max-matches", "0"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", "file=$generatedSamplePath printed=0 of 2 matches"); MustNotContain = @("match[0]", "match[1]") },
  @{ Name = "cfg_max_matches_large"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "count,offset", "--max-matches", "10"); ExpectedExit = 0; MustContain = @("match[0] start=30 end=45", "match[1] start=49 end=67"); MustNotContain = @("printed=") },
  @{ Name = "cfg_max_matches_per_file"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count,offset", "--max-matches", "1"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath printed=1 of 2 matches", "file=tests/find_fixture.cpp printed=1 of 2 matches", "total_matches=4") },
  @{ Name = "cfg_strict_with_find_valid"; Args = @("--csp", $findPattern, "--strict", "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2") },
  @{ Name = "cfg_invalid_output_mode"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output", "bogus"); ExpectedExit = 1; MustContain = @("Invalid --output value") },
  @{ Name = "cfg_missing_output_value"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--output"); ExpectedExit = 1; MustContain = @("Missing value for --output") },
  @{ Name = "cfg_invalid_max_matches_value"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--max-matches", "abc"); ExpectedExit = 1; MustContain = @("Invalid --max-matches value") },
  @{ Name = "cfg_missing_max_matches_value"; Args = @("--csp", $findPattern, "--find", $generatedSamplePath, "--max-matches"); ExpectedExit = 1; MustContain = @("Missing value for --max-matches") }
)

$configResults = @()
foreach ($case in $configCases) {
  $configResults += Invoke-GeneratorCase -SuiteName "config_find" -Name $case.Name `
    -ArgList $case.Args `
    -ExpectedExit $case.ExpectedExit `
    -MustContain $case.MustContain `
    -MustNotContain $case.MustNotContain
}

$replacePattern = 'if ( $cond ) { $$body }'
$replaceCases = @(
  @{ Name = "repl_basic_negate_sample"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath replacements=2", "if ( !(x) ) { x++; }", "if ( !(x) ) { x += 2; }", "file=$generatedSamplePath matches=2") },
  @{ Name = "repl_cond_duplicated"; Args = @("--csp", $replacePattern, "--replace", 'if ( $cond && $cond ) { $$body }', "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("if ( x && x ) { x++; }", "if ( x && x ) { x += 2; }") },
  @{ Name = "repl_body_prefixed"; Args = @("--csp", $replacePattern, "--replace", 'if ( $cond ) { int z = 0; $$body }', "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("if ( x ) { int z = 0; x++; }", "if ( x ) { int z = 0; x += 2; }") },
  @{ Name = "repl_body_duplicated_list"; Args = @("--csp", $replacePattern, "--replace", 'if ( $cond ) { $$body $$body }', "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("if ( x ) { x++; x++; }", "if ( x ) { x += 2; x += 2; }") },
  @{ Name = "repl_unknown_single_hole_removed"; Args = @("--csp", $replacePattern, "--replace", 'if ( $missing ) { $$body }', "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("if (  ) { x++; }", "if (  ) { x += 2; }") },
  @{ Name = "repl_list_as_single_fallback"; Args = @("--csp", $replacePattern, "--replace", 'if ( $cond ) { $body }', "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("if ( x ) { x++; }", "if ( x ) { x += 2; }") },
  @{ Name = "repl_raw_output_kept"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--output", "raw"); ExpectedExit = 0; MustContain = @('match[0] raw="if (x) { x++; }"', 'match[1] raw="if (x) { x += 2; }"') },
  @{ Name = "repl_count_offset_output"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--output", "count,offset"); ExpectedExit = 0; MustContain = @("match[0] start=30 end=45", "match[1] start=49 end=67") },
  @{ Name = "repl_count_pipe_output"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--output", "count|raw"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath matches=2", 'match[0] raw="if (x) { x++; }"') },
  @{ Name = "repl_max_matches_one"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--output", "count,offset", "--max-matches", "1"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath replacements=2", "file=$generatedSamplePath printed=1 of 2 matches") },
  @{ Name = "repl_max_matches_zero"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--output", "count,offset", "--max-matches", "0"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath replacements=2", "file=$generatedSamplePath printed=0 of 2 matches"); MustNotContain = @("match[0]", "match[1]") },
  @{ Name = "repl_fixture_negate"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", "tests/find_fixture.cpp", "--output", "count"); ExpectedExit = 0; MustContain = @("file=tests/find_fixture.cpp replacements=2", "if ( !(y) ) { y--; }", "if ( !(y) ) {") },
  @{ Name = "repl_fixture_list_single_fallback"; Args = @("--csp", $replacePattern, "--replace", 'if ( $cond ) { $body }', "--find", "tests/find_fixture.cpp", "--output", "count"); ExpectedExit = 0; MustContain = @("if ( y ) { y--; }", "if ( y ) { y -= 2; }") },
  @{ Name = "repl_multifile_total_and_markers"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count"); ExpectedExit = 0; MustContain = @("total_matches=4") },
  @{ Name = "repl_multifile_with_limit"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count,offset", "--max-matches", "1"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath printed=1 of 2 matches", "file=tests/find_fixture.cpp printed=1 of 2 matches") },
  @{ Name = "repl_requires_find"; Args = @("--csp", $replacePattern, "--replace", 'if ( !($cond) ) { $$body }'); ExpectedExit = 1; MustContain = @("--replace/--remove requires at least one --find target file") },
  @{ Name = "repl_missing_value"; Args = @("--csp", $replacePattern, "--find", $generatedSamplePath, "--replace"); ExpectedExit = 1; MustContain = @("Missing value for --replace") },
  @{ Name = "repl_invalid_pattern_strict"; Args = @("--csp", '@', "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedSamplePath, "--strict"); ExpectedExit = 5; MustContain = @("Pattern[0] parse error: no AST roots extracted") },
  @{ Name = "repl_function_decl_body"; Args = @("--csp", '$type $function ( $$params ) { $$body }', "--replace", '$type $function ( $$params ) { return 42; }', "--find", $generatedSamplePath, "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedSamplePath replacements=1", "return 42;", "file=$generatedSamplePath matches=1") },
  @{ Name = "repl_function_decl_on_fixture"; Args = @("--csp", '$type $function ( $$params ) { $$body }', "--replace", '$type $function ( $$params ) { return 7; }', "--find", "tests/find_fixture.cpp", "--output", "count"); ExpectedExit = 0; MustContain = @("file=tests/find_fixture.cpp replacements=1", "return 7;", "file=tests/find_fixture.cpp matches=1") },
  @{ Name = "remove_basic"; Args = @("--csp", $replacePattern, "--remove", "--find", $removeInputPath, "--output", "count"); ExpectedExit = 0; MustContain = @("replacements=0 removals=2 conflicts=0", "file=$removeInputPath matches=2") },
  @{ Name = "remove_requires_find"; Args = @("--csp", $replacePattern, "--remove"); ExpectedExit = 1; MustContain = @("--replace/--remove requires at least one --find target file") },
  @{ Name = "remove_rules_file"; Args = @("--rules", $rulesPathWithRemove, "--find", $removeInputPath2, "--output", "count"); ExpectedExit = 0; MustContain = @("replacements=0 removals=2 conflicts=0", "file=$removeInputPath2 matches=2") }
)

$replaceResults = @()
foreach ($case in $replaceCases) {
  $replaceResults += Invoke-GeneratorCase -SuiteName "replacement" -Name $case.Name `
    -ArgList $case.Args `
    -ExpectedExit $case.ExpectedExit `
    -MustContain $case.MustContain `
    -MustNotContain $case.MustNotContain
}

$descPattern = @'
if ($cond) {
  // <desc
  if ($inner) { $$innerBody }
  // desc>
  $tail = 1;
}
'@

$generatedReplaceCases = @(
  @{ Name = "gen_repl_desc_basic"; Args = @("--csp", $descPattern, "--replace", 'if ($cond) { $tail = 2; $$innerBody }', "--find", $generatedDescPath, "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedDescPath replacements=1", "if (x) { x = 2; x += 3; }", "file=$generatedDescPath matches=1") },
  @{ Name = "gen_repl_desc_max_matches_zero"; Args = @("--csp", $descPattern, "--replace", 'if ($cond) { $tail = 2; $$innerBody }', "--find", $generatedDescPath, "--output", "count,offset", "--max-matches", "0"); ExpectedExit = 0; MustContain = @("file=$generatedDescPath printed=0 of 1 matches") },
  @{ Name = "gen_repl_desc_raw"; Args = @("--csp", $descPattern, "--replace", 'if ($cond) { $tail = 2; $$innerBody }', "--find", $generatedDescPath, "--output", "raw"); ExpectedExit = 0; MustContain = @('match[0] raw="if (x) {') },
  @{ Name = "gen_repl_desc_multifile_total"; Args = @("--csp", $descPattern, "--replace", 'if ($cond) { $tail = 2; $$innerBody }', "--find", $generatedDescPath, "--find", $generatedExprPath, "--output", "count"); ExpectedExit = 0; MustContain = @("total_matches=1") },
  @{ Name = "gen_repl_expr_negate_generated"; Args = @("--csp", 'if ( $cond ) { $$body }', "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedExprPath, "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedExprPath replacements=2", "if ( !(a && b) ) {", "if ( !(a) ) {") },
  @{ Name = "gen_repl_expr_duplicate_body_generated"; Args = @("--csp", 'if ( $cond ) { $$body }', "--replace", 'if ( $cond ) { $$body $$body }', "--find", $generatedExprPath, "--output", "count"); ExpectedExit = 0; MustContain = @("a += b; a += b;", "a++; a++;") },
  @{ Name = "gen_repl_expr_unknown_hole_generated"; Args = @("--csp", 'if ( $cond ) { $$body }', "--replace", 'if ( $missing ) { $$body }', "--find", $generatedExprPath, "--output", "count"); ExpectedExit = 0; MustContain = @("if (  ) {") },
  @{ Name = "gen_repl_expr_offset_generated"; Args = @("--csp", 'if ( $cond ) { $$body }', "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedExprPath, "--output", "count,offset"); ExpectedExit = 0; MustContain = @("match[0] start=", "match[1] start=") },
  @{ Name = "gen_repl_expr_limit_generated"; Args = @("--csp", 'if ( $cond ) { $$body }', "--replace", 'if ( !($cond) ) { $$body }', "--find", $generatedExprPath, "--output", "count,offset", "--max-matches", "1"); ExpectedExit = 0; MustContain = @("printed=1 of 2 matches") },
  @{ Name = "gen_repl_function_generated"; Args = @("--csp", '$type $function ( $$params ) { $$body }', "--replace", '$type $function ( $$params ) { return 0; }', "--find", $generatedFuncPath, "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedFuncPath replacements=2", "return 0;", "file=$generatedFuncPath matches=2") },
  @{ Name = "gen_repl_function_generated_multifile"; Args = @("--csp", '$type $function ( $$params ) { $$body }', "--replace", '$type $function ( $$params ) { return 1; }', "--find", $generatedFuncPath, "--find", $generatedExprPath, "--output", "count"); ExpectedExit = 0; MustContain = @("total_matches=3") },
  @{ Name = "gen_repl_desc_pattern_strict"; Args = @("--csp", $descPattern, "--replace", 'if ($cond) { $tail = 2; $$innerBody }', "--find", $generatedDescPath, "--strict", "--output", "count"); ExpectedExit = 0; MustContain = @("file=$generatedDescPath replacements=1") }
)

$generatedReplaceResults = @()
foreach ($case in $generatedReplaceCases) {
  $generatedReplaceResults += Invoke-GeneratorCase -SuiteName "generated_replacement" -Name $case.Name `
    -ArgList $case.Args `
    -ExpectedExit $case.ExpectedExit `
    -MustContain $case.MustContain `
    -MustNotContain $case.MustNotContain
}

# ── Compilation Database Suite ───────────────────────────────────────────────
$compdbCases = @(
  @{ Name = "db_find_two_files";   Args = @("--csp", $findPattern, "--db", $generatedCompdbPath, "--output", "count");
     ExpectedExit = 0; MustContain = @("total_matches=4") },
  @{ Name = "db_dedup";            Args = @("--csp", $findPattern, "--db", $generatedCompdbDedupPath, "--output", "count");
     ExpectedExit = 0; MustContain = @("matches=2"); MustNotContain = @("total_matches=") },
  @{ Name = "db_with_replace";     Args = @("--csp", $findPattern, "--replace", 'if ( !($cond) ) { $$body }', "--db", $generatedCompdbPath, "--output", "count");
     ExpectedExit = 0; MustContain = @("total_matches=4", "if ( !(x) ) {", "if ( !(y) ) {") },
  @{ Name = "db_plus_extra_find";  Args = @("--csp", $findPattern, "--db", $generatedCompdbPath, "--find", $generatedExprPath, "--output", "count");
     ExpectedExit = 0; MustContain = @("total_matches=6") },
  @{ Name = "db_missing";          Args = @("--csp", $findPattern, "--db", "tests/generated/nonexistent_compdb.json");
     ExpectedExit = 1; MustContain = @("Cannot open compilation database") }
)

$compdbResults = @()
foreach ($case in $compdbCases) {
  $compdbResults += Invoke-GeneratorCase -SuiteName "compdb" -Name $case.Name `
    -ArgList $case.Args `
    -ExpectedExit $case.ExpectedExit `
    -MustContain $case.MustContain `
    -MustNotContain $case.MustNotContain
}

# ── Rules-file Suite ─────────────────────────────────────────────────────────
$rulesCases = @(
  # ── Happy-path: find-only ─────────────────────────────────────────────────
  @{ Name = "rules_single_find_count_offset"
     Args = @("--rules", $rulesPathSingleFind, "--find", $generatedSamplePath)
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2", "match[0] start=30 end=45", "match[1] start=49 end=67") },

  @{ Name = "rules_single_find_output_raw"
     Args = @("--rules", $rulesPathSingleFind, "--find", $generatedSamplePath, "--output", "raw")
     ExpectedExit = 0
     MustContain = @('match[0] raw="if (x) { x++; }"', 'match[1] raw="if (x) { x += 2; }"') },

  @{ Name = "rules_single_find_output_count_only"
     Args = @("--rules", $rulesPathSingleFind, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2")
     MustNotContain = @("match[0]") },

  # ── Happy-path: find + replace ───────────────────────────────────────────
  @{ Name = "rules_find_replace_basic"
     Args = @("--rules", $rulesPathFindReplace, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     HasReplacement = $true
     MustContain = @("file=$generatedSamplePath replacements=2", "if ( !(x) ) { x++; }", "if ( !(x) ) { x += 2; }", "file=$generatedSamplePath matches=2") },

  @{ Name = "rules_find_replace_on_fixture"
     Args = @("--rules", $rulesPathFindReplace, "--find", "tests/find_fixture.cpp", "--output", "count")
     ExpectedExit = 0
     HasReplacement = $true
     MustContain = @("file=tests/find_fixture.cpp replacements=2", "if ( !(y) ) { y--; }") },

  @{ Name = "rules_comments_and_blanks"
     Args = @("--rules", $rulesPathWithComments, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     HasReplacement = $true
     MustContain = @("file=$generatedSamplePath replacements=2", "if ( !(x) ) {") },

  # ── Multi-pattern rules file ─────────────────────────────────────────────
  @{ Name = "rules_multi_patterns_count"
     Args = @("--rules", $rulesPathMulti, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=3") },

  @{ Name = "rules_multi_patterns_raw"
     Args = @("--rules", $rulesPathMulti, "--find", $generatedSamplePath, "--output", "raw")
     ExpectedExit = 0
     MustContain = @('match[0] raw=', 'match[1] raw=', 'match[2] raw=') },

  @{ Name = "rules_multi_one_replace"
     Args = @("--rules", $rulesPathMultiReplace, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     HasReplacement = $true
     MustContain = @("file=$generatedSamplePath replacements=2", "file=$generatedSamplePath matches=3", "if ( !(x) ) { x++; }") },

  # ── Combining --rules with --csp on the command line ─────────────────────
  @{ Name = "rules_combined_with_csp"
     Args = @("--rules", $rulesPathSingleFind, "--csp", 'return $x;', "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=3") },

  @{ Name = "rules_csp_before_rules"
     Args = @("--csp", 'return $x;', "--rules", $rulesPathSingleFind, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=3") },

  # ── Two --rules files ────────────────────────────────────────────────────
  @{ Name = "rules_two_files_combined"
     Args = @("--rules", $rulesPathSingleFind, "--rules", $rulesPathSecond, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=3") },

  # ── Multi --find with rules ───────────────────────────────────────────────
  @{ Name = "rules_multifile_find_only"
     Args = @("--rules", $rulesPathSingleFind, "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2", "file=tests/find_fixture.cpp matches=2", "total_matches=4") },

  @{ Name = "rules_multifile_replacement"
     Args = @("--rules", $rulesPathFindReplace, "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count")
     ExpectedExit = 0
     HasReplacement = $true
     MustContain = @("total_matches=4") },

  # ── Rules + --db ─────────────────────────────────────────────────────────
  @{ Name = "rules_with_db"
     Args = @("--rules", $rulesPathSingleFind, "--db", $generatedCompdbPath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("total_matches=4") },

  # ── max-matches interacts with rules ─────────────────────────────────────
  @{ Name = "rules_max_matches_one"
     Args = @("--rules", $rulesPathSingleFind, "--find", $generatedSamplePath, "--output", "count,offset", "--max-matches", "1")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2", "match[0] start=30 end=45", "file=$generatedSamplePath printed=1 of 2 matches")
     MustNotContain = @("match[1]") },

  @{ Name = "rules_max_matches_zero"
     Args = @("--rules", $rulesPathSingleFind, "--find", $generatedSamplePath, "--output", "count,offset", "--max-matches", "0")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2", "file=$generatedSamplePath printed=0 of 2 matches")
     MustNotContain = @("match[0]", "match[1]") },

  # ── Error: replace: before any find: ────────────────────────────────────
  @{ Name = "rules_error_replace_before_find"
     Args = @("--rules", $rulesPathBadReplaceOrder, "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("'replace:' without a preceding 'find:'") },

  # ── Error: missing rules file ─────────────────────────────────────────────
  @{ Name = "rules_error_missing_file"
     Args = @("--rules", "tests/generated/nonexistent_rules.txt", "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("Cannot open rules file") },

  # ── Error: no find: entries in file ──────────────────────────────────────
  @{ Name = "rules_error_no_find_entries"
     Args = @("--rules", $rulesPathEmpty, "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("Rules file contains no 'find:' entries") },

  # ── Error: unrecognised line ──────────────────────────────────────────────
  @{ Name = "rules_error_bad_line"
     Args = @("--rules", $rulesPathBadLine, "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("unrecognised line") },

  # ── Error: empty pattern after find: ─────────────────────────────────────
  @{ Name = "rules_error_empty_pattern"
     Args = @("--rules", $rulesPathEmptyPattern, "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("empty pattern after 'find:'") },

  # ── Error: --rules flag with no argument ─────────────────────────────────
  @{ Name = "rules_error_missing_value"
     Args = @("--csp", $findPattern, "--rules")
     ExpectedExit = 1
     MustContain = @("Missing value for --rules") }
)

$rulesResults = @()
foreach ($case in $rulesCases) {
  $hr = [bool]$case.HasReplacement
  $rulesResults += Invoke-GeneratorCase -SuiteName "rules_file" -Name $case.Name `
    -ArgList $case.Args `
    -ExpectedExit $case.ExpectedExit `
    -MustContain $case.MustContain `
    -MustNotContain $case.MustNotContain `
    -HasReplacement:$hr
}

$patternTotal = $results.Count
$patternPassed = ($results | Where-Object { $_.Pass -eq "PASS" }).Count
$patternFailed = $patternTotal - $patternPassed

$configTotal = $configResults.Count
$configPassed = ($configResults | Where-Object { $_.Pass -eq "PASS" }).Count
$configFailed = $configTotal - $configPassed

$replaceTotal = $replaceResults.Count
$replacePassed = ($replaceResults | Where-Object { $_.Pass -eq "PASS" }).Count
$replaceFailed = $replaceTotal - $replacePassed

$generatedReplaceTotal = $generatedReplaceResults.Count
$generatedReplacePassed = ($generatedReplaceResults | Where-Object { $_.Pass -eq "PASS" }).Count
$generatedReplaceFailed = $generatedReplaceTotal - $generatedReplacePassed

$compdbTotal = $compdbResults.Count
$compdbPassed = ($compdbResults | Where-Object { $_.Pass -eq "PASS" }).Count
$compdbFailed = $compdbTotal - $compdbPassed

$rulesTotal = $rulesResults.Count
$rulesPassed = ($rulesResults | Where-Object { $_.Pass -eq "PASS" }).Count
$rulesFailed = $rulesTotal - $rulesPassed

# ── Filter Suite ─────────────────────────────────────────────────────
# Auto-discover cl.exe when CSP_CXX is not already set.
$savedCspCxx = $env:CSP_CXX
if (-not $env:CSP_CXX) {
  $clExe = Get-ChildItem "C:\Program Files\Microsoft Visual Studio" `
               -Recurse -Filter "cl.exe" -ErrorAction SilentlyContinue |
           Where-Object { $_.FullName -cmatch 'Hostx64\\x64\\cl\.exe$' } |
           Select-Object -First 1
  if ($clExe) { $env:CSP_CXX = $clExe.FullName }
}

$filterDefsFile  = "tests/sample_filters.cpp"
$filterPattern   = 'if ( $cond ) { $$body }'

$filterCases = @(
  # ── Happy path: no extra args ──────────────────────────────────────────
  @{ Name = "flt_accept_all"
     Args = @("--csp", $filterPattern, "--filter", "accept_all",
              "--filter-defs", $filterDefsFile, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2") },

  @{ Name = "flt_reject_all"
     Args = @("--csp", $filterPattern, "--filter", "reject_all",
              "--filter-defs", $filterDefsFile, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=0") },

  # ── Happy path: extra numeric arg ────────────────────────────────────
  @{ Name = "flt_extra_arg_pass"       # cond="x" (1 char) < 5 → both match
     Args = @("--csp", $filterPattern, "--filter", "cond_shorter_than(5)",
              "--filter-defs", $filterDefsFile, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2") },

  @{ Name = "flt_extra_arg_reject"     # cond="x" (1 char) not shorter than 1 → no match
     Args = @("--csp", $filterPattern, "--filter", "cond_shorter_than(1)",
              "--filter-defs", $filterDefsFile, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=0") },

  # ── Happy path: extra string arg ─────────────────────────────────────
  @{ Name = "flt_extra_string_pass"    # cond="x" in sample file → cond_equals("x") passes
     Args = @("--csp", $filterPattern, "--filter", 'cond_equals("x")',
              "--filter-defs", $filterDefsFile, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2") },

  @{ Name = "flt_extra_string_reject"  # cond="x", not "z" → all rejected
     Args = @("--csp", $filterPattern, "--filter", 'cond_equals("z")',
              "--filter-defs", $filterDefsFile, "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=0") },

  # ── Per-pattern filtering: two --csp each with own filter ────────────────
  @{ Name = "flt_per_pattern"           # if: accept_all (2); return: reject_all (0) → total 2
     Args = @("--csp", $filterPattern,      "--filter", "accept_all",
              "--csp", 'return $x;',          "--filter", "reject_all",
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2") },

  # ── Filter combined with replacement ─────────────────────────────────
  @{ Name = "flt_with_replace"
     Args = @("--csp", $filterPattern, "--replace", 'if ( !($cond) ) { $$body }',
              "--filter", "accept_all",
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     HasReplacement = $true
     MustContain = @("file=$generatedSamplePath replacements=2", "if ( !(x) ) { x++; }") },

  # ── Multiple find files ──────────────────────────────────────────────
  @{ Name = "flt_multifile"
     Args = @("--csp", $filterPattern, "--filter", "accept_all",
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath, "--find", "tests/find_fixture.cpp", "--output", "count")
     ExpectedExit = 0
     MustContain = @("total_matches=4") },

  # ── Rules file with filter: key ───────────────────────────────────────
  @{ Name = "flt_rules_filter_key"
     Args = @("--rules", $rulesPathWithFilter,
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=2") },

  @{ Name = "flt_rules_filter_reject"
     Args = @("--rules", $rulesPathWithFilterReject,
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath, "--output", "count")
     ExpectedExit = 0
     MustContain = @("file=$generatedSamplePath matches=0") },

  # ── Error: --filter without preceding --csp ───────────────────────────
  @{ Name = "flt_error_no_csp"
     Args = @("--filter", "accept_all",
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("--filter must follow a --csp") },

  # ── Error: --filter-defs with no argument ───────────────────────────
  @{ Name = "flt_error_missing_defs_value"
     Args = @("--csp", $filterPattern, "--filter", "accept_all", "--filter-defs")
     ExpectedExit = 1
     MustContain = @("Missing value for --filter-defs") },

  # ── Error: function not declared in defs file ──────────────────────
  @{ Name = "flt_error_bad_function_name"
     Args = @("--csp", $filterPattern, "--filter", "no_such_function",
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath)
     ExpectedExit = 3
     MustContain = @("filter compile error") },

  # ── Error: defs file does not exist ───────────────────────────────
  @{ Name = "flt_error_bad_defs_path"
     Args = @("--csp", $filterPattern, "--filter", "accept_all",
              "--filter-defs", "tests/generated/nonexistent_filters.cpp",
              "--find", $generatedSamplePath)
     ExpectedExit = 3
     MustContain = @("filter compile error") },

  # ── Error: rules file: filter: before find: ─────────────────────────
  @{ Name = "flt_rules_filter_before_find"
     Args = @("--rules", $rulesPathFilterBeforeFind,
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("'filter:' without a preceding 'find:'") },

  # ── Error: rules file: empty filter expression ──────────────────────
  @{ Name = "flt_rules_filter_empty_expr"
     Args = @("--rules", $rulesPathFilterEmpty,
              "--filter-defs", $filterDefsFile,
              "--find", $generatedSamplePath)
     ExpectedExit = 1
     MustContain = @("empty expression after 'filter:'") }
)

$filterResults = @()
foreach ($case in $filterCases) {
  $hr = [bool]$case.HasReplacement
  $filterResults += Invoke-GeneratorCase -SuiteName "filter" -Name $case.Name `
    -ArgList $case.Args `
    -ExpectedExit $case.ExpectedExit `
    -MustContain $case.MustContain `
    -MustNotContain $case.MustNotContain `
    -HasReplacement:$hr
}

# Restore original CSP_CXX
$env:CSP_CXX = $savedCspCxx

$filterTotal = $filterResults.Count
$filterPassed = ($filterResults | Where-Object { $_.Pass -eq "PASS" }).Count
$filterFailed = $filterTotal - $filterPassed

$total = $patternTotal + $configTotal + $replaceTotal + $generatedReplaceTotal + $compdbTotal + $rulesTotal + $filterTotal
$passed = $patternPassed + $configPassed + $replacePassed + $generatedReplacePassed + $compdbPassed + $rulesPassed + $filterPassed
$failed = $total - $passed

$lines = @()
$lines += "# CSP Robustness Suite"
$lines += ""
$lines += "- Total cases: $total"
$lines += "- Pattern parse cases: $patternPassed/$patternTotal passed"
$lines += "- Configuration/find cases: $configPassed/$configTotal passed"
$lines += "- Replacement cases: $replacePassed/$replaceTotal passed"
$lines += "- Generated replacement cases: $generatedReplacePassed/$generatedReplaceTotal passed"
$lines += "- Compilation database cases: $compdbPassed/$compdbTotal passed"
$lines += "- Rules-file cases: $rulesPassed/$rulesTotal passed"
$lines += "- Filter cases: $filterPassed/$filterTotal passed"
$lines += "- Passed: $passed"
$lines += "- Failed: $failed"
$lines += ""
$lines += "## Pattern Parse Suite"
$lines += ""
$lines += "| Case | CSP | Mode | Expect | Actual | Exit | Status | First Output Line |"
$lines += "|---|---|---|---|---|---:|---|---|"
foreach ($r in $results) {
  $safeCsp = Escape-MarkdownCell -Text $r.Csp
  $safeFirst = Escape-MarkdownCell -Text $r.FirstLine
  $lines += "| $($r.Name) | $safeCsp | $($r.Mode) | $($r.Expect) | $($r.Actual) | $($r.ExitCode) | $($r.Pass) | $safeFirst |"
}

$lines += ""
$lines += "## Configuration and Offset Suite"
$lines += ""
$lines += "| Case | Command | Expect Exit | Actual Exit | Status | First Output Line |"
$lines += "|---|---|---:|---:|---|---|"
foreach ($r in $configResults) {
  $safeCmd = Escape-MarkdownCell -Text $r.Command
  $safeFirst = Escape-MarkdownCell -Text $r.FirstLine
  $lines += "| $($r.Name) | $safeCmd | $($r.ExpectExit) | $($r.ActualExit) | $($r.Pass) | $safeFirst |"
}

$lines += ""
$lines += "## Replacement Suite"
$lines += ""
$lines += "| Case | Command | Expect Exit | Actual Exit | Status | First Output Line |"
$lines += "|---|---|---:|---:|---|---|"
foreach ($r in $replaceResults) {
  $safeCmd = Escape-MarkdownCell -Text $r.Command
  $safeFirst = Escape-MarkdownCell -Text $r.FirstLine
  $lines += "| $($r.Name) | $safeCmd | $($r.ExpectExit) | $($r.ActualExit) | $($r.Pass) | $safeFirst |"
}

$lines += ""
$lines += "## Generated Replacement Suite"
$lines += ""
$lines += "| Case | Command | Expect Exit | Actual Exit | Status | First Output Line |"
$lines += "|---|---|---:|---:|---|---|"
foreach ($r in $generatedReplaceResults) {
  $safeCmd = Escape-MarkdownCell -Text $r.Command
  $safeFirst = Escape-MarkdownCell -Text $r.FirstLine
  $lines += "| $($r.Name) | $safeCmd | $($r.ExpectExit) | $($r.ActualExit) | $($r.Pass) | $safeFirst |"
}

$lines += ""
$lines += "## Compilation Database Suite"
$lines += ""
$lines += "| Case | Command | Expect Exit | Actual Exit | Status | First Output Line |"
$lines += "|---|---|---:|---:|---|---|"
foreach ($r in $compdbResults) {
  $safeCmd = Escape-MarkdownCell -Text $r.Command
  $safeFirst = Escape-MarkdownCell -Text $r.FirstLine
  $lines += "| $($r.Name) | $safeCmd | $($r.ExpectExit) | $($r.ActualExit) | $($r.Pass) | $safeFirst |"
}

$lines += ""
$lines += "## Rules-File Suite"
$lines += ""
$lines += "| Case | Command | Expect Exit | Actual Exit | Status | First Output Line |"
$lines += "|---|---|---:|---:|---|---|"
foreach ($r in $rulesResults) {
  $safeCmd = Escape-MarkdownCell -Text $r.Command
  $safeFirst = Escape-MarkdownCell -Text $r.FirstLine
  $lines += "| $($r.Name) | $safeCmd | $($r.ExpectExit) | $($r.ActualExit) | $($r.Pass) | $safeFirst |"
}

$lines += ""
$lines += "## Filter Suite"
$lines += ""
$lines += "| Case | Command | Expect Exit | Actual Exit | Status | First Output Line |"
$lines += "|---|---|---:|---:|---|---|"
foreach ($r in $filterResults) {
  $safeCmd   = Escape-MarkdownCell -Text $r.Command
  $safeFirst = Escape-MarkdownCell -Text $r.FirstLine
  $lines += "| $($r.Name) | $safeCmd | $($r.ExpectExit) | $($r.ActualExit) | $($r.Pass) | $safeFirst |"
}

$lines -join "`n" | Set-Content -Path $ReportPath -Encoding ascii

Write-Host "Wrote report to $ReportPath"
Write-Host "Wrote case artifacts to $artifactRoot"
Write-Host "Summary: $passed/$total passed"
if ($failed -gt 0) {
  exit 1
}
