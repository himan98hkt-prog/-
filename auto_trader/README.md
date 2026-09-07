# Multi-Agent 주식 완전 자동매매 프로그램

한국투자증권(KIS) Open API로 **국내 주식**을 대상으로, Claude와 Gemini 두 AI의 **합의(Consensus)** 에 따라
매수/매도/관망을 결정하고 자동 실행하는 프로그램입니다.

> **현재 상태: Step 2(KIS 연동) 완료.** 데이터 파이프라인·AI 판단은 Step 3 이후 단계에서 연결됩니다.

## 절대 규칙

1. **모의투자 우선** — 기본 도메인은 KIS 모의투자(`openapivts...:29443`). 실전 전환은 `.env`의 `KIS_ENV=REAL` 로만 가능.
2. **DRY_RUN 필수** — `DRY_RUN=true`면 주문 API를 호출하지 않고 로그·알림만 남깁니다.
3. **리스크 규칙 > AI 판단** — 리스크 규칙을 위반하는 주문은 AI가 강하게 권해도 실행하지 않습니다.
4. **AI 응답 파싱 실패 = HOLD**.
5. **프로그램은 죽지 않는다** — 종목·사이클 단위 예외를 모두 잡고, 치명적 오류만 알림 후 안전 종료.

## 빠른 시작

```bash
cd auto_trader
python -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -r requirements.txt

cp .env.example .env        # 키 입력 (KIS_ENV=VTS, DRY_RUN=true 유지)
python -c "from config.loader import load; print(load())"   # 설정 검증 (비밀값 마스킹 출력)
python main.py              # 로깅 구성 + SQLite 스키마 생성 + 구성 요약

pytest                      # 단위 테스트 (외부 API는 전부 mock)
python scripts/test_kis.py  # 모의계좌 실연동 검증 (조회 + 1주 매수/매도)
```

`scripts/test_kis.py` 는 토큰 캐시 → 시세·일봉·호가 → 잔고 → **1주 시장가 매수 → 체결 확인 → 1주 매도**
순으로 확인합니다. 조회만 하려면 `--no-order`, 종목을 바꾸려면 `--code 000660`.
실전(`KIS_ENV=REAL`)에서는 주문 단계를 자동으로 건너뜁니다.

`.env` 필수 키가 빠지면 **누락 항목을 한 번에 모아** 알려줍니다.

## 설정

| 파일 | 용도 |
|---|---|
| `.env` | 비밀값·실행 환경 (`KIS_ENV`, `DRY_RUN`, API 키). git 제외 |
| `config/settings.yaml` | 매매 파라미터 (유니버스·스케줄·리스크·AI) |
| `config/holidays.txt` | KRX 휴장일 (`YYYY-MM-DD` 한 줄씩, 선택 — 없거나 비면 주말만 제외하고 경고) |

주요 리스크 파라미터: 운용 총액 `total_investment_cap_krw`, 종목당 비중 `max_position_pct`,
동시 보유 `max_positions`, 당일 손실 한도 `daily_loss_limit_pct`, 손절 `stop_loss_pct`, 익절 `take_profit_pct`.

## 구조

```
auto_trader/
├── main.py                 진입점 (Step 1: 부트스트랩 / Step 6: 스케줄러)
├── config/loader.py        .env + settings.yaml 로드·검증 (비밀값 마스킹)
├── agents/                 Claude·Gemini 판단 엔진, 프롬프트, 스키마      (Step 4)
├── trading/                KIS 인증·API·주문 실행·장 운영일 판단          (Step 2, 5)
├── data_pipeline/          유니버스·시세/지표·뉴스 수집                   (Step 3)
├── logic/                  합의 엔진·리스크 규칙·포트폴리오               (Step 5)
├── utils/                  로거·DB·알림·재시도                            (Step 1, 2, 5)
├── data/                   trader.db, token.json, snapshots/  (git 제외)
└── logs/                   trader_YYYYMMDD.log (10MB × 5 회전, git 제외)
```

## KIS 연동 (Step 2)

| 모듈 | 역할 |
|---|---|
| `trading/kis_auth.py` | 토큰 발급·캐시(`data/token.json`)·갱신, hashkey, 공통 헤더, TR_ID 매핑 |
| `trading/kis_api.py` | 시세·잔고·주문 래퍼 + 초당 호출 제한 |
| `trading/market_calendar.py` | 장 운영일/시간 판단 (09:00–15:30 KST, 휴장일 파일) |

- **토큰은 만료 10분 전에만 재발급**합니다. KIS 발급 횟수 제한 때문에 매 실행 발급은 금지이며,
  환경(모의↔실전)이나 APP KEY가 바뀌면 캐시를 재사용하지 않습니다.
- **초당 호출 제한**: 모의 2건/초, 실전 19건/초(공식 20건에서 1건 여유)를 rate limiter가 강제합니다.
- **주문 API는 재시도하지 않습니다** — 중복 주문을 막기 위해, 실패 시 체결 조회로 상태를 확인합니다.
  조회 API만 `@retry(max=3, backoff=2)` 대상입니다.
- TR_ID는 `trading/kis_auth.py:TR_IDS` 한 곳에서 실전(`T`)/모의(`V`) 접두어로 매핑합니다.
  매수 `TTTC0802U`/`VTTC0802U`, 매도 `TTTC0801U`/`VTTC0801U`, 시장가 `ORD_DVSN=01`, 지정가 `00`.
- **거래량 순위 API는 모의투자 도메인에서 제공되지 않습니다.** VTS에서 호출하면 명확한
  `KisApiError`를 던지므로, 유니버스는 `watchlist` 모드를 사용하세요(Step 3에서 자동 폴백 처리).

## 데이터베이스 (`data/trader.db`)

| 테이블 | 내용 |
|---|---|
| `positions` | 보유 포지션 스냅샷 (매 사이클 KIS 잔고로 동기화) |
| `orders` | 주문·체결 내역 (DRY_RUN 주문 포함, `dry_run`·`kis_env` 컬럼으로 구분) |
| `decisions` | AI 원문 응답 + 파싱 결과 + 최종 결정 + 리스크 판정 (사후 검증용) |
| `daily_pnl` | 일자별 손익 요약 |

## 로깅

- `logs/trader_YYYYMMDD.log` — 10MB 롤링 5개, 콘솔 동시 출력, 시각은 항상 KST.
- `utils.logger.register_secret()` 에 등록한 값은 모든 로그에서 `***REDACTED***` 로 치환됩니다.

## 개발 단계

| Step | 범위 | 상태 |
|---|---|---|
| 1 | 뼈대: 구조·설정 로더·로거·DB 스키마 | ✅ 완료 |
| 2 | KIS 연동 (토큰 캐시, 시세/잔고/주문 API, 장 운영일) | ✅ 코드·테스트 완료 / 모의계좌 실연동 검증 대기 |
| 3 | 데이터 파이프라인 (유니버스·지표·뉴스) | 대기 |
| 4 | AI 에이전트 (Claude/Gemini 병렬 호출·JSON 파싱) | 대기 |
| 5 | 합의·리스크·주문 실행·알림 | 대기 |
| 6 | 스케줄러 조립 (apscheduler, 시그널, 일간 리포트) | 대기 |
| 7 | 모의투자 실주문 검증 (5거래일 무인 운영) | 대기 |

각 Step은 완료 후 사용자 확인을 받고 다음 단계로 넘어갑니다.

## 범위 밖

백테스팅, 해외주식, 선물/옵션, 신용거래, 웹 대시보드는 이번 개발 범위에 포함하지 않습니다.
