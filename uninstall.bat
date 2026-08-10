@echo off
setlocal
title Grocery POS - Uninstall

set "INSTALL_DIR=%LOCALAPPDATA%\GroceryPOS"

echo ================================================
echo   Grocery POS - Uninstall
echo ================================================
echo.
echo This will remove the application and shortcuts.
echo Your sales database can be kept as a backup copy.
echo.

set /p BACKUP="Save a backup copy of the database to your Desktop first? (Y/N): "
if /i "%BACKUP%"=="Y" (
    if exist "%INSTALL_DIR%\data\pos.db" (
        copy "%INSTALL_DIR%\data\pos.db" "%USERPROFILE%\Desktop\pos_backup_before_uninstall.db" >nul
        echo Backup saved to Desktop as pos_backup_before_uninstall.db
    )
)

echo Removing shortcuts ...
del "%USERPROFILE%\Desktop\Grocery POS.lnk" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Grocery POS.lnk" >nul 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Grocery POS.lnk" >nul 2>nul

echo Removing application folder ...
rmdir /S /Q "%INSTALL_DIR%"

echo.
echo Uninstall complete.
pause
