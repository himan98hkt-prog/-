# 월드 팩 — 3인칭 뒷모습 · Odyssey 톤

`PROMPTS_RIDE.md`(1인칭)로 뽑았을 때 그림이 이상하게 나왔다면 **이 팩을 쓰세요.**
같은 자전거 내리막인데 결과가 완전히 달라집니다.

---

## 왜 1인칭이 망가졌나

미드저니는 **1인칭 손·핸들바를 잘 못 그립니다.** 손가락이 늘어나고,
핸들바가 휘고, 앞바퀴가 두 개가 됩니다. "first person view" 를 넣을수록
카메라가 아니라 **몸의 일부**를 그리려 들기 때문입니다.

**해결은 카메라를 뒤로 빼는 것입니다.**

| | 1인칭 | 3인칭 뒷모습 |
|---|---|---|
| 손·핸들바 | 자주 망가짐 | **아예 안 보임** |
| 얼굴 | 안 보임 | **안 보임** (뒷모습) |
| 규모감 | 약함 | 사람이 작게 들어가 **풍경이 거대해 보임** |
| 영상 전환 | 배경만 확대되기 쉬움 | 사람이 고정 기준이 되어 **앞으로 나아감** |

레퍼런스로 본 계정(Odyssey 등)이 전부 이 구도인 데는 이유가 있습니다.

---

## 이 팩의 공식 세 가지

### ① 사람은 화면 아래쪽, 작게

인물이 크면 인물 사진이 됩니다. **화면의 1/6 이하**로 작게 두고,
나머지를 전부 풍경에 쓰세요.

> `small figure in the lower third` · `seen from behind` · `tiny rider`

### ② 세 겹 깊이 + 대기 원근

가까이·중간·멀리가 **뿌옇기가 다르게** 겹쳐야 거대해 보입니다.

```
near: 길가의 풀·바위    mid: 굽어 내려가는 길    far: 안개 속 거대한 무엇
```

> `layered atmospheric haze` · `deep distance` · `receding into haze`

### ③ 말이 안 되는 것을 하나

이게 "판타지"의 정체입니다. 사실적인 풍경 하나에 **불가능한 것 딱 하나**를
넣으세요. 두 개 넣으면 게임 콘셉트아트가 되고, 없으면 여행 사진이 됩니다.

> 하늘을 가로지르는 거대 아치 · 뒤집혀 걸린 도시 · 지평선을 채운 행성 ·
> 구름 위로 뻗은 다리 · 사막에 좌초한 거대 구조물

---

## 공통 접미사

```
--ar 9:16 --style raw
```

**HD로 뽑는 법**: 마음에 드는 것의 **U 버튼** → **Upscale (Subtle)**.

> ⚠️ 첫 줄을 그대로 두세요. 작업실이 **파일 이름**을 읽어 테마·제목·훅을
> 자동으로 붙입니다. 뒷줄은 마음껏 고쳐도 됩니다.

---

# 1. 거대 아치 협곡

```
third person view behind a cyclist coasting downhill into a wide green valley at sunset
tiny rider small in the lower third seen from behind, a colossal stone arch spanning the
whole valley in the far distance, river threading below, layered haze, towering cumulus,
warm rim light, hyper detailed, cinematic
```

# 2. 절벽 언덕 마을

```
third person view behind a cyclist riding downhill through a hillside town, god rays
breaking over a turquoise bay far below, stacked terracotta rooftops and power lines,
small figure seen from behind in the lower third, a white waterfall on the far cliff,
deep atmospheric distance, hyper detailed, cinematic
```

# 3. 뒤집힌 하늘 도시

```
third person view behind a cyclist coasting downhill through a city, giant moon rising
behind an upside down city hanging in the sky, streets and towers mirrored overhead,
tiny rider small in the lower third seen from behind, low sun, long shadows,
layered haze, hyper detailed, cinematic
```

# 4. 좌초한 거대 구조물

```
third person view behind a cyclist riding downhill across a sand dune sea at first light
an enormous half-buried metal hull rising from the sand ahead, ribbed and weathered,
small figure seen from behind in the lower third, wind-blown sand, pale gold sky,
deep distance, hyper detailed, cinematic
```

# 5. 은하가 걸린 분화구

```
third person view behind a cyclist coasting downhill into a crater under the milky way
a still turquoise lake at the bottom reflecting the whole sky, black volcanic slopes,
tiny rider seen from behind small in the lower third, faint green airglow on the horizon,
layered haze, hyper detailed, cinematic
```

# 6. 열대 군도

```
third person view behind a cyclist riding downhill along an archipelago road at sunset
dozens of green islands scattered across a glowing sea, causeways linking them, small
figure seen from behind in the lower third, birds far below the road, towering cumulus
catching the last light, deep distance, hyper detailed, cinematic
```

# 7. 구름 위의 다리

```
third person view behind a cyclist coasting downhill on a cloud bridge, god rays below
an impossibly long white bridge running above a sea of cloud, no railings, sky in every
direction, tiny rider small in the lower third seen from behind, a distant landmass
floating at the far end, layered haze, hyper detailed, cinematic
```

