# 첫 영상 만들기 — 30분 가이드

이 문서만 따라 하면 오늘 안에 첫 영상이 나온다.
**총 비용 약 $5** (충전 후 릴스 2편 정도 뽑아볼 수 있는 금액).

---

## 지금 상태

| | 상태 |
|---|---|
| 프로그램 코드 | ✅ 완성 · 테스트 80개 통과 |
| 실제로 만든 영상 | ❌ **0편** |

코드는 다 됐지만 **API 키가 없어서 진짜 영상 모델을 단 한 번도 호출한 적이 없다.**
아래 STEP 3의 API 키 하나만 넣으면 그때부터 진짜 영상이 나온다.

---

## STEP 1 — 코드 받기 (5분)

### 준비물 설치

**Windows**
1. Python: https://www.python.org/downloads/ → 설치 시 **"Add Python to PATH" 체크**
2. ffmpeg: https://www.gyan.dev/ffmpeg/builds/ → `ffmpeg-release-essentials.zip` 받아
   압축 풀고 `bin` 폴더를 시스템 환경변수 PATH 에 추가
3. Git: https://git-scm.com/download/win

**Mac**
```bash
brew install python ffmpeg git
```

### 코드 내려받기

```bash
git clone https://github.com/himan98hkt-prog/-.git shorts
cd shorts
git checkout claude/auto-video-generation-upload-3kilh6
cd shorts-pipeline
pip install -r requirements.txt
```

설치 확인:
```bash
ffmpeg -version
python main.py --help
```
둘 다 출력이 나오면 성공이다.

---

## STEP 2 — 시드 이미지 준비 (5분)

체이닝의 출발점이 될 **세로 이미지 1장**이 필요하다.

### 어떤 이미지가 좋은가

레퍼런스 계정들이 쓰는 그림은 공통점이 뚜렷하다:

- **9:16 세로** (1080x1920 권장 — 아니어도 자동 크롭된다)
- **앞으로 나아갈 길이 보이는 구도** — 도로, 터널, 계단, 강, 복도
- **어둡고 채도 높은 색** — 야경, 네온, 오로라, 심해
- 사람이 나온다면 **뒷모습**. 얼굴은 체이닝에서 가장 먼저 무너진다

### 어디서 구하나

| 방법 | 비용 |
|---|---|
| 이미 갖고 있는 AI 이미지 | $0 |
| ChatGPT / Gemini 에게 이미지 생성 요청 | 구독 내 |
| Midjourney, Leonardo.ai 무료 티어 | $0~ |
| 직접 찍은 세로 사진 | $0 |

프롬프트 예시:
```
vertical 9:16, first-person view riding through a neon-lit tunnel at night,
wet asphalt reflecting lights, cinematic, deep blue and magenta, ultra detailed
```

받은 이미지를 `shorts-pipeline/seeds/` 에 넣는다. 이름은 아무거나.

---

## STEP 3 — API 키 발급 (10분) ⭐ 여기가 핵심

**첫 영상은 fal.ai 로 시작한다.** 구독 없이 쓴 만큼만 내고, 카드만 등록하면 끝이다.

1. https://fal.ai 가입
2. **Billing** → 카드 등록 → **$5 충전** (첫 테스트에 충분)
3. **Keys** → *Add key* → 키 복사

프로젝트 폴더에서:
```bash
cp .env.example .env
```

`.env` 를 메모장으로 열어 **딱 한 줄만** 채운다:
```bash
FAL_API_KEY=여기에_복사한_키
```

나머지는 전부 비워둬도 된다. 유튜브·인스타는 나중 단계다.

---

## STEP 4 — 첫 영상 만들기 (10분)

### 먼저 비용부터 확인 (API 호출 없음, 무료)

```bash
python main.py estimate --clips 5 --duration 5
```

```
│ 클립      : 5개 x 5초  (원본 25초)
│ 영상 생성 : 5 x $0.3500 = $1.75
│ ▶ 실질 예상 : $3.22
```

### 실행

```bash
python main.py generate --image seeds/내이미지.png --mode montage --clips 5
```

비용을 보여주고 `계속할까요? [y/N]` 을 묻는다. `y` 입력.
**5~10분** 뒤 `runs/{날짜시각}/final.mp4` 가 나온다.

> **왜 `--mode montage` 인가**
> 장면이 서로 독립적이라 화질이 무너지지 않는다. 실패율이 낮아 첫 시도에 적합하다.
> 끊김 없이 계속 전진하는 @odysseyml 스타일은 `--mode chain` 인데, 4~5회차부터
> 풍경이 붕괴해 재시도 비용이 더 든다. **montage 로 감을 잡고 chain 으로 넘어가라.**

### 결과가 마음에 안 들면

```bash
# 클립만 다시 이어붙이기 (추가 비용 $0)
python main.py stitch --run 20260821_193000

# 회차마다 확인하며 진행 — 망가지면 중간에 끊는다. 비용 절약에 가장 효과적
python main.py generate --image seeds/내이미지.png --interactive
```

