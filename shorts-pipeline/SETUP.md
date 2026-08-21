# 매일 저녁 9시 자동 업로드 — 세팅 안내

> 💡 **여기 나오는 키 입력은 전부 작업실 [설정] 탭에서 클릭으로 할 수 있습니다.**
> 명령어 없이 하려면 **[START_HERE.md](START_HERE.md)** 를 보세요.
> 이 문서는 각 키를 *어디서 어떻게 발급받는지* 를 자세히 설명합니다.

**회원님이 직접 하셔야 하는 것만** 순서대로 모았습니다.
각 단계 끝에서 `python main.py doctor` 를 돌리면 뭐가 남았는지 알려줍니다.

> 이 프로그램은 **회원님 PC 에서** 돕니다. 저는 회원님 계정에 접근할 수 없으니
> 아래 키 발급과 인증은 직접 하셔야 합니다.

---

## 전체 그림

```
seeds/파일.png  ─┐
seeds/파일.yaml ─┤ 제목·훅·프롬프트
                 ↓
      generate   영상 생성 (5~10분, 편당 약 $3)
                 ↓
       ┌─────────┴─────────┐
   유튜브 업로드        인스타 업로드
   (파일 직접)      (R2 → 공개 URL → Graph API)
                 ↓
      seeds/_used/ 로 이동 (재사용 방지)
```

매일 **20:30** 에 cron 이 시작 → 생성 → **21:00 정각**에 두 곳 동시 게시.

---

## STEP 1 · 프로그램 설치 (15분)

영상을 만들려면 **Python**(프로그램 실행)과 **ffmpeg**(영상 합성)이 필요합니다.
Git 은 없어도 됩니다 — 깃허브에서 zip 으로 받으면 됩니다.

### Windows — 자동 (권장)

`winget` 이 PATH 설정까지 해주므로 이 방법이 가장 쉽습니다.

1. `Windows` + `X` → **터미널(관리자)** 선택
2. 아래를 붙여넣고 실행 (붙여넣기는 마우스 오른쪽 클릭)
   ```powershell
   winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
   winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
   ```
3. **터미널을 완전히 닫고 새로 엽니다.** ← 여기서 대부분 막힙니다.
   새로 열지 않으면 방금 설치한 것을 인식하지 못합니다
4. 확인
   ```powershell
   python --version
   ffmpeg -version
   ```

`Python 3.12.x` 와 `ffmpeg version ...` 이 나오면 성공입니다.

### Windows — 수동

winget 이 없을 때만 씁니다.

1. https://www.python.org/downloads/ 에서 노란 **Download Python** 버튼
2. 설치 첫 화면의 **"Add python.exe to PATH"** 를 **반드시 체크**하고 Install Now
3. https://www.gyan.dev/ffmpeg/builds/ 에서 `ffmpeg-release-essentials.zip`
4. 압축을 풀어 `C:\ffmpeg` 로 옮깁니다. `C:\ffmpeg\bin\ffmpeg.exe` 가 있어야 합니다
5. 시작 → `환경 변수` 검색 → **시스템 환경 변수 편집**
6. **[환경 변수]** 버튼
7. 아래쪽 **"시스템 변수"** 의 **Path** 선택 → **[편집]**
8. **[새로 만들기]** → `C:\ffmpeg\bin` 입력 → 확인 3번
9. 터미널을 **새로 열고** 위 확인 명령 실행

### Mac

```bash
brew install python ffmpeg
python3 --version
ffmpeg -version
```

> Mac 은 `python` 이 아니라 **`python3`** 입니다. 이후 모든 명령에서 바꿔 입력하세요.

### 코드 내려받기

Git 없이 zip 으로 받는 편이 간단합니다.

1. 깃허브에서 브랜치 zip 을 받습니다
   `https://github.com/himan98hkt-prog/-/archive/refs/heads/claude/auto-video-generation-upload-3kilh6.zip`
2. 압축을 풀고 안의 `shorts-pipeline` 폴더를 `C:\shorts-pipeline` 처럼 찾기 쉬운 곳으로 옮깁니다
3. 그 폴더에서 터미널을 엽니다 (폴더 빈 곳 우클릭 → **터미널에서 열기**)
4. ```bash
   pip install -r requirements.txt
   copy .env.example .env      # Mac: cp .env.example .env
   ```

Git 을 쓰시겠다면:
```bash
git clone https://github.com/himan98hkt-prog/-.git shorts
cd shorts && git checkout claude/auto-video-generation-upload-3kilh6
cd shorts-pipeline && pip install -r requirements.txt && cp .env.example .env
```

