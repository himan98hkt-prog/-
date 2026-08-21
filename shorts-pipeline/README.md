# shorts-pipeline

이미지 1장 → **끊김 없이 전진하는 세로 영상** → YouTube Shorts / Instagram Reels 자동 업로드.

첨부된 레퍼런스 계정(@odysseyml, @cyborg.digitalart, @hellopersonality 등)을
실측 분석해 파라미터를 역산했다. 근거는 [docs/REFERENCE_ANALYSIS.md](docs/REFERENCE_ANALYSIS.md).

---

## 빠른 시작

```bash
cd shorts-pipeline
pip install -r requirements.txt
cp .env.example .env          # FAL_API_KEY 등을 채운다

# 1) API 를 부르지 않고 비용부터 확인
python main.py estimate --compare

# 2) 생성
python main.py generate --image ./photo.png --clips 6 --interactive

# 3) 업로드
python main.py publish --run 20260821_193000 --youtube --title "Endless Ride"
```

ffmpeg 가 필요하다. `brew install ffmpeg` / `apt-get install ffmpeg`.

---

## 두 가지 모드

레퍼런스를 분석해보니 하나의 포맷이 아니라 둘이었다.

### `mode: chain` — 끊기지 않는 전진
클립의 **마지막 프레임을 다음 클립의 시작 이미지로** 넘겨 하나의 긴 샷을 만든다.
경계마다 0.3초 크로스페이드로 이음매를 지운다.

```
입력 → [클립1] → 라스트프레임 → 업스케일 → [클립2] → … → 크로스페이드 합성
```

@odysseyml, @hellopersonality 스타일. 몰입감이 강하지만 4~5회차부터
풍경이 무너지므로 `--interactive` 로 지켜봐야 한다.

### `mode: montage` — 장면 몽타주
독립 장면 5~6개를 각각 5초로 만들어 하드 컷으로 붙인다. 장면끼리
이어지지 않으므로 **화질 열화가 누적되지 않는다.**

@cyborg.digitalart 의 "Infinite peace part N" 이 정확히 이 구조다
(실측: 5초 x 6장면 = 25.5초, 마지막에 첫 장면으로 회귀).

```bash
python main.py generate --image seed.png --mode montage --clips 5
```

**실패율이 낮아 비용이 덜 든다. 기본으로 이쪽을 권한다.**

---

## 명령

| 명령 | 하는 일 |
|---|---|
| `generate` | 이미지 1장에서 영상 생성 |
| `resume --run ID` | 중단된 실행을 이어서 완료 |
| `stitch --run ID` | 이미 만든 클립으로 합성만 다시 |
| `estimate [--compare]` | API 호출 없이 비용만 계산 |
| `publish --run ID` | YouTube / Instagram 업로드 (필요 시 S3 자동 업로드) |
| `upload --run ID` | S3 에만 올려 공개 URL 생성 (자격증명 점검용) |

주요 옵션:

```bash
--clips 6              # 클립 수
--duration 5           # 클립당 초
--mode chain|montage
--model kling_30_pro   # config 의 모델 키
--provider fal|higgsfield
--no-upscale           # 업스케일 끄기 (비용 절감)
--pad                  # 9:16 변환 시 크롭 대신 블러 패딩
--interactive          # 회차마다 프레임 확인 후 계속/리셋/중단
--yes                  # 비용 확인 프롬프트 생략
```

---

## provider

| provider | 과금 | 특징 |
|---|---|---|
| **fal** | 종량제 (초당) | 모델이 많다. 로컬 이미지를 data URI 로 바로 올린다 |
| **higgsfield** | 구독 크레딧 | 월 55편까지는 가장 싸다. 이미지에 공개 URL 이 필요하다 |

Higgsfield 를 넣은 이유: 레퍼런스 @cyborg.digitalart 의 프로필 bio 에
사용 스택이 그대로 적혀 있다 — `Adobe | Openart | Higgsfield | hailuo | kling | wery ai | pixverse`.

모델 ID 와 단가는 전부 `config.yaml` 에 있다. **코드에 하드코딩하지 않았으므로
공급사가 가격을 바꾸면 yaml 만 고치면 된다.**

---

## 비용

```
25초 1편 기준 (5클립 x 5초, 재시도 x1.8 반영)
  higgsfield / kling3_0_turbo   $2.26
  fal / wan_25_480p             $2.32
  fal / kling_25_turbo_pro      $3.22
  fal / kling_30_pro            $5.11
```

**계획한 클립 수 = 실제 호출 수가 아니다.** 실패·품질 리젝 때문에
1.6~2.2배가 실제로 나간다. `cost.retry_multiplier` 가 이걸 견적에 반영한다.

실행 전 항상 예상 비용이 뜨고, `cost.hard_cap_usd` 를 넘으면 `--yes` 가 있어도 막는다.

시나리오별 상세는 [docs/COST_ANALYSIS.md](docs/COST_ANALYSIS.md).

---

## 정기 업로드

`seeds/` 에 이미지를 쌓아두고 cron 을 건다. 쓴 시드는 `seeds/_used/` 로 옮겨져
중복되지 않는다.

