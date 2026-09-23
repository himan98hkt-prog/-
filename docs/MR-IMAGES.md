# 반주(MR) 화면에 넣을 이미지 — 자리와 프롬프트

화면이 왜 이렇게 생겼는지는 [MR-DESIGN.md](MR-DESIGN.md) 에 있습니다.

만들어 올리시면 바로 붙습니다. **지금 상태에서도 화면은 완성돼 있습니다** — 아래
이미지는 전부 *있으면 더 좋은 것*이고, 하나도 없어도 화면이 무너지지 않습니다.
그게 이 목록의 전제입니다.

---

## 먼저: 어디에 넣을 수 있고, 어디에 넣으면 안 되나

| 화면 | 이미지 | 왜 |
|---|---|---|
| **발표회 운영** (무대) | **넣어도 됩니다** | 서버에서 뜨고, 없으면 CSS 로 그린 무대가 그대로 나옵니다 |
| **카탈로그·화성확인·PDF올리기** | 넣어도 됩니다 | 우리가 쓰는 제작 도구. 온라인 전제 |
| **플레이어 곡목록·연주** | **조심** | 오프라인 꾸러미입니다 (지금 **172 KB** 전부) |
| 플레이어 배경 영상 | **안 됩니다** | ⑤-1 「오프라인은 타협 불가」. 영상 한 편이 꾸러미의 수십 배입니다 |

플레이어에 이미지를 넣으신다면 **한 장에 40 KB 이하**로, 그리고 **없어도 되는 자리**에만
넣습니다. 지금 디자인이 이미지를 안 쓰는 이유가 이것입니다 — 연주홀 와이파이는 못
믿고, 비행기 모드에서도 똑같이 떠야 합니다.

> **영상은 발표회 운영 화면에만.** `img/hall.mp4` 가 있으면 무대 배경으로 얹히고,
> 없으면 CSS 무대가 나옵니다. 이 화면은 서버에서 뜨는 화면이라 용량이 자유롭습니다.

---

## 1. 발표회 무대 배경 (제일 값어치가 큽니다)

**넣는 곳** `mr/server/static/img/hall.jpg` · 영상이면 `img/hall.mp4`
**크기** 2400×1350 (16:9) · JPEG 품질 80 · **400 KB 이하**
**주의** 화면 아래쪽 40%에 글자(다음 순서·곡명)가 올라갑니다. **아래쪽은 어둡고 조용하게.**

```
empty concert hall stage viewed from the audience, grand piano at center,
deep crimson velvet curtains drawn to the sides, warm amber spotlight pooling
on the piano from above, dark polished wood floor, rows of seats fading into
darkness in the foreground, volumetric light haze, cinematic, shallow depth of
field, moody low-key lighting, bottom third very dark and uncluttered,
no people, no text --ar 16:9 --style raw --v 6
```

**변주** — 학원 분위기에 맞춰 고르세요.
- 따뜻하고 아담하게: `small recital hall` `wooden walls` `intimate`
- 크고 격식 있게: `large auditorium` `balcony seats` `ornate proscenium arch`
- 현대적으로: `modern minimalist concert hall` `clean architectural lines`

> **꼭 지킬 것: 사람 없이.** 아이 얼굴이 들어간 AI 이미지는 학부모에게 보이는
> 화면에 쓸 수 없습니다. 그리고 무대에 올라가는 건 그 학원 아이들이지 모델이 아닙니다.

---

## 2. 무대 바닥 반사 / 전경 (있으면 깊이가 살아납니다)

**넣는 곳** `mr/server/static/img/floor.png` · **투명 PNG**
**크기** 2400×600 · 200 KB 이하

```
polished dark wood stage floor with soft warm reflections, seen at a low
grazing angle, transparent background at the top edge fading to solid at the
bottom, subtle amber light reflection streaks, no objects, no people,
photographic, PNG with alpha --ar 4:1 --style raw --v 6
```

---

## 3. 앱 아이콘 (홈 화면에 깔릴 때)

**넣는 곳** `mr/server/static/player/icon.svg` 를 대신할 `icon-512.png`
**크기** 512×512 · 투명 배경 아님(홈 화면 아이콘은 꽉 찬 사각형)

```
app icon, minimal flat symbol of a grand piano silhouette merged with three
rising sound waves, warm amber and deep wine gradient on near-black background,
centered, thick confident strokes, no text, no letters, generous padding,
iOS app icon style, flat vector look --ar 1:1 --v 6
```

