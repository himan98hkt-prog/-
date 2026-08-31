# 골든 회귀 리포트

- 생성 시각: 2026-08-31T06:36:41+00:00
- 엔진: `stub`
- 프롬프트 버전: `motif`=motif-v3.1, `plan`=plan-v3.1, `realize_phrase`=realize-v3.1, `critic`=critic-v3.1

## 요약

| 지표 | 값 |
|---|---|
| 케이스 | 20 |
| 하드 검증 통과율 | 100% |
| 프레이즈 완성률 | 100% |
| 평균 musicality(10점) | 7.953 |
| 평균 종합점수 | 8.25 |
| 품질 문턱 통과율 | 100% |
| 난이도 ±1 적중률 | 60% (기준선 55%) |
| 총 API 비용 | $0.0 |

## 케이스별

| id | 마디 | 검증 | musicality | 비평 | 종합 | 라운드 | 난이도(목표) | 미달 지표 |
|---|---|---|---|---|---|---|---|---|
| g01 | 52/52 | 통과 | 7.98 | 8.45 | 8.26 | 0 | 3.78(3.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g02 | 52/52 | 통과 | 8.17 | 8.55 | 8.4 | 0 | 4.57(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g03 | 60/60 | 통과 | 7.92 | 8.37 | 8.19 | 0 | 4.11(5.0) | repetition_balance, melodic_contour, harmonic_consistency, dynamic_curve |
| g04 | 28/28 | 실패 difficulty | 6.56 | 7.87 | 7.35 | 0 | 3.33(2.0) | motif_consistency, repetition_balance, melodic_contour, harmonic_consistency |
| g05 | 88/88 | 통과 | 8.07 | 8.55 | 8.36 | 0 | 5.35(6.0) | motif_consistency, harmonic_consistency |
| g06 | 68/68 | 통과 | 8.25 | 8.6 | 8.46 | 0 | 4.68(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g07 | 92/92 | 실패 difficulty | 8.2 | 8.61 | 8.45 | 0 | 5.45(7.0) | motif_consistency, harmonic_consistency |
| g08 | 76/76 | 실패 difficulty | 8.03 | 8.38 | 8.24 | 0 | 4.09(3.0) | repetition_balance, harmonic_consistency, playability |
| g09 | 80/80 | 통과 | 8.54 | 8.76 | 8.67 | 0 | 4.47(5.0) | melodic_contour, harmonic_consistency |
| g10 | 44/44 | 통과 | 8.09 | 8.51 | 8.34 | 0 | 4.21(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g11 | 80/80 | 통과 | 8.2 | 8.62 | 8.45 | 0 | 5.24(6.0) | harmonic_consistency |
| g12 | 24/24 | 실패 difficulty | 6.51 | 7.86 | 7.32 | 0 | 3.17(2.0) | motif_consistency, repetition_balance, harmonic_consistency, dynamic_curve |
| g13 | 96/96 | 실패 difficulty | 8.6 | 8.73 | 8.68 | 0 | 6.58(8.0) | harmonic_consistency, playability |
| g14 | 60/60 | 통과 | 7.84 | 8.33 | 8.13 | 0 | 4.64(5.0) | repetition_balance, melodic_contour, harmonic_consistency, dynamic_curve |
| g15 | 44/44 | 통과 | 8.04 | 8.48 | 8.3 | 0 | 3.97(3.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g16 | 48/48 | 실패 difficulty | 7.22 | 8.02 | 7.7 | 0 | 4.29(7.0) | repetition_balance, harmonic_consistency, dynamic_curve |
| g17 | 60/60 | 통과 | 7.91 | 8.36 | 8.18 | 0 | 4.44(4.0) | repetition_balance, melodic_contour, harmonic_consistency, dynamic_curve |
| g18 | 56/56 | 실패 difficulty | 8.14 | 8.63 | 8.43 | 0 | 4.98(6.0) | repetition_balance, harmonic_consistency |
| g19 | 64/64 | 통과 | 8.18 | 8.56 | 8.41 | 0 | 4.44(5.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g20 | 96/96 | 실패 difficulty | 8.61 | 8.73 | 8.68 | 0 | 6.47(9.0) | harmonic_consistency, playability |
