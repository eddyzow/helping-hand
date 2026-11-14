# Execute only the confidence assignment and rejection expression from the listener AST.
$source = Join-Path (Split-Path $PSScriptRoot -Parent) 'rubby_listen.ps1'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw $errors[0] }
$assignment = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.AssignmentStatementAst] -and
    $node.Right.Extent.Text -eq '[math]::Round($heard.Confidence, 2)'
}, $true)
$rejection = $ast.Find({ param($node)
    $node -is [System.Management.Automation.Language.IfStatementAst] -and
    $node.Extent.Text.StartsWith('if ($heard.Confidence -lt $Sure')
}, $true)
if ($null -eq $assignment -or $null -eq $rejection) { throw 'Confidence check AST changed; inspect the fixture.' }
$check = [scriptblock]::Create('param($heard, $commands, $Sure)' + "`n" + $assignment.Extent.Text +
    "`n-not (" + $rejection.Clauses[0].Item1.Extent.Text + ')')
$commands = [ordered]@{ 'wave' = 'run wave' }
$failures = @()
foreach ($case in @(@(0.9, 0.8, $true), @(0.2, 0.8, $false), @(0.755, 0.7, $true))) {
    $heard = [pscustomobject]@{ Confidence = $case[0] }
    $text = 'wave'
    $accepted = & $check $heard $commands $case[1]
    Write-Output "confidence=$($case[0]) threshold=$($case[1]) accepted=$accepted expected=$($case[2])"
    if ($accepted -ne $case[2]) { $failures += $case }
}
if ($failures.Count) { throw 'Configured speech confidence threshold was not preserved.' }
