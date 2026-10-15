# AutoShorts-Engine

롱폼 영상(유튜브 URL 또는 로컬 MP4)을 AI 로 분석해 **자막이 합성된 9:16 쇼츠**를
자동으로 만들어 주는 로컬 파이프라인입니다.

전사는 로컬 `faster-whisper`, 하이라이트 선정은 Gemini 무료 티어, 렌더링은 FFmpeg —
**전 구간 오픈소스/무료 티어로 무과금 동작**합니다. Gemini 키가 없으면 내장 휴리스틱
분석기로 자동 대체되어 완전 오프라인에서도 끝까지 돕니다.

```
[0. 급상승 탐색]    YouTube Data API  키워드/채널 → V/S 높은 '떡상 영상' (선택)
        ▼
[1. 다운로드/추출]  yt-dlp            영상 + 16kHz 모노 WAV
        ▼
[2. 음성→텍스트]    faster-whisper    단어 단위 타임스탬프 (transcription.json / .srt)
        ▼
[3. 하이라이트]     Gemini Flash      30~60초 구간 3~5개 + 후킹 제목 + 바이럴 점수
        ▼
[4. 리프레이밍]     FFmpeg            16:9 → 9:16 (블러 배경 / 중앙 크롭)
        ▼
[5. 자막 번인]      FFmpeg + ASS      단어별 노란색 강조 자막 → 최종 MP4
```

## 집 PC 설치 (처음 한 번만)

### 1) 내려받기

```bash
git clone -b claude/vibrant-goldberg-otvlgf https://github.com/himan98hkt-prog/-.git autoshorts
cd autoshorts/autoshorts-engine
```

압축 파일로 받으셨다면 풀고 `autoshorts-engine` 폴더로 들어가세요.

### 2) 설치 스크립트 실행

가상환경을 만들고 의존성을 모두 넣어 줍니다. FFmpeg 와 파이썬 버전도 함께 확인합니다.

```bash
# macOS / Linux
bash install.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File install.ps1
```

### 3) API 키 입력

```bash
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
autoshorts setup
```

키를 물어보는 대로 붙여 넣으면 `.env` 에 저장됩니다(권한 600, 이 PC 밖으로 나가지 않음).
엔터만 치면 건너뛰며, **둘 다 비워도 로컬 제작은 됩니다.**

| 키 | 쓰임 | 없으면 |
|---|---|---|
| `GEMINI_API_KEY` | 하이라이트 선정 | 오프라인 휴리스틱으로 대체 |
| `YOUTUBE_API_KEY` | 급상승 탐색(`trend`) | `trend` 명령만 못 씀 |

### 4) 업로드 인증 (업로드를 쓸 때만)

업로드는 조회용 API 키가 아니라 **OAuth 로그인**이 필요합니다.

