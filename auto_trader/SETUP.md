# 키 발급부터 첫 실행까지 — 전체 순서

처음부터 끝까지 순서대로 따라가면 됩니다. 소요 시간은 **KIS 계좌가 이미 있으면 30분,
없으면 계좌 개설(영업일 기준 즉시~1일) + 30분** 정도입니다.

| 단계 | 내용 | 필수 |
|---|---|---|
| 0 | 프로그램 실행 (`./start.sh`) | 필수 |
| 1 | 한국투자증권 계좌 + 모의투자 참가신청 | 필수 |
| 2 | KIS API 키 발급 | 필수 |
| 3 | Anthropic(Claude) API 키 | 필수 |
| 4 | Google(Gemini) API 키 | 필수 |
| 5 | 텔레그램 봇 · 채팅 ID | 필수 |
| 6 | 네이버 검색 API | 선택 |
| 7 | 키 입력 (대시보드 또는 파일) | 필수 |
| 8 | 키 점검 → 단계별 검증 | 필수 |

> **키는 절대 채팅·이슈·커밋에 붙여넣지 마세요.** `.env` 파일에만 넣습니다.
> 이 파일은 `.gitignore` 에 있어 커밋되지 않고, 로그에도 자동 마스킹됩니다.

---

## 0. 프로그램 실행 — 명령 하나