### 최신 코드 받기 (설치 후 언제든)

`shorts-pipeline` 폴더의 **`update.bat` 을 더블클릭**하면 됩니다.
`.env`(fal 키), `seeds`(고른 이미지), `runs`(만든 영상)는 그대로 유지됩니다.

처음 한 번은 아래 명령으로 받으세요 (그다음부터는 더블클릭):

```powershell
$z="$env:TEMP\a.zip"; $t="$env:TEMP\a_x"; Invoke-WebRequest "https://github.com/himan98hkt-prog/-/archive/refs/heads/claude/auto-video-generation-upload-3kilh6.zip" -OutFile $z -UseBasicParsing; Remove-Item $t -Recurse -Force -EA SilentlyContinue; Expand-Archive $z $t -Force; $s=Get-ChildItem $t -Recurse -Directory -Filter shorts-pipeline | Where-Object { Test-Path (Join-Path $_.FullName main.py) } | Select-Object -First 1; if(-not $s){Write-Host "실패" -ForegroundColor Red}else{Copy-Item "$($s.FullName)\*" "C:\shorts-pipeline\" -Recurse -Force; Write-Host "완료" -ForegroundColor Green}
```

### 설치 스크립트 (Windows)

저장소에 `install.ps1` 이 있습니다. 코드를 받은 뒤 한 번에 처리하려면:
```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

✅ 확인: `python main.py doctor` → **[기본 환경]** 네 줄이 전부 ✓

### 자주 막히는 곳

| 메시지 | 해결 |
|---|---|
| `...은(는) 내부 또는 외부 명령이 아닙니다` | 터미널을 완전히 닫고 새로 여세요 |
| `cmdlet ... 인식되지 않습니다` | 위와 같습니다. 그래도 안 되면 PATH 등록 확인 |
| `pip ... 인식되지 않습니다` | `python -m pip install -r requirements.txt` 로 실행 |

---

## STEP 2 · fal.ai 키 (10분) — 영상 생성에 필수

1. https://fal.ai 가입
2. **Billing** → 카드 등록 → **$20 충전** (약 6편 분량)
3. **Keys** → *Add key* → 복사

작업실 **[설정] 탭 → fal.ai 키** 에 붙여넣고 **[저장하기]**.
터미널로 하려면 `.env` 에:
```bash
FAL_API_KEY=발급받은_키
```

✅ 확인: [설정] 탭의 **영상 만들기** 칸에 초록불이 켜지면 됩니다.
(터미널: `python main.py doctor` → **영상 생성 (fal)** 이 ✓)

---

## STEP 3 · 시드 이미지와 제목 (30분) — 품질을 좌우하는 단계

### 이미지 준비
`seeds/` 에 **9:16 세로 이미지**를 넣습니다. **최소 7장**(일주일치)을 권합니다.

좋은 이미지의 조건 — 레퍼런스 계정들의 공통점입니다:
- 앞으로 나아갈 **길이 보이는 구도** (도로 · 터널 · 계단 · 강 · 복도)
- **어둡고 채도 높은 색** (야경 · 네온 · 오로라 · 심해)
- 사람이 나오면 **뒷모습**. 얼굴은 체이닝에서 가장 먼저 무너집니다

ChatGPT·Gemini·Midjourney 등으로 만들면 됩니다. 프롬프트 예시:
```
vertical 9:16, first-person view riding through a neon-lit tunnel at night,
wet asphalt reflecting lights, cinematic, deep blue and magenta, ultra detailed
```

### 제목·설명 채우기 (중요)

```bash
python main.py plan
```

`seeds/` 의 이미지마다 `.yaml` 양식이 생깁니다. 열어서 채우세요:

```yaml
title:  비 내리는 네온 골목을 끝없이 달리다
hook:   이 길 끝에 뭐가 있을까
prompt: forward motion through a rain-soaked neon alley, steady speed, no cut
```

| 항목 | 어디에 쓰이나 |
|---|---|
| `title` | 유튜브 제목 → `{title} \| AI DEOKHU #Shorts` |
| `hook` | **유튜브 설명 첫 줄 + 인스타 캡션 첫 줄** |
| `prompt` | 이 영상의 카메라 움직임 (비우면 config 기본값) |

> `hook` 이 가장 중요합니다. 인스타 피드에서 **첫 줄만 안 잘립니다.**
> "이 길 끝에 뭐가 있을까" 처럼 궁금하게 만드는 한 줄을 쓰세요.

