# Multi-Agent 주식 완전 자동매매 프로그램

한국투자증권(KIS) Open API로 **국내 주식**을 대상으로, Claude와 Gemini 두 AI의 **합의(Consensus)** 에 따라
매수/매도/관망을 결정하고 자동 실행하는 프로그램입니다.

> **현재 상태: 전 단계 코드 완료 + 로컬 대시보드 포함.** 남은 것은 실제 키로 모의투자 5거래일 무인 운영하는 일뿐입니다.

## 절대 규칙

1. **모의투자 우선** — 기본 도메인은 KIS 모의투자(`openapivts...:29443`). 실전 전환은 `.env`의 `KIS_ENV=REAL` 로만 가능.
2. **DRY_RUN 필수** — `DRY_RUN=true`면 주문 API를 호출하지 않고 로그·알림만 남깁니다.
3. **리스크 규칙 > AI 판단** — 리스크 규칙을 위반하는 주문은 AI가 강하게 권해도 실행하지 않습니다.
4. **AI 응답 파싱 실패 = HOLD**.
5. **프로그램은 죽지 않는다** — 종목·사이클 단위 예외를 모두 잡고, 치명적 오류만 알림 후 안전 종료.

## 빠른 시작 — 한 번만 실행하면 됩니다

**macOS / Linux**
```bash
./start.sh
```

**Windows** — `start.bat` 더블클릭

이 한 줄이 가상환경 준비 → 의존성 설치 → 대시보드 실행 → 브라우저 열기까지 합니다.
그 다음은 화면에서:

1. **설정** 화면에 API 키를 붙여넣고 **저장**
2. **키 점검 실행** 으로 전부 ✅ 확인
3. **현황** 화면에서 **▶ 자동매매 시작**

키를 바꾼 뒤에는 **🔄 재시작 (설정 반영)** 을 누르면 새 설정으로 다시 뜹니다.

브라우저를 못 쓰는 환경이면 터미널에서도 입력할 수 있습니다:

```bash
python scripts/setup_keys.py --check   # 항목을 순서대로 묻고 저장 후 점검까지
```

> 어떤 키가 어느 칸에 들어가는지, 어디서 발급받는지는 [`SETUP.md`](SETUP.md) 7장에 표로 정리돼 있습니다.
> 입력한 키는 본인 PC의 `.env` 에만 저장됩니다(권한 0600). 채팅·이슈·PR 에 붙여넣지 마세요.

### 터미널로 직접 다루기

```bash
source .venv/bin/activate

python scripts/setup_keys.py    # 키를 터미널에서 입력
python scripts/check_keys.py    # 키가 실제로 동작하는지 확인
python main.py --check          # 설정·DB·사이클 시각 점검
python main.py --status         # 현재 상태
python main.py --stop           # 긴급 정지 / --resume 로 재개
python main.py                  # 포그라운드로 직접 실행

python scripts/test_kis.py      # 모의계좌 실연동 (평일 09:00~15:30)
python scripts/test_pipeline.py # 스냅샷 수집
python scripts/test_agents.py   # AI 분석
python scripts/test_cycle.py    # DRY_RUN end-to-end
python scripts/export_report.py # 운영 리포트 CSV
pytest                          # 테스트
```

## 설정

| 파일 | 용도 |
|---|---|
| `.env` | 비밀값·실행 환경 (`KIS_ENV`, `DRY_RUN`, API 키). git 제외 |
| `config/settings.yaml` | 매매 파라미터 (유니버스·스케줄·리스크·AI) |
| `config/holidays.txt` | KRX 휴장일 (`YYYY-MM-DD` 한 줄씩, 선택 — 없거나 비면 주말만 제외하고 경고) |

주요 리스크 파라미터: 운용 총액 `total_investment_cap_krw`, 종목당 비중 `max_position_pct`,
동시 보유 `max_positions`, 당일 손실 한도 `daily_loss_limit_pct`, 손절 `stop_loss_pct`, 익절 `take_profit_pct`,
손절 감시 주기 `guard_interval_min`.

## 구조

