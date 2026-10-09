@echo off
cd /d "%~dp0"
if not exist "%~dp0OG Companion.exe" (
    echo OG Companion.exe is missing. Extract or copy the complete OG Companion folder.
    pause
    exit /b 1
)
start "" "%~dp0OG Companion.exe"