비워두면 파일명이 제목이 됩니다. 업로드는 되지만 조회수에 불리합니다.

✅ 확인: `python main.py doctor` → **시드 이미지** 가 ✓

---

## STEP 4 · 첫 영상 만들어보기 (10분)

자동화를 걸기 전에 **반드시 한 번 수동으로** 돌려보세요.

```bash
python main.py estimate --clips 5 --duration 5     # 비용 확인 (무료)
python main.py generate --image seeds/파일명.png --mode montage --clips 5
```

`runs/{날짜}/final.mp4` 를 열어 확인합니다. 마음에 안 들면:

```bash
python main.py generate --image seeds/파일명.png --interactive   # 회차마다 확인
python main.py stitch --run 20260821_210000                      # 합성만 다시 ($0)
```

---

## STEP 5 · 유튜브 연결 (20분)

### 5-1. OAuth 클라이언트 만들기
1. https://console.cloud.google.com → 프로젝트 생성
2. **API 및 서비스 → 라이브러리** → `YouTube Data API v3` → **사용**
3. **OAuth 동의 화면** → 외부 → 앱 이름·이메일 입력 →
   **테스트 사용자**에 본인 구글 계정 추가
4. **사용자 인증 정보 → 만들기 → OAuth 클라이언트 ID → 데스크톱 앱**
5. JSON 다운로드 → `shorts-pipeline/secrets/client_secret.json` 로 저장

### 5-2. 공개 설정 바꾸기
기본값이 **비공개**입니다. 자동 게시하려면 `config.yaml` 에서:
```yaml
publish:
  youtube:
    privacy: public      # private -> public
```

### 5-3. 최초 인증 ⚠️ 반드시 수동으로
**cron 은 브라우저를 못 엽니다.** 자동화 전에 한 번 직접 올려 토큰을 만드세요.

```bash
python main.py publish --run 20260821_210000 --youtube
```
브라우저가 열리면 로그인·허용 → `secrets/youtube_token.json` 생성.
이 파일이 있어야 이후 자동 업로드가 됩니다.

✅ 확인: `python main.py doctor` → **유튜브 업로드: 준비됨**

---

## STEP 6 · 인스타그램 연결 (40분) — 가장 손이 많이 갑니다

### 6-1. 계정 준비
1. @ai.deokhu 를 **프로페셔널(비즈니스 또는 크리에이터)** 계정으로 전환
   — 설정 → 계정 유형 및 도구 → 프로페셔널 계정으로 전환
2. **페이스북 페이지**를 만들고 인스타 계정에 연결
   — 인스타 설정 → 비즈니스 → 페이스북 페이지 연결

### 6-2. Meta 앱 만들기
1. https://developers.facebook.com → **내 앱 → 앱 만들기** → 유형 **비즈니스**
2. **제품 추가 → Instagram Graph API**
3. **도구 → 그래프 API 탐색기**에서 권한 선택:
   `instagram_basic`, `instagram_content_publish`,
   `pages_show_list`, `pages_read_engagement`
4. **액세스 토큰 생성** → 단기 토큰 복사

### 6-3. 장기 토큰과 계정 ID 받기
단기 토큰은 1시간이면 만료됩니다. 60일짜리로 바꿉니다.

```bash
# 1) 장기 토큰 (60일)
curl -s "https://graph.facebook.com/v21.0/oauth/access_token?\
grant_type=fb_exchange_token&client_id=앱ID&client_secret=앱시크릿&\
fb_exchange_token=단기토큰"

# 2) 페이지 목록에서 페이지 ID 확인
curl -s "https://graph.facebook.com/v21.0/me/accounts?access_token=장기토큰"

# 3) 그 페이지에 연결된 인스타 계정 ID
curl -s "https://graph.facebook.com/v21.0/페이지ID?\
fields=instagram_business_account&access_token=장기토큰"
```

작업실 **[설정] 탭 → 인스타그램 연결** 에 두 값을 넣고 **[인스타 확인하기]**.
계정 이름(@ai.deokhu)이 뜨면 성공입니다.
터미널로 하려면 `.env` 에:
```bash
IG_USER_ID=위에서_받은_숫자_ID
IG_ACCESS_TOKEN=장기토큰
```

> ⚠️ **장기 토큰도 60일이면 만료됩니다.** 두 달에 한 번 재발급해야 업로드가
> 끊기지 않습니다. 달력에 알림을 걸어두세요.

