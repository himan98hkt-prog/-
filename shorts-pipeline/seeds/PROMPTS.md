# 미드저니 시드 프롬프트 팩 — AI DEOKHU

레퍼런스 계정(@odysseyml · @cyborg.digitalart · @hellopersonality · @nexyra.visuals)
실측 분석에서 뽑은 조건에 맞춘 **판타지 중심** 프롬프트입니다.

---

## 절대 조건 3가지

판타지든 아니든 이 셋은 지켜야 합니다. 이 파이프라인은 **이미지에서 앞으로
나아가는 영상**을 만들기 때문입니다.

| 조건 | 이유 |
|---|---|
| **앞으로 갈 길이 화면 안에** | 소실점이 있어야 모델이 "전진"을 이해합니다. 다리·계단·회랑·강·궤도·구름길 무엇이든 좋습니다 |
| **어둡고 채도 높게** | 밝고 평평하면 영상이 밋밋합니다. 밤·여명·마법광·발광생물이 잘 먹힙니다 |
| **사람은 뒷모습만** | 얼굴이 체이닝 2~3회차에서 가장 먼저 무너집니다 |

> 판타지에서 가장 흔한 실수는 **멋진 풍경을 정면으로 놓는 것**입니다.
> 성이 멀리 보이는 그림보다, **성으로 이어지는 다리 위에 선 시점**이 훨씬 좋습니다.

## 공통 접미사

```
--ar 9:16 --style raw
```

미드저니 버전 플래그는 평소 쓰시던 것을 붙이면 됩니다.
`--style raw` 는 과한 연출을 줄여 영상 변환에 유리합니다.

---

## 조립 공식 — 무한히 만들어 쓰는 법

고정된 목록보다 이 표를 조합하는 편이 훨씬 많은 그림을 뽑습니다.

```
[시점] + [길] + [세계] + [광원] + [분위기] + --ar 9:16 --style raw
```

| 칸 | 고를 것 |
|---|---|
| **시점** | first person view walking / POV riding / low aerial flying through / seen from behind a lone traveler |
| **길** | stone bridge · spiral staircase · cathedral corridor · glowing river · root tunnel · cloud path · rope bridge · aqueduct · crystal ravine |
| **세계** | floating islands · sunken temple · crystal cavern · spirit forest · sky kingdom · ancient library · frozen palace · mushroom valley |
| **광원** | bioluminescent glow · floating lanterns · god rays through mist · aurora · twin moons · molten veins · will-o-wisps |
| **분위기** | ethereal · haunting · serene · epic scale · dreamlike · ominous |

예:
```
first person view walking across a stone bridge toward floating islands,
will-o-wisps drifting alongside, twin moons overhead, ethereal,
epic scale, cinematic --ar 9:16 --style raw
```

---

## 1. 부유섬 · 천공 세계

```
first person view standing on a rope bridge between floating islands,
waterfalls pouring off the edges into an endless cloud sea below,
twin moons in a violet sky, glowing lanterns strung along the ropes,
epic scale, cinematic --ar 9:16 --style raw
```

```
low aerial flight through a canyon of floating rock islands connected by
ancient stone arches, waterfalls falling into nothing, golden hour light
piercing the mist, epic fantasy, cinematic --ar 9:16 --style raw
```

```
POV walking up a staircase of floating stone steps rising into the clouds,
each step glowing faintly as it is stepped on, distant sky temple at the
top, dawn light, ethereal, cinematic --ar 9:16 --style raw
```

```
sky kingdom at night seen from a windswept bridge, spires wrapped in
glowing runes, airships with lantern lights drifting between towers,
deep indigo sky, cinematic --ar 9:16 --style raw
```

## 2. 정령의 숲 · 발광 자연

```
first person view walking a narrow path through a spirit forest at night,
enormous glowing mushrooms on both sides, blue will-o-wisps drifting in
the air, ancient roots arching overhead, ethereal, cinematic
--ar 9:16 --style raw
```

```
POV walking through a tunnel formed by giant tree roots, bioluminescent
moss lighting the walls in teal, a glowing clearing visible far ahead,
volumetric mist, cinematic --ar 9:16 --style raw
```

```
a narrow wooden walkway over a glowing swamp at night, luminescent lilies
below, fireflies swarming, twisted trees draped in moss, ominous but
beautiful, cinematic --ar 9:16 --style raw
```

```
path of fallen golden leaves leading deep into an autumn forest at dusk,
spirit foxes with glowing tails watching from the trees, lanterns hanging
from branches, dreamlike, cinematic --ar 9:16 --style raw
```

## 3. 고대 유적 · 신전

