#!/usr/bin/env bash
# Build espcontrol with *this* project's tokenizer and model, merge it into one
# image, and flash it.
#
# Everything is self-consistent here in a way the official release image is not:
# the sketch compiles against the bpe.h / symbols.h that gen_assets.py produced
# from this project's data/bpe.json, and model.bin was exported by this
# project's export.py. Mixing an official app image with a locally trained model
# gives valid-looking but wrong commands with nothing in the logs, so the two
# halves are always rebuilt together.
#
# All heavy artefacts live on E: -- this machine's C: is full, and an
# arduino-cli build of the ESP32 core leaves hundreds of MB of objects behind.
#
#   ./flash.sh COM7
set -euo pipefail

PORT="${1:-COM7}"

ACLI="C:/Users/aaron/WorkBuddy/2026-10-15-18-26-44/tools/arduino-cli/arduino-cli.exe"
CFG="C:/Users/aaron/WorkBuddy/2026-10-15-18-26-44/tools/arduino-cli/arduino-cli.yaml"
ROOT="C:/Users/aaron/WorkBuddy/2026-10-15-18-26-44/esp32-gpio-llm"

WORK="E:/esp32-tools/build"
BUILD="$WORK/sketch"
DIST="E:/esp32-tools/dist"
IMAGE="$DIST/espcontrol-esp32s3-local.bin"
SKETCH="$ROOT/firmware/device/espcontrol"
BOOT_APP0="E:/esp32-tools/arduino15/packages/esp32/hardware/esp32/3.3.12/tools/partitions/boot_app0.bin"

# PSRAM=opi  : this board has 8 MB in-package octal PSRAM; the ~200 KB KV cache
#              is allocated there first.
# CDCOnBoot=cdc: Serial goes to the chip's own USB, which is the port we flash
#              through. Match this to the physical port or the console is silent.
# PartitionScheme=custom: without it partitions.csv is ignored, the `model`
#              partition does not exist, and setup() stops at "no 'model' partition".
FQBN='esp32:esp32:esp32s3:PartitionScheme=custom,PSRAM=opi,CDCOnBoot=cdc'

step() { printf '\n=== %s ===\n' "$1"; }

step "sync shared sources into the sketch directory"
bash "$ROOT/firmware/device/sync.sh"

step "compile  ($FQBN)"
mkdir -p "$BUILD" "$DIST"
"$ACLI" compile --config-file "$CFG" --fqbn "$FQBN" \
  --build-path "$BUILD" --output-dir "$DIST/out" "$SKETCH" 2>&1 | tail -14

step "check the model still fits its partition"
PART_HEX=$(awk -F',' '/^model,/ {gsub(/[ \t]/,"",$5); print $5}' "$SKETCH/partitions.csv")
PART_BYTES=$((PART_HEX))
MODEL_BYTES=$(wc -c < "$ROOT/firmware/model/model.bin" | tr -d ' ')
printf 'model.bin %s bytes into a %s byte partition\n' "$MODEL_BYTES" "$PART_BYTES"
if [ "$MODEL_BYTES" -gt "$PART_BYTES" ]; then
  echo "FAIL: model.bin overflows the model partition by $((MODEL_BYTES - PART_BYTES)) bytes" >&2
  exit 1
fi
echo "PASS: fits with $((PART_BYTES - MODEL_BYTES)) bytes spare"

step "merge into one flashable image"
[ -f "$BOOT_APP0" ] || { echo "boot_app0.bin not found at $BOOT_APP0" >&2; exit 1; }
cd "$ROOT"
uv run --with esptool python -m esptool --chip esp32s3 merge_bin -o "$IMAGE" \
  --flash_mode dio --flash_freq 80m --flash_size 16MB \
  0x0      "$BUILD/espcontrol.ino.bootloader.bin" \
  0x8000   "$BUILD/espcontrol.ino.partitions.bin" \
  0xe000   "$BOOT_APP0" \
  0x10000  "$BUILD/espcontrol.ino.bin" \
  0x210000 "$ROOT/firmware/model/model.bin" 2>&1 | tail -6

step "flash to $PORT"
uv run --with esptool python -m esptool --chip esp32s3 --port "$PORT" --baud 921600 \
  --before default-reset --after hard-reset write_flash 0x0 "$IMAGE" 2>&1 | tail -18

printf '\nflashed %s\n' "$IMAGE"
