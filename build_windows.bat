@echo off
REM ================================================================
REM  PrintBridge - Windows Build Script
REM  Run from the print-agent\ directory on a Windows machine.
REM
REM  Prerequisites:
REM    1. Python 3.10+ installed and on PATH
REM    2. pip install -r requirements.txt
REM    3. (Optional) Put SumatraPDF.exe in this folder so it is bundled
REM       into the .exe. If missing, PrintBridge will look for a
REM       system-installed SumatraPDF at runtime.
REM ================================================================

echo.
echo ==========================================================
echo   PrintBridge - Windows Build
echo ==========================================================
echo.

REM 1. Generate icons (png + ico)
echo [1/3] Generating icons...
call python generate_icon.py
if %ERRORLEVEL% neq 0 (
    echo ERROR: Icon generation failed!
    pause
    exit /b 1
)

REM 2. Build single-file .exe with PyInstaller
set "SUMATRA_DATA="
if exist SumatraPDF.exe set "SUMATRA_DATA=--add-data ^"SumatraPDF.exe;.^""
echo.
echo [2/3] Building .exe with PyInstaller...
if exist SumatraPDF.exe (
    echo    Bundling SumatraPDF.exe
) else (
    echo    SumatraPDF.exe not found - skipping bundled copy
)
call pyinstaller ^
    --name "PrintBridge" ^
    --onefile ^
    --windowed ^
    --icon icon.ico ^
    --add-data "icon.png;." ^
    --add-data "tspl_sender.py;." ^
    --add-data "fonts;fonts" ^
    --exclude-module pymupdf ^
    --exclude-module fitz ^
    --hidden-import pystray._win32 ^
    --hidden-import win32print ^
    --hidden-import win32api ^
    --hidden-import arabic_reshaper ^
    --hidden-import bidi ^
    --hidden-import svg2pdf_py ^
    --clean ^
    --noconfirm ^
    %SUMATRA_DATA% agent.py

if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)

REM 3. Build installer with NSIS (if available)
echo.
echo [3/3] Building installer with NSIS...
where makensis >nul 2>&1
if %ERRORLEVEL% equ 0 (
    makensis installer.nsi
    if %ERRORLEVEL% equ 0 (
        echo    Installer: PrintBridge-Setup.exe
    ) else (
        echo    WARNING: NSIS build failed, but .exe is ready in dist\
    )
) else (
    echo    NSIS not found - skipping installer.
    echo    You can distribute dist\PrintBridge.exe directly.
    echo    To build the installer, install NSIS: https://nsis.sourceforge.io/
)

echo.
echo ==========================================================
echo   Build complete!
echo   .exe:       dist\PrintBridge.exe
echo   installer:  PrintBridge-Setup.exe (if NSIS installed)
echo ==========================================================
echo.
pause
