# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

FIXTURES = os.path.join(ROOT, 'fixtures')
SCORES = os.path.join(FIXTURES, 'scores')


def score(name: str) -> str:
    return os.path.join(SCORES, name + '.musicxml')