```
first person view descending a vast temple staircase lit by braziers,
enormous carved stone guardians lining both sides, glowing runes on the
steps, dust in the light shafts, epic scale, cinematic
--ar 9:16 --style raw
```

```
POV walking down an endless cathedral corridor, impossibly tall stained
glass windows casting colored light across the floor, floating candles,
volumetric god rays, haunting, cinematic --ar 9:16 --style raw
```

```
sunken temple corridor half-flooded with clear turquoise water, sunlight
shafts breaking through the collapsed ceiling, carved pillars receding
into the distance, serene, cinematic --ar 9:16 --style raw
```

```
a lone traveler in a red cloak seen from behind, walking a cracked stone
causeway toward a colossal ruined gate, sandstorm haze, setting sun
behind the gate, epic scale, cinematic --ar 9:16 --style raw
```

## 4. 크리스탈 동굴 · 지하 왕국

```
first person view walking through a crystal cavern, enormous violet
crystals glowing from within, an underground river running alongside the
path, reflections everywhere, ethereal, cinematic --ar 9:16 --style raw
```

```
POV on a boat drifting down a subterranean river, cavern ceiling covered
in glowing blue larvae like a starfield, stalactites, silent and vast,
dreamlike, cinematic --ar 9:16 --style raw
```

```
descending a spiral staircase carved into a colossal cavern wall, a
dwarven city of molten forges glowing far below, orange light rising
through the dark, epic scale, cinematic --ar 9:16 --style raw
```

## 5. 얼음 왕국 · 오로라

```
first person view walking a frozen river between towering ice cliffs,
green aurora rippling overhead, the ice glowing faintly from beneath,
a distant crystal palace ahead, serene, cinematic --ar 9:16 --style raw
```

```
POV crossing a bridge of ice toward a frozen palace, snow drifting
sideways, blue and violet aurora, frozen waterfalls on either side,
ethereal, cinematic --ar 9:16 --style raw
```

```
sled POV racing across a moonlit snowfield toward distant glowing pines,
northern lights overhead, snow spray, deep blue night, cinematic
--ar 9:16 --style raw
```

## 6. 마법 도시 · 마도 문명

```
first person view walking a canal street in a floating magic city at
night, glowing paper lanterns strung overhead, arcane shop signs, boats
drifting on luminous water, dreamlike, cinematic --ar 9:16 --style raw
```

```
POV climbing a narrow alley staircase in a wizard city, crooked towers
leaning overhead, glowing windows, a giant clocktower ahead, blue hour,
cinematic --ar 9:16 --style raw
```

```
low aerial flight down a grand avenue of a fantasy capital at festival
night, thousands of floating lanterns rising, banners, castle at the far
end, warm gold and deep blue, epic scale, cinematic --ar 9:16 --style raw
```

## 7. 용 · 비행

```
POV riding on the back of a dragon flying low through a mountain valley
at sunset, wings visible at the edges of frame, clouds rushing past,
distant peaks, epic scale, cinematic --ar 9:16 --style raw
```

```
first person view from a small airship deck flying into a storm of
floating islands, lightning between the clouds, rigging in frame,
dramatic, cinematic --ar 9:16 --style raw
```

```
POV on the back of a giant white bird gliding above an endless cloud sea
at dawn, first light hitting the clouds gold, serene, cinematic
--ar 9:16 --style raw
```

## 8. 심해 · 수중 왕국

```
first person view swimming through a sunken city street, coral growing
over marble columns, bioluminescent fish swirling, shafts of light from
far above, ethereal, cinematic --ar 9:16 --style raw
```

```
POV descending through a deep ocean trench past a glowing ancient
structure, jellyfish drifting, deep indigo water, volumetric light,
haunting, cinematic --ar 9:16 --style raw
```

```
walking a glass tunnel through an underwater kingdom at night,
luminescent coral towers outside, schools of glowing fish, serene,
cinematic --ar 9:16 --style raw
```

## 9. 거대 존재 · 초현실 스케일

```
first person view walking along the spine of a colossal sleeping creature
overgrown with forest, its scales like hills, mist below, dawn light,
epic scale, cinematic --ar 9:16 --style raw
```

```
POV walking a path across the palm of a titanic stone statue lying in a
valley, its fingers rising like towers, wildflowers growing in the cracks,
golden hour, epic scale, cinematic --ar 9:16 --style raw
```

```
a lone figure seen from behind walking toward an impossibly large door
standing alone in a field of tall grass, light spilling from the gap,
night, dreamlike, cinematic --ar 9:16 --style raw
```

## 10. 마법 도서관 · 시계탑

```
first person view walking down an infinite library corridor, bookshelves
rising beyond sight, floating books drifting past, warm lamplight, dust
motes in the light shafts, dreamlike, cinematic --ar 9:16 --style raw
```