> 지금은 SVG 아이콘이 들어 있어 **비워 두셔도 됩니다.** 벡터라 어느 크기에서도
> 안 깨지고 1 KB 도 안 됩니다. 사진풍 아이콘을 원하실 때만 바꾸세요.

---

## 4. 편성 일곱 가지 표지

**만들어 두었습니다 — 일곱 장 다 SVG 입니다.** 아래 「만들어 둔 것」에서 받으세요.

> 전에 여기 「각 96×96 WebP 로 뽑아 일곱 장 합쳐 120 KB 이하」라고 적어 두었는데,
> **벡터로 나와서 그 걱정이 없어졌습니다.** 몇 KB짜리 SVG 라 오프라인 꾸러미에
> 부담이 안 됩니다. 어느 크기에서도 안 깨지는 것은 덤입니다.

**넣는 곳** `mr/server/static/player/img/style-<키>.svg`

| 편성 | **키 (파일 이름)** | 그린 것 |
|---|---|---|
| 현악 앙상블 | `strings` | 바이올린과 첼로 |
| 실내악 | `chamber` | 의자 넷과 보면대 |
| 풀 오케스트라 | `orchestra` | 부채꼴 좌석과 지휘대 |
| 동화풍 | **`fairytale`** | 첼레스타와 하프, 작은 별 하나 |
| 따뜻한 소편성 | `warm` | 통기타와 플루트 |
| 행진곡풍 | `march` | 작은북과 트럼펫 |
| 팝·재즈풍 | `pop` | 일렉 피아노 건반과 비브라폰 |

> **키를 한 번 틀리게 적어 두었습니다.** 동화풍은 `fairy` 가 아니라 **`fairytale`**
> 입니다(`piano_mr/orchestration.py` 의 `STYLES`). 파일 이름이 키와 안 맞으면 조용히
> 안 뜹니다 — 고장 표시도 없이 그냥 안 보입니다.

### 화면에는 제가 그린 그림이 붙어 있습니다

**플레이어의 편성 고르는 곳은 이미 그림 단추로 바뀌었습니다** — 다만 붙은 그림은
힉스필드 것이 아니라 **제가 SVG 로 직접 그린 일곱 개**이고, 파일이 아니라 `js/app.js`
안에 들어 있습니다. 이유는 하나입니다.

> 파일 일곱 개로 두면 `sw.js` 의 `SHELL_FILES` 에도 일곱 줄이 붙습니다. 그중 하나라도
> 빠지면 `cache.addAll` 이 **전부 거부해 서비스워커 설치가 통째로 실패합니다** —
> 온라인에서는 멀쩡하고 **비행기 모드에서만** 플레이어가 안 뜹니다. 일곱 개 합쳐
> 1.6 KB 라 파일로 나눌 이유가 없었습니다. (`tests/test_player_wiring.py` 가 이제
> 이 실수를 막습니다.)

힉스필드 그림으로 바꾸고 싶으시면 **받아서 내용을 `STYLE_ICON` 에 옮겨 넣으면**
됩니다 — 그러면 그것도 파일이 아니라 코드 안에 들어가므로 위 문제가 안 생깁니다.
말씀해 주시면 제가 합니다.

**곡 목록의 조성 배지(`C` `E♭`)는 그대로 두었습니다.** 편성은 재생할 때마다 고르는
값이라 목록에 찍히는 것은 「기본 편성」일 뿐입니다. 조성은 곡의 성질이라 안 바뀌고요 —
아이에게 곡을 고를 때 쓸모 있는 쪽은 조성입니다.

남은 쓸모는 **마케팅 상세페이지**입니다. 일곱 편성이 있다는 것을 글로 설명하는 것보다
빠릅니다.

## 5. 마케팅 상세페이지용 (화면 안이 아니라 판매용)

이건 용량 제한이 없습니다. 학원에 보여 드릴 자료입니다.

**히어로**
```
a child's hands on piano keys in a warm practice room, a tablet propped on the
music stand showing a dark app screen with amber accents, late afternoon light
through a window, shallow depth of field, warm and calm, documentary
photography style, no faces visible, no text on screen --ar 16:9 --style raw --v 6
```

**발표회 장면**
```
recital hall from the wings, grand piano under a single warm spotlight,
audience silhouettes out of focus in the dark, a music stand with a tablet
glowing softly, cinematic, warm amber and deep wine palette, no faces,
no text --ar 3:2 --style raw --v 6
```

---

## 들어왔습니다 — 무엇이 붙었고 무엇이 안 붙었나

