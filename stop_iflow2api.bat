@echo off
setlocal
set "ROOT=%~dp0"

if exist "%ROOT%dist\iflow2api-agent.exe" (
  "%ROOT%dist\iflow2api-agent.exe" stop
  exit /b %ERRORLEVEL%
)

if exist "%ROOT%iflow2api-agent.exe" (
  "%ROOT%iflow2api-agent.exe" stop
  exit /b %ERRORLEVEL%
)

python "%ROOT%iflow_agent.py" stop
exit /b %ERRORLEVEL%
