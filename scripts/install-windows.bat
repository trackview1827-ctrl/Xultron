@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
where powershell.exe >nul 2>&1
if errorlevel 1 (
  echo PowerShell bulunamadi. Windows PowerShell 5.1 veya PowerShell 7 gereklidir.
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
if errorlevel 1 exit /b %errorlevel%
echo Xultron kurulumu tamamlandi. Masaustu kisayolu olusturuldu.
endlocal
