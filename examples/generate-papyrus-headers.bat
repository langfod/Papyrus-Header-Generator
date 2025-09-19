@echo off
REM Simple batch file wrapper for generate-papyrus-headers.ps1
REM This script scans .psc files and generates headers for external dependencies

echo Starting Papyrus header generation...

REM Check if PowerShell script exists
if not exist "generate-papyrus-headers.ps1" (
    echo ERROR: generate-papyrus-headers.ps1 not found in current directory
    pause
    exit /b 1
)

REM Run the PowerShell script with default parameters
pwsh -ExecutionPolicy Bypass -File "generate-papyrus-headers.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Script execution failed
    pause
    exit /b 1
)

echo Header generation complete!
pause