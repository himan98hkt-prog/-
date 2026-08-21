# 미드저니 시드 프롬프트 팩 — AI DEOKHU

레퍼런스 계정(@odysseyml · @cyborg.digitalart · @hellopersonality · @nexyra.visuals)
실측 분석에서 뽑은 공통 조건에 맞춘 프롬프트입니다.

---

## 지켜야 할 3가지

이 파이프라인은 **이미지에서 앞으로 나아가는 영상**을 만듭니다.
그래서 시드 이미지가 이 조건을 만족해야 합니다.

1. **앞으로 갈 길이 화면 안에 있을 것** — 도로 · 터널 · 계단 · 강 · 복도 · 궤도
   소실점이 보이면 영상 모델이 "전진"을 훨씬 잘 이해합니다.
2. **어둡고 채도 높을 것** — 야경 · 네온 · 오로라 · 심해
   밝고 평평한 이미지는 영상으로 만들면 밋밋해집니다.
3. **사람은 뒷모습만** — 얼굴은 체이닝 2~3회차에서 가장 먼저 무너집니다.

## 공통 접미사

모든 프롬프트 끝에 붙이세요.

```
--ar 9:16 --style raw
```

미드저니 버전 플래그(`--v` 등)는 평소 쓰시던 것을 그대로 붙이면 됩니다.
`--style raw` 는 미드저니 특유의 과한 연출을 줄여 영상 변환에 유리합니다.

---

## 1. 야간 드라이브 POV
레퍼런스에서 가장 조회수가 높았던 계열입니다.

```
first person view from inside a car at night, glowing red dashboard,
hands on steering wheel, rain-streaked windshield, neon city lights
streaking past, wet asphalt reflections, deep blue and magenta,
cinematic, shallow depth of field --ar 9:16 --style raw
```

```
driver POV racing through a mountain tunnel at night, orange sodium
lights repeating into the distance, motion blur on tunnel walls,
vanishing point dead center, cinematic --ar 9:16 --style raw
```

```
cockpit view of a futuristic car on an elevated highway above a
cyberpunk city, holographic dashboard, skyscrapers with neon signage
on both sides, night, teal and hot pink --ar 9:16 --style raw
```

## 2. 자전거 · 도보 POV

```
first person view riding a bicycle down a narrow Japanese alley at
night, paper lanterns overhead, wet stone path reflecting warm light,
hydrangeas along the wall, cinematic, deep blue hour
--ar 9:16 --style raw
```

```
POV walking up a long stone staircase at night, red torii gates
receding into the distance, lanterns glowing, mist, moonlight,
cinematic depth --ar 9:16 --style raw
```

```
handlebar POV cycling through a forest path at dawn, sunbeams cutting
through mist between tall trees, golden light on the trail ahead,
cinematic --ar 9:16 --style raw
```

## 3. 터널 · 통로

```
looking down an endless neon tunnel, concentric rings of cyan and
magenta light receding to a bright vanishing point, wet reflective
floor, volumetric fog, cinematic --ar 9:16 --style raw
```

```
abandoned subway tunnel lit by flickering emergency lights,
tracks running into darkness, water on the floor reflecting,
eerie teal glow, cinematic --ar 9:16 --style raw
```

```
underwater glass tunnel through a coral reef at night, bioluminescent
fish surrounding, deep blue water, light shafts from above,
cinematic --ar 9:16 --style raw
```

## 4. 해안 · 바다
@nexyra.visuals · @caelum.waves 계열. 좋아요 전환이 높은 편입니다.

```
tropical beach at night, glowing bioluminescent waves on dark sand,
palm silhouettes, enormous milky way overhead, a wooden path leading
to the water, cinematic --ar 9:16 --style raw
```

```
long wooden pier stretching into a calm ocean at sunset, giant moon
rising on the horizon, orange and deep blue gradient sky, reflections
on water, cinematic --ar 9:16 --style raw
```

```
coastal cliff road at blue hour, guardrail curving along the edge,
ocean far below, distant lighthouse beam, dramatic clouds,
cinematic --ar 9:16 --style raw
```

## 5. 우주 · 행성

```
alien planet surface at night, glowing purple river winding toward
the horizon, enormous ringed planet in the sky, crystalline rock
formations, cinematic --ar 9:16 --style raw
```

