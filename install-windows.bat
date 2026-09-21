@echo off
setlocal EnableExtensions
call "%~dp0scripts\install-windows.bat" %*
set "EXIT_CODE=%errorlevel%"
endlocal & exit /b %EXIT_CODE%
