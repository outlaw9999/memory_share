@echo off
rem .kit Plugin Shim for Vantage (v1.2.3)
rem [ARCHITECTURE MANDATE: THE VANTAGE PROTOCOL SHIM]
rem Delegates 'kit vantage ...' to the Vantage CLI binary

set VANTAGE_BIN_RELEASE="E:\DEV\opensource_contrib\Vantage\target\release\vantage.exe"
set VANTAGE_BIN_DEBUG="E:\DEV\opensource_contrib\Vantage\target\debug\vantage.exe"

if exist %VANTAGE_BIN_RELEASE% (
    set VANTAGE_BIN=%VANTAGE_BIN_RELEASE%
) else if exist %VANTAGE_BIN_DEBUG% (
    set VANTAGE_BIN=%VANTAGE_BIN_DEBUG%
) else (
    echo [kit-vantage] Error: Vantage binary not found at either release or debug locations. 
    echo Please build it first: cd E:\DEV\opensource_contrib\Vantage\cli ^& cargo build --release
    exit /b 1
)

%VANTAGE_BIN% %*