```
POV climbing the inside of a colossal clocktower, brass gears turning
around the staircase, moonlight through the clock face above,
cinematic --ar 9:16 --style raw
```

## 11. 영혼의 길 · 동양 판타지

```
first person view climbing endless stone steps lined with red torii
gates at night, paper lanterns glowing, spirit lights drifting between
the gates, mist, ethereal, cinematic --ar 9:16 --style raw
```

```
POV walking a mountain path toward a shrine at blue hour, stone
lanterns lighting the way, cherry petals in the wind, a giant moon
behind the shrine, serene, cinematic --ar 9:16 --style raw
```

```
a boat drifting down a river of stars between dark mountains, spirit
lights rising from the water, enormous constellations reflected,
dreamlike, cinematic --ar 9:16 --style raw
```

## 12. 애니메이션 톤 판타지
`montage` 모드와 잘 맞습니다. 부드러운 색감으로 뽑으세요.

```
hand-painted animation style, a girl seen from behind walking a country
path toward a floating castle in the sky, tall grass, cumulus clouds,
soft watercolor palette, warm afternoon light --ar 9:16 --style raw
```

```
hand-painted animation style, wooden boat drifting through a flooded
forest at dawn, glowing spirits in the water, soft mist, pastel sky
--ar 9:16 --style raw
```

```
hand-painted animation style, a small dragon and a child seen from
behind sitting on a cliff edge overlooking a valley of floating islands,
sunset, soft clouds --ar 9:16 --style raw
```

---

## 현실 기반 (변화를 주고 싶을 때)

판타지만 계속 올리면 피드가 단조로워집니다. 3~4편에 한 번씩 섞으세요.

```
first person view from inside a car at night, glowing red dashboard,
rain-streaked windshield, neon city lights streaking past, wet asphalt
reflections, deep blue and magenta, cinematic --ar 9:16 --style raw
```

```
POV riding a bicycle down a narrow alley at night, paper lanterns
overhead, wet stone path reflecting warm light, hydrangeas along the
wall, blue hour, cinematic --ar 9:16 --style raw
```

```
red mountain train descending a snowy track at night, glowing tail
lights, tunnel entrance ahead, village lights on the cliff above,
cinematic --ar 9:16 --style raw
```

---

## 피해야 할 것

| 넣지 말 것 | 이유 |
|---|---|
| 멀리 보이는 풍경 (정면 구도) | 갈 길이 없으면 카메라가 멈춥니다. **길 위에 서 있는 시점**으로 |
| 정면 얼굴 클로즈업 | 체이닝 2~3회차에서 가장 먼저 무너집니다 |
| 룬 문자 · 간판 · 책의 글자 | 영상으로 만들면 알아볼 수 없게 뭉개집니다 |
| 날개 편 용의 전신 | 형태가 크게 변형됩니다. **탑승 시점**이 안전합니다 |
| 군중 · 전투 장면 | 사람이 많을수록 붕괴가 눈에 띕니다 |
| 밝고 평평한 낮 | 판타지도 저조도가 훨씬 잘 나옵니다 |

---

## 작업 순서

1. 미드저니에서 뽑고 **U 버튼으로 업스케일**해 받습니다 (1080×1920 이상)
2. `seeds/` 에 넣습니다. 파일명은 영문/숫자로 짧게 (`floating_bridge_01.png`)
3. ```bash
   python main.py plan
   ```
4. 생성된 `.yaml` 에 제목과 훅을 채웁니다

```yaml
title:  구름 위 다리를 건너 성으로
hook:   이 다리 끝에 뭐가 있을까
prompt: forward motion across a stone bridge toward floating islands, no cut
```

`hook` 은 **인스타 피드에서 잘리지 않는 유일한 줄**입니다. 여기에 승부를 거세요.

### 판타지용 훅 예시
```
이 다리 끝에 뭐가 있을까
여긴 지도에 없는 곳입니다
문을 열면 안 되는 거였는데
30초 동안 다른 세계에 다녀오세요
끝까지 본 사람만 아는 장면
소리 켜고 보세요
돌아가는 길은 없었습니다
```

---

## 얼마나 만들어 둘까

하루 1편이면 **최소 7장**, 여유 있게 **14~20장**을 권합니다.
`seeds/` 가 비면 자동 업로드가 그날부터 멈춥니다.
`python main.py doctor` 가 남은 일수를 알려줍니다.

카테고리를 돌아가며 뽑으면 피드가 지루해지지 않습니다.
예: 부유섬 → 정령숲 → 현실(야간 드라이브) → 크리스탈 동굴 → 신전 → …
