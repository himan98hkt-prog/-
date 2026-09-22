# 발표회 운영 화면 (프로그램 대시보드)

지시서 모듈 ⑤-3 이 "**원장님이 진짜 돈 낼 기능**"이라고 한 큐 리스트와,
⑤-2 가 "**이 버튼 하나가 원장님 마음을 산다**"고 한 페이드아웃을 실제로 만든 화면.

```bash
cd mr && python3 seed_catalog.py && python3 serve.py
# http://127.0.0.1:8765/static/program.html
```

## 무엇이 되는가

| 지시서 모듈 ⑤ | 구현 |
|---|---|
| ⑤-3 프로그램 큐 리스트 — 순서대로 세팅, 다음 곡 자동 대기 | 큐 전체가 보이고 현재 순서가 강조된다. 곡이 끝나면 다음 순서로 **대기**만 한다 |
| ⑤-2 페이드아웃 버튼 (크게) — 3초 안에 반주만 사라짐 | 큰 버튼. **실측 3.04초** (지시서 11장 검증 기준 통과) |
| 원장님은 재생만 누름 | 큰 재생 버튼 하나. 스페이스바로도 된다 |
| ⑤-1 오프라인 | 무대 장면이 CSS·SVG 라 이미지가 없어도, 네트워크가 죽어도 화면은 뜬다 |

그 외: 다음 곡 미리 받아 두기(무대에서 안 기다리게), 줄 클릭으로 순서 이동,
키보드(스페이스=재생/정지, Esc=페이드아웃, ←→=순서 이동),
카탈로그에 없는 곡·화성 미확인 곡 경고 표시.

**소리는 진짜다.** 카탈로그의 MR(반주만)을 그대로 튼다. 데모용 가짜 재생이 아니다.

## 화면

무대를 위에 크게 두고, 프로그램 목록을 아래에 둔다. 무대 오른쪽에 조명 기둥과
그랜드 피아노, 왼쪽에 지금 연주할 아이의 이름.

```
┌──────────────────────────────────────────────┐
│  2026 겨울 발표회 · 12-20 · 아트홀 · 10곡 30분  │
│  ① 1번째                            ╱│╲      │
│  김지우                            ╱ │ ╲     │
│  작은 왈츠 (C장조)                  피아노     │
│  ♩=84 · 동화풍 · 보통 · 카운트인 1마디         │
│  [▶ 재생] [반주 페이드아웃] [◀][▶]            │
│  0:00 ──────────────────── 0:26              │
│  다음 ▸ 박서준 — 3/8박 작은 노래               │
├──────────────────────────────────────────────┤
│  프로그램                                     │
│  1 ▸ 김지우   작은 왈츠 · 리허설 완료   ♩=84   │
│  2   박서준   3/8박 작은 노래          ♩=88   │
└──────────────────────────────────────────────┘
```

### 무대는 왜 CSS 로 그렸나

지시서 ⑤-1 이 "연주홀 와이파이는 믿을 수 없다. **타협 불가**"라고 못 박았다.
배경이 이미지 파일에 의존하면 그 파일이 안 뜨는 날 화면이 무너진다.

그래서 무대(커튼·조명 기둥·바닥 반사·떠다니는 먼지·그랜드 피아노 실루엣)는 전부
CSS 와 인라인 SVG 다. 파일 0바이트로 동작한다. 애니메이션도 CSS 라
`prefers-reduced-motion` 을 존중한다.

이미지·영상을 넣으면 그 위에 얹힌다. `/api/stage` 가 무엇이 있는지 알려 주므로
없는 파일을 찔러 보며 콘솔에 404 를 남기지 않는다.

## Higgsfield 로 만든 배경

무대 배경용으로 이미지 3장과 영상 1편을 생성했다.

| 용도 | 모델 | 비용 |
|---|---|---|
| 무대 배경 (연주홀 전경) | `gpt_image_2_5` 1344×752 | 1 크레딧 |
| 건반 클로즈업 | `gpt_image_2_5` 1344×752 | 1 |
| 벨벳 커튼 텍스처 | `gpt_image_2_5` 1344×752 | 1 |
| 무대 배경 영상 (먼지·조명 흔들림) | `kling3_0_turbo` 1080p 5초 | 10 |

프롬프트 (그대로 다시 쓸 수 있게):

> **연주홀 전경** — Elegant empty concert hall interior of a fine arts center.
> A polished black grand piano stands alone at center stage under a single warm
> golden spotlight. Deep burgundy velvet curtains frame the stage, rows of empty
> seats fade into darkness. Soft volumetric light beams, faint dust motes drifting
> in the air. Cinematic, luxurious, restrained. Warm amber highlights against deep
> navy and charcoal shadows. Photorealistic high-end architectural photography,
> wide establishing shot, shallow depth of field, no people, no text.

> **건반 클로즈업** — Extreme close-up of a grand piano keyboard on a darkened
> concert stage. Warm golden stage light rakes low across the white and black keys,
> catching the polished lacquer. Background dissolves into soft bokeh of distant
> amber stage lights. Deep navy and charcoal shadows, warm amber accents.
> Cinematic, luxurious, photorealistic, very shallow depth of field, no people, no text.

> **커튼 텍스처** — Abstract minimal texture of deep burgundy velvet theater curtain
> folds, lit from above by a soft warm golden gradient that falls off into near-black
> at the bottom. Elegant, understated, luxurious fabric detail. Cinematic moody
> lighting, photorealistic, no people, no text, no objects.

> **배경 영상** (연주홀 전경을 start_image 로) — Extremely slow, subtle ambient
> motion. Fine dust motes drift lazily through the warm golden spotlight beam above
> the grand piano. The stage light breathes almost imperceptibly. A barely
> perceptible slow camera push toward the piano. Nothing else moves. No cuts, no
> people, no text. Calm, luxurious, cinematic, seamless looping feel.

### 파일이 저장소에 없는 이유

**이 세션의 컨테이너는 조직 egress 정책상 해당 CDN(cloudfront)에 접근할 수 없다.**
프록시가 CONNECT 에 403 을 돌려준다. 정책 거부는 우회하지 않는 것이 원칙이라
파일을 받아 커밋하지 못했다.

내려받을 URL 과 명령은 `mr/server/static/img/README.md` 에 그대로 적어 두었다.
네트워크가 되는 곳에서 그 폴더에 넣으면 서버가 알아서 찾아 얹는다.
**넣지 않아도 화면은 지금 그대로 동작한다.**

## 데이터

`catalog.json` 의 `programs` 를 읽는다 (지시서 6장 발표회 프로그램 큐 그대로).
씨앗에 예시 프로그램이 하나 들어 있다 — 10곡, 약 30분, 실제 카탈로그 곡으로만.

```
GET /api/programs        프로그램 목록
GET /api/programs/{i}    큐 + 곡 제목·편성·템포까지 붙여서
GET /api/stage           무대 배경 파일이 있는지
```

곡의 음원은 기존 `GET /api/songs/{id}/audio?mix=mr` 을 그대로 쓴다.

## 아직 아닌 것

이 화면은 **3단계(플레이어 PWA)의 미리보기**다. 지시서 9장이 순서를 바꾸지 말라고
했으므로 3단계 본체는 시작하지 않았다. 아직 없는 것:

- 오프라인 재생 (서비스워커로 음원을 캐시) — ⑤-1 의 본체
- 집 연습 링크, 아이별 설정 저장, 템포 슬라이더·조옮김 실시간 변경 — ⑤-5·6·9·10
- 프로그램을 화면에서 편집하기 (지금은 `catalog.json` 에 넣는다)
