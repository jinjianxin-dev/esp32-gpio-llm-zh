"""End-to-end chain gate, run against the generated val split.

scripts/release.sh's gate 3 compares the C runtime against PyTorch over the
project's held-out sets (data/eval/*.jsonl). Those files are gitignored and the
author did not publish them, so c_check.py correctly refuses to run rather than
reporting PASS on zero utterances.

This is the same comparison over the generated val split instead: identical
loop, identical stopping rule, identical prompt truncation, only the source of
the utterances differs. It proves the port, not the model's held-out quality --
those are different questions and the generated split cannot answer the second.

    uv run python build/gate3_chain_check.py [limit]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data"))

os.chdir(ROOT)

import c_check                               # noqa: E402
from evaluate import Decoder                 # noqa: E402

BIN = ROOT / "build" / "repl.exe"
MODEL = ROOT / "firmware" / "model" / "model.bin"
RUN = ROOT / "runs" / "cmd-v1-s0.pt"


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 500

    texts = [json.loads(l)["text"]
             for l in (ROOT / "data" / "corpus" / "val.jsonl").open()]
    texts = [t for t in texts if "\n" not in t and t.strip()][:limit]
    print(f"{len(texts)} utterances from data/corpus/val.jsonl")

    proc = subprocess.run([str(BIN), str(MODEL)],
                          input="\n".join(texts) + "\n",
                          capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"repl failed: {proc.stderr[:400]}")
    got = proc.stdout.strip().split("\n")

    dec = Decoder(RUN)
    bad = 0
    for i, t in enumerate(texts):
        want = c_check.torch_ids(dec, t)
        mine = ([int(x) for x in got[i].split()]
                if i < len(got) and got[i].strip() else [])
        if want != mine:
            bad += 1
            if bad <= 6:
                print(f"MISMATCH {i}: {t!r}\n  torch: {want}\n  c    : {mine}")

    print(f"\n{len(texts) - bad}/{len(texts)} utterances match")
    if bad:
        print(f"FAIL: {bad} mismatched")
        return 1
    print("PASS: the C chain reproduces PyTorch on every utterance")
    return 0


if __name__ == "__main__":
    sys.exit(main())
