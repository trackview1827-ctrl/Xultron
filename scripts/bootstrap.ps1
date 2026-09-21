param(
  [switch]$SkipShortcut
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Venv = Join-Path $Root 'backend\.venv'
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw 'Python 3.11+ bulunamadı. https://www.python.org/downloads/windows/ adresinden kurun.' }
$PythonBin = $Python.Source
if (-not (Test-Path $Venv)) {
  & $PythonBin -m venv $Venv
  if ($LASTEXITCODE -ne 0) { throw 'Python sanal ortamı oluşturulamadı.' }
}
$VenvPython = Join-Path $Venv 'Scripts\python.exe'
$VenvFlask = Join-Path $Venv 'Scripts\flask.exe'
Write-Host 'Installing backend dependencies...'
& $VenvPython -m pip install -r (Join-Path $Root 'backend\requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Backend bağımlılıkları kurulamadı.' }
Write-Host 'Installing frontend dependencies...'
$Frontend = Join-Path $Root 'frontend'
if (Test-Path (Join-Path $Frontend 'package-lock.json')) { npm --prefix $Frontend ci } else { npm --prefix $Frontend install }
if ($LASTEXITCODE -ne 0) { throw 'Frontend bağımlılıkları kurulamadı.' }
Write-Host 'Applying database migrations...'
Push-Location (Join-Path $Root 'backend')
try { & $VenvFlask --app run.py db upgrade } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Veritabanı migration işlemi başarısız oldu.' }
if (-not $SkipShortcut) {
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root 'scripts\install-windows-shortcut.ps1') -Root $Root
  if ($LASTEXITCODE -ne 0) { throw 'Masaüstü kısayolu oluşturulamadı.' }
}
Write-Host 'Xultron is ready. Run: .\scripts\start-windows.ps1'
