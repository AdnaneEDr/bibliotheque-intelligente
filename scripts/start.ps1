$ErrorActionPreference = 'Stop'
$projectDir = Split-Path $PSScriptRoot -Parent
Set-Location $projectDir
$projectPython = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Exécuter scripts\install.ps1 au préalable.' }
& $projectPython -c 'import fastapi, streamlit, uvicorn'
if ($LASTEXITCODE -ne 0) { throw 'Installation incomplète. Exécuter scripts\install.ps1.' }
$apiProcess = Start-Process -FilePath $projectPython -ArgumentList @('-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectDir -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $projectDir 'backend.log') -RedirectStandardError (Join-Path $projectDir 'backend-error.log')
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($apiProcess.HasExited) { throw 'Backend arrêté : voir backend-error.log.' }
        try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/api/health'; if ($health.status -eq 'ok') { $ready = $true; break } } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'Backend non disponible : voir backend-error.log.' }
    & $projectPython -m streamlit run frontend/app.py --server.address 127.0.0.1
} finally {
    if (-not $apiProcess.HasExited) { Stop-Process -Id $apiProcess.Id }
}
