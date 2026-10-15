# 자전거 다운힐 팩 — 상쾌한 1인칭 내리막

`PROMPTS_HD.md` 는 어둡고 신비한 판타지입니다. 이 팩은 **정반대**입니다.
바람이 얼굴을 스치고, 눈앞이 탁 트이고, 보고 나면 기분이 좋아지는 쪽.

목표는 하나입니다 — **보는 사람이 지금 그 안장에 앉아 있다고 느끼게 하는 것.**

---

## 이 팩만의 규칙 세 가지

### ① 핸들바가 화면 아래에 있어야 1인칭입니다

"first person view" 라고만 쓰면 미드저니는 그냥 **낮은 각도 풍경**을 줍니다.
화면 **아래쪽 20%** 에 자전거의 일부가 있어야 진짜 내리막이 됩니다.

| 넣을 것 | 영어 |
|---|---|
| 핸들바 | `handlebars in foreground`, `handlebar grips in frame` |
| 앞바퀴 | `front wheel visible below`, `front tire on the road` |
| 그림자 | `rider's shadow cast ahead on the road` |

영상으로 바꿀 때 이게 결정적입니다. **고정된 앞쪽 물체가 있어야**
모델이 "카메라가 앞으로 간다"를 이해합니다. 없으면 배경만 확대됩니다.

### ② 길이 아래로 굽어 사라져야 합니다

평지 직선 도로는 30초가 지루합니다. **굽이쳐 내려가다 시야에서 사라지는 길**을
넣으면 "저 모퉁이 너머에 뭐가 있지?" 가 생겨서 끝까지 봅니다.

```
winding down out of sight · sweeping curve ahead · the road dropping away below
```

### ③ 밝게 가되, 평평하게 가지 마세요

기분 좋은 장면을 만들려다 **밝고 평평한** 사진이 되면 영상이 밋밋합니다.
밝기를 올리는 대신 **빛의 방향**을 지정하세요. 그림자가 길어야 입체가 삽니다.

> `golden hour` · `low sun backlight` · `god rays through cloud` ·
> `long shadows` · `sunbeams flickering through trees`

---

## 공통 접미사

```
--ar 9:16 --style raw
```

**HD로 뽑는 법**: 4장 중 마음에 드는 것의 **U 버튼** → **Upscale (Subtle)**.
가로가 약 1600px 이 됩니다. Creative 는 없던 디테일을 지어내니 쓰지 마세요.

> ⚠️ 첫 줄을 그대로 두세요. 작업실이 **파일 이름**을 읽어 테마·제목·훅을
> 자동으로 붙입니다. 첫 줄의 단어를 바꾸면 제목이 엉뚱해집니다.
> 뒷줄은 마음껏 고쳐도 됩니다.

---

# 1. 알프스 고갯길

```
first person view cycling down a switchback mountain road at golden hour, handlebars
in the lower frame, hairpin turns stacked below winding out of sight, alpine meadows
on both sides, snow capped ridges on the horizon, long shadows, crisp clean air,
exhilarating, cinematic
```

# 2. 절벽 해안 도로

```
first person view coasting downhill along a cliff road above the sea, sunlight shafts
breaking through cloud onto the water, guardrail posts flicking past on the right,
the road curving down toward a distant white beach, turquoise ocean far below,
open and uplifting, cinematic
```

# 3. 포도밭 언덕

```
first person view riding downhill through rolling vineyard hills at dawn, front wheel
and handlebars in frame, neat green rows sweeping past on both sides, morning haze
sitting in the valley below, a small stone village further down the slope,
warm low sun, peaceful, cinematic
```

# 4. 계단식 논

```
first person view cycling downhill through green paddy terraces in morning mist
handlebars in the lower frame, mirrored water steps falling away layer by layer,
a narrow dirt track winding between them, distant blue mountains, soft light,
fresh and calm, cinematic
```

# 5. 라벤더 꽃밭

```
first person view coasting downhill into an endless lavender field, handlebar grips
in foreground, purple rows converging toward the horizon, a lone tree at the bottom
of the slope, bees and drifting pollen catching the light, huge open sky,
bright and joyful, cinematic
```

# 6. 차밭

```
first person view riding downhill between rolling tea plantation rows at sunset,
handlebars in frame, curved green hedges rippling away in every direction,
a dirt path dropping toward a tea house below, low orange sun raking across the rows,
warm, serene, cinematic
```

# 7. 피오르 절벽 길

```
first person view cycling downhill on a road above a deep fjord, waterfalls opposite
pouring down sheer green walls, handlebars in the lower frame, dark still water far
below, the road switching back toward a tiny red cabin at the shoreline,
cool clear light, awe, cinematic
```

