param([switch]$Demo, [switch]$NativeVerifier)
$ErrorActionPreference = 'Stop'
if ($Demo -and $NativeVerifier) { throw 'Choose offline Demo or the live local NativeVerifier preview.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed' }
}
& $pythonPath -m pip install -r requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& $pythonPath -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Application installation failed' }
& $pythonPath -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot '.env'))) {
    & $pythonPath scripts/init_env.py
    if ($LASTEXITCODE -ne 0) { throw 'Local configuration initialization failed' }
}
Write-Host 'Open http://localhost:8000. Use your saved Settings login if changed; otherwise use ADMIN_USER/ADMIN_PASSWORD from the local .env.'
$savedSettings = @{}
try {
    if ($Demo) {
        $demoDirectory = Join-Path $projectRoot 'data/demo'
        & $pythonPath scripts/demo.py --data-dir $demoDirectory
        if ($LASTEXITCODE -ne 0) { throw 'Demo creation failed' }
        foreach ($name in @('DATA_DIR', 'WORKER_ENABLED', 'SENDING_ENABLED', 'PUBLIC_URL')) {
            $savedSettings[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        }
        $env:DATA_DIR = $demoDirectory
        $env:WORKER_ENABLED = 'false'
        $env:SENDING_ENABLED = 'false'
        $env:PUBLIC_URL = 'http://localhost:8000'
        Write-Host 'Offline demo: fictional data only. Research/verification jobs will not run.'
    } elseif ($NativeVerifier) {
        foreach ($name in @('REACHER_URL', 'SENDING_ENABLED')) {
            $savedSettings[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        }
        $env:REACHER_URL = 'http://127.0.0.1:8081'
        $env:SENDING_ENABLED = 'false'
        & $pythonPath -c 'import json; from outreach.config import Settings; from scripts.reacher_smoke import check; s=Settings(); print(json.dumps(check(s.reacher_url, s.reacher_secret)))'
        if ($LASTEXITCODE -ne 0) { throw 'Native verifier startup/auth/syntax check failed; no app server started.' }
        Write-Host 'Local native verifier preview: sending disabled; private configuration unchanged.'
    }
    & $pythonPath -m uvicorn outreach.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
    if ($LASTEXITCODE -ne 0) { throw 'Application stopped with an error' }
} finally {
    foreach ($name in $savedSettings.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedSettings[$name], 'Process')
    }
}