---

## STEP 5 — 유튜브 업로드 (선택, 15분)

유튜브는 **S3 가 필요 없다.** 파일을 직접 올린다.

1. https://console.cloud.google.com → 프로젝트 생성
2. **API 및 서비스** → **YouTube Data API v3** 사용 설정
3. **사용자 인증 정보** → *OAuth 클라이언트 ID* → **데스크톱 앱**
4. JSON 을 받아 `shorts-pipeline/secrets/client_secret.json` 로 저장

```bash
python main.py publish --run 20260821_193000 --youtube --title "Neon Ride"
```

처음 한 번만 브라우저 인증이 뜬다. 기본값은 **비공개(private)** 업로드라
유튜브에서 직접 확인한 뒤 공개로 바꾸면 된다.
공개로 바로 올리려면 `config.yaml` 의 `publish.youtube.privacy` 를 `public` 으로.

---

## STEP 6 — 인스타그램 (선택, 나중에)

인스타는 준비물이 많다. **유튜브부터 돌려보고 감을 잡은 뒤에 하는 걸 권한다.**

필요한 것:
1. 인스타 계정을 **프로페셔널(비즈니스/크리에이터)** 로 전환
2. **페이스북 페이지**에 연결
3. Meta 개발자 앱 생성 + `instagram_content_publish` 권한
4. **Cloudflare R2** 버킷 (무료) — 인스타가 로컬 파일을 안 받고 공개 URL 만 받는다

R2 는 https://dash.cloudflare.com → R2 → 버킷 생성 →
*Manage API Tokens* → **Object Read & Write** 토큰 발급.
`.env` 에 4줄 추가:

```bash
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_BUCKET=버킷이름
AWS_ACCESS_KEY_ID=발급받은_키
AWS_SECRET_ACCESS_KEY=발급받은_시크릿
```

돈 쓰기 전에 연결부터 확인:
```bash
python main.py upload --file runs/20260821_193000/final.mp4
```

R2 무료 티어(10GB·이그레스 무료) 안에서 계속 $0 로 돌아간다.

---

## STEP 7 — 자동 정기 업로드

`seeds/` 에 이미지를 쌓아두고 예약을 건다. 쓴 이미지는 `seeds/_used/` 로 옮겨져
같은 걸 두 번 쓰지 않는다.

**Mac/Linux** — `crontab -e`
```cron
0 9,21 * * * cd /경로/shorts-pipeline && python -m publish.scheduler \
  --seeds ./seeds --mode montage --publish --youtube
```

**Windows** — 작업 스케줄러에서 위 명령을 등록

연재물로 만들려면 (@cyborg.digitalart 의 "part 16" 방식):
```bash
python -m publish.scheduler --series "Infinite Peace" --publish --youtube
```
제목이 `Infinite Peace part 17` 처럼 자동으로 붙는다.

---

## 첫 실행에서 막히면

| 증상 | 원인과 해결 |
|---|---|
| `ffmpeg 를 찾을 수 없습니다` | ffmpeg 미설치 또는 PATH 누락. STEP 1 재확인 |
| `FAL_API_KEY 가 설정되지 않았습니다` | `.env` 가 `shorts-pipeline/` 안에 있는지 확인 |
| **`fal HTTP 422`** | **모델 엔드포인트 경로 문제.** 아래 참고 |
| `fal HTTP 402` | fal 잔액 부족. 충전 필요 |
| 4회차부터 그림이 뭉개짐 | 정상이다. `--interactive` 로 그 지점에서 끊어라 |
| 영상이 너무 짧다/길다 | `--clips` 로 조절. 5클립=25초, 6클립=30초 |

### 422 가 뜨면 (가능성 있음)

`config.yaml` 의 fal 모델 엔드포인트는 조사한 값이라 **실제 호출로 검증하지
못했다.** 공급사가 경로를 바꿨을 수 있다.

1. https://fal.ai/models 에서 쓰려는 모델을 찾는다
2. 페이지의 엔드포인트 문자열을 복사 (예: `fal-ai/kling-video/v2.5-turbo/pro/image-to-video`)
3. `config.yaml` 의 해당 `endpoint:` 값을 교체

단가도 같은 페이지에서 확인해 `price_per_second` 를 맞춰두면 견적이 정확해진다.

---

## 요약 — 오늘 할 일

- [ ] STEP 1 — Python · ffmpeg · 코드 설치
- [ ] STEP 2 — 세로 이미지 1장을 `seeds/` 에
- [ ] STEP 3 — fal.ai 가입 · $5 충전 · `.env` 에 키 한 줄
- [ ] STEP 4 — `python main.py generate --image seeds/내이미지.png --mode montage --clips 5`

여기까지가 첫 영상이다. 유튜브·인스타·자동화는 그 다음에 붙이면 된다.