```
view from a space station corridor looking out at Earth, long window
panels receding down the hall, blue planet glow, sci-fi interior,
cinematic --ar 9:16 --style raw
```

```
walking toward a glowing portal on a barren moon, stars filling the
sky, dust floating, rim light on the rocks, cinematic
--ar 9:16 --style raw
```

## 6. 도시 · 항공

```
aerial view flying low over a neon megacity at night, canyon of
skyscrapers below, holographic billboards, flying vehicles with light
trails, rain, cinematic --ar 9:16 --style raw
```

```
looking straight down a vertical city canyon at night, buildings
converging toward tiny street lights far below, vertigo perspective,
cinematic --ar 9:16 --style raw
```

```
snowy alpine village at night seen from a cable car, warm window
lights below, mountain peaks under stars, cinematic
--ar 9:16 --style raw
```

## 7. 기차 · 궤도
@odysseyml 의 대표 소재입니다.

```
red mountain train descending a snowy track at night, glowing tail
lights, tunnel entrance ahead, alpine village lights on the cliff
above, cinematic --ar 9:16 --style raw
```

```
railway tracks stretching into a foggy forest at dawn, rails catching
first light, mist between the trees, cinematic --ar 9:16 --style raw
```

## 8. 판타지 · 초현실

```
floating islands connected by glowing rope bridges, waterfalls
falling into clouds below, path leading forward across the bridges,
sunset, cinematic --ar 9:16 --style raw
```

```
enormous library corridor with impossibly tall bookshelves,
warm lamps receding into the distance, dust motes in light shafts,
cinematic --ar 9:16 --style raw
```

```
a lone figure in a red coat seen from behind, walking down a field
path toward a giant blood moon, tall grass, night, cinematic
--ar 9:16 --style raw
```

## 9. 애니메이션 톤
@cyborg.digitalart "Infinite peace" 계열. montage 모드와 잘 맞습니다.

```
anime style, a boy and girl seen from behind standing at a rural gas
station at golden hour, sunflowers, dramatic clouds, Makoto Shinkai
inspired lighting --ar 9:16 --style raw
```

```
anime style, girl with umbrella climbing stone steps lined with blue
hydrangeas, rain, torii gate at the top, lush green, cinematic
--ar 9:16 --style raw
```

```
anime style, small wooden boat on a still lake at sunrise, mountains
reflected, lily pads, warm light, seen from behind the boat
--ar 9:16 --style raw
```

---

## 피해야 할 것

| 넣지 말 것 | 이유 |
|---|---|
| 정면 얼굴 클로즈업 | 체이닝 2~3회차에서 가장 먼저 무너집니다 |
| 글자 · 간판 텍스트 | 영상으로 만들면 알아볼 수 없게 뭉개집니다 |
| 밝고 평평한 낮 풍경 | 영상으로 만들면 밋밋합니다 |
| 복잡한 군중 | 형태 붕괴가 눈에 띕니다 |
| 정사각 · 가로 구도 | 크롭하면 핵심이 잘립니다 |

---

## 작업 순서

1. 미드저니에서 위 프롬프트로 뽑고 **U 버튼으로 업스케일**해 받습니다
   (1080×1920 이상 권장)
2. `seeds/` 에 넣습니다. 파일명은 영문/숫자로 짧게 (`neon_alley_01.png`)
3. ```bash
   python main.py plan
   ```
   이미지마다 `.yaml` 양식이 생깁니다
4. 각 `.yaml` 에 `title` 과 `hook` 을 채웁니다

```yaml
title:  비 내리는 네온 골목을 끝없이 달리다
hook:   이 길 끝에 뭐가 있을까
prompt: forward motion through a rain-soaked neon alley, steady speed, no cut
```

`hook` 은 **인스타 피드에서 잘리지 않는 유일한 줄**입니다. 여기에 승부를 거세요.

### 훅 예시
```
이 길 끝에 뭐가 있을까
한 번도 안 멈추고 달렸습니다
여긴 존재하지 않는 곳입니다
소리 켜고 보세요
30초 동안 아무 생각 안 하기
끝까지 본 사람만 아는 장면
```

---

## 얼마나 만들어 둘까

하루 1편이면 **최소 7장**, 여유 있게 **14~20장**을 권합니다.
`seeds/` 가 비면 자동 업로드가 그날부터 멈춥니다.
`python main.py doctor` 가 남은 일수를 알려줍니다.
