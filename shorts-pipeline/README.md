# shorts-pipeline

이미지 1장 → **끊김 없이 전진하는 세로 영상** → YouTube Shorts / Instagram Reels 자동 업로드.

첨부된 레퍼런스 계정(@odysseyml, @cyborg.digitalart, @hellopersonality 등)을
실측 분석해 파라미터를 역산했다. 근거는 [docs/REFERENCE_ANALYSIS.md](docs/REFERENCE_ANALYSIS.md).

---

> ## 명령어 없이 쓰려면 → **[START_HERE.md](START_HERE.md)**
> 바탕화면 아이콘과 브라우저 화면만으로 영상 제작·업로드까지 끝냅니다.
>
> | 더블클릭할 파일 | 하는 일 |
> |---|---|
> | `shortcuts.bat` | 바탕화면에 바로가기 3개를 만듭니다 (처음 한 번) |
> | `start.bat` | 작업실을 엽니다. 필요한 것은 알아서 설치합니다 |
> | `update.bat` | 최신 코드를 받습니다. 키·이미지·영상은 그대로 |
>
> 작업실의 **[간편 모드]** 탭에는 지금 눌러야 할 버튼 하나만 나오고,
> **[설정]** 탭에서 fal 키·유튜브·인스타를 전부 연결할 수 있습니다.
> `SHORTS_MOCK=1 python main.py ui` 로 띄우면 비용 없이 둘러볼 수 있습니다.
>
> **매일 자동 업로드까지 세팅** → **[SETUP.md](SETUP.md)**
> 직접 발급해야 하는 키와 계정 설정을 순서대로 정리했습니다.
>
> **브랜드 에셋·문구** → **[brand/BRAND.md](brand/BRAND.md)**
> 유튜브/인스타 프로필·배너 이미지와 채널 소개 문구가 들어 있습니다.
>
> **터미널로 하시겠다면** → **[QUICKSTART.md](QUICKSTART.md)**
> 계정 가입부터 첫 영상까지 30분 · 약 $5 로 따라 할 수 있게 정리했습니다.

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

## 배경음악

영상만 나오면 끝까지 보지 않습니다. `music/` 아래 **분위기 폴더**에 곡을
넣어 두면 시드의 테마에 맞는 것을 골라 자동으로 깝니다.

```
music/bright   밝고 상쾌 — 다운힐, 해안, 애니
music/epic     웅장     — 용·비행, 거대 존재, 부유섬, 신전
music/calm     잔잔     — 영혼의 길, 도서관, 숲, 기차
music/mystic   신비     — 크리스탈, 심해, 얼음, 우주, 터널
music/city     도시 밤   — 마법 도시, 야간 드라이브, 골목
music/any      위가 비었을 때의 보험
```

- `config.yaml` 의 `output.audio: auto` 가 기본값입니다
- 곡은 **파일명 해시**로 고릅니다. 같은 시드는 항상 같은 곡 — 다시 만들어도 비교가 됩니다
- 라우드니스 -14 LUFS 로 자동 정규화, 앞 1초 페이드인·뒤 1.6초 페이드아웃
- 곡이 하나도 없으면 경고만 남기고 **무음으로 진행**합니다. 하루치가 통째로 날아가지 않게

수노(Suno) 프롬프트 25개가 `music/PROMPTS_SUNO.md` 에 있습니다.
**[Instrumental] 을 켜고 40~60초**로 뽑으세요.

---

## 명령

| 명령 | 하는 일 |
|---|---|
| `generate` | 이미지 1장에서 영상 생성 |
| `resume --run ID` | 중단된 실행을 이어서 완료 |
| `stitch --run ID` | 이미 만든 클립으로 합성만 다시 |
| `ui` | **브라우저 작업실** — 클릭으로 제작·업로드 |
| `estimate [--compare]` | API 호출 없이 비용만 계산 |
| `publish --run ID` | YouTube / Instagram 업로드 (필요 시 S3 자동 업로드) |
| `upload --run ID` | S3 에만 올려 공개 URL 생성 (자격증명 점검용) |
| `intake --from 폴더` | 새로 받은 이미지 중 **아직 안 들여온 것만** seeds/ 에 넣기 |
| `reclassify` | seeds/ 를 전부 다시 살펴 테마·사이드카 맞추기 |
| `curate --from 폴더` | 수백 장을 훑어 테마마다 상위 N장만 고르기 (초기 세팅용) |

