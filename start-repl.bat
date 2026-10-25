@echo off
rem ============================================================
rem  Host-side REPL on the C runtime (not PyTorch).
rem  Reads firmware\model\model.bin -- currently the Chinese model,
rem  exported from runs\cmd-zh-s0.pt.
rem
rem  Why this exists next to start-repl-zh.bat:
rem    this one       = the C code that will run on the board.
rem                     Same tokenizer, same forward pass. What you see
rem                     here is what the ESP32 will do. Labels are English
rem                     because they are printf strings compiled into
rem                     command.h, shared with the device serial log.
rem    start-repl-zh  = PyTorch, Chinese labels, friendlier explanations.
rem
rem  Keep this file PURE ASCII: cmd.exe parses .bat bytes with the OEM
rem  code page (936), so UTF-8 Chinese here is shredded into fake commands
rem  and the script stops working -- not just garbled.
rem ============================================================

setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist "build\repl.exe" (
  echo.
  echo   build\repl.exe not found. Build it first:
  echo     gcc -O3 -Ifirmware/generated -o build\repl.exe firmware/host_verify/repl.c -lm
  echo.
  pause
  exit /b 1
)
if not exist "firmware\model\model.bin" (
  echo.
  echo   firmware\model\model.bin not found. Export it first:
  echo     .venv\Scripts\python.exe src\export.py zh-s0
  echo.
  pause
  exit /b 1
)

echo ============================================================
echo  C runtime REPL - what the board itself will answer
echo  Model: firmware\model\model.bin  (Chinese, cmd-zh-s0)
echo ============================================================
echo.
echo  Type a Chinese sentence and press Enter.
echo  Same examples as start-repl-zh.bat, and see that file for them.
echo  Ctrl-Z then Enter, or Ctrl-C, to quit.
echo ------------------------------------------------------------
echo.

build\repl.exe firmware\model\model.bin --pretty
echo.
echo (repl closed)
pause
endlocal