# 8. 하늘을 비추는 소금 사막

```
third person view behind a cyclist riding downhill onto a salt flat in morning mist
a thin sheet of water turning the whole plain into a mirror, sky doubled below,
small figure seen from behind in the lower third, distant mountains floating on the
reflection, soft pastel light, deep distance, hyper detailed, cinematic
```

# 9. 눈 덮인 화산 고갯길

```
third person view behind a cyclist coasting down a switchback, snow capped volcano ahead
filling half the frame, black lava fields on both sides of the road, tiny rider seen from
behind small in the lower third, a plume of steam drifting from the summit, cold clear
light, layered haze, hyper detailed, cinematic
```

# 10. 거대 삼나무 숲

```
third person view behind a cyclist riding downhill through a moss covered cedar forest
trunks so wide the road passes between two of them, shafts of light through the canopy,
small figure seen from behind in the lower third, ferns and fog at ground level,
deep green, hyper detailed, cinematic
```

# 11. 등불 켜진 계단 마을

```
third person view behind a cyclist coasting downhill on a stone step street, paper lanterns
strung overhead in long rows, warm windows on both sides, tiny rider seen from behind small
in the lower third, the street dropping toward a dark harbour, a huge ringed planet low on
the horizon, layered haze, hyper detailed, cinematic
```

# 12. 폭포 벼랑길

```
third person view behind a cyclist riding downhill on a cliff path beside a waterfall
that falls further than the eye can follow into cloud, wet rock and hanging moss,
small figure seen from behind in the lower third, a rainbow in the spray, second and
third waterfalls receding into haze, hyper detailed, cinematic
```

---

## 조립해서 더 만들기

```
"third person view behind a cyclist" + [내리막 동사] [지형], [빛],
small figure seen from behind in the lower third, [불가능한 것 하나],
layered haze, hyper detailed, cinematic
```

| 칸 | 고를 것 |
|---|---|
| **내리막 동사** | coasting downhill · riding downhill · coasting down a switchback |
| **지형** | wide green valley · hillside town · city · sand dune sea · crater · archipelago road · cloud bridge · salt flat · switchback · cedar forest · stone step street · cliff path |
| **빛** | at sunset · at first light · god rays · under the milky way · in morning mist |
| **불가능한 것** | a colossal stone arch spanning the valley · an upside down city in the sky · a huge ringed planet on the horizon · an enormous half-buried hull · a floating landmass · a waterfall that falls into cloud |

인물을 바꿔도 됩니다. `a cyclist` 대신 `a child running`, `a lone walker`,
`a rider on horseback` — 다만 **첫 줄의 내리막 동사와 지형은 그대로** 두세요.
그 두 개로 테마와 제목이 정해집니다.

---

## 피해야 할 단어

첫 줄에 아래 단어가 들어가면 자전거가 아니라 **다른 테마로 잘못 분류**됩니다.

| 넣지 말 것 | 잘못 잡히는 테마 |
|---|---|
| `colossal` · `giant statue` · `titanic` | 거대 존재 |
| `temple` · `shrine` · `pillar` · `causeway` | 고대 유적 |
| `crystal` · `cavern` · `molten` | 크리스탈 동굴 |
| `frozen` · `snowy` · `glacier` · `aurora` | 얼음 왕국 |
| `dragon` · `wings` · `gliding` · `airship` | 용 · 비행 |
| `floating island` · `cloud sea` · `rope bridge` | 부유섬 |
| `starfield` · `nebula` · `space station` | 우주 |
| `highway` · `dashboard` · `cockpit` | 야간 드라이브 |
| `stone lantern` · `torii` · `cherry` | 영혼의 길 |

`colossal` 은 **둘째 줄부터는 써도 됩니다.** 파일 이름에는 앞부분만 들어갑니다.
위 12개 프롬프트도 그렇게 배치해 두었습니다.

---

## 뽑고 나서 확인할 것

| 확인 | 아니면 |
|---|---|
| **사람이 충분히 작나** | 크면 인물 사진이 됩니다 |
| **뒷모습만 보이나** | 얼굴이 보이면 체이닝 2~3회차에서 무너집니다 |
| **말이 안 되는 것이 하나 있나** | 없으면 그냥 여행 사진입니다 |
| **멀리가 뿌옇나** | 전부 선명하면 납작해 보입니다 |

---

## 세 팩을 어떻게 나눠 쓰나

| 팩 | 톤 | 언제 |
|---|---|---|
| `PROMPTS_HD.md` | 어둡고 신비한 1인칭 | 동굴·신전·심해처럼 **좁고 어두운** 공간 |
| `PROMPTS_RIDE.md` | 밝은 1인칭 내리막 | 손·핸들바가 잘 나왔을 때만 |
| `PROMPTS_WORLD.md` | 밝고 웅장한 3인칭 | **막히면 여기부터.** 실패율이 가장 낮습니다 |

업로드는 작업실 **[1 · 이미지 고르기]** 탭. 또는 다운로드 폴더 경로를 넣고
**[가져오기]** 를 누르면 새로 받은 것만 알아서 들어갑니다.