`intake` 와 `curate` 는 목적이 다릅니다. **계속 다운로드하면서 쓰는 쪽은
`intake`** 입니다. 이미 들여온 그림은 내용 해시로 기억해 두고 건너뛰므로
같은 폴더를 몇 번 가리켜도 안전합니다.

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

### 스토리지 — Cloudflare R2 무료 티어 기준

기본값이 R2 무료 티어에 맞춰져 있다. **이 용도에서는 사실상 계속 $0 이다.**

| R2 무료 티어 (월 갱신) | 릴스 1편이 쓰는 양 |
|---|---|
| 보관 10GB | 발행 직후 삭제 → **0 에 수렴** |
| 쓰기(Class A) 1M/월 | **1회** (단일 PUT) |
| 읽기(Class B) 10M/월 | **1회** (인스타그램이 1번 받아감) |
| 이그레스 **무제한 무료** | — |

R2 대시보드 → R2 → *Manage API Tokens* 에서 **Object Read & Write** 토큰을
만들면 아래 3개를 한 번에 준다. `.env` 에 넣을 것은 4줄이 전부다.

```bash
S3_ENDPOINT_URL=https://<account_id>.r2.cloudflarestorage.com
S3_BUCKET=my-reels
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

`S3_REGION` 은 **비워둔다** — R2 가 요구하는 `auto` 로 자동 설정된다.

돈 쓰기 전에 자격증명부터 확인하고, 남은 무료 용량도 같이 본다:

```bash
$ python main.py upload --file ./test.mp4

✓ 업로드 완료 (12.0 MB)
  만료 : 2026-08-21 13:49 UTC
  URL  : https://....r2.cloudflarestorage.com/reels/...?X-Amz-Signature=...

  보관 0.04 / 10GB  [························] 0.4%  (3개 객체)
```

**AWS S3 를 쓰려면** `S3_ENDPOINT_URL` 을 비우고 `S3_REGION` 에 실제 리전을
넣으면 된다. 나머지 기본값은 그대로 써도 문제없다.
Backblaze B2 · MinIO 도 엔드포인트만 바꾸면 동작한다.

#### 기본값이 이렇게 잡힌 이유

| 키 | 기본값 | 이유 |
|---|---|---|
| `url_strategy` | `presigned` | 서명된 만료 URL. **버킷을 공개로 열 필요가 없다.** 인스타그램은 컨테이너 생성 시 한 번만 받아가므로 충분하다 |
| `delete_after_publish` | `true` | 발행 후 삭제 → 보관량 0 → 무료 티어 영구 유지. 로컬 `runs/{id}/final.mp4` 는 남으므로 원본을 잃지 않는다 |
| `multipart_threshold_mb` | `100` | 릴스는 8~20MB 라 대부분 단일 PUT 으로 나간다. R2 의 멀티파트 파트 크기 제약을 안 건드리고 Class A 도 4회 → 1회로 준다 |
| `acl` | 비움 | **R2 는 ACL 을 지원하지 않는다.** 값을 넣으면 실행 전에 막는다 |
| `expiry_seconds` | `3600` | 인스타그램 인코딩 대기까지 감안한 여유. 60 ~ 604800(7일) |
| `prefix` | `reels` | 키는 `reels/{run_id}/final.mp4` |

> **botocore 1.36+ 대응**: 최신 boto3 는 `PutObject` 에 CRC32 체크섬을 기본으로
> 붙이는데 R2 가 이를 거부한다 (`x-amz-checksum-algorithm ... not implemented`).
> 커스텀 엔드포인트에서는 `request_checksum_calculation` 을 `when_required` 로
> 되돌려 이 문제를 피한다. AWS S3 에서는 무결성 검사를 그대로 둔다.

`--video-url` 로 직접 URL 을 주면 스토리지 단계를 건너뛴다.

---

## 검증

API 를 한 번도 부르지 않고(비용 $0) 파이프라인 전 구간을 검사한다.
가짜 provider 가 ffmpeg 로 합성 클립을 만들어 체이닝·추출·합성·resume 을 돌린다.

```bash
python tests/test_pipeline.py    # 통과 35 / 실패 0
python tests/test_storage.py     # 통과 45 / 실패 0  (moto 필요)
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
