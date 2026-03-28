@echo off
setlocal

echo Installing .kit - Cognitive OS Layer

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: 'python' is required.
    exit /b 1
)

set "INSTALL_DIR=%USERPROFILE%\.kit-engine"
set "BIN_DIR=%USERPROFILE%\.local\bin"
set "WRAPPER_SCRIPT=%BIN_DIR%\kit.bat"

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

for %%D in (kit kit_agent runtime scripts) do (
    if exist "%INSTALL_DIR%\%%D" rmdir /S /Q "%INSTALL_DIR%\%%D"
    xcopy /E /I /Y "%%D" "%INSTALL_DIR%\%%D" >nul
    if %errorlevel% neq 0 (
        echo Error: failed to copy %%D
        exit /b 1
    )
)

copy /Y "kit.py" "%INSTALL_DIR%\" >nul
if %errorlevel% neq 0 (
    echo Error: failed to copy kit.py
    exit /b 1
)

> "%WRAPPER_SCRIPT%" echo @echo off
>> "%WRAPPER_SCRIPT%" echo setlocal
>> "%WRAPPER_SCRIPT%" echo set "KIT_ENGINE=%%USERPROFILE%%\.kit-engine"
>> "%WRAPPER_SCRIPT%" echo set "PYTHONUTF8=1"
>> "%WRAPPER_SCRIPT%" echo set "PYTHONIOENCODING=utf-8"
>> "%WRAPPER_SCRIPT%" echo set "PYTHONPATH=%%KIT_ENGINE%%;%%PYTHONPATH%%"
>> "%WRAPPER_SCRIPT%" echo python -m kit.cli.main %%*

echo .kit installed successfully.
echo.
echo Wrapper:
echo   %WRAPPER_SCRIPT%
echo.
echo If `kit recall` still resolves to a pip launcher, remove the stale editable install:
echo   python -m pip uninstall memory-share-kit
echo Then ensure "%BIN_DIR%" appears before Python\Scripts in PATH.
echo.
echo Next steps:
echo   cd your-project
echo   kit init

endlocal
