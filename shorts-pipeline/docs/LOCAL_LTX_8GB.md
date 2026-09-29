# 8GB 그래픽카드로 집 PC 에서 만들기 — LTX-Video 0.9.8

원리한입 채널(`config.wonri.yaml`)이 쓰는 엔진이다. 한 편에 **$0**.

## 왜 `provider: local` 이 아닌가

이 저장소에는 집 PC 엔진이 **둘** 있다. 둘은 서로 다른 모델이다.

| | `local` | `ltx09` (이 문서) |
|---|---|---|
| 모델 | LTX-2.5 (22B) | LTX-Video 0.9.8 (2B distilled) |
| 그래픽카드 | **15GB 이상** (전체 적재 28GB) | 8GB 에서 돈다 |
| 설치 용량 | 약 70GB | 훨씬 작다 |
| 화질 | 더 좋다 | 한 세대 앞 |
| 소리 | 모델이 함께 만든다 | 만들지 않는다 (music/ 의 곡을 깐다) |

`local` 은 8GB 에서 **어떤 설정으로도 돌지 않는다.** Lightricks 의 LTX Desktop
도 15~16GB 미만은 '지원 안 함' 으로 보고 모든 생성을 유료 클라우드로 보낸다.
억지로 돌리면 디스크까지 쓰며 한 클립에 몇 시간이 걸리거나 도중에 죽는다.
예약이 걸려 있으면 **매일 아침 조용히 실패한다.**

그래서 한 세대 앞의 경량 모델을 쓴다. Lightricks 는 2B distilled 를
*"Smaller model … ideal for fast generation with light VRAM usage"* 라고 적었다.

## 설치

```powershell
# 1) 받기
git clone https://github.com/Lightricks/LTX-Video C:\LTX-Video
cd C:\LTX-Video

# 2) 가상환경 + 의존성
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e .[inference]

# 3) 확인
cd <이 저장소>\shorts-pipeline
python main.py doctor --config config.wonri.yaml
```

모델 파일은 첫 실행 때 Hugging Face 에서 자동으로 받는다. 폴더를 다른 곳에
두었으면 `.env` 에 `LTX09_DIR=D:\LTX-Video` 처럼 적거나
`config.wonri.yaml` 의 `providers.ltx09.ltx_dir` 에 적는다.

## 8GB 에서 지켜야 하는 것

세 가지는 **어기면 실행 시점에 깨진다.** 설정에서 미리 막아 두었지만,
값을 바꿀 때 알고 있어야 한다.

| | 규칙 | 지금 값 |
|---|---|---|
| 해상도 | **32 의 배수**, 720x1280 이하 권장 | 544x960 |
| 프레임 수 | **8k+1**, 257 미만 권장 | 193 (8초 × 24fps) |
| 오프로드 | 8GB 면 켜야 한다 | `auto` → 켜짐 |

프레임 수는 `clip_duration` 에서 자동으로 계산된다(8k+1 로 맞춰진다).
24fps 기준 상한이 약 10.6초라, 16초 영상을 **8초 × 2클립**으로 나눈다.

### 메모리가 모자라면

효과가 큰 순서다. `config.wonri.yaml` 에서 바꾼다.

1. `clip_duration: 8` → `6` (193 → 145 프레임)
2. `providers.ltx09.width/height` `544x960` → `480x864` (둘 다 32 의 배수)
3. 그래도 안 되면 `provider: fal` 로 되돌린다 (유료, 편당 약 $0.80)

메모리 부족으로 죽으면 파이프라인이 그 사실을 알아보고 무엇을 줄일지
알려준다 — 로그에 `out of memory` 가 보이면 이 순서를 밟으면 된다.

## 얼마나 걸리나

8GB + CPU 오프로드는 **느리다.** 한 클립에 수십 분이 걸릴 수 있어
`clip_timeout_minutes` 를 120 으로 두었다.

그래서 예약은 게시 시각보다 **두 시간 앞서** 시작한다
(`win_schedule.LEAD_MINUTES_LOCAL`). 09:00 게시면 07:00 시작이다.
`schedule on` 이 설정의 provider 를 보고 알아서 고른다.

```bash
python main.py schedule on --config config.wonri.yaml
```

> 실제 소요 시간은 카드마다 다르다. 먼저 `python main.py preview --config
> config.wonri.yaml` 로 4초짜리 한 클립을 뽑아 시간을 재 보고, 07:00 시작으로
> 09:00 에 못 맞출 것 같으면 `--at` 으로 게시 시각을 늦추거나 길이를 줄인다.

## 화질

모델이 544x960 으로 만들고, 그 뒤 두 번 키운다.

1. **Real-ESRGAN** — `tools/realesrgan` 에 넣어 두면 클립마다 2배. 없으면 건너뛴다.
2. **합성 단계** — 최종 1080x1920 으로 맞춘다.

없던 디테일이 생기지는 않는다. 1080p 로 올리기 위한 규격 맞추기에 가깝다.

## 소리

0.9.x 는 **소리를 만들지 않는다.** `music/` 의 곡을 테마에 맞춰 깐다
(`output.audio: auto`). 곡이 하나도 없으면 무음으로 나가고 그 사실을 알려준다 —
소리가 없으면 끝까지 보지 않는다. `music/PROMPTS_SUNO.md` 에 곡 만드는 프롬프트가 있다.
