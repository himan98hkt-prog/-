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

## 힉스필드로 만들어 둔 것 — 받아서 넣기만 하면 됩니다

**제 컨테이너에서는 결과 파일을 못 받습니다.** 힉스필드 CDN(`cdn.higgsfield.ai`)도,
결과가 실제로 놓이는 CloudFront 주소(`d8j0ntlcm91z4.cloudfront.net`)도 조직 egress
정책에 **403 으로 막혀** 있습니다(프록시가 CONNECT 를 거부). 정책 거부는 우회하지
않는 것이 원칙이라 받아서 커밋하지 못했습니다. **네트워크가 되는 곳에서 받아 아래
자리에 넣어 주시면** 제가 붙이고 검사까지 돌립니다.

### 2026-09-23 — 무대 3안 · 영상 2편 · 아이콘 · 마케팅 2장

| 무엇 | 모델 | 크기 | 넣을 자리 |
|---|---|---|---|
| **영상** 무대 — 아담한 리사이틀홀 | Kling v3.0 pro | 1920×1080 · 10초 · 무음 | `mr/server/static/img/hall.mp4` |
| **영상** 무대 — 격식 있는 대강당 | Kling v3.0 pro | 1920×1080 · 10초 · 무음 | 〃 (둘 중 하나만) |
| 무대 — 아담한 리사이틀홀 | Recraft V4.1 2k | 2688×1536 | `mr/server/static/img/hall.jpg` |
| 무대 — 격식 있는 대강당 | Recraft V4.1 2k | 2688×1536 | 〃 (셋 중 하나만) |
| 무대 — 현대 미니멀 | Soul Location | 2048×1152 | 〃 |
| 앱 아이콘 (**SVG**) | Recraft V4.1 vector | 1024 | `mr/server/static/player/icon.svg` |
| 마케팅 히어로 — 연습실 | Recraft V4.1 2k | 2688×1536 | 화면 밖. 상세페이지용 |
| 마케팅 — 무대 옆에서 본 발표회 | Recraft V4.1 2k | 2560×1664 | 〃 |

```bash
cd mr/server/static/img
B=https://d8j0ntlcm91z4.cloudfront.net/user_3GQvWIPUy5cSGTXYMKA9lfLrTXy

# 영상 — 둘 중 하나를 hall.mp4 로
curl -o hall.mp4  "$B/hf_20260923_011640_7e8a3aed-7f83-49ee-be25-ac4bcee950de.mp4"  # 아담한 홀
curl -o hall.mp4  "$B/hf_20260923_011640_9c6fbb62-9e93-420c-acc4-f940783e2621.mp4"  # 대강당

# 그림 — 셋 중 하나를 hall.jpg 로 (아래 「줄이는 법」을 거쳐서)
curl -o hall-warm.png   "$B/hf_20260923_010336_c49f5ac8-f1ad-4bdc-ad94-18447e0566c6.png"
curl -o hall-grand.png  "$B/hf_20260923_010336_35b61730-378a-42e6-8ac3-8438a7f20bef.png"
curl -o hall-modern.png "$B/hf_20260923_010336_f6e2074c-74a4-4079-8a12-505ddf69840c.png"

# 앱 아이콘 (SVG — 그대로 덮어쓰면 됩니다)
curl -o ../player/icon.svg "$B/hf_20260923_010336_bc3c9c96-d48a-4e2a-8d1d-ba1ea5a50159.svg"

# 마케팅용 (저장소에 넣지 않아도 됩니다)
curl -o ~/mk-hero.png    "$B/hf_20260923_010336_1707dcde-81cb-48a2-a932-da18f4673f40.png"
curl -o ~/mk-recital.png "$B/hf_20260923_010336_8d4025e7-fd79-4661-95cd-135dcd129c28.png"
```

**영상 두 편은 시작 프레임과 끝 프레임을 같은 그림으로 잡았습니다.** 무대 화면이
`loop` 로 돌리므로 이음매가 보이면 안 됩니다. 소리는 껐습니다 — 그 화면에서 울려야
하는 것은 반주이고, `<video>` 도 `muted` 입니다.

