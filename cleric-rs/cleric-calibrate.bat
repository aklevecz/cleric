@echo off
cd /d %~dp0
rem Share the repo's config.json (one level up). Edit if yours lives elsewhere.
set CLERIC_CONFIG=%~dp0..\config.json
set EXE=target\release\cleric.exe
if not exist "%EXE%" (
  echo Build it first:  cargo build --release
  pause
  exit /b 1
)
set /p GUY="Name for this health bar (e.g. tank): "
"%EXE%" calibrate "%GUY%"
pause
