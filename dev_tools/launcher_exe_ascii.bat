@echo off
title Life Simulator
cd /d "%~dp0"

echo ============================================================
echo            Life Simulator  (Standalone EXE)
echo ============================================================
echo.
echo Starting... (no Python needed)
echo.

if not exist "save" mkdir "save"

start "" "LifeSimulator.exe" --portable

echo Game window opened. You may close this black window.
echo All gameplay happens in the game window.
timeout /t 6 >nul
