@echo off
cd /d %~dp0

if not defined PYTHON (set PYTHON=python)

rem Prefer the repo venv if present, else fall back to system python.
if exist "%~dp0..\venv\Scripts\python.exe" set PYTHON="%~dp0..\venv\Scripts\python.exe"

%PYTHON% boot.py --new

pause