Python 3.11 이상이 필요합니다. **3.12 를 권장합니다** — 3.14 처럼 너무 최신 버전은
아직 설치 파일이 없는 패키지가 있어 설치가 오래 걸리거나 실패할 수 있습니다.
(`python3 --version` 으로 확인, 없으면 https://www.python.org/downloads/ 에서 설치)

```bash
git clone <이 저장소 주소>
cd <저장소>/auto_trader
```

**macOS / Linux**
```bash
./start.sh
```

**Windows** — 탐색기에서 `start.bat` 더블클릭

이게 전부입니다. 가상환경 생성 → 의존성 설치 → 대시보드 실행 → 브라우저 열기까지
자동으로 하고, **http://127.0.0.1:8765** 가 열립니다.
(처음 한 번은 의존성 설치로 몇 분 걸립니다. 두 번째부터는 몇 초.)

화면이 뜨면 키 발급을 먼저 하러 갔다가, 다 받은 뒤 7단계로 돌아와 입력하면 됩니다.

### 아이콘 만들기 · 업데이트

`install.bat` 을 한 번 실행하면 바탕화면에 **자동매매** 아이콘이 생깁니다.
이후에는 아이콘만 더블클릭하면 됩니다.

새 버전이 나오면 현황 화면의 **⬆️ 업데이트** 버튼 하나로 끝납니다.
다시 내려받을 필요도, **키를 다시 넣을 필요도 없습니다** — `.env` 와 `data/` 는
업데이트가 건드리지 않습니다.

---

### start.bat 이 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| 창이 뜨자마자 닫힌다 | 예전 버전입니다. 이제 실패해도 창이 멈추고 이유를 보여줍니다. 다시 받으세요 |
| `Python 3.11 or newer was not found` | python.org 에서 설치하고 **"Add python.exe to PATH"** 를 체크하세요 |
| 파이썬 설치했는데도 같은 메시지 | Microsoft Store 판 파이썬은 동작하지 않습니다. python.org 판으로 설치하세요 |
| 브라우저에 "연결할 수 없음" | 검은 창에 `Dashboard:` 줄이 나온 뒤 새로고침하세요. 첫 실행은 준비에 몇 분 걸립니다 |
| 설치 중 오래 멈춰 있다 | 첫 설치는 몇 분 걸립니다. 줄이 계속 올라오면 정상입니다 |
| `Building wheel` 에서 10분 넘게 멈춤 | 파이썬이 너무 최신입니다. **3.12** 를 설치하고 `.venv` 폴더를 지운 뒤 다시 실행하세요 |
| `Could not create the virtual environment` | OneDrive/바탕화면 대신 `C:\autotrader` 같은 단순한 경로로 옮기고 다시 실행하세요 |

---

## 1. 한국투자증권 계좌 + 모의투자 참가신청

### 1-1. 계좌가 없다면 먼저 개설

- 모바일 앱 **한국투자 (KIS)** 설치 → 비대면 계좌개설
- 신분증과 본인 명의 은행계좌가 필요합니다
- **종합계좌(주식)** 로 개설하세요

### 1-2. 모의투자 참가신청 ← 이 단계를 빠뜨리면 모의계좌가 없습니다

- https://securities.koreainvestment.com 로그인
- 메뉴에서 **모의투자** 를 찾아 **주식 모의투자 참가신청**
  (메뉴 위치는 개편될 수 있습니다. 사이트 검색창에 "모의투자 참가신청" 을 넣어보세요.)
- 신청하면 **모의투자 전용 계좌번호**가 생성됩니다. 실전 계좌와 **다른 번호**입니다.

**확인해 둘 것**: 모의투자 계좌번호 (예: `50123456-01` 형태)
- 앞 8자리 `50123456` → `KIS_ACCOUNT_NO`
- 뒤 2자리 `01` → `KIS_ACCOUNT_PRODUCT_CD`

---

## 2. KIS API 키 발급 (모의투자용)

**https://apiportal.koreainvestment.com** (KIS Developers)

1. 우측 상단 **로그인** — 증권 계좌와 동일한 아이디를 씁니다
2. **API 신청** 또는 **KIS Developers 서비스 신청** 메뉴로 이동
3. 신청 화면에서 **모의투자** 를 선택합니다
   > 실전투자와 모의투자는 **키가 완전히 별개**입니다.
   > 실전 키를 모의 도메인에 쓰면 401/403 이 납니다. 지금은 반드시 **모의투자** 를 고르세요.
4. 신청 시 사용할 **계좌번호**로 1-2 에서 만든 모의투자 계좌를 지정합니다
5. 발급 완료 후 **APP KEY** 와 **APP SECRET** 을 복사해 둡니다

**받는 것**
- `KIS_APP_KEY` — 36자 내외 문자열
- `KIS_APP_SECRET` — 180자 내외의 긴 문자열 (줄바꿈 없이 한 줄로 복사)

**참고**
- APP SECRET 은 재조회가 안 되는 경우가 있습니다. 안전한 곳에 보관하세요.
- 실제 매매에 쓰는 **접근토큰**은 프로그램이 APP KEY/SECRET 으로 자동 발급합니다.
  직접 만들 필요 없습니다. (토큰은 `data/token.json` 에 캐시되고 만료 10분 전에만 재발급합니다.
  KIS 는 짧은 간격의 재발급을 막으므로, 캐시 파일을 함부로 지우지 마세요.)

---

## 3. Anthropic (Claude) API 키

**https://console.anthropic.com**

1. 가입 / 로그인
2. **Settings → Billing** 에서 **크레딧을 충전**합니다
   > 선결제 방식입니다. 잔액이 0이면 키가 있어도 호출이 거부됩니다. 처음엔 $5~10 이면 충분합니다.
3. **Settings → API keys → Create Key**
4. 표시된 키(`sk-ant-...`)를 즉시 복사합니다 — **창을 닫으면 다시 볼 수 없습니다**

**받는 것**: `ANTHROPIC_API_KEY`

**모델 이름**은 `.env` 의 `CLAUDE_MODEL` 로 관리합니다. 기본값은 `claude-sonnet-5` 입니다.

---

## 4. Google (Gemini) API 키

**https://aistudio.google.com/apikey**

1. Google 계정으로 로그인
2. **API 키 만들기 (Create API key)** 클릭
3. Google Cloud 프로젝트를 고르거나 새로 만듭니다 (아무 프로젝트나 괜찮습니다)
4. 생성된 키를 복사합니다 (`AIza...` 로 시작)

**받는 것**: `GEMINI_API_KEY`

무료 티어가 있지만 분당·일일 호출 한도가 있습니다. 한도에 걸리면 해당 종목은
자동으로 HOLD 처리되며 프로그램은 멈추지 않습니다.

---

## 5. 텔레그램 봇 · 채팅 ID

매매 알림과 일간 리포트를 받는 통로입니다.

### 5-1. 봇 만들기

1. 텔레그램에서 **https://t.me/BotFather** 를 엽니다
2. `/newbot` 입력
3. 봇 **이름** 입력 (아무거나, 예: `내 자동매매`)
4. 봇 **사용자명** 입력 — 반드시 `bot` 으로 끝나야 합니다 (예: `my_trader_9x_bot`)
5. BotFather 가 주는 토큰(`123456789:AAE...` 형태)을 복사합니다

**받는 것**: `TELEGRAM_BOT_TOKEN`

### 5-2. 채팅 ID 알아내기 ← 이 단계가 빠지면 알림이 오지 않습니다

1. 방금 만든 봇을 검색해 대화창을 열고 **`/start` 를 보냅니다**
   > 텔레그램 봇은 사용자가 먼저 말을 걸어야 메시지를 보낼 수 있습니다. 필수입니다.
2. 채팅 ID 확인 방법 두 가지 중 하나:
   - **https://t.me/userinfobot** 에게 아무 메시지나 보내면 본인 ID를 알려줍니다
   - 또는 **8단계의 키 점검 스크립트**가 `TELEGRAM_CHAT_ID` 가 비어 있으면
     봇 대화에서 찾은 ID 후보를 알려줍니다 (가장 간편)

**받는 것**: `TELEGRAM_CHAT_ID` (숫자, 예: `987654321`)

---

## 6. 네이버 검색 API (선택 — 건너뛰어도 됩니다)

뉴스 감성을 AI 판단에 넣고 싶을 때만 필요합니다. 없으면 뉴스 없이 지표만으로 판단합니다.
**검증 단계에서는 비워두고 넘어가시길 권합니다.**

> ⚠️ **네이버 로그인 아이디·비밀번호가 아닙니다.**
> 아래에서 앱을 등록하면 발급되는 **Client ID / Client Secret** 입니다.
> 계정 정보는 어디에도 입력하지 마세요.

**https://developers.naver.com/apps/#/register**

1. 네이버 계정으로 로그인
2. **애플리케이션 이름** 입력 (예: `auto-trader`)
3. **사용 API** 에서 **검색** 을 선택
4. 환경 추가에서 **웹 서비스 URL** 을 요구하면 `http://localhost` 를 넣어도 됩니다
5. 등록 후 **Client ID** 와 **Client Secret** 을 복사합니다

**받는 것**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` (둘 다 넣거나 둘 다 비워야 합니다)

---

## 7. 키 입력하기

### 어떤 키가 어디로 가는지 — 한눈에

발급받은 값이 대시보드 **설정** 화면의 어느 칸에 들어가는지, `.env` 의 어느 이름으로 저장되는지입니다.
입력하는 곳은 **한 군데뿐**입니다. 다른 파일이나 코드는 건드릴 필요가 없습니다.

| 발급받은 것 | 어디서 (2~6장) | 설정 화면의 칸 | `.env` 이름 |
|---|---|---|---|
| KIS APP KEY | 2장 · KIS 포털 | **APP KEY** | `KIS_APP_KEY` |
| KIS APP SECRET | 2장 · KIS 포털 | **APP SECRET** | `KIS_APP_SECRET` |
| 모의계좌 번호 앞 8자리 | 1-2장 · 모의투자 참가신청 | **계좌번호 앞 8자리** | `KIS_ACCOUNT_NO` |
| 계좌번호 뒤 2자리 | 위와 같은 곳 | **계좌 상품코드** | `KIS_ACCOUNT_PRODUCT_CD` |
| Claude 키 (`sk-ant-…`) | 3장 · console.anthropic.com | **Anthropic API 키** | `ANTHROPIC_API_KEY` |
| Gemini 키 (`AIza…`) | 4장 · aistudio.google.com | **Gemini API 키** | `GEMINI_API_KEY` |
| 텔레그램 봇 토큰 | 5-1장 · @BotFather | **텔레그램 봇 토큰** | `TELEGRAM_BOT_TOKEN` |
| 텔레그램 채팅 ID | 5-2장 | **텔레그램 채팅 ID** | `TELEGRAM_CHAT_ID` |
| (디스코드를 쓸 때) 웹훅 URL | 5장 대안 | **디스코드 웹훅** | `DISCORD_WEBHOOK_URL` |
| 네이버 Client ID / Secret *(선택)* | 6장 | **네이버 Client ID / Secret** | `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` |

나머지 칸(`KIS_ENV`, `DRY_RUN`, 모델 이름 등)은 기본값 그대로 두면 됩니다.
검증이 끝나기 전까지 **`KIS_ENV=VTS`, `DRY_RUN=true`** 는 절대 바꾸지 마세요.

> 입력한 값은 본인 PC의 `auto_trader/.env` 파일에만 저장됩니다(권한 0600).
> **키를 채팅창이나 이슈·PR 에 붙여넣지 마세요.**

아래 세 가지 방법 중 편한 것 하나만 쓰면 됩니다.

### 방법 A — 대시보드에서 입력 (권장)

0단계에서 띄운 화면(**http://127.0.0.1:8765**)의 **설정** 탭입니다.
꺼져 있으면 `./start.sh` (Windows: `start.bat`) 로 다시 띄우세요.

칸을 채우고 **저장** → **키 점검 실행** 을 누르면 각 키가 실제로 동작하는지 바로 확인됩니다.

- 저장된 비밀값은 `PSdu******YZ` 처럼 마스킹되어 표시되고 원문은 브라우저로 내려가지 않습니다
- 이미 저장된 칸을 비워둔 채 저장하면 **기존 값이 유지**됩니다 (지우려면 `__CLEAR__` 입력)
- 따옴표·인라인 주석·앞뒤 공백은 저장할 때 자동으로 정리됩니다
- 이 화면은 **127.0.0.1 에만** 열립니다. 외부에서 접근할 수 없습니다

### 방법 B — 터미널에서 하나씩 묻고 답하기

브라우저를 쓸 수 없을 때(SSH 접속 등) 씁니다. 항목을 순서대로 물어보고 `.env` 를 만들어 줍니다.

```bash
cd auto_trader
source .venv/bin/activate
python scripts/setup_keys.py            # 전체 항목을 순서대로
python scripts/setup_keys.py --missing  # 아직 비어 있는 필수 항목만
python scripts/setup_keys.py --check    # 입력이 끝나면 키 점검까지 이어서
```

- 비밀값은 입력해도 **화면에 찍히지 않습니다**
- 이미 값이 있는 칸은 그냥 **Enter** 를 치면 유지됩니다 (지우려면 `-` 입력)
- 잘못 고르면 다시 묻습니다. 중간에 그만두려면 **Ctrl+C** — `.env` 는 그대로 남습니다

### 방법 C — 파일 직접 편집

`auto_trader/.env` 를 텍스트 편집기로 열어 값을 채웁니다.

```bash
# --- 실행 환경 ---  (이 두 줄은 그대로 두세요)
KIS_ENV=VTS
DRY_RUN=true
LOG_LEVEL=INFO

# --- 한국투자증권 ---
KIS_APP_KEY=여기에_APP_KEY
KIS_APP_SECRET=여기에_APP_SECRET
KIS_ACCOUNT_NO=50123456
KIS_ACCOUNT_PRODUCT_CD=01

# --- AI ---
ANTHROPIC_API_KEY=sk-ant-여기에
CLAUDE_MODEL=claude-sonnet-5
CLAUDE_TEMPERATURE=
CLAUDE_EFFORT=
GEMINI_API_KEY=AIza여기에
GEMINI_MODEL=gemini-2.5-pro
GEMINI_TEMPERATURE=0.2

# --- 뉴스 (선택) ---
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=

# --- 알림 ---
NOTIFIER=telegram
TELEGRAM_BOT_TOKEN=123456789:AAE여기에
TELEGRAM_CHAT_ID=987654321
DISCORD_WEBHOOK_URL=
```

### 입력할 때 흔한 실수

| 실수 | 결과 |
|---|---|
| `KIS_APP_KEY=abc   # 내 키` 처럼 **값 뒤에 주석** | 주석까지 값으로 읽힙니다. 설명은 윗줄에 두세요 |
| 값을 따옴표로 감싸기 (`KEY="abc"`) | 따옴표가 값에 포함될 수 있습니다. 그냥 `KEY=abc` |
| APP SECRET 이 줄바꿈된 채 붙여넣기 | 인증 실패. 반드시 한 줄로 |
| 계좌번호를 `50123456-01` 통째로 | 앞 8자리만. 뒤 2자리는 `KIS_ACCOUNT_PRODUCT_CD` |
| `CLAUDE_TEMPERATURE=0.2` 입력 | 최신 모델은 이 값을 거부(400)합니다. **비워두세요** |
| `KIS_ENV=REAL` 로 시작 | 실전 계좌입니다. 검증 전에는 절대 금지 |

---

## 8. 확인 — 여기서부터는 명령만 따라 하면 됩니다

### 8-1. 키가 실제로 동작하는지 점검

대시보드의 **키 점검 실행** 버튼과 같은 검사입니다. 터미널에서는:

```bash
python scripts/check_keys.py
```

각 키를 **독립적으로** 검사해 어디가 잘못됐는지 알려줍니다.

```
✅ KIS 계좌번호              50****56 (VTS)
✅ KIS 인증                 VTS 토큰 발급 성공
✅ Anthropic (Claude)      claude-sonnet-5 호출 성공
✅ Google (Gemini)         gemini-2.5-pro 호출 성공
✅ 텔레그램 봇                @my_trader_9x_bot
✅ 텔레그램 CHAT_ID          987654321
⏭️ 네이버 뉴스 (선택)           미설정 — 뉴스 없이 동작합니다
```

텔레그램으로 **테스트 메시지까지 실제로 받아보려면**:

```bash
python scripts/check_keys.py --telegram-test
```

### 8-2. 설정·DB 점검

```bash
python main.py --check
```

### 8-3. KIS 실연동 — **장중(09:00~15:30, 평일)에 실행하세요**

```bash
python scripts/test_kis.py
```

모의계좌로 삼성전자 **1주 시장가 매수 → 체결 확인 → 1주 매도**까지 수행합니다.
모의투자 계좌에는 보통 초기 자금이 들어 있지만, 잔고가 부족하면 매수가 거부됩니다.

### 8-4. 데이터 수집

```bash
python scripts/test_pipeline.py
```

### 8-5. AI 분석 (실제 API 비용이 발생합니다 — 2종목이면 몇 센트 수준)

```bash
python scripts/test_agents.py
```

### 8-6. 전체 사이클 (DRY_RUN — 주문 안 나감)

```bash
python scripts/test_cycle.py
```

여기서 **텔레그램으로 사이클 요약이 오면** 모든 연결이 끝난 것입니다.

### 8-7. 무인 운영 시작 — 버튼 하나

1. 설정 화면에서 **주문 전송** 을 `false` 로 바꾸고 저장
   (= `DRY_RUN=false`. **거래 환경은 `VTS` 그대로 둡니다**)
2. 현황 화면에서 **▶ 자동매매 시작**

프로세스는 대시보드를 껐다 켜도 계속 돕니다. 시작 후 몇 초간 지켜보다가
문제가 있으면 실패 원인을 화면에 보여줍니다.

터미널을 선호하면:

```bash
nohup python main.py >> logs/stdout.log 2>&1 &
```

### 8-8. 키나 설정을 바꿨을 때

**🔄 재시작 (설정 반영)** 버튼을 누르면 진행 중 사이클을 마치고 새 설정으로 다시 뜹니다.
이미 떠 있는 프로세스는 옛 설정을 들고 있으므로, 저장만 해서는 반영되지 않습니다.

5거래일 뒤:

```bash
python scripts/export_report.py --days 5
```

이후 절차와 실전 전환은 `README.md` 의 **모의투자 무인 운영** · **실전 전환 절차** 를 보세요.

### 멈추고 싶을 때

| 상황 | 대시보드 | 터미널 |
|---|---|---|
| 새 매매만 멈추기 (프로세스 유지) | **🛑 긴급 정지** | `python main.py --stop` |
| 다시 시작 | **▶️ 매매 재개** | `python main.py --resume` |
| 설정 바꾼 뒤 반영 | **🔄 재시작** | 프로세스 종료 후 재실행 |
| 프로세스 자체를 끄기 | **⏹ 봇 종료** | `kill $(cat data/trader.pid)` |
| 지금 상태 확인 | 헤더 배지 | `python main.py --status` |

어느 쪽이든 진행 중인 사이클을 마치고 안전하게 멈춥니다. `kill -9` 는 쓰지 마세요.

---

## 비용 대략

| 항목 | 대략 |
|---|---|
| KIS 모의투자 API | 무료 |
| Claude (Sonnet급) | 기본 설정(10종목 × 12사이클 = 하루 120회 호출) 기준 **하루 $1~3** 수준 |
| Gemini | 무료 티어 내에서 가능. 초과 시 과금 |
| 네이버 검색 | 무료 (일일 한도 있음) |

비용을 줄이려면 `config/settings.yaml` 의 `universe.max_candidates_per_cycle` 를 줄이거나,
`schedule.cycle_interval_min` 을 늘리거나, `.env` 의 `CLAUDE_EFFORT=low` 를 설정하세요.
정확한 단가는 각 제공사 요금 페이지에서 확인하세요.

---

## 막혔을 때

| 증상 | 원인·조치 |
|---|---|
| `설정 검증 실패` + 키 목록 | `.env` 에 해당 키가 비어 있습니다 |
| `KIS 인증 실패 (HTTP 403)` | 실전 키를 모의 도메인에 쓰는 중. 모의투자용으로 다시 발급 |
| `EGW00133` | 토큰 재발급 간격 제한. 1분 뒤 재시도 |
| `모의투자 장운영시간이 아닙니다` | 평일 09:00~15:30 에 실행 |
| 텔레그램 알림이 안 옴 | 봇에게 `/start` 를 보냈는지, `TELEGRAM_CHAT_ID` 가 맞는지 확인 |
| `거래량 순위 미지원` | 모의투자는 이 API가 없습니다. `watchlist` 모드를 쓰세요(기본값) |
| Claude 호출이 `credit` 오류 | 콘솔 Billing 에서 크레딧 충전 |