### 6-4. Cloudflare R2 (무료)
인스타는 로컬 파일을 안 받고 **공개 URL 만** 받습니다.

1. https://dash.cloudflare.com → **R2** → 버킷 생성 (이름 예: `ai-deokhu`)
2. **Manage API Tokens** → **Object Read & Write** 토큰 생성
3. 작업실 **[설정] 탭 → 영상 보관함** 에 네 값을 넣고 **[저장하기]**.
   터미널로 하려면 `.env` 에:
```bash
S3_ENDPOINT_URL=https://<계정ID>.r2.cloudflarestorage.com
S3_BUCKET=ai-deokhu
AWS_ACCESS_KEY_ID=발급받은_키
AWS_SECRET_ACCESS_KEY=발급받은_시크릿
```
`S3_REGION` 은 **비워둡니다** (R2 는 auto).

돈 쓰기 전에 연결 확인:
```bash
python main.py upload --file runs/20260821_210000/final.mp4
```

R2 무료 티어(10GB·이그레스 무료) 안에서 계속 $0 입니다.
발행 후 자동 삭제되므로 보관량이 쌓이지 않습니다.

✅ 확인: `python main.py doctor` → **인스타그램 업로드: 준비됨**

---

## STEP 7 · 매일 저녁 9시 자동화

수동으로 한 번 전체를 돌려보고 나서 겁니다.

```bash
python -m publish.scheduler --youtube --instagram --dry-run   # 안전 점검
python -m publish.scheduler --youtube --instagram             # 진짜 1회
```

### Mac / Linux — `crontab -e`
```cron
30 20 * * * cd /경로/shorts-pipeline && /usr/bin/python3 -m publish.scheduler \
  --at 21:00 --mode montage --youtube --instagram >> runs/cron.log 2>&1
```

### Windows — 작업 스케줄러
1. **작업 만들기** → 트리거: 매일 **오후 8:30**
2. 동작: 프로그램 `python`,
   인수 `-m publish.scheduler --at 21:00 --mode montage --youtube --instagram`,
   시작 위치 `C:\경로\shorts-pipeline`
3. **사용자가 로그온했는지 여부와 관계없이 실행** 체크

> **왜 20:30 시작인가**: 생성에 5~10분이 걸립니다. `--at 21:00` 이 완성 후
> 21시 정각까지 기다렸다 올리므로, 게시 시각이 정확히 맞습니다.

### 연재물로 올리려면
```bash
python -m publish.scheduler --series "끝나지 않는 여행" --at 21:00 --youtube --instagram
```
제목이 `끝나지 않는 여행 part 17` 처럼 자동으로 붙습니다.

---

## 운영 중 확인할 것

```bash
python main.py doctor              # 전체 상태
tail -20 runs/schedule.log         # 매일 결과 이력
ls seeds/                          # 남은 시드 (떨어지면 업로드가 멈춥니다)
```

`runs/schedule.log` 예시:
```
2026-08-21 21:00:12  OK  20260821_203012  비 내리는 네온 골목  성공=유튜브,인스타그램  실패=-
```

| 증상 | 원인 |
|---|---|
| 업로드가 멈춤 | `seeds/` 소진. 이미지를 더 넣으세요 |
| 유튜브만 실패 | 토큰 만료. `python main.py publish --run ... --youtube` 로 재인증 |
| 인스타만 실패 | 60일 토큰 만료. STEP 6-3 재실행 |
| `fal HTTP 402` | 잔액 부족. 충전 |
| `fal HTTP 422` | 모델 주소 변경. fal.ai/models 에서 확인 후 `config.yaml` 수정 |

---

## 세팅 체크리스트

- [ ] STEP 1 — Python · ffmpeg · 코드 · `.env`
- [ ] STEP 2 — fal.ai 키 + 충전
- [ ] STEP 3 — 시드 이미지 7장 + `.yaml` 제목·훅
- [ ] STEP 4 — 첫 영상 수동 생성 확인
- [ ] STEP 5 — 구글 OAuth JSON + `privacy: public` + **최초 브라우저 인증**
- [ ] STEP 6 — 인스타 프로페셔널 전환 + 페이스북 페이지 + Meta 앱 +
      장기 토큰 + R2 버킷
- [ ] STEP 7 — 수동 1회 성공 확인 후 cron 등록

**STEP 1~4 만 하면 영상은 만들 수 있습니다.** 5·6 은 업로드 자동화용이니
나눠서 하셔도 됩니다.
