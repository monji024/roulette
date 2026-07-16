@echo off

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo  ROULETTE - Installer

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found on PATH. Please install Python 3.10+.
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo -^> Found %%v

where ruby >nul 2>nul
if errorlevel 1 (
    echo -^> WARNING: Ruby was not found on PATH.
    echo    The game will still run, but atmospheric narration and ASCII
    echo    effects will fall back to a minimal built-in text set.
    echo    Install Ruby from https://rubyinstaller.org for the full experience.
) else (
    for /f "tokens=*" %%v in ('ruby --version') do echo -^> Found %%v
)

if not exist ".venv" (
    echo -^> Creating virtual environment ^(.venv^)...
    python -m venv .venv
) else (
    echo -^> Virtual environment already exists, reusing it.
)

echo -^> Installing Python dependencies...
call ".venv\Scripts\pip.exe" install --upgrade pip >nul
call ".venv\Scripts\pip.exe" install -r requirements.txt

if not exist "data" mkdir data
if not exist "data\scores.json" (
    echo {"wins":0,"losses":0,"best_score":0,"current_streak":0,"best_streak":0,"total_games":0,"history":[]} > data\scores.json
)
type nul >> data\deaths.log

echo.
echo  Installation complete.
echo.
echo  To play:
echo    .venv\Scripts\activate
echo    python client\main.py

endlocal