```
auto_trader/
├── main.py                 진입점 (Step 1: 부트스트랩 / Step 6: 스케줄러)
├── config/loader.py        .env + settings.yaml 로드·검증 (비밀값 마스킹)
├── agents/                 Claude·Gemini 판단 엔진, 프롬프트, 스키마      (Step 4)
├── trading/                KIS 인증·API·주문 실행·장 운영일 판단          (Step 2, 5)
├── data_pipeline/          유니버스·시세/지표·뉴스 수집                   (Step 3)
├── logic/                  합의 엔진·리스크 규칙·포트폴리오               (Step 5)
├── utils/                  로거·DB·알림·재시도·실행락·키점검
├── dashboard/              로컬 웹 대시보드 (설정 입력 + 현황)
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

## 데이터 파이프라인 (Step 3)

| 모듈 | 역할 |
|---|---|
| `data_pipeline/universe.py` | 매매 대상 종목 선정 → `data/universe_YYYYMMDD.json` |
| `data_pipeline/market_data.py` | 현재가·일봉 60일·호가 수집 + 지표 계산 → 고정 스키마 스냅샷 |
| `data_pipeline/news.py` | 네이버 뉴스 검색 (키 없거나 실패하면 빈 리스트) |

- **보유 종목은 유니버스 모드와 무관하게 항상 포함**되고 맨 앞에 옵니다(매도 판단 필요).
  `max_candidates_per_cycle` 상한은 후보에만 적용되고 보유 종목은 제외됩니다.
- 제외 키워드 중 한 글자(`우`)는 **우선주 접미사로만** 판정합니다 — `우리금융지주`처럼
  이름에 포함만 된 종목이 걸러지지 않도록 하기 위함입니다(`삼성전자우`, `현대차2우B`는 제외).
- `volume_rank` 모드에서 거래량 순위 API가 실패하면(모의투자 미지원) **`watchlist`로 자동 폴백**하고
  유니버스 파일에 `source: watchlist(fallback)`으로 기록합니다.
- 지표는 전부 `ta` 라이브러리로 계산합니다: MA5/20/60, RSI14, MACD(12,26,9), 볼린저(20,2),
  거래량 20일 평균 대비 배율. 데이터가 기간보다 짧거나 NaN이면 **0.0으로 접어** JSON 직렬화를 보장합니다.
- 호가·뉴스 수집 실패는 기본값으로 넘어가고, 현재가·일봉 실패만 예외로 올립니다(판단 근거가 없으므로).

## AI 에이전트 (Step 4)

| 모듈 | 역할 |
|---|---|
| `agents/schemas.py` | `AgentDecision` + 응답 검증(범위 clamp, 형식 오류는 예외) |
| `agents/prompts.py` | 시스템/유저 프롬프트와 응답 JSON 스키마 (한 곳에서 관리) |
| `agents/base_agent.py` | 호출 → JSON 추출 → 검증 → 재요청 → HOLD 폴백, 병렬 실행 |
| `agents/claude_agent.py` | Claude (anthropic SDK, Structured Outputs) |
| `agents/gemini_agent.py` | Gemini (google-genai SDK, `response_mime_type=application/json`) |

- **파싱 실패 = HOLD**: 마크다운 코드블록·설명문이 섞이면 첫 `{`~마지막 `}` 만 잘라 파싱하고,
  그래도 실패하면 "JSON만 출력"을 재강조해 `max_retries` 까지 재요청합니다.
  끝내 실패하면 `ok=False`인 HOLD를 반환합니다 — 호출 실패·타임아웃도 동일합니다.
- 두 에이전트는 `concurrent.futures` 로 **병렬 호출**하며, 시작 시점 기준 공통 마감시각으로
  각자 `timeout_sec` 을 갖습니다. 한쪽이 타임아웃·예외로 죽어도 다른 쪽 결과는 살아남습니다.
- 응답 형식은 프롬프트뿐 아니라 **API 차원에서도 강제**합니다(Claude: `output_config.format`
  json_schema / Gemini: `response_schema`). 프롬프트 지시만으로 기대하지 않습니다.

### `temperature` 에 대한 주의

지시서는 Claude에 `temperature=0.2` 를 지정하도록 되어 있으나, **Sonnet 5·Opus 5 등 최신 모델은
`temperature` 파라미터를 거부(HTTP 400)합니다.** 그래서 `CLAUDE_TEMPERATURE` 는 기본적으로 비워 두고
아예 전송하지 않습니다. 구형 모델을 쓸 때만 값을 넣으세요. 값이 설정된 채 모델이 거부하면
경고 로그를 남기고 파라미터를 뺀 뒤 한 번 재시도합니다. Gemini는 `temperature` 를 지원하므로
`GEMINI_TEMPERATURE`(기본 0.2)가 그대로 적용됩니다.

AI 호출 비용은 `CLAUDE_EFFORT`(low/medium/high/xhigh/max)와 `universe.max_candidates_per_cycle`
로 조절합니다.

## 합의·리스크·주문 (Step 5)

| 모듈 | 역할 |
|---|---|
| `logic/decision_maker.py` | 두 AI 판단 → 최종 행동 (합의 매트릭스) |
| `logic/risk_manager.py` | 매수 7개 규칙 + 강제 청산 판정 |
| `logic/portfolio.py` | KIS 잔고 동기화, 주문·결정 기록, 체결 대기 |
| `trading/order_executor.py` | 수량 계산 → 주문 → 체결 확인 → 기록 → 알림 |
| `utils/notifier.py` | 텔레그램/디스코드 알림 (4,096자 분할) |

### 합의 매트릭스

| Claude \\ Gemini | BUY | HOLD | SELL |
|---|---|---|---|
| **BUY** | STRONG_BUY (둘 다 confidence ≥ `min_confidence`) / 아니면 BUY_SMALL | HOLD | HOLD (보유 시 REDUCE) |
| **HOLD** | HOLD | HOLD | HOLD (보유 시 REDUCE) |
| **SELL** | HOLD (보유 시 REDUCE) | HOLD (보유 시 REDUCE) | SELL_ALL (보유 시) |

- 한쪽이라도 파싱 실패(`ok=False`)면 **무조건 HOLD** — 만장일치 매도라도 실행하지 않습니다.
- 미보유 종목의 SELL/REDUCE는 HOLD로 치환합니다.
- `STRONG_BUY` 비중 = 두 AI 권장 비중의 평균, `BUY_SMALL` = 그 절반. 상한은 `max_position_pct`.
- `REDUCE` = 보유수량의 50%, `SELL_ALL` = 전량.

### 리스크 규칙 (AI 판단보다 상위)

1. 총 투자액 + 신규 금액 ≤ `total_investment_cap_krw`
2. 종목 금액(기보유분 포함) ≤ 총액 × `max_position_pct`
3. 보유 종목 수 < `max_positions` (보유 종목 추가매수는 허용)
4. 당일 손익 > `-daily_loss_limit_pct`
5. 현재 시각 ≤ `last_new_buy`
6. 주문 금액 ≥ `min_order_krw`
7. 동일 종목 당일 매수 1회

거부 사유는 로그와 텔레그램 사이클 요약에 그대로 실립니다.
**손절선 도달은 AI 판단 없이 즉시 전량 매도**하고, 익절선 도달은 플래그로 합의 엔진에 전달해
AI가 응답하지 않으면 절반 매도합니다.

**손절 감시(`guard_interval_min`, 기본 3분).** 정규 사이클은 30분 간격이라 그 사이에 급락하면
다음 사이클까지 방치됩니다. 그래서 장중 몇 분마다 **보유 종목의 손절선만** 따로 봅니다.
잔고 조회 1회로 끝나고 AI를 부르지 않으므로 추가 비용이 없습니다. 익절은 AI 재판단이
필요하므로 감시 대상이 아닙니다 — 놓쳐도 자산이 깎이지 않기 때문입니다.

**주문이 거부되면 반드시 알립니다.** 특히 손절 매도가 실패하면 포지션이 그대로 남으므로
`🚨 손절 매도 실패` 로 즉시 알리고, 다음 감시 주기에 다시 시도합니다.

### 주문

- `DRY_RUN=true` 면 주문 API를 호출하지 않고 `[DRY_RUN]` 로그·알림만 남기며, `orders` 테이블에
  `dry_run=1` 로 기록합니다.
- 매수 수량 = `floor(min(가용현금, 총액×비중%) / 현재가)` — 0주면 스킵합니다.
- 체결은 최대 30초 동안 5초 간격으로 확인하고, **지정가 미체결은 취소**, 시장가 미체결은
  다음 사이클에서 재조회합니다.

## 스케줄러 (Step 6)

`python main.py` 로 기동하면 아래 잡이 **평일**에 등록되고, 각 잡은 실행 시점에 휴장일을 다시 확인합니다.

| 잡 | 시각 (`settings.yaml`) | 내용 |
|---|---|---|
| 유니버스 갱신 | `universe_refresh` (08:30) | 매매 대상 종목 재구성 |
| 사이클 | `first_cycle`(09:05)부터 `cycle_interval_min`(30분) 간격, **15:00까지** | 수집 → 합의 → 리스크 → 주문 |
| 손절 감시 | 장중 `guard_interval_min`(3분) 간격 | **보유 종목 손절선만** 확인 후 즉시 청산 (AI 호출 없음) |
| 청산 점검 | `eod_review` (15:10) | **보유 종목만** 대상으로 청산 재판단 |
| 일간 리포트 | `daily_report` (15:40) | 당일 손익·주문·보유 요약 전송 |

기본 설정에서 사이클은 09:05부터 14:35까지 12회입니다 (`python main.py --check` 로 확인).

### 장애 처리

- **종목 단위 예외**는 해당 종목만 건너뛰고 사이클을 계속합니다(오류 알림 후 다음 종목).
- **사이클 단위 예외**는 연속 실패 횟수를 세고, **3회 연속 실패하면** "치명적 오류" 알림 후
  스케줄러를 중단합니다. 한 번이라도 성공하면 카운터는 0으로 돌아갑니다.
- 사이클 잡은 `max_instances=1` · `coalesce=True` — 앞 사이클이 길어져도 겹쳐 실행되지 않습니다.

### 안전 종료

`SIGINT`(Ctrl+C)·`SIGTERM` 을 받으면 **진행 중인 사이클을 마친 뒤** 종료 알림을 보내고 멈춥니다.
종료 대기 중에는 새 사이클을 시작하지 않으며, 같은 신호를 한 번 더 받으면 즉시 종료합니다.

## 대시보드

```bash
python scripts/dashboard.py          # http://127.0.0.1:8765
```

**127.0.0.1 에만 바인딩됩니다.** API 키를 입력하고 매매를 멈출 수 있는 화면이라 외부에 노출하지 않습니다.
원격 서버에서 보려면 SSH 포트포워딩을 쓰세요: `ssh -L 8765:127.0.0.1:8765 사용자@서버`

| 화면 | 내용 |
|---|---|
| **설정** (`/setup`) | 모든 키·파라미터 입력. 저장된 비밀값은 `PSdu******YZ` 로만 표시되고 **원문은 브라우저로 내려가지 않습니다**. 빈 칸으로 저장하면 기존 값이 유지되고, 지우려면 `__CLEAR__` 를 입력합니다 |
| **키 점검** (`/setup/verify`) | 저장된 값으로 KIS 토큰 발급·Claude·Gemini 호출·텔레그램 발송을 실제로 한 번씩 시도해 항목별 성공/실패를 보여줍니다 |
| **현황** (`/`) | 당일 손익·평가자산·주문 수·AI 비용·사이클 상태 타일, 자산 추이·일별 손익률·AI 비용 차트, 보유 종목(손절·익절까지 남은 거리 포함), AI 판단 내역, 주문, **리스크 규칙 차단 사유**, 오늘 로그 꼬리 |
| **제어** | 시작 · 재시작(설정 반영) · 긴급 정지/재개 · 봇 종료 |

**버튼별 차이**

| 버튼 | 프로세스 | 효과 |
|---|---|---|
| ▶ 자동매매 시작 | 띄움 | 스케줄러 기동. 필수 키가 비어 있으면 설정 화면으로 보냅니다 |
| 🔄 재시작 (설정 반영) | 내렸다 띄움 | **키를 바꾼 뒤 반영하는 방법.** 진행 중 사이클을 마치고 새 설정으로 다시 뜹니다 |
| 🛑 긴급 정지 | 유지 | 새 사이클만 막습니다. 재개하면 즉시 이어집니다 |
| ⏹ 봇 종료 | 내림 | 진행 중 사이클을 마치고 프로세스를 내립니다 |

시작 후 몇 초간 지켜보다가 프로세스가 죽으면 **실패 원인을 로그에서 뽑아 화면에 보여줍니다**
(키가 틀렸을 때 "시작됨"으로 잘못 알리지 않습니다).

30초마다 자동 새로고침하며, 입력 중이거나 탭이 숨겨져 있으면 건너뜁니다.
등락 색은 한국 시장 관행(상승 빨강 / 하락 파랑)을 따릅니다.

## 운영 안전장치

| 장치 | 동작 |
|---|---|
| **중복 실행 방지** | `data/trader.pid` 락. 같은 계좌에 두 프로세스가 붙어 **이중 주문**이 나는 것을 막습니다. 죽은 프로세스의 락은 자동 회수 |
| **긴급 정지** | `data/STOP` 파일이 있으면 새 사이클을 시작하지 않습니다. 대시보드 버튼, `python main.py --stop`, `touch data/STOP` 모두 동일 |
| **미체결 정리** | 사이클 시작 때 지난 미체결 실주문을 체결조회로 재확인해 상태를 확정합니다 |
| **손실 한도 알림** | 당일 손실 한도에 처음 도달하면 텔레그램으로 1회 알립니다 |
| **알림 폭주 억제** | 같은 오류가 반복되면 10분간 재알림하지 않습니다 |
| **AI 비용 추적** | 호출마다 토큰·추정 비용을 `ai_usage` 에 기록하고 대시보드에 표시합니다 |

## 모의투자 무인 운영 (Step 7)

### 시작 전 점검

```bash
python main.py --check          # 설정·DB·사이클 시각
python scripts/test_kis.py      # 모의계좌 1주 매수→체결→매도
python scripts/test_cycle.py    # DRY_RUN end-to-end + 텔레그램 요약 수신 확인
```

세 가지가 모두 통과하면 `.env` 에서 `DRY_RUN=false` 로 바꿉니다. **`KIS_ENV=VTS` 는 그대로 둡니다.**

### 상주 실행

세션이 끊겨도 계속 돌도록 백그라운드로 띄웁니다.

```bash
nohup python main.py >> logs/stdout.log 2>&1 &
echo $! > data/trader.pid          # 종료: kill $(cat data/trader.pid)
```

`SIGTERM` 을 받으면 진행 중 사이클을 마치고 안전하게 종료하므로 `kill -9` 는 쓰지 마세요.

systemd 를 쓴다면:

```ini
# /etc/systemd/system/auto-trader.service
[Unit]
Description=Multi-Agent 자동매매
After=network-online.target

