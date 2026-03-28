@echo off
rem .kit Plugin Shim for Vantage (v1.2.3)
rem [ARCHITECTURE MANDATE: THE VANTAGE PROTOCOL SHIM]
rem Delegates 'kit vantage ...' to the Vantage CLI binary

set VANTAGE_BIN="E:\DEV\opensource_contrib\Vantage\target\debug\vantage.exe"

if not exist %VANTAGE_BIN% (
    echo [kit-vantage] Error: Vantage binary not found. 
    echo Please build it first: cd E:\DEV\opensource_contrib\Vantage\cli ^&^& cargo build
    exit /b 1
)

%VANTAGE_BIN% %*
