# 골든 회귀 리포트

- 생성 시각: 2026-09-01T12:47:13+00:00
- 엔진: `stub`
- 프롬프트 버전: `motif`=motif-v3.1, `plan`=plan-v3.1, `realize_phrase`=realize-v3.1, `critic`=critic-v3.1

## 요약

| 지표 | 값 |
|---|---|
| 케이스 | 20 |
| 하드 검증 통과율 | 100% |
| 프레이즈 완성률 | 100% |
| 평균 musicality(10점) | 7.867 |
| 평균 종합점수 | 8.22 |
| 품질 문턱 통과율 | 100% |
| 난이도 ±1 적중률 | 55% (기준선 55%) |
| 총 API 비용 | $0.0 |
| 형식 유사도 최대 | 1.00 (한계 0.60) |
| 같은 틀로 걸리는 쌍 | 39쌍 |

> 형식 유사도는 **재기만 한다**. 규칙 기반 스텁은 모든 요청에 같은 설계
> 뼈대를 내놓으므로 여기서는 높게 나오는 것이 정상이다 — 스텁의 알려진
> 한계다. 실제 작곡 경로(API·세션 엔진)에서는 Plan 규칙이 하드로 막는다.

## 케이스별

| id | 마디 | 검증 | musicality | 비평 | 종합 | 라운드 | 난이도(목표) | 미달 지표 |
|---|---|---|---|---|---|---|---|---|
| g01 | 48/48 | 통과 | 7.7 | 8.29 | 8.05 | 1 | 3.81(3.0) | repetition_balance, melodic_contour, harmonic_consistency, dynamic_curve |
| g02 | 50/50 | 통과 | 8.0 | 8.52 | 8.31 | 1 | 4.58(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g03 | 56/56 | 통과 | 7.95 | 8.47 | 8.26 | 1 | 4.16(5.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g04 | 24/24 | 실패 difficulty | 6.32 | 7.62 | 7.1 | 1 | 3.12(2.0) | motif_consistency, repetition_balance, melodic_contour, harmonic_consistency, dynamic_curve |
| g05 | 80/80 | 통과 | 7.82 | 8.39 | 8.16 | 1 | 5.07(6.0) | motif_consistency, harmonic_consistency |
| g06 | 62/62 | 통과 | 8.23 | 8.61 | 8.46 | 1 | 4.64(4.0) | melodic_contour, harmonic_consistency |
| g07 | 86/86 | 실패 difficulty | 8.11 | 8.62 | 8.42 | 1 | 5.22(7.0) | motif_consistency, harmonic_consistency |
| g08 | 70/70 | 실패 difficulty | 8.35 | 8.61 | 8.51 | 1 | 4.08(3.0) | repetition_balance, harmonic_consistency |
| g09 | 72/72 | 통과 | 8.36 | 8.7 | 8.56 | 1 | 4.45(5.0) | melodic_contour, harmonic_consistency |
| g10 | 42/42 | 통과 | 7.7 | 8.4 | 8.12 | 1 | 4.2(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g11 | 72/72 | 실패 difficulty | 7.74 | 8.44 | 8.16 | 1 | 4.99(6.0) | motif_consistency, repetition_balance, harmonic_consistency |
| g12 | 22/22 | 실패 difficulty | 6.79 | 7.96 | 7.49 | 1 | 3.14(2.0) | motif_consistency, repetition_balance, harmonic_consistency, dynamic_curve |
| g13 | 96/96 | 실패 difficulty | 8.46 | 8.82 | 8.68 | 1 | 6.25(8.0) | harmonic_consistency |
| g14 | 58/58 | 통과 | 7.96 | 8.46 | 8.26 | 1 | 4.64(5.0) | melodic_contour, harmonic_consistency, dynamic_curve |
| g15 | 42/42 | 통과 | 7.7 | 8.4 | 8.12 | 1 | 3.98(3.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g16 | 46/46 | 실패 difficulty | 7.8 | 8.39 | 8.15 | 1 | 4.08(7.0) | repetition_balance, harmonic_consistency |
| g17 | 56/56 | 통과 | 8.07 | 8.54 | 8.35 | 1 | 4.48(4.0) | repetition_balance, melodic_contour, harmonic_consistency |
| g18 | 50/50 | 실패 difficulty | 7.57 | 8.37 | 8.05 | 1 | 4.74(6.0) | motif_consistency, repetition_balance, harmonic_consistency |
| g19 | 60/60 | 통과 | 8.27 | 8.69 | 8.52 | 1 | 4.41(5.0) | melodic_contour, harmonic_consistency |
| g20 | 96/96 | 실패 difficulty | 8.44 | 8.82 | 8.67 | 1 | 6.14(9.0) | harmonic_consistency |