[Service]
Type=simple
User=trader
WorkingDirectory=/home/trader/auto_trader
ExecStart=/home/trader/auto_trader/.venv/bin/python main.py
Restart=on-failure
RestartSec=60
KillSignal=SIGTERM
TimeoutStopSec=120

[Install]
WantedBy=multi-user.target
```

### 매일 확인할 것

- 15:40 일간 리포트 알림 수신 여부 (오지 않으면 프로세스가 죽었을 가능성)
- `logs/trader_YYYYMMDD.log` 의 `ERROR` / `CRITICAL` 라인
- "치명적 오류" 알림 — 사이클 3회 연속 실패로 스케줄러가 멈춘 상태입니다

### 5거래일 후 리포트

```bash
python scripts/export_report.py --days 5
```

`data/reports/<시작일>_<종료일>/` 에 `decisions.csv` · `orders.csv` · `daily_pnl.csv` 가 저장되고
콘솔에는 요약이 출력됩니다 (CSV 는 UTF-8 BOM 이라 엑셀에서 한글이 깨지지 않습니다).

요약에서 특히 볼 것:

| 항목 | 정상 범위 | 벗어나면 |
|---|---|---|
| 파싱 실패율 | 5% 미만 | 프롬프트나 모델 설정 점검 |
| 최종 결정 분포 | HOLD 가 다수 | STRONG_BUY 가 과다하면 `min_confidence` 상향 |
| 리스크 거부 사유 | 한도 관련 | 같은 사유가 반복되면 파라미터 재조정 |
| 일자별 손익 | — | `daily_loss_limit_pct` 도달 빈도 확인 |

## 실전(REAL) 전환 절차

> **실전 전환은 사용자가 명시적으로 결정할 때만 진행합니다.** 아래 조건을 모두 만족하기 전에는
> 전환하지 마세요.

### 전제 조건

1. 모의투자에서 **5거래일 이상 무인 운영**을 마쳤고 중단 없이 돌았을 것
2. `decisions` · `orders` CSV 를 직접 검토해 AI 판단과 주문이 납득 가능할 것
3. 파싱 실패율이 5% 미만일 것
4. 리스크 규칙이 실제로 작동한 기록(거부 사례)이 있을 것

### 전환 순서

1. **KIS 실전 API 키를 새로 발급받습니다.** 모의투자 키는 실전 도메인에서 동작하지 않습니다.
2. `data/token.json` 을 삭제합니다 (환경이 바뀌면 캐시를 재사용하지 않지만, 명시적으로 지웁니다).
3. `.env` 를 수정합니다.
   ```
   KIS_ENV=REAL
   KIS_APP_KEY=<실전 키>
   KIS_APP_SECRET=<실전 시크릿>
   KIS_ACCOUNT_NO=<실전 계좌 앞 8자리>
   DRY_RUN=true          # ← 먼저 true 로 시작합니다
   ```
4. `config/settings.yaml` 의 `total_investment_cap_krw` 를 **잃어도 되는 금액**으로 낮춥니다.
   처음에는 100만 원 이하를 권합니다.
5. `python scripts/test_kis.py --no-order` 로 실전 계좌 조회가 되는지 확인합니다.
   (실전에서는 `--allow-real` 없이 주문 단계가 자동으로 건너뛰어집니다.)
6. `DRY_RUN=true` 상태로 최소 1거래일 운영하며 실전 시세 기준 판단을 확인합니다.
7. 문제가 없으면 `DRY_RUN=false` 로 바꿉니다. 기동 시 텔레그램으로
   **"⚠️ 실전 모드 시작 — 실제 자금이 사용됩니다"** 경고가 전송되는지 확인하세요.

### 실전 운영 주의사항

- **거래량 순위 API 는 실전에서만 동작합니다.** `universe.mode: volume_rank` 를 쓸 생각이라면
  실전 전환 후에야 실제 동작을 확인할 수 있습니다.
- **초당 호출 제한이 다릅니다** (모의 2건 → 실전 20건). 코드가 자동으로 전환하지만,
  종목 수를 늘릴 때는 사이클 소요 시간을 로그로 확인하세요.
- **AI 호출 비용**은 종목 수 × 2(에이전트) × 사이클 수만큼 발생합니다. 기본 설정(10종목 × 12사이클)이면
  하루 240회입니다. `universe.max_candidates_per_cycle` 와 `CLAUDE_EFFORT` 로 조절하세요.
- **손절은 AI 판단 없이 즉시 실행**됩니다. `stop_loss_pct` 를 너무 좁게 잡으면 잦은 손절매가 납니다.
- 시장 급변 시에는 프로그램을 멈추는 것이 안전합니다: `kill $(cat data/trader.pid)`
- 이 프로그램은 **투자 조언이 아닙니다.** 모든 손익은 운영자 책임입니다.

## 데이터베이스 (`data/trader.db`)

| 테이블 | 내용 |
|---|---|
| `positions` | 보유 포지션 스냅샷 (매 사이클 KIS 잔고로 동기화) |
| `orders` | 주문·체결 내역 (DRY_RUN 주문 포함, `dry_run`·`kis_env` 컬럼으로 구분) |
| `decisions` | AI 원문 응답 + 파싱 결과 + 최종 결정 + 리스크 판정 (사후 검증용) |
| `daily_pnl` | 일자별 손익 요약 |
| `ai_usage` | AI 호출 토큰·추정 비용 (비용 추적) |
| `bot_state` | 봇 실행 상태 한 줄 (대시보드용) |

## 로깅

- `logs/trader_YYYYMMDD.log` — 10MB 롤링 5개, 콘솔 동시 출력, 시각은 항상 KST.
  **자정을 넘기면 자동으로 다음 날짜 파일로 넘어갑니다** (무인 운영 시 첫날 파일에 계속 쌓이지 않도록).
- `utils.logger.register_secret()` 에 등록한 값은 모든 로그에서 `***REDACTED***` 로 치환됩니다.

## 개발 단계

| Step | 범위 | 상태 |
|---|---|---|
| 1 | 뼈대: 구조·설정 로더·로거·DB 스키마 | ✅ 완료 |
| 2 | KIS 연동 (토큰 캐시, 시세/잔고/주문 API, 장 운영일) | ✅ 코드·테스트 완료 / 모의계좌 실연동 검증 대기 |
| 3 | 데이터 파이프라인 (유니버스·지표·뉴스) | ✅ 코드·테스트 완료 / 실연동 검증 대기 |
| 4 | AI 에이전트 (Claude/Gemini 병렬 호출·JSON 파싱) | ✅ 코드·테스트 완료 / 실API 검증 대기 |
| 5 | 합의·리스크·주문 실행·알림 | ✅ 코드·테스트 완료 / 실연동 검증 대기 |
| 6 | 스케줄러 조립 (apscheduler, 시그널, 일간 리포트) | ✅ 코드·테스트 완료 / 실연동 검증 대기 |
| 7 | 모의투자 실주문 검증 (5거래일 무인 운영) | 🔑 준비 완료 / 실제 키로 운영만 남음 |

각 Step은 완료 후 사용자 확인을 받고 다음 단계로 넘어갑니다.

## 범위 밖

백테스팅, 해외주식, 선물/옵션, 신용거래, 웹 대시보드는 이번 개발 범위에 포함하지 않습니다.
