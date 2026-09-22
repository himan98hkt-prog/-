# -*- coding: utf-8 -*-
"""피아노학원 자동 반주(MR) 엔진.

파이프라인 (지시서 4장):
    악보 -> ① score_loader -> ② harmony -> [화성 확인] -> ③ orchestration/arranger
         -> ④ render -> 음원
"""
__version__ = '0.1.0'

from . import arranger, catalog, harmony, orchestration, render, score_loader  # noqa: F401

__all__ = ['score_loader', 'harmony', 'orchestration', 'arranger', 'render',
           'catalog', '__version__']
