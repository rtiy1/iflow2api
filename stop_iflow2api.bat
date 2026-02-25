@echo off
setlocal
set "ROOT=%~dp0"

if exist "%ROOT%dist\iflow2api-agent.exe" (
  "%ROOT%dist\iflow2api-agent.exe" stop
  set "STOP_CODE=%ERRORLEVEL%"
  "%ROOT%dist\iflow2api-agent.exe" uninstall-autostart
  if not "%STOP_CODE%"=="0" exit /b %STOP_CODE%
  exit /b %ERRORLEVEL%
)

if exist "%ROOT%iflow2api-agent.exe" (
  "%ROOT%iflow2api-agent.exe" stop
  set "STOP_CODE=%ERRORLEVEL%"
  "%ROOT%iflow2api-agent.exe" uninstall-autostart
  if not "%STOP_CODE%"=="0" exit /b %STOP_CODE%
  exit /b %ERRORLEVEL%
)

python "%ROOT%iflow_agent.py" stop
set "STOP_CODE=%ERRORLEVEL%"
python "%ROOT%iflow_agent.py" uninstall-autostart
if not "%STOP_CODE%"=="0" exit /b %STOP_CODE%
exit /b %ERRORLEVEL%
