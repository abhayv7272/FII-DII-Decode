#!/usr/bin/env python3
"""Convenience entry point for the historical replay harness.

Equivalent to:
    PYTHONPATH=src python -m fiidii.cli backtest ...
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fiidii.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["backtest", *sys.argv[1:]]))
