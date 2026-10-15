#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""피아노학원 자동 반주(MR) — CLI 진입점.

    python mr.py score.mxl --style chamber --level normal --bpm 84 -o out.mp3
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from piano_mr.cli import main  # noqa: E402

if __name__ == '__main__':
    raise SystemExit(main())
