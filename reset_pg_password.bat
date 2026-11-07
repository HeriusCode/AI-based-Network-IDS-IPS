@echo off
chcp 65001 >nul
title Dat lai mat khau PostgreSQL thanh 123456

:: Kiem tra quyen Administrator, neu chua co thi tu dong prompt UAC
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [!] Dang yeu cau quyen Administrator...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

:: Goi script PowerShell da duoc chuan bi
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0reset_pg_password.ps1"

