$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Création du venv échouée. Installer Python 3.11 ou 3.12.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw 'Installation échouée : vérifier la connexion réseau.' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests échoués.' }
Write-Host 'Installation terminée. Exécuter scripts\start.ps1.'