> **「현대 미니멀」은 제 프롬프트가 안 먹었습니다.** Soul Location 은 프롬프트 대신
> 내장 로케이션(`Hartman Recital Hall`)으로 그립니다. 그림 자체는 쓸 만하지만
> 「아래쪽 40%를 비워 달라」는 주문이 안 들어갔으니, 아이 이름과 곡명이 올라가는
> 자리를 꼭 보고 고르세요. 나머지 둘은 그 주문이 들어간 프롬프트로 나왔습니다.

> **아이콘이 SVG 로 나온 것은 운이 좋았습니다.** 벡터라 어느 크기에서도 안 깨지고
> 몇 KB 밖에 안 됩니다 — 오프라인 꾸러미에 부담 없이 들어갑니다.

### 2026-09-22 — 먼저 만들어 둔 것

프롬프트는 [MR-DASHBOARD.md](MR-DASHBOARD.md) 에 그대로 적혀 있습니다.

| 무엇 | 모델 |
|---|---|
| 무대 배경 영상 | `kling3_0_turbo` 1080p · 5초 |
| 무대 전경 | `gpt_image_2_5` 1344×752 |
| 건반 클로즈업 | 〃 |
| 벨벳 커튼 텍스처 | 〃 |

```bash
cd mr/server/static/img
B=https://d8j0ntlcm91z4.cloudfront.net/user_3GQvWIPUy5cSGTXYMKA9lfLrTXy

curl -o hall.mp4    "$B/hf_20260922_032317_136d7d52-d9f4-4335-aa10-f223c779aad0.mp4"
curl -o hall.png    "$B/hf_20260922_032103_87ca9469-2d3e-4867-96e3-8705d307ef66.png"
curl -o keys.png    "$B/hf_20260922_032103_a23af0bd-16cf-4413-a5f1-aca5c958b4d1.png"
curl -o curtain.png "$B/hf_20260922_032103_e0875405-8534-474f-a9bf-6fe0c85f99d6.png"
```

> CDN 주소가 언제까지 살아 있을지 모릅니다. **오래 쓰실 것이면 받아서 저장소에
> 커밋해 두세요.**

### 받으신 그림을 줄이는 법

무대 배경 그림은 **그대로 넣으면 너무 큽니다.** 2400×1350 · JPEG 80 · 400 KB 이하로.

```bash
python3 - <<'EOF'
from PIL import Image
im = Image.open('hall-warm.png').convert('RGB')          # 고른 파일
im.resize((2400, 1350), Image.LANCZOS).save(
    'mr/server/static/img/hall.jpg', quality=80, optimize=True)
EOF
ls -l mr/server/static/img/hall.jpg      # 400 KB 이하인지
```

`keys.png` · `curtain.png` 도 같은 방식으로 `.jpg` 로 줄여 두시면 됩니다.

> **`hall.mp4` 가 있으면 `hall.jpg` 는 안 쓰입니다.** 서버가 영상을 먼저 봅니다.
> 둘 다 넣어 두시면 영상이 이깁니다 — 그림은 영상을 뺄 때를 위한 보험입니다.

### 아직 안 만든 것

말씀해 주시면 같은 방식으로 더 돌립니다.

- **편성 일곱 표지** — 일곱 장 합쳐 120 KB 이하라야 해서, 지금은 조성 머리글자를 씁니다
- **무대 바닥 반사** (`img/floor.png`) — 투명 PNG 가 필요한데 생성 모델이 알파를 잘 못 냅니다

## 넣으신 뒤

```bash
cd mr && python3 tools/player_check.py     # 11항목 (오프라인 재생이 그대로인지)
python3 catalog_cli.py package /tmp/pkg    # 꾸러미 용량이 얼마나 늘었는지
```

꾸러미가 **300 KB를 넘어가면** 다시 보셔야 합니다. 원장님 학원의 인터넷이 느릴 수도,
학부모 휴대폰 데이터가 아까울 수도 있습니다.
