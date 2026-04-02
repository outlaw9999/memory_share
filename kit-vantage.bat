@echo off
rem .kit Plugin Shim for Vantage (v1.2.3)
rem [ARCHITECTURE MANDATE: THE VANTAGE PROTOCOL SHIM]
rem Delegates 'kit vantage ...' to the Vantage CLI binary

set VANTAGE_EXE_RELEASE="E:\DEV\opensource_contrib\Vantage\target\release\vantage.exe"
set VANTAGE_VERIFY_RELEASE="E:\DEV\opensource_contrib\Vantage\target\release\vantage-verify.exe"
set VANTAGE_EXE_DEBUG="E:\DEV\opensource_contrib\Vantage\target\debug\vantage.exe"
set VANTAGE_VERIFY_DEBUG="E:\DEV\opensource_contrib\Vantage\target\debug\vantage-verify.exe"

if "%1"=="verify" (
    if exist %VANTAGE_VERIFY_RELEASE% (
        set VANTAGE_CMD=%VANTAGE_VERIFY_RELEASE%
    ) else (
        set VANTAGE_CMD=%VANTAGE_VERIFY_DEBUG%
    )
    rem Pass all arguments starting from the second one
    shift
    %VANTAGE_CMD% %1 %2 %3 %4 %5 %6 %7 %8 %9
    exit /b %errorlevel%
)

if exist %VANTAGE_EXE_RELEASE% (
    set VANTAGE_CMD=%VANTAGE_EXE_RELEASE%
) else if exist %VANTAGE_EXE_DEBUG% (
    set VANTAGE_CMD=%VANTAGE_EXE_DEBUG%
) else (
    echo [kit-vantage] Error: Vantage binary not found.
    echo Please build it first: cd E:\DEV\opensource_contrib\Vantage\cli ^& cargo build --release
    exit /b 1
)

:run
%VANTAGE_CMD% %*
