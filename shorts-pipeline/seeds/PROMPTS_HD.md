# 고급 프롬프트 팩 — 1인칭 탐험

기본 팩(`PROMPTS.md`)보다 한 단계 위를 노립니다. 목표는 하나입니다 —
**보는 사람이 그 세계 안에 서 있다고 느끼게 하는 것.**

---

## 기본 팩과 무엇이 다른가

같은 판타지라도 이 셋을 넣으면 결과가 확연히 달라집니다.

### ① 내 몸이 화면에 있어야 1인칭이 됩니다

"first person view" 라고만 쓰면 미드저니는 그냥 **낮은 각도 풍경**을 줍니다.
화면 앞쪽에 **내 것**이 하나 있어야 진짜 1인칭이 됩니다.

| 넣을 것 | 예 |
|---|---|
| 손 | 등불을 든 손, 밧줄을 쥔 손, 지팡이 끝 |
| 탈것 | 뱃머리, 곤돌라 앞코, 용의 목덜미, 말 귀 |
| 옷 | 바람에 날리는 망토 자락, 후드 가장자리 |

영상으로 바꿀 때도 이게 큰 차이를 냅니다. **고정된 앞쪽 물체가 있으면
모델이 "카메라가 움직인다"를 이해**하고, 없으면 배경만 확대됩니다.

### ② 가까이·중간·멀리 — 세 겹을 지정하세요

앞으로 나아갈 때 세 겹이 **서로 다른 속도로 흘러가야** 진짜 이동으로 보입니다.
한 겹만 있으면 줌으로 보입니다.

```
near: 뱃머리와 물살    mid: 양옆 기둥들    far: 안개 속 거대 구조물
```

### ③ "와" 하는 순간을 심어두세요

**절반쯤 가려진 거대한 무엇**을 넣으세요. 카메라가 전진하면서 그게 드러납니다.
그 드러남이 시청자를 붙잡습니다.

> `half-hidden`, `emerging from mist`, `partially obscured`, `just coming into view`

---

## 공통 접미사

```
--ar 9:16 --style raw
```

**HD로 뽑는 법**: 4장이 나오면 마음에 드는 것의 **U 버튼** → **Upscale (Subtle)**.
가로가 약 1600px 이 됩니다. 기본 출력(816px)보다 영상 품질이 확실히 낫습니다.

> Creative 말고 **Subtle** 을 쓰세요. Creative 는 없던 디테일을 지어내서
> 원래 구도가 틀어지는 일이 있습니다.

---

# 1. 부유섬 · 천공

```
first person view crossing a rope bridge between floating islands, hands
gripping the frayed ropes in foreground, cloud sea far below, a vast ringed
landmass half-hidden in mist ahead, waterfalls pouring into empty sky,
twin moons, volumetric god rays, ethereal, epic scale, cinematic
```

```
first person view standing on the prow of a small sky ship, floating islands
drifting past on both sides, cloud sea glowing amber at dawn, an enormous
sky kingdom emerging from the clouds ahead, flocks of white birds,
soft haze, serene, epic scale, cinematic
```

# 2. 정령의 숲

```
first person view walking into a spirit forest at night, a paper lantern
held forward in one hand, glowing mushrooms lining the path, will-o-wisps
drifting between giant tree roots, a colossal ancient tree half-hidden in
fog ahead, fireflies, deep teal and gold, ethereal, haunting, cinematic
```

```
first person view pushing through tall glowing ferns in a spirit forest,
fingertips brushing the leaves in foreground, a river of soft light winding
deeper into the woods, enormous antlered silhouette barely visible in the
mist far ahead, fireflies swirling, dreamlike, cinematic
```

# 3. 고대 유적 · 신전

```
first person view walking down a vast temple causeway, a lit brazier passing
close on the left, rows of weathered stone pillars receding into haze,
a titanic seated statue partially obscured by mist at the end, dust motes
in shafts of light, ominous, epic scale, cinematic
```

```
first person view descending a temple staircase carved into a cliff, one
hand on the worn stone rail, braziers burning at each landing below,
a ruined gate opening onto a glowing valley just coming into view,
low sun, warm amber against deep blue shadow, epic scale, cinematic
```

# 4. 크리스탈 동굴

```
first person view wading through a shallow underground river in a crystal
cavern, lantern light rippling on the water in foreground, luminous blue
crystal formations rising on both sides, an immense cathedral-sized chamber
opening ahead, stalactites, bioluminescent glow, ethereal, cinematic
```

```
first person view climbing a narrow ledge inside a crystal cavern, gloved
hand on a glowing crystal outcrop, molten veins running through the rock
far below, a vast subterranean city half-hidden in steam ahead,
orange against violet, ominous, epic scale, cinematic
```

# 5. 얼음 왕국

```
first person view walking across a frozen lake, breath fogging the frame,
cracks glowing faintly beneath the ice underfoot, a frozen palace of blue
spires emerging from the blizzard ahead, aurora rippling overhead,
snow drifting sideways, haunting, epic scale, cinematic
```

```
first person view riding a sled through a glacier canyon, fur-trimmed hood
edge in foreground, sheer walls of blue ice rushing past on both sides,
a colossal frozen waterfall just coming into view around the bend,
aurora, cold cyan and deep indigo, exhilarating, cinematic
```

# 6. 마법 도시

