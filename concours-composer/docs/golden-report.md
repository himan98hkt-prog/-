# 골든 회귀 리포트

- 생성 시각: 2026-08-31T07:24:07+00:00
- 엔진: `stub`
- 프롬프트 버전: `motif`=motif-v3.1, `plan`=plan-v3.1, `realize_phrase`=realize-v3.1, `critic`=critic-v3.1

## 요약

| 지표 | 값 |
|---|---|
| 케이스 | 20 |
| 하드 검증 통과율 | 100% |
| 프레이즈 완성률 | 100% |
| 평균 musicality(10점) | 7.906 |
| 평균 종합점수 | 8.159 |
| 품질 문턱 통과율 | 100% |
| 난이도 ±1 적중률 | 60% (기준선 55%) |
| 총 API 비용 | $0.0 |

## 케이스별

| id | 마디 | 검증 | musicality | 비평 | 종합 | 라운드 | 난이도(목표) | 미달 지표 |
|---|---|---|---|---|---|---|---|---|
| g01 | 52/52 | 통과 | 7.91 | 8.28 | 8.13 | 0 | 3.77(3.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g02 | 52/52 | 통과 | 7.99 | 8.39 | 8.23 | 0 | 4.56(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g03 | 60/60 | 통과 | 8.03 | 8.41 | 8.26 | 0 | 4.13(5.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g04 | 28/28 | 실패 difficulty | 6.44 | 7.5 | 7.08 | 0 | 3.3(2.0) | motif_consistency, repetition_balance, melodic_contour, harmonic_consistency, playability |
| g05 | 88/88 | 통과 | 8.12 | 8.32 | 8.24 | 0 | 5.08(6.0) | motif_consistency, harmonic_consistency, playability |
| g06 | 68/68 | 통과 | 8.19 | 8.45 | 8.35 | 0 | 4.66(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g07 | 92/92 | 실패 difficulty | 8.18 | 8.57 | 8.41 | 0 | 5.24(7.0) | motif_consistency, harmonic_consistency, playability |
| g08 | 76/76 | 실패 difficulty | 7.86 | 8.14 | 8.03 | 0 | 4.1(3.0) | repetition_balance, harmonic_consistency, playability |
| g09 | 80/80 | 통과 | 8.47 | 8.59 | 8.54 | 0 | 4.45(5.0) | melodic_contour, harmonic_consistency |
| g10 | 44/44 | 통과 | 8.07 | 8.45 | 8.3 | 0 | 4.18(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g11 | 80/80 | 통과 | 8.04 | 8.52 | 8.33 | 0 | 5.01(6.0) | harmonic_consistency, playability |
| g12 | 24/24 | 실패 difficulty | 6.36 | 7.58 | 7.09 | 0 | 3.15(2.0) | motif_consistency, repetition_balance, harmonic_consistency, dynamic_curve, playability |
| g13 | 96/96 | 실패 difficulty | 8.58 | 8.69 | 8.65 | 0 | 6.26(8.0) | harmonic_consistency, playability |
| g14 | 60/60 | 통과 | 8.05 | 8.42 | 8.27 | 0 | 4.66(5.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g15 | 44/44 | 통과 | 8.0 | 8.34 | 8.2 | 0 | 3.96(3.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g16 | 48/48 | 실패 difficulty | 7.2 | 7.99 | 7.67 | 0 | 4.05(7.0) | repetition_balance, harmonic_consistency, dynamic_curve, playability |
| g17 | 60/60 | 통과 | 8.01 | 8.34 | 8.21 | 0 | 4.45(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g18 | 56/56 | 실패 difficulty | 7.91 | 8.49 | 8.26 | 0 | 4.72(6.0) | repetition_balance, harmonic_consistency, playability |
| g19 | 64/64 | 통과 | 8.12 | 8.41 | 8.29 | 0 | 4.41(5.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g20 | 96/96 | 실패 difficulty | 8.59 | 8.69 | 8.65 | 0 | 6.15(9.0) | harmonic_consistency, playability |
