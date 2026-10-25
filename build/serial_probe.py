#!/usr/bin/env python3
"""Open the board's serial console, capture the boot banner, drive it by hand.

The sketch only writes to USB CDC once a host has the port open, so the banner
printed in setup() is normally lost by the time esptool lets go of the port.
Toggling DTR/RTS first gives the chip a reset with the port already open, which
is what makes the banner visible.
"""
import sys
import time

import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM7"
BAUD = 115200

LINES = [
    "turn on pin 4",
    "blink pin 4 every 500ms 3 times",
    "chase pins 2 3 4 every 1 second",
    "turn on pin 4 5 and 6",
    "switch off pin 100",
    "blink pin 4 every 60 seconds",
    "chase pins 1 2 3 4 5 6 7 8 9 every 1 second",
    "turn on the aquarium pump",
    "alias desk lamp = 4",
    "turn on the desk lamp",
    "alias",
    "TURN OFF 39",
]


def read_for(s, seconds, label=""):
    end = time.time() + seconds
    buf = b""
    while time.time() < end:
        chunk = s.read(256)
        if chunk:
            buf += chunk
            end = time.time() + 0.7      # keep reading while output keeps arriving
    text = buf.decode("utf-8", "replace")
    if label:
        print(f"[{label}]")
    print(text, end="" if text.endswith("\n") else "\n")
    return text


def main():
    s = serial.Serial(PORT, BAUD, timeout=0.3)
    time.sleep(0.4)
    try:
        s.dtr = False
        s.rts = True
        time.sleep(0.15)
        s.rts = False
        time.sleep(0.05)
    except Exception as exc:
        print(f"(reset toggle unavailable: {exc})")

    read_for(s, 3.0, "boot banner")

    for line in LINES:
        s.write((line + "\n").encode())
        s.flush()
        read_for(s, 4.0, line)

    s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
