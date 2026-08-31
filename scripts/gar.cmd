@echo off
setlocal
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%~dp0gar" %*
) else (
  python "%~dp0gar" %*
)
exit /b %ERRORLEVEL%
