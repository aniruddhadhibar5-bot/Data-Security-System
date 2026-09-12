param(
    [switch]$Install,
    [switch]$Test
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $pythonCommand) {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
}
if ($null -eq $pythonCommand) {
    throw "Python was not found. Install Python 3.11 or newer, then run this launcher again."
}
$python = $pythonCommand.Source

if ($Install) {
    & $python -m pip install -r .\requirements.txt
}

if ($Test) {
    & $python -m compileall -q .
    & $python -m unittest discover -s tests -v
    exit $LASTEXITCODE
}

& $python .\main.py