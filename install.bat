@echo off
setlocal enabledelayedexpansion
title Grocery POS - Setup

echo ================================================
echo   Aling Nena's Grocery POS ^& Admin - Setup
echo ================================================
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\GroceryPOS"
set "SCRIPT_DIR=%~dp0"

REM ---------------------------------------------------------------
REM 1. Find a REAL Python. Windows ships a fake "python.exe" stub
REM    (an App Execution Alias) that sits on PATH even when Python
REM    is NOT installed - "where python" finds it, but running it
REM    just prints a Microsoft Store message and does nothing. So
REM    we don't trust "where" - we actually run each candidate and
REM    check that it prints a real version number.
REM ---------------------------------------------------------------
set "PYEXE="
for %%P in (python py python3) do (
    if not defined PYEXE (
        set "CANDIDATE_OUT="
        for /f "delims=" %%O in ('%%P --version 2^>^&1') do if not defined CANDIDATE_OUT set "CANDIDATE_OUT=%%O"
        echo(!CANDIDATE_OUT! | findstr /b /i "Python " >nul
        if not errorlevel 1 (
            set "PYEXE=%%P"
        )
    )
)

if not defined PYEXE (
    echo Python was not found on this PC ^(or only the Microsoft Store
    echo placeholder is present^).
    echo.
    where winget >nul 2>nul
    if !errorlevel! neq 0 (
        echo Please install Python 3.9 or newer from:
        echo   https://www.python.org/downloads/
        echo During installation, make sure to check the box:
        echo   "Add python.exe to PATH"
        echo Then double-click install.bat again.
        echo.
        pause
        exit /b 1
    )
    echo Installing Python via winget - this may take a few minutes...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    echo.
    echo Python was just installed. Please CLOSE this window and
    echo double-click install.bat again so Windows picks up the new PATH.
    echo.
    echo If it still isn't found next time, open Windows Settings ^>
    echo Apps ^> Advanced app settings ^> App execution aliases, and
    echo turn OFF the "python.exe" / "python3.exe" entries - those are
    echo the fake Store shortcuts that confuse this check.
    pause
    exit /b 0
)

echo Found Python ^(using "%PYEXE%"^):
%PYEXE% --version
echo.

REM ---------------------------------------------------------------
REM 2. Copy the application into a permanent, per-user location
REM    (no admin rights required).
REM ---------------------------------------------------------------
echo Installing application files to:
echo   %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
xcopy /E /I /Y "%SCRIPT_DIR%app\*" "%INSTALL_DIR%\" >nul
if %errorlevel% neq 0 (
    echo ERROR: Could not copy application files.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM 3. Auto-create and initialize the SQL (SQLite) database.
REM    Safe to re-run: only seeds default data the very first time
REM    data\pos.db does not exist yet.
REM ---------------------------------------------------------------
echo Setting up the SQL database ...
pushd "%INSTALL_DIR%"
%PYEXE% -c "import server; server.init_db()"
if %errorlevel% neq 0 (
    echo ERROR: Database setup failed.
    popd
    pause
    exit /b 1
)
popd

REM ---------------------------------------------------------------
REM 4. Create the launcher script inside the install folder, baked
REM    with the exact Python command that worked above.
REM ---------------------------------------------------------------
> "%INSTALL_DIR%\Start-GroceryPOS.bat" (
    echo @echo off
    echo cd /d "%%~dp0"
    echo echo Starting Grocery POS server ...
    echo start "" http://localhost:8080/
    echo %PYEXE% server.py 8080
)

REM ---------------------------------------------------------------
REM 5. Desktop + Start Menu shortcuts.
REM ---------------------------------------------------------------
echo Creating shortcuts ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ws = New-Object -ComObject WScript.Shell;" ^
    "$paths = @(\"$env:USERPROFILE\Desktop\Grocery POS.lnk\", \"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Grocery POS.lnk\");" ^
    "foreach ($p in $paths) { $s = $ws.CreateShortcut($p); $s.TargetPath = '%INSTALL_DIR%\Start-GroceryPOS.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.IconLocation = 'shell32.dll,138'; $s.Save() }"

REM ---------------------------------------------------------------
REM 6. Optional: launch automatically when this PC signs in
REM    (handy for a dedicated store/cashier PC).
REM ---------------------------------------------------------------
set /p AUTOSTART="Start Grocery POS automatically when this PC signs in? (Y/N): "
if /i "%AUTOSTART%"=="Y" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$ws = New-Object -ComObject WScript.Shell;" ^
        "$s = $ws.CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Grocery POS.lnk\");" ^
        "$s.TargetPath = '%INSTALL_DIR%\Start-GroceryPOS.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Save()"
    echo Autostart enabled.
)

echo.
echo ================================================
echo   Installation complete!
echo ================================================
echo  Double-click "Grocery POS" on the Desktop to start it.
echo  It opens automatically in your web browser at
echo    http://localhost:8080
echo.
echo  Default accounts (CHANGE THESE after first login,
echo  under Admin - Users):
echo    Admin:   admin / admin123
echo    Cashier: cashier / cashier123
echo.
echo  Database file location:
echo    %INSTALL_DIR%\data\pos.db
echo.
echo  Other PCs on the same shop network can use this
echo  register as the server too - see README.md for
echo  the "multiple terminals" section.
echo ================================================
pause