```cron
# 매일 09시와 21시
0 9,21 * * * cd /path/to/shorts-pipeline && \
  python -m publish.scheduler --seeds ./seeds --mode montage --publish --youtube --instagram
```

`--series "Infinite peace"` 를 주면 제목이 `Infinite peace part 17` 처럼
자동으로 회차가 붙는다 — 레퍼런스 계정이 쓰는 연재 방식이다.

---

## 업로드 준비

### YouTube
1. Google Cloud Console → YouTube Data API v3 사용 설정
2. OAuth 클라이언트 ID(데스크톱 앱) 생성 → JSON 을 `secrets/client_secret.json` 로
3. 첫 실행 시 브라우저 인증. 토큰은 `secrets/youtube_token.json` 에 저장된다

`videos.insert` 는 2026-06-01 부터 **전용 일일 버킷(약 100회)** 을 쓴다.

### Instagram
1. 계정을 프로페셔널(비즈니스/크리에이터)로 전환 + 페이스북 페이지 연결
2. Meta 앱에 `instagram_content_publish` 권한
3. 장기 액세스 토큰을 `.env` 에 기록

**인스타그램은 로컬 파일을 못 받는다.** 최종 mp4 가 공개 URL 로 접근
가능해야 하므로 S3 업로드가 `publish --instagram` 에 내장돼 있다 (아래 참고).

발행 한도는 24시간 롤링 50~100건. `GET /{ig-user-id}/content_publishing_limit`
로 실사용량을 조회할 수 있다.

### S3 (또는 R2 / B2 / MinIO)

`.env` 에 버킷과 키만 넣으면 `publish --instagram` 이 알아서 올리고 URL 을 만든다.

```bash
S3_BUCKET=my-reels
S3_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

기본 전략은 **presigned URL** 이다. 서명된 만료 URL 이라 **버킷을 공개로 열
필요가 없다** — 인스타그램은 컨테이너 생성 시 한 번만 받아가므로 충분하다.

AWS 가 아니면 엔드포인트만 바꾸면 된다:

```bash
# Cloudflare R2
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_REGION=auto
```

자격증명이 맞는지는 영상 생성에 돈을 쓰기 전에 확인할 수 있다:

```bash
python main.py upload --file ./anything.mp4
```

`config.yaml` 의 `publish.storage` 에서 조정한다:

| 키 | 기본값 | 설명 |
|---|---|---|
| `url_strategy` | `presigned` | `public` 으로 두면 영구 URL (공개 버킷/CDN 필요) |
| `expiry_seconds` | `3600` | presigned 만료. 60 ~ 604800 |
| `public_base_url` | — | CloudFront / R2 커스텀 도메인 |
| `prefix` | `reels` | 키 앞부분. `reels/{run_id}/final.mp4` |
| `delete_after_publish` | `false` | 발행 후 객체를 지워 보관 비용을 아낀다 |

`--video-url` 로 직접 URL 을 주면 S3 단계를 건너뛴다.

---

## 검증

API 를 한 번도 부르지 않고(비용 $0) 파이프라인 전 구간을 검사한다.
가짜 provider 가 ffmpeg 로 합성 클립을 만들어 체이닝·추출·합성·resume 을 돌린다.

```bash
python tests/test_pipeline.py    # 통과 35 / 실패 0
python tests/test_storage.py     # 통과 26 / 실패 0  (moto 필요)
```

S3 쪽은 `moto` 로 실제 S3 프로토콜을 흉내내 검사한다 — presigned 서명,
Content-Type, 삭제까지 실제로 확인한다. `pip install "moto[s3]"`.

---

## 구조

```
shorts-pipeline/
├── main.py                  CLI
├── config.yaml              모델 ID · 단가 · 프롬프트 · 업로드 설정
├── pipeline/
│   ├── config.py            로드 · 검증 · 오버라이드
│   ├── costs.py             견적 / 사후 정산
│   ├── validator.py         9:16 크롭 · 블러 패딩
│   ├── generator.py         재시도 래퍼
│   ├── frame_extractor.py   라스트 프레임 추출
│   ├── modes.py             chain / montage 오케스트레이션
│   ├── stitcher.py          xfade · concat 합성
│   ├── runlog.py            runs/ 관리 · log.jsonl · resume 상태
│   └── providers/           fal · higgsfield (확장 가능)
├── publish/
│   ├── youtube.py           Data API v3
│   ├── instagram.py         Graph API (컨테이너 → 폴링 → 발행)
│   ├── storage.py           S3 / R2 / B2 / MinIO 업로드, presigned URL
│   └── scheduler.py         cron 용 배치
├── docs/
│   ├── REFERENCE_ANALYSIS.md   레퍼런스 실측 분석
│   └── COST_ANALYSIS.md        비용 시나리오
└── tests/test_pipeline.py
```

새 provider 는 `pipeline/providers/base.py` 의 `VideoProvider` 만 구현하고
레지스트리에 등록하면 나머지는 그대로 돈다.