1. [Google Cloud Console](https://console.cloud.google.com) → API 및 서비스 → 사용자 인증 정보
2. **OAuth 클라이언트 ID** 만들기 → 유형은 **데스크톱 앱**
3. JSON 을 받아 `~/.autoshorts/client_secret.json` 에 저장
   (Windows: `C:\Users\<사용자>\.autoshorts\client_secret.json`)
4. 로그인 — 브라우저가 열립니다. **최초 1회면 끝**이고, 이후 예약 실행은 무인으로 돕니다.

```bash
autoshorts login
```

### 5) 점검

```bash
autoshorts doctor
```

FFmpeg·의존성·키·로그인·예약 상태를 한 번에 확인하고, 빠진 것은 설치 명령까지 알려 줍니다.

## 설치

```bash
# 1) 파이썬 패키지 (Python 3.10+)
pip install -r requirements.txt        # 또는: pip install -e .

# 2) FFmpeg (필수 · 별도 설치)
brew install ffmpeg                    # macOS
sudo apt install ffmpeg fonts-nanum    # Ubuntu (한글 자막 폰트 포함)
winget install Gyan.FFmpeg             # Windows

# 3) API 키 (선택)
cp .env.example .env && $EDITOR .env
#    GEMINI_API_KEY   하이라이트 선정 — 없으면 오프라인 휴리스틱으로 대체
#    YOUTUBE_API_KEY  급상승 탐색(autoshorts trend) — 이 기능을 쓸 때만 필요
```

> **한글 자막이 네모(□)로 나온다면** 폰트가 없는 것입니다. `fonts-nanum` 등 한글
> 폰트를 설치하거나 `--font "설치된 폰트 이름"` 으로 지정하세요.

## 사용법

```bash
# 급상승 영상 찾아서 1위로 바로 쇼츠까지 — 원클릭
autoshorts trend "재테크" --run
autoshorts trend "@채널핸들" --days 30 --run

# 전체 파이프라인 — 서브커맨드는 생략 가능
autoshorts "https://www.youtube.com/watch?v=..."
autoshorts run 강의영상.mp4 --mode crop --model small -o shorts

# 단계별 실행 (중간 산출물 재사용)
autoshorts transcribe 강의영상.mp4              # → work/.../transcription.json + .srt
autoshorts analyze work/.../transcription.json  # → clips.json (구간 검토·수정 가능)
autoshorts render 강의영상.mp4 --clips clips.json --transcript work/.../transcription.json

# 웹 대시보드 (pip install gradio)
autoshorts ui
```

`python -m autoshorts ...` 로도 동일하게 실행됩니다.

### 자주 쓰는 옵션

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--mode {blur,crop}` | `blur` | `blur` 상하단 블러 배경 + 원본 중앙 배치 / `crop` 중앙 크롭 |
| `--model` | `base` | Whisper 모델 (`tiny`/`base`/`small`/`medium`/`large-v3`) |
| `--device` | `auto` | `auto` 는 CUDA 감지 시 GPU(float16), 아니면 CPU(int8) |
| `--language` | 자동 감지 | `ko`, `en` 등으로 강제 지정하면 더 빠르고 정확 |
| `--min-seconds` / `--max-seconds` | `30` / `60` | 클립 길이 범위 |
| `--min-clips` / `--max-clips` | `3` / `5` | 클립 개수 범위 |
| `--crf` / `--preset` | `20` / `veryfast` | 화질·속도 트레이드오프 (CRF 낮을수록 고화질) |
| `--no-subtitles` | off | 자막 번인 생략 |
| `--no-word-highlight` | off | 단어별 노란색 강조 대신 단색 자막 |
| `--lossless-cut` | off | 스트림 복사로 먼저 무손실 컷한 뒤 렌더 (아래 참고) |
| `--dry-run` | off | FFmpeg 실행 없이 명령만 확인 |
| `--overwrite` | off | 같은 이름의 결과 파일 덮어쓰기 (기본은 `-2`, `-3` 을 붙여 보존) |

### 급상승 탐색 (`autoshorts trend`)

키워드나 채널에서 **구독자 대비 조회수(V/S Ratio)** 가 높은 최근 영상을 찾습니다.

```bash
autoshorts trend "부업"                      # 목록만 보기
autoshorts trend "부업" --json trend.json    # 결과 저장
autoshorts trend "부업" --run                # 1위 영상으로 쇼츠까지 자동 제작
autoshorts trend "@채널핸들" --days 30        # 특정 채널의 최근 30일 업로드 중에서
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--run` | off | 1위 영상 URL 을 그대로 파이프라인에 넘겨 쇼츠까지 제작 |
| `--channel` | 자동 판별 | 입력을 채널로 강제 해석 (`@핸들`·채널 URL·`UC…` 는 자동 인식) |
| `--days` | `14` | 최근 며칠 안의 업로드만 대상 |
| `--top` | `10` | 상위 몇 개를 남길지 |
| `--min-vs` | `1.0` | 최소 V/S 비율. `1.0` 이면 구독자 수만큼은 조회돼야 통과 |
| `--min-subscribers` | `1000` | 최소 구독자 수 |
| `--min-duration` | `180` | 원본 최소 길이(초). 기본 3분 — 이미 쇼츠인 영상을 걸러냅니다 |
| `--region` / `--lang` | 없음 | 지역 코드(`KR`) · 관련 언어(`ko`) |

**순위 산정**은 V/S 비율을 뼈대로 두 가지를 보정합니다.

```
점수 = V/S 비율 × 신선도 × 반응도
  신선도  탐색 창 안에서 오래될수록 최대 70% 감점
          (영상은 시간이 지나면 조회수가 쌓이므로 보정 없이는 오래된 영상이 유리해집니다)
  반응도  좋아요/조회 비율로 최대 +20% 가산
```

기본 필터가 걸러내는 것들 — 이유가 있습니다.

- **구독자 1,000명 미만 채널**: 구독자 10명에 조회수 5,000이면 V/S 가 500 이 되어 순위를 점령합니다. 지표가 의미를 가지려면 하한이 필요합니다.
- **구독자 수 비공개 채널**: V/S 를 계산할 수 없어 제외합니다.
- **3분 미만 영상**: 이미 쇼츠이거나, 30~60초 하이라이트를 뽑을 여지가 없습니다.
- **라이브/예정 방송**: 다운로드 대상이 아닙니다.

**할당량 주의.** 무료 한도는 하루 10,000 유닛인데 `search.list` 만 **1회 100 유닛**입니다(하루 100회). 채널을 지정하면 `playlistItems` 경로를 타서 **1회 4 유닛 안팎**으로 끝나므로, 특정 채널을 반복해서 볼 때는 `--channel` 쪽이 압도적으로 유리합니다. 실행할 때마다 소모한 유닛을 출력합니다.

### 자동 업로드 (`autoshorts upload` · `--upload`)

```bash
autoshorts upload output/output_01_제목.mp4                  # 파일 하나 올리기
autoshorts upload output/*.mp4 --privacy unlisted            # 여러 개
autoshorts auto "재테크" --upload --publish-in 6h            # 만들고 6시간 뒤 공개 예약
```

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--privacy` | `private` | `private` / `unlisted` / `public` |
| `--publish-at` | 없음 | 절대 시각 예약 공개 (`2026-09-15T09:00:00+09:00`) |
| `--publish-in` | 없음 | 상대 시각 예약 공개 (`90m` · `6h` · `2d`) |
| `--upload-count` | 전부 | 몇 개까지 올릴지 |
| `--tags` | 없음 | 쉼표로 구분 (`재테크,부업`) |
| `--dry-run-upload` | off | 쇼츠는 만들되 업로드 직전에 멈춤 |

**공개 범위 기본값이 `private` 인 이유.** 남의 영상을 잘라 만든 쇼츠를 자동으로 공개하면
저작권 신고나 채널 경고로 이어질 수 있습니다. 기본은 비공개로 올려 두고, 눈으로 확인한 뒤
직접 공개하시길 권합니다. `--privacy public` 을 쓰면 경고를 한 번 출력합니다.

**예약 공개**를 쓰면 비공개로 올라간 뒤 지정한 시각에 YouTube 가 알아서 공개합니다.
여러 개를 한 번에 올리면 24시간 간격으로 자동으로 벌려 줍니다.

> **업로드 할당량이 진짜 제약입니다.** `videos.insert` 는 **1건에 1,600 유닛**이라
> 무료 한도(하루 10,000)로는 **하루 6건**이 상한입니다. 이 도구는 이력을 보고 한도를
> 넘지 않도록 스스로 멈춥니다.

### 정기 예약 발행 (`autoshorts schedule`)

집 PC 의 기본 스케줄러(윈도우 작업 스케줄러 · cron · launchd)에 등록하므로
**상주 프로그램이 필요 없고 PC 를 껐다 켜도 유지**됩니다.

```bash
# 매일 09시 — 급상승 1위로 쇼츠 2개를 만들어 비공개 업로드
autoshorts schedule add "재테크" --at 09:00 -- --upload --upload-count 2

# 매주 월요일 21시, 특정 채널에서
autoshorts schedule add "@채널핸들" --at 21:00 --weekday mon -- --upload

# 6시간마다
autoshorts schedule add "부업" --every-hours 6 -- --upload --publish-in 12h

autoshorts schedule show      # 현재 등록 확인
autoshorts schedule remove    # 해제
autoshorts schedule add "재테크" --at 09:00 --dry-run   # 등록될 내용만 미리보기
```

`--` 뒤에 쓴 인자는 `autoshorts auto` 에 그대로 전달됩니다.
(`--auto-args="--upload"` 형태도 됩니다.)

**같은 영상을 두 번 만들지 않습니다.** 처리한 원본을 `~/.autoshorts/history.json` 에
남겨 두고, 다음 실행에서 이미 처리한 영상은 건너뛰고 그다음 후보로 넘어갑니다.
일부러 다시 만들려면 `--allow-reprocess` 를 쓰세요.

**예약 실행 전 확인 사항**
- `autoshorts login` 을 미리 해 두어야 무인 업로드가 됩니다(예약 실행은 브라우저를 띄우지 않습니다).
- 예약 시각에 PC 가 켜져 있어야 합니다. 절전 모드면 깨어난 뒤 실행됩니다.
- 로그를 남기려면 `--log ~/autoshorts.log` 를 붙이세요.

### 출력 규격

- 해상도 **1080 × 1920** (9:16) · **H.264 / AAC** MP4 · `+faststart`
- 파일명 **`output_[클립번호]_[후킹제목].mp4`** (예: `output_01_아무도_모르는_사실.mp4`)
- `output/manifest.json` 에 선정 구간·점수·선정 이유·경로가 모두 기록됩니다.

## 동작 방식

### Module F — `uploader.py`
OAuth 2.0 으로 인증해 `videos.insert` 를 호출합니다. 요청 본문을 만드는 부분은 순수
함수라 테스트로 고정돼 있고, 제목 100자·설명 5,000자·태그 500자 상한과 `<`/`>` 금지
문자를 자동으로 맞춥니다. 갱신 토큰은 `~/.autoshorts/youtube_token.json` 에 권한 600
으로 저장하며 저장소에는 절대 올라가지 않습니다(`.gitignore` 등록).

### Module G — `scheduler.py` / `state.py`
OS 기본 스케줄러에 등록할 명령을 만들고 설치·해제합니다. 명령 문자열을 만드는 함수는
부수효과가 없어 `--dry-run` 으로 무엇이 등록될지 먼저 확인할 수 있습니다.
`state.py` 는 처리 이력과 하루 업로드 횟수를 관리해 중복 제작과 할당량 초과를 막습니다.

### Module E — `trend_finder.py`
YouTube Data API v3 를 표준 라이브러리 `urllib` 로 직접 호출합니다(추가 의존성 없음).
`videos.list` / `channels.list` 는 50개씩 묶어 호출해 할당량을 아끼고, HTTP 계층은
주입 가능해서 테스트가 네트워크 없이 돕니다. API 키는 로그와 오류 메시지 어디에도
남지 않습니다.

### Module A — `downloader.py`
`yt-dlp` 로 최고 화질 비디오 + 최고 음질 오디오를 받아 MP4 로 병합합니다. 로컬
파일은 복사 없이 그대로 참조하고, 어느 쪽이든 STT 규격(16kHz·모노·PCM)의 WAV 를
분리 추출합니다. 로그인이 필요한 영상은 `--cookies-from-browser chrome` 를 쓰세요.

### Module B — `transcriber.py`
`faster-whisper` 로 단어 단위 타임스탬프까지 추출해 `transcription.json` 과 `.srt` 로
저장합니다. VAD 로 무음을 걸러 내고, `condition_on_previous_text=False` 로 긴 영상에서
흔한 환각 반복을 억제합니다. GPU 초기화가 실패하면 자동으로 CPU(int8)로 내려갑니다.

### Module C — `ai_analyzer.py`
타임스탬프가 붙은 전사본을 Gemini 에 넘겨 `start_time` / `end_time` / `title` /
`reason` / `score` 를 JSON 스키마로 강제 반환받습니다. 모델 출력은 그대로 믿지 않고
다음을 기계적으로 교정합니다.

- 영상 길이 밖으로 나간 구간 잘라 맞추기
- 발화 경계로 스냅해 문장 중간에서 시작·종료하지 않게 하기
- 30초 미만은 늘리고 60초 초과는 자르기
- 크게 겹치는 구간은 점수가 높은 쪽만 남기기

**API 키가 없거나 호출이 실패(쿼터 초과 등)하면** 발화 밀도·훅 표현·수치 언급으로
점수를 매기는 오프라인 휴리스틱으로 자동 대체합니다(광고·구독 유도 구간은 감점).
대체를 원치 않으면 `--no-offline-fallback` 으로 중단시킬 수 있습니다.

### Module D — `video_renderer.py` / `subtitles.py`
리프레이밍과 자막 번인을 **한 번의 FFmpeg 패스**로 처리합니다.

- `blur`: 배경은 화면을 채우도록 확대 후 가우시안 블러, 전경은 원본 비율 그대로 중앙 배치
- `crop`: 목표 비율로 중앙 크롭 후 1080×1920 스케일

자막은 구간에 해당하는 단어만 잘라 ASS 로 만들고, 현재 발화 중인 단어를 노란색으로
키우며 강조합니다(`--no-word-highlight` 로 끌 수 있음).

**`--lossless-cut`**: 먼저 스트림 복사(재인코딩 없음)로 구간만 떼어 낸 뒤 그 조각만
렌더링합니다. 긴 원본에서 반복 탐색 비용이 줄지만, 스트림 복사는 시작점이 키프레임으로
스냅되므로 시작이 최대 몇 초 어긋날 수 있습니다. 기본값(단일 패스)이 프레임 단위로
정확하므로, 아주 긴 원본에서 속도가 급할 때만 쓰세요.

## 캐시와 재실행

작업 디렉터리는 소스별로 분리됩니다(`work/<이름>-<해시>/`). 같은 소스를 다시 돌리면
다운로드와 전사를 건너뛰고 분석·렌더링만 다시 합니다. 강제로 다시 하려면
`--overwrite` 를 쓰세요.

## 테스트

```bash
pip install pytest
pytest                 # 454건 — FFmpeg·API 키·네트워크 없이 전부 통과
```

무거운 의존성(`yt-dlp`, `faster-whisper`, Gemini SDK, `gradio`)은 전부 지연 임포트라
설치 없이도 패키지 임포트와 테스트가 가능합니다. FFmpeg 관련 테스트는 명령·필터
그래프 문자열을 검증하고, 실제 실행은 가로챕니다.

## 알아 둘 점

- **저작권**: 남의 영상을 잘라 재배포하는 일은 저작권 문제가 될 수 있습니다. 본인 영상이나
  이용 허락을 받은 영상에 쓰시고, 자동 업로드는 비공개로 두었다가 확인 후 공개하세요.
- **급상승 지표의 한계**: V/S 비율은 '구독자 대비 얼마나 퍼졌나'를 볼 뿐, 영상이
  쇼츠로 만들기 좋은지는 말해 주지 않습니다. `--run` 으로 바로 만들기 전에 목록을
  한 번 눈으로 보시길 권합니다.
- **처리 시간**: 전사가 대부분을 차지합니다. CPU `base` 모델 기준 대략 영상 길이의
  0.3~1배, `--model tiny` 면 더 빠르고 `small` 이상은 더 정확합니다.
- **Gemini 무료 티어**에는 분당/일일 요청 한도가 있습니다. 한도를 넘으면 자동으로
  오프라인 분석으로 넘어갑니다.
## 라이선스

MIT
