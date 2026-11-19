<#
.SYNOPSIS
  Windows smoke test for Monte-Neo: install, verify, MCP, CLI and pytest.

.DESCRIPTION
  PREPARED, NOT YET VERIFIED ON WINDOWS. Written on macOS and never run there; the first
  real run is on Windows 11 (ARM or x64). Windows is therefore not in the package classifiers.

  Mirrors scripts/verify_pypi_install.sh. Works in a temp folder, writes nothing to the repository,
  exits non-zero on the first failed step and prints a PASS/FAIL table.

.PARAMETER Source
  'local' (default): install the checkout this script lives in. 'pypi': install the released package.

.PARAMETER Python
  Interpreter or launcher spec, e.g. 'py -3.12' or 'python'. Default: 'py -3' if available, else 'python'.

.PARAMETER SkipPytest
  Skip the test-suite step (local source only; pytest needs the checkout's tests/).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\win_smoke.ps1
  powershell -ExecutionPolicy Bypass -File scripts\win_smoke.ps1 -Source pypi -SkipPytest
#>
[CmdletBinding()]
param(
    [ValidateSet('local', 'pypi')][string]$Source = 'local',
    [string]$Python = '',
    [switch]$SkipPytest
)

$ErrorActionPreference = 'Continue'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Work = Join-Path ([System.IO.Path]::GetTempPath()) ("monte-neo-win-smoke-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $Work | Out-Null
$Results = New-Object System.Collections.ArrayList

# Deliberately NOT forcing UTF-8 here: the product must cope with the default console code page.
$env:PYTHONUTF8 = ''
Remove-Item Env:\PYTHONUTF8 -ErrorAction SilentlyContinue
$env:NO_COLOR = '1'

function Add-Result([string]$Name, [bool]$Ok, [string]$Detail) {
    [void]$Results.Add([pscustomobject]@{ Step = $Name; Result = $(if ($Ok) { 'PASS' } else { 'FAIL' }); Detail = $Detail })
    $color = if ($Ok) { 'Green' } else { 'Red' }
    Write-Host ("[{0}] {1} {2}" -f $(if ($Ok) { 'PASS' } else { 'FAIL' }), $Name, $Detail) -ForegroundColor $color
}

# Runs an executable, returns @{Code; Out}. Never throws.
function Invoke-Step([string]$Exe, [string[]]$Arguments, [string]$Cwd = $Work) {
    Push-Location $Cwd
    try {
        $out = & $Exe @Arguments 2>&1 | Out-String
        $code = $LASTEXITCODE
    } catch {
        $out = $_ | Out-String
        $code = 1
    } finally {
        Pop-Location
    }
    return @{ Code = $code; Out = $out }
}

function Test-Step([string]$Name, [string]$Exe, [string[]]$Arguments, [int[]]$ExpectCodes = @(0), [string]$Cwd = $Work) {
    $r = Invoke-Step $Exe $Arguments $Cwd
    $ok = $ExpectCodes -contains $r.Code
    $tail = ($r.Out.Trim() -split "`r?`n" | Select-Object -Last 3) -join ' | '
    Add-Result $Name $ok ("exit=" + $r.Code + $(if (-not $ok) { " expected=" + ($ExpectCodes -join ',') + " :: " + $tail } else { '' }))
    return $r
}

try {
    # 1. Interpreter --------------------------------------------------------------------------
    if (-not $Python) {
        $Python = if (Get-Command py -ErrorAction SilentlyContinue) { 'py -3' } else { 'python' }
    }
    $pyParts = $Python -split '\s+'
    $pyExe = $pyParts[0]
    $pyPre = @($pyParts | Select-Object -Skip 1)
    $v = Invoke-Step $pyExe ($pyPre + @('-c', 'import sys, platform; print(sys.version.split()[0], platform.machine(), sys.getdefaultencoding(), sys.stdout.encoding)'))
    Add-Result 'python' ($v.Code -eq 0) $v.Out.Trim()
    if ($v.Code -ne 0) { throw 'no usable Python' }

    # 2. Virtualenv + install -----------------------------------------------------------------
    $venv = Join-Path $Work 'venv'
    $r = Invoke-Step $pyExe ($pyPre + @('-m', 'venv', $venv))
    Add-Result 'venv' ($r.Code -eq 0) ''
    if ($r.Code -ne 0) { throw 'venv failed' }
    $py = Join-Path $venv 'Scripts\python.exe'
    $mn = Join-Path $venv 'Scripts\monte-neo.exe'
    $null = Invoke-Step $py @('-m', 'pip', 'install', '-q', '--upgrade', 'pip')

    if ($Source -eq 'local') {
        $spec = "$Repo[sign]"
        $pipArgs = @('-m', 'pip', 'install', '-q', $spec)
        if (-not $SkipPytest) { $pipArgs += @('pytest>=9.0.3', 'pytest-asyncio>=0.21', 'pytest-xdist>=3.3', 'scipy>=1.11') }
    } else {
        $pipArgs = @('-m', 'pip', 'install', '-q', 'monte-neo[sign]')
    }
    $r = Invoke-Step $py $pipArgs
    Add-Result 'pip install' ($r.Code -eq 0) $(if ($r.Code -ne 0) { ($r.Out.Trim() -split "`r?`n" | Select-Object -Last 3) -join ' | ' } else { $Source })
    if ($r.Code -ne 0) { throw 'install failed' }

    # 3. Import without Apple frameworks ------------------------------------------------------
    $r = Invoke-Step $py @('-c', "import sys; import monte_neo, monte_neo.verify, monte_neo.mcp; assert 'mlx' not in sys.modules and 'Metal' not in sys.modules; print(monte_neo.__file__)")
    Add-Result 'import (no MLX/Metal)' ($r.Code -eq 0) $r.Out.Trim()

    # 4. CLI ----------------------------------------------------------------------------------
    $null = Test-Step 'cli --version' $mn @('--version')
    $null = Test-Step 'cli --help' $mn @('--help')

    # 5. verify -------------------------------------------------------------------------------
    $null = Invoke-Step $py @('-c', "from monte_neo.backtest import synthetic_ohlcv; synthetic_ohlcv(3000, seed=1).to_csv('prices.csv', index=False)")
    Set-Content -Path (Join-Path $Work 'leaky.py') -Encoding UTF8 -Value @'
import numpy as np

def signal(df):
    return np.sign(df["close"].shift(-1) - df["close"])
'@
    Set-Content -Path (Join-Path $Work 'sma.py') -Encoding UTF8 -Value @'
def signal(df, fast=10, slow=40):
    c = df["close"]
    return (c.rolling(fast).mean() > c.rolling(slow).mean()).astype(int)
'@
    $null = Test-Step 'verify --demo' $mn @('verify', '--demo')
    # Cross-process file lock (msvcrt on Windows) must acquire and release.
    $lockPy = "import tempfile, os`nfrom monte_neo.verify.filelock import file_lock`np = os.path.join(tempfile.mkdtemp(), 'x.lock')`nwith file_lock(p):`n    pass`nprint('lock ok')"
    $r = Invoke-Step $py @('-c', $lockPy)
    Add-Result 'filelock acquire/release' ($r.Code -eq 0) $r.Out.Trim()
    # A look-ahead leak must be REJECT (exit 2).
    $null = Test-Step 'verify leaky -> REJECT (exit 2)' $mn @('verify', '--ohlcv', 'prices.csv', '--strategy', 'leaky.py', '--out', 'cert.json', '--format', 'json') @(2)
    $null = Test-Step 'verify --recheck' $mn @('verify', '--recheck', 'cert.json', '--ohlcv', 'prices.csv', '--strategy', 'leaky.py')
    $null = Test-Step 'verify --demo-quotes' $mn @('verify', '--demo-quotes') @(0, 1, 2)
    $null = Test-Step 'verify --keygen' $mn @('verify', '--keygen', 'k')
    $null = Test-Step 'verify sma signed' $mn @('verify', '--ohlcv', 'prices.csv', '--strategy', 'sma.py', '--sign', 'k.key', '--out', 'signed.json') @(0, 1, 2)
    $null = Test-Step 'verify --check-signature' $mn @('verify', '--check-signature', 'signed.json', '--public-key', 'k.pub')

    # 6. Console encoding: non-ASCII output must not crash on a legacy code page ---------------
    $r = Invoke-Step $py @('-c', "from rich.console import Console; Console().print('check \u2713 \u2014 \u2192 \u00e9')")
    Add-Result 'console non-ASCII output' ($r.Code -eq 0) $(if ($r.Code -ne 0) { ($r.Out.Trim() -split "`r?`n" | Select-Object -Last 2) -join ' | ' } else { '' })

    # 7. MCP ----------------------------------------------------------------------------------
    $mcpCheck = @'
import json
from monte_neo.mcp import tools
from monte_neo.mcp.server import build_server

build_server()
names = sorted(fn.__name__ for fn in tools.TOOLS)
assert {"verify_strategy", "check_signature", "recheck_certificate"} <= set(names), names
assert json.load(open("cert.json", encoding="utf-8"))["verdict"] == "REJECT"
print("mcp tools:", len(names))
'@
    Set-Content -Path (Join-Path $Work 'mcp_check.py') -Encoding UTF8 -Value $mcpCheck
    $null = Test-Step 'mcp build_server + tools' $py @('mcp_check.py')
    # The stdio server must start and exit cleanly when stdin closes.
    $mcpExe = Join-Path $venv 'Scripts\monte-neo-mcp.exe'
    $p = Start-Process -FilePath $mcpExe -RedirectStandardInput (Join-Path $Work 'empty.txt') -RedirectStandardOutput (Join-Path $Work 'mcp.out') -RedirectStandardError (Join-Path $Work 'mcp.err') -PassThru -WindowStyle Hidden -ErrorAction SilentlyContinue
    if ($null -eq $p) {
        New-Item -ItemType File -Path (Join-Path $Work 'empty.txt') -Force | Out-Null
        $p = Start-Process -FilePath $mcpExe -RedirectStandardInput (Join-Path $Work 'empty.txt') -RedirectStandardOutput (Join-Path $Work 'mcp.out') -RedirectStandardError (Join-Path $Work 'mcp.err') -PassThru -WindowStyle Hidden
    }
    $exited = $p.WaitForExit(30000)
    if (-not $exited) { $p.Kill() }
    Add-Result 'mcp stdio server starts and stops' $exited $(if (-not $exited) { 'still running after 30 s, killed' } else { 'exit=' + $p.ExitCode })

    # 8. Bench round trip ---------------------------------------------------------------------
    $null = Test-Step 'bench init' $mn @('bench', 'init', 'hb', '--bars', '400')

    # 9. pytest -------------------------------------------------------------------------------
    if ($Source -eq 'local' -and -not $SkipPytest) {
        $r = Invoke-Step $py @('-m', 'pytest', 'tests', '-q', '--no-header', '-W', 'ignore', '-p', 'no:cacheprovider', '-n', '4') $Repo
        $summary = ($r.Out.Trim() -split "`r?`n" | Select-Object -Last 3) -join ' | '
        Add-Result 'pytest tests' ($r.Code -eq 0) $summary
        $r.Out | Set-Content -Path (Join-Path $Work 'pytest.log') -Encoding UTF8
    } else {
        Add-Result 'pytest tests' $true 'skipped'
    }
} catch {
    Add-Result 'abort' $false $_.Exception.Message
} finally {
    Write-Host ''
    $Results | Format-Table -AutoSize -Wrap | Out-String | Write-Host
    $failed = @($Results | Where-Object { $_.Result -eq 'FAIL' }).Count
    Write-Host ("Work folder (logs): " + $Work)
    if ($failed -eq 0) { Write-Host 'WIN SMOKE: ALL PASS' -ForegroundColor Green } else { Write-Host ("WIN SMOKE: " + $failed + " FAILED") -ForegroundColor Red }
}
if (@($Results | Where-Object { $_.Result -eq 'FAIL' }).Count -gt 0) { exit 1 } else { exit 0 }
