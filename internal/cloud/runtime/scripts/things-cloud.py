#!/usr/bin/env python3
"""Stable launcher usable directly from any installed plugin folder."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from things_cloud.cli import main

raise SystemExit(main())
