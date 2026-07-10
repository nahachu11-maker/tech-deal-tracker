@echo off
REM Double-click me (Windows). Starts the tracker and opens it in your browser.
cd /d "%~dp0"
start "" "http://localhost:8000"
python -m http.server 8000
if errorlevel 1 py -m http.server 8000
