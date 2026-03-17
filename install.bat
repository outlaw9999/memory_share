@echo off
setlocal

echo 🧠 Installing .kit - Cognitive OS Layer

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: 'python' is required.
    exit /b 1
)

set "INSTALL_DIR=%USERPROFILE%\.kit-engine"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Assuming we are inside the source directory, copy files
xcopy /E /I /Y kit "%INSTALL_DIR%\kit" >nul
copy /Y kit.py "%INSTALL_DIR%\" >nul

:: Create the executable wrapper (.bat)
set "BIN_DIR=%USERPROFILE%\.local\bin"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"
set "WRAPPER_SCRIPT=%BIN_DIR%\kit.bat"

(
echo @echo off
echo python "%USERPROFILE%\.kit-engine\kit.py" %%*
) > "%WRAPPER_SCRIPT%"

echo ✅ .kit installed successfully!
echo.
echo Please ensure your PATH includes "%BIN_DIR%"
echo Next steps:
echo   cd your-project
echo   kit init

endlocal
