@echo off
rem ============================================================
rem  Chinese REPL for the trained model (double-click to run).
rem  Loads runs\cmd-zh-s0.pt, no board / no GCC / no serial needed.
rem ============================================================
rem
rem  This file is deliberately PURE ASCII. cmd.exe parses .bat bytes with
rem  the OEM code page (936 here), so UTF-8 Chinese in a batch file gets
rem  shredded into fake commands -- it does not merely look garbled, the
rem  script stops working. All Chinese text is printed by Python instead
rem  (console is switched to UTF-8 below).
rem
rem  chcp 65001 : without it, typed Chinese reaches Python as GBK bytes and
rem               the tokenizer (UTF-8) sees garbage -- silently.
rem  PYTHONUTF8 : without it, Python reads the Chinese BPE / eval files as
rem               GBK on Windows and raises UnicodeDecodeError.

setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "..\.venv\Scripts\python.exe" set "PY=..\.venv\Scripts\python.exe"
if not defined PY if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" set "PY=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not defined PY (
  where python >nul 2>nul
  if not errorlevel 1 set "PY=python"
)

if not defined PY (
  echo.
  echo   Python not found. Create the environment first:
  echo     uv venv
  echo     uv pip install torch numpy tokenizers
  echo.
  pause
  exit /b 1
)

if not exist "runs\cmd-zh-s0.pt" (
  echo.
  echo   runs\cmd-zh-s0.pt is missing - the Chinese checkpoint was not copied here.
  echo.
  pause
  exit /b 1
)

"%PY%" src\zh_demo.py %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo   exited with code %RC%
  pause
)
endlocal
