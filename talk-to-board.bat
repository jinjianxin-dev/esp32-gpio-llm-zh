@echo off
title espcontrol - talk to your ESP32-S3
echo ============================================================
echo   espcontrol : type English, the board drives its GPIO pins
echo ============================================================
echo.
echo   Try these:
echo     turn on pin 4
echo     blink pin 4 every 500ms 3 times
echo     chase pins 2 3 4 every 1 second
echo     switch off pin 100            (refused - no such pin)
echo     blink pin 4 every 60 seconds  (refused - interval too long)
echo.
echo   Give a pin a name, then use the name:
echo     alias desk lamp = 4
echo     turn on the desk lamp
echo.
echo   Press Ctrl+C to quit.
echo ------------------------------------------------------------
echo.
"C:\Users\aaron\WorkBuddy\2026-10-15-18-26-44\tools\arduino-cli\arduino-cli.exe" --config-file "C:\Users\aaron\WorkBuddy\2026-10-15-18-26-44\tools\arduino-cli\arduino-cli.yaml" monitor -p COM7 --config baudrate=115200
echo.
echo (monitor closed)
pause