# 8. 붉은 사막 메사

```
first person view coasting downhill on a desert road below red mesa cliffs, first light
striking the rock faces orange, handlebars and rider's shadow stretched ahead on the
asphalt, empty road running straight then curving out of sight, huge pale blue sky,
vast and free, cinematic
```

# 9. 호숫가 내리막

```
first person view cycling downhill to a lakeside road, snow capped peaks reflected
perfectly in the still water ahead, handlebars in frame, pine trees flicking past
on the left, the road easing down to the water's edge, clean cold morning light,
refreshing, cinematic
```

# 10. 고원 들판

```
first person view coasting downhill across an open highland plateau, wildflowers
scattered through the grass on both sides, handlebars in the lower frame, cloud
shadows racing across the hills, a single ribbon of road running far into the
distance, big wind, uplifting, cinematic
```

# 11. 초록 협곡

```
first person view cycling downhill into a lush green valley, waterfalls on both walls
catching the sun, handlebars in frame, the road descending in long sweeping curves,
mist rising off the river at the bottom, deep greens against bright sky,
alive and fresh, cinematic
```

# 12. 자작나무 숲길

```
first person view coasting downhill through a bright birch forest, sunbeams flickering
between the white trunks, handlebars in the lower frame, the track dropping away and
curving out of sight, leaves spinning up in the slipstream, dappled light,
light-hearted, cinematic
```

---

## 조립해서 더 만들기

같은 틀에 칸만 바꾸면 얼마든지 늘릴 수 있습니다.

```
"first person view" + [내리막 동사] [풍경], [빛],
handlebars in frame, [양옆에 흐르는 것], [저 아래 목적지], [분위기], cinematic
```

| 칸 | 고를 것 |
|---|---|
| **내리막 동사** | cycling downhill · coasting downhill · riding downhill · cycling down a switchback |
| **풍경** | mountain road · cliff road · vineyard hills · paddy terraces · lavender field · tea plantation · fjord · desert road · lakeside road · highland plateau · green valley · birch forest |
| **빛** | golden hour · first light · sunset · sunlight shafts · sunbeams · morning mist |
| **양옆** | guardrail posts · pine trees · stone walls · tall grass · vineyard rows |
| **저 아래** | a village · a white beach · a tea house · a red cabin · the shoreline |
| **분위기** | exhilarating · uplifting · serene · refreshing · light-hearted · awe |

**첫 줄에는 반드시 내리막 동사 + 풍경**을 넣으세요. 그 두 개로 테마와 제목이 정해집니다.

---

## 피해야 할 단어

작업실은 파일 이름으로 테마를 고릅니다. 첫 줄에 아래 단어가 들어가면
자전거가 아니라 **다른 테마로 잘못 분류**됩니다.

| 넣지 말 것 | 잘못 잡히는 테마 |
|---|---|
| `temple` · `shrine` · `pillar` · `causeway` | 고대 유적 |
| `crystal` · `cavern` · `molten` | 크리스탈 동굴 |
| `frozen` · `snowy` · `glacier` · `aurora` | 얼음 왕국 |
| `dragon` · `wings` · `gliding` | 용 · 비행 |
| `highway` · `dashboard` · `cockpit` | 야간 드라이브 |
| `cherry` · `torii` | 영혼의 길 |
| `festival` · `arcane` · `wizard` | 마법 도시 |

`snow capped` 는 괜찮습니다. `snowy` 만 피하면 됩니다.

---

## 뽑고 나서 확인할 것

업로드 전에 이 셋만 보세요. 하나라도 아니면 버리는 게 낫습니다.

| 확인 | 아니면 |
|---|---|
| **화면 아래에 핸들바나 앞바퀴가 있나** | 없으면 그냥 풍경 줌이 됩니다 |
| **길이 아래로 굽어 사라지나** | 정면 벽·막다른 길이면 영상이 멈춥니다 |
| **그림자가 길게 있나** | 평평하면 밝기만 높고 밋밋합니다 |

사람 얼굴이 보이는 것도 빼세요. 체이닝 2~3회차에서 가장 먼저 무너집니다.

---

## 몇 장이나

하루 1편이니 **12장이면 12일**입니다. 판타지 팩(`PROMPTS_HD.md`)과 번갈아 올리면
피드가 한쪽으로 쏠리지 않습니다.

업로드는 작업실 **[1 · 이미지 고르기]** 탭에 끌어다 놓으면 됩니다.
테마(자전거 다운힐)·제목·훅·움직임 문구까지 자동으로 붙습니다.
