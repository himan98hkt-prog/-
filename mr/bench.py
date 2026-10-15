#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""회귀 테스트 정확도 리포트.

    python bench.py                 # 현재 엔진
    python bench.py --compare       # 고정분할(프로토타입 방식) 대비 개선폭
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piano_mr import evaluate  # noqa: E402

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--compare', action='store_true',
                    help='적응형 분할 on/off 를 나란히 비교')
    ap.add_argument('--stages', action='store_true',
                    help='프로토타입 -> 현재까지 무엇이 얼마나 올렸는지')
    ap.add_argument('--seg-target', type=float, default=2.0)
    ap.add_argument('--worst', type=int, default=5)
    a = ap.parse_args()

    suite = evaluate.run_suite(FIX, seg_target=a.seg_target, adaptive=True)
    print('■ 회귀 테스트 — 오리지널 20곡 (정답 화성 대조)\n')
    print(suite.table())

    if a.compare:
        fixed = evaluate.run_suite(FIX, seg_target=a.seg_target, adaptive=False)
        print('\n■ 적응형 분할 off (고정 분할만)\n')
        print(fixed.table())
        print(f'\n개선폭: 화성 {(suite.accuracy - fixed.accuracy) * 100:+.1f}%p  '
              f'틀린 마디 {fixed.bars_wrong} -> {suite.bars_wrong}')

    if a.stages:
        print('\n■ 1단계 보강이 각각 얼마나 올렸나\n')
        stages = [
            ('프로토타입 방식 (마디 분할 + 3화음만)',
             dict(split_mode='legacy', sevenths=False)),
            ('  + 딸림7화음 · V/vi 후보', dict(split_mode='legacy')),
            ('  + 박에 맞춘 고정 분할', dict(split_mode='fixed')),
            ('  + 적응형 분할 (현재)', dict(split_mode='adaptive')),
        ]
        print(f"{'구성':<38} {'화성':>7} {'7화음':>7} {'틀린마디':>9}")
        for name, kw in stages:
            su = evaluate.run_suite(FIX, **kw)
            print(f'{name:<38} {su.accuracy * 100:6.1f}% '
                  f'{su.accuracy_strict * 100:6.1f}% '
                  f'{su.bars_wrong:5d}/{su.bars_total}')

    worst = suite.worst(a.worst)
    if worst and worst[0].accuracy < 1.0:
        print(f'\n■ 정확도가 낮은 {len(worst)}곡')
        for r in worst:
            if r.accuracy >= 1.0:
                continue
            print(f'  {r.song_id:<24} {r.accuracy * 100:5.1f}%  '
                  f'틀린 마디 {r.wrong_bars}')
    print('\n완료 기준(지시서 11장): 화성 정확도 95% 이상 · 1곡 5초 이내')
    print(f'현재: {suite.accuracy * 100:.1f}% · 최대 {suite.slowest:.2f}초 '
          f'· 조성 {suite.key_accuracy * 100:.0f}%')
    return 0 if suite.accuracy >= 0.95 else 1


if __name__ == '__main__':
    raise SystemExit(main())
