@echo off
cd /d "%~dp0"
if not exist "%~dp0OG Code Companion.exe" (
    echo OG Code Companion.exe is missing. Extract or copy the complete OG Code Companion folder.
    pause
    exit /b 1
)
start "" "%~dp0OG Code Companion.exe"