2026-09-23, 원장님이 19개를 통째로 올려 주셨습니다. 아래가 그중 **실제로 쓰인 것**과
**안 쓴 것, 그리고 왜 안 썼는지**입니다.

### 붙인 것

| 파일 | 무엇 | 크기 |
|---|---|---|
| `mr/server/static/img/hall.mp4` | 무대 배경 영상 — 아담한 리사이틀홀 (Kling v3.0 pro) | 1904×1088 · 10초 · 무음 · 1.9 MB |
| `mr/server/static/img/hall.jpg` | 같은 홀의 정지 사진 (영상이 안 뜰 때) | 2400×1350 · 168 KB |
| `mr/server/static/img/keys.jpg` | 건반 클로즈업 (예비) | 1600×895 · 101 KB |
| `mr/server/static/img/curtain.jpg` | 벨벳 커튼 (예비) | 1600×895 · 96 KB |
| `mr/server/static/player/icon.svg` | 앱 아이콘 | **SVG** · 10.9 KB |

영상과 사진은 **같은 홀**로 맞췄습니다. 영상이 안 뜨는 기기에서 사진으로 되돌아갈 때
전혀 다른 홀이 나오면 안 됩니다.

### 안 붙인 것 — 편성 일곱 표지

**26px 에서 뭉개집니다.** 78px 로 보면 바이올린·의자·하프까지 살아 있는 훌륭한 선화인데,
실제로 쓰는 크기에서는 얼룩이 됩니다. 세밀한 선화가 아이콘 크기를 못 버팁니다.

편성 단추에는 **26px 용으로 그린 것**이 붙어 있습니다(`js/app.js` 의 `STYLE_ICON`,
일곱 개 합쳐 1.6 KB). 받으신 일곱 장은 **마케팅 상세페이지**에서 크게 쓰시면 제값을 합니다.

### 안 붙인 것 — 무대 그림 2안과 마케팅 2장

무대는 **셋 중 하나만** 씁니다. 「대강당」안도 좋으니 바꾸고 싶으시면 말씀해 주세요 —
`hall.jpg`/`hall.mp4` 를 대강당 쪽으로 갈아 끼우면 됩니다. 「현대 미니멀」안은 프롬프트가
안 먹어(내장 로케이션으로 그리는 모델) 피아노가 작고 구도가 밋밋해 권하지 않습니다.

마케팅 2장은 저장소에 넣을 것이 아니라 **상세페이지 만드실 때** 쓰시면 됩니다.

### 손본 것

- **C2PA 이력 블록을 걷어냈습니다.** SVG 들이 23~28 KB 였는데 화면에 안 그려지는
  생성 이력 메타데이터가 90%였습니다(8장 합쳐 213 → 74.5 KB). 어느 모델로 만들었는지는
  이 문서가 기록입니다.
- **사진은 줄였습니다.** 무대 그림 원본이 2688×1536 · 4.7 MB 라 2400×1350 · JPEG 80 으로.

### 이 과정에서 찾은 버그 둘

| 버그 | 왜 아무도 몰랐나 |
|---|---|
| `<video preload="none">` 이라 `loadeddata` 가 영영 안 와서 **영상이 붙어도 투명한 채로** 남았다 | **영상 파일이 없어서 이 경로를 아무도 못 돌려 봤다** |
| 사진을 얹으면 그려 둔 무대가 그대로 남아 **피아노가 둘, 조명이 둘, 커튼이 둘**이 됐다 | 〃 |

둘 다 고쳤습니다. 이제 사진·영상이 **실제로 떴을 때만** 그린 무대가 물러나고, 못 뜨면
CSS 무대로 되돌아갑니다 — 그게 이 화면의 마지막 방어선입니다.

### 바꾸고 싶으시면

무대를 대강당으로 바꾸거나 아이콘을 되돌리는 건 파일 하나 갈아 끼우는 일입니다.
원본 19개는 원장님 힉스필드 계정에 그대로 있고, 어떤 파일이 무엇인지는 위 표와
[MR-DASHBOARD.md](MR-DASHBOARD.md)(09-22 배치 프롬프트)에 적혀 있습니다.

## 넣으신 뒤

```bash
cd mr && python3 tools/player_check.py     # 11항목 (오프라인 재생이 그대로인지)
python3 catalog_cli.py package /tmp/pkg    # 꾸러미 용량이 얼마나 늘었는지
```

꾸러미가 **300 KB를 넘어가면** 다시 보셔야 합니다. 원장님 학원의 인터넷이 느릴 수도,
학부모 휴대폰 데이터가 아까울 수도 있습니다.
