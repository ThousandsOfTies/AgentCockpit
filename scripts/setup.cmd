@echo off
setlocal
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%~dp0setup" %*
) else (
  python "%~dp0setup" %*
)
exit /b %ERRORLEVEL%
