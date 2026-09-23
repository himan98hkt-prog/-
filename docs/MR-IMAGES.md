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
| **플레이어 곡목록·연주** | **조심** | 오프라인 꾸러미입니다 (지금 **160 KB** 전부) |
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

## 4. 편성 일곱 가지 표지 (선택 — 곡 목록을 화려하게)

지금은 조성 머리글자(`C` `F` `G`)가 표지로 붙습니다. 편성 그림으로 바꾸면 목록이
훨씬 풍성해지지만, **곡 목록은 오프라인 꾸러미 안**이라 일곱 장을 합쳐 **120 KB 이하**로
잡아야 합니다. 각 96×96 WebP 로 뽑으면 맞습니다.

**넣는 곳** `mr/server/static/player/img/style-<이름>.webp`
(`strings` `chamber` `orchestra` `fairy` `warm` `march` `pop`)

```
minimal icon on dark near-black background, warm amber line art,
{악기}, centered, thick clean strokes, no text, no background detail,
flat vector look, generous padding --ar 1:1 --v 6
```

`{악기}` 자리에 넣을 것:

| 편성 | `{악기}` |
|---|---|
| 현악 앙상블 | `violin and cello silhouette` |
| 실내악 | `string quartet arrangement of four chairs and stands` |
| 풀 오케스트라 | `orchestra seating fan with conductor podium` |
| 동화풍 | `celesta and harp with a small star` |
| 따뜻한 소편성 | `acoustic guitar and soft flute` |
| 행진곡풍 | `snare drum and trumpet` |
| 팝·재즈풍 | `electric piano keys with a vibraphone bar` |

---

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

## 힉스필드로 만드신다면

제 컨테이너에서 힉스필드 CDN(`cdn.higgsfield.ai`)이 조직 egress 정책에 **막혀 있어
(403)** 제가 생성해도 결과 파일을 저장소에 넣지 못합니다. 그래서:

1. 제가 힉스필드로 생성 → **위젯에 뜬 것을 직접 내려받아** 주세요
2. 위 경로에 넣고 알려 주시면 제가 붙이고 검사까지 돌립니다

원하시면 위 프롬프트 그대로 힉스필드에 돌려 드립니다 — 크레딧이 소모되니
말씀해 주시면 시작합니다. 영상(무대 배경)은 힉스필드 쪽이 미드저니보다 낫습니다.

---

## 넣으신 뒤

```bash
cd mr && python3 tools/player_check.py     # 11항목 (오프라인 재생이 그대로인지)
python3 catalog_cli.py package /tmp/pkg    # 꾸러미 용량이 얼마나 늘었는지
```

꾸러미가 **300 KB를 넘어가면** 다시 보셔야 합니다. 원장님 학원의 인터넷이 느릴 수도,
학부모 휴대폰 데이터가 아까울 수도 있습니다.
