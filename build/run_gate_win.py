"""Windows wrapper: run the repo's host gates with native .exe paths.

The repo hardcodes `/tmp/tok_test` and `/tmp/repl`. On Windows, Python resolves
`/tmp/...` against the current drive root and the executables carry a `.exe`
suffix, so both the existence guard and the subprocess call miss. This wrapper
reuses the repo's own test logic and edge cases verbatim -- it only redirects
BIN to the locally built binaries. Nothing about the check itself changes.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

os.chdir(ROOT)

which = sys.argv[1] if len(sys.argv) > 1 else "tok"

if which == "tok":
    import tok_check
    tok_check.BIN = os.path.join(ROOT, "build", "tok_test.exe")
    sys.exit(tok_check.main())

import c_check
c_check.BIN = os.path.join(ROOT, "build", "repl.exe")
sys.exit(c_check.main())
