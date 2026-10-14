"""Shared plugin launcher: find the installed CLI even outside a shell's PATH."""

import os
from pathlib import Path
import shutil
import sys


def main():
    binary = os.environ.get("THINGS_CLI_BINARY") or shutil.which("things-cli") or str(Path.home() / ".local/bin/things-cli")
    try:
        os.execv(binary, [binary, "serve"])
    except OSError:
        print("Cannot start Things CLI. Install the macOS/Linux package, then run things-cli login in your terminal.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
