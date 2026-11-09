@echo off
chcp 65001 >nul 2>&1
title JPX Lab • Automation Leads & CRM v3.2
cd /d "%~dp0"

echo.
echo   ======================================================================
echo    JPX LAB • AUTOMATION LEADS ^& CRM v3.2 (Rust + Python + Cofre AEAD)
echo   ======================================================================
echo.

REM 1. Se o binario otimizado em Rust ja existir, executa imediatamente
if exist "target\release\jpx-crm.exe" (
    echo   [OK] Iniciando motor nativo otimizado ^(target\release\jpx-crm.exe^)...
    "target\release\jpx-crm.exe" serve
    goto :fim
)

REM 2. Se o compilador Rust (cargo) estiver disponivel, compila com otimizacao maxima (LTO + O3)
where cargo >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [BUILD] Compilando executavel nativo otimizado em Rust ^(--release^)...
    cargo build --release
    if exist "target\release\jpx-crm.exe" (
        "target\release\jpx-crm.exe" serve
        goto :fim
    )
)

REM 3. Fallback direto em Python (cria .venv e instala dependencias automaticamente)
if exist ".venv\Scripts\python.exe" (
    echo   [OK] Iniciando pelo ambiente virtual Python ^(.venv^)...
    ".venv\Scripts\python.exe" app.py
    goto :fim
)

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [SETUP] Preparando ambiente e iniciando aplicacao...
    python app.py
    goto :fim
)

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   [SETUP] Preparando ambiente via Python Launcher...
    py -3 app.py
    goto :fim
)

echo   [ERRO] Python 3 ou Rust nao foram encontrados no sistema.
echo   Instale Python 3.11+ em https://www.python.org/downloads/
pause

:fim
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   O processo encerrou com codigo %ERRORLEVEL%.
    pause
)
