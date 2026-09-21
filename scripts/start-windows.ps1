param(
  [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [int]$Port = 5000
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$Venv = Join-Path $Root 'backend\.venv'
$Python = Join-Path $Venv 'Scripts\python.exe'
$Flask = Join-Path $Venv 'Scripts\flask.exe'
if (-not (Test-Path $Python) -or -not (Test-Path $Flask)) { throw 'Backend bağımlılıkları eksik. Önce .\scripts\bootstrap.ps1 çalıştırın.' }
Write-Host 'Building frontend...'
npm --prefix (Join-Path $Root 'frontend') run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build başarısız oldu.' }
Push-Location (Join-Path $Root 'backend')
try {
  & $Flask --app run.py db upgrade
  if ($LASTEXITCODE -ne 0) { throw 'Veritabanı migration işlemi başarısız oldu.' }
  Write-Host "Xultron başlatılıyor: http://127.0.0.1:$Port"
  $env:PORT = [string]$Port
  & $Python run.py
  exit $LASTEXITCODE
} finally { Pop-Location }