```
first person view riding a gondola through arcane canal streets, the boat's
carved prow in foreground, floating lanterns drifting overhead, warm windows
stacked high on both sides, an enormous clocktower half-hidden in evening
mist ahead, reflections on black water, serene, cinematic
```

```
first person view walking a rain-slick arcane market street at night, hood
edge in frame, glowing sigils floating above the stalls, a wizard tower
spiraling into low cloud ahead barely visible, magenta and cyan neon on wet
stone, floating lantern festival, dreamlike, cinematic
```

# 7. 용 · 비행

```
first person view riding on a dragon's neck, the scaled ridge and beating
wing edge in foreground, low over a cloud sea at sunrise, mountain peaks
piercing the clouds ahead, a second dragon gliding far below,
golden rim light, exhilarating, epic scale, cinematic
```

```
first person view from an airship bow, brass railing and rigging ropes in
foreground, gliding low through a canyon of red rock, a fleet of distant
airships half-hidden in dust haze ahead, sun flare, warm ochre,
adventurous, epic scale, cinematic
```

# 8. 심해 · 수중

```
first person view swimming down toward a sunken city, both hands reaching
forward in frame, shafts of light cutting through the blue, drowned marble
columns rising on either side, an immense domed structure barely visible in
the murk below, jellyfish drifting, ethereal, haunting, cinematic
```

```
first person view descending an ocean trench in a small submersible, curved
porthole glass and instrument glow in foreground, bioluminescent coral walls
sliding past, a colossal unknown silhouette half-hidden in the dark ahead,
deep indigo, ominous, epic scale, cinematic
```

# 9. 거대 존재

```
first person view walking along the spine of a sleeping colossal creature,
mossy plates and one's own boot tips in frame, forest grown over its back,
the horizon curving away, its enormous horned head just coming into view
far ahead through low cloud, dawn light, awe, epic scale, cinematic
```

```
first person view standing between the feet of a giant statue, looking up
along the causeway that runs between them, worn stone filling both sides of
the frame, a second impossibly large statue half-hidden in mist beyond,
birds circling, ominous, epic scale, cinematic
```

# 10. 마법 도서관

```
first person view walking a narrow catwalk inside an infinite library,
one hand trailing the iron rail, bookshelves rising and falling out of
sight above and below, floating books drifting past, a vast reading rotunda
glowing warm at the far end, dust in lamplight, serene, cinematic
```

```
first person view climbing a spiral staircase in a library tower, candle
held forward, shelves curving around, an enormous orrery of brass and light
half-hidden above through the stairwell opening, warm gold against deep
brown shadow, dreamlike, cinematic
```

# 11. 영혼의 길

```
first person view walking a tunnel of vermillion torii gates at night, a
paper lantern swinging in one hand, stone lanterns glowing at intervals,
the tunnel curving out of sight ahead, a river of stars visible through
gaps between the gates, mist at ankle height, serene, haunting, cinematic
```

```
first person view crossing a stone lantern path over still water, hem of a
dark robe in foreground, cherry petals drifting down, a shrine roof
half-hidden in fog on the far shore, reflections doubling the lanterns,
soft pink against deep blue, ethereal, cinematic
```

# 12. 우주 · 이계

```
first person view stepping through a glowing portal onto an alien planet,
the portal's rim of light still framing the edges, a valley of black glass
spires ahead, a ringed planet filling half the sky, two small moons,
violet and teal, awe, epic scale, cinematic
```

```
first person view walking a narrow bridge on a space station hull, gloved
hand on the guide cable, starfield and nebula filling the background, an
enormous docked vessel half-hidden in shadow ahead, running lights,
cold blue against deep black, ominous, epic scale, cinematic
```

---

## 조립해서 더 만들기

```
[1인칭 앵커] + [길] + [세 겹 깊이] + [가려진 거대한 것] + [광원] + [분위기]
```

| 칸 | 고를 것 |
|---|---|
| **1인칭 앵커** | hands gripping · lantern held forward · boat prow · hood edge in frame · gloved hand on rail · boot tips in frame |
| **길** | causeway · catwalk · spiral staircase · rope bridge · glowing river · canyon · trench · torii tunnel |
| **가려진 것** | half-hidden in mist · emerging from clouds · just coming into view · barely visible in the murk |
| **광원** | bioluminescent · braziers · aurora · floating lanterns · god rays · molten veins · starfield |
| **분위기** | ethereal · haunting · ominous · serene · awe · exhilarating |

---

## 뽑고 나서 확인할 것

업로드 전에 이 셋만 보세요. 하나라도 아니면 버리는 게 낫습니다.

| 확인 | 아니면 |
|---|---|
| **앞으로 갈 길이 보이나** | 정면 벽·막다른 길이면 영상이 멈춥니다 |
| **화면 앞쪽에 내 것이 있나** | 없으면 그냥 풍경 줌이 됩니다 |
| **어둡고 채도가 높나** | 밝고 평평하면 밋밋합니다 |

얼굴이 보이는 것도 빼세요. 체이닝 2~3회차에서 가장 먼저 무너집니다.

---

## 몇 장이나

하루 1편이니 **30장이면 한 달**입니다. 테마별로 2~3장씩 고르면
피드가 단조로워지지 않습니다.

업로드는 작업실 **[1 · 이미지 고르기]** 탭에 끌어다 놓으면 됩니다.
테마 분류·제목·훅·움직임 문구까지 자동으로 붙습니다.
