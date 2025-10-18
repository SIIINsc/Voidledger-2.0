@echo off
title Voidledger Final Builder

echo =================================
echo  BUILDING THE FINAL VERSION
echo =================================
echo.

echo [1/3] Deleting old build files...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
if exist "*.spec" del "*.spec"
echo Clean complete.
echo.

echo [2/3] Installing trusted packages from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages.
    pause
    exit /b
)
echo Packages installed.
echo.

echo [3/3] Building the executable...
set "exe_name=VoidLedger"

pyinstaller --noconfirm --onefile --windowed --name "%exe_name%" --icon="voidledger.ico" --add-data "static;static" --add-data "sounds;sounds" --add-data "mappings.js;." main.py

if %errorlevel% neq 0 (
    echo BUILD FAILED!
    pause
    exit /b
)

if exist "%exe_name%.spec" del "*.spec"
if exist "build" rmdir /s /q build

echo.
echo ============================================
echo  BUILD SUCCESSFUL!
echo ============================================
echo Your file, '%exe_name%.exe', is in the 'dist' folder.
echo.

pause