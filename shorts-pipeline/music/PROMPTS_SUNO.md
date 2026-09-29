# 수노(Suno) 음악 프롬프트 팩

영상만 나오면 아무도 끝까지 안 봅니다. **소리가 절반**입니다.

여기 있는 프롬프트로 곡을 만들어 아래 폴더에 넣으면, 영상을 만들 때
시드의 테마에 맞는 곡이 **자동으로 붙습니다.**

```
music/
  bright/   밝고 상쾌 — 자전거 다운힐, 해안, 애니 톤
  epic/     웅장     — 용·비행, 거대 존재, 부유섬, 신전
  calm/     잔잔     — 영혼의 길, 도서관, 숲, 기차
  mystic/   신비     — 크리스탈, 심해, 얼음, 우주, 터널
  city/     도시 밤   — 마법 도시, 야간 드라이브, 골목
  any/      아무 데나 (위 폴더가 비었을 때의 보험)
```

**최소 이것만**: 폴더마다 3곡씩, 총 15곡. 하루 1편이면 같은 곡이
5일에 한 번 돌아옵니다. 5곡씩이면 더 좋습니다.

---

## 만들기 전에 — 이 셋만 지키세요

### ① 가사 없이 (Instrumental)

수노에서 **[Instrumental] 토글을 켜세요.** 가사가 있으면 세 가지가 망가집니다.

- 한국어 자막·훅과 부딪칩니다
- 유튜브·인스타 저작권 필터에 걸릴 확률이 올라갑니다
- 30초 안에 한 소절도 못 끝내고 잘립니다

### ② 40초 이상으로

영상은 30초입니다. 곡이 30초보다 짧으면 반복 이음매가 들립니다.
**40~60초**로 만들어 두면 뒷부분이 자연스럽게 페이드아웃됩니다.

> 자동으로 앞 1초 페이드인 · 뒤 1.6초 페이드아웃이 들어갑니다.
> 음량도 유튜브 기준(-14 LUFS)에 맞춰 자동으로 고릅니다. 곡마다
> 크기가 달라도 신경 쓰지 않아도 됩니다.

### ③ 드럼은 약하게, 시작은 조용하게

첫 1초에 큰 소리가 터지면 이탈합니다. 프롬프트에 **`soft intro`**,
**`no sudden drop`** 을 넣으세요.

---

## 다운로드 후 할 일

수노에서 **MP3 다운로드** → 위 폴더 중 맞는 곳에 넣기. 끝입니다.
파일 이름은 아무래도 상관없습니다.

---

# bright — 밝고 상쾌 (자전거 다운힐, 해안)

```
uplifting cinematic instrumental, bright acoustic guitar and warm strings,
gentle four-on-the-floor kick, airy synth pads, feeling of wind and speed,
soft intro building to an open chorus, no vocals, no sudden drop, 100 bpm
```

```
feel-good indie folk instrumental, fingerpicked acoustic guitar, light claps,
glockenspiel, warm bass, summer morning air, hopeful and moving forward,
soft intro, no vocals, 108 bpm
```

```
bright synthwave instrumental, shimmering arpeggio, soft analog pads,
punchy but gentle drums, open sky feeling, coasting downhill, no vocals,
soft intro, 112 bpm
```

```
orchestral pop instrumental, soaring strings over light percussion,
piano ostinato, sense of freedom and wide landscape, warm and clean,
builds gently then settles, no vocals, 96 bpm
```

```
lo-fi acoustic instrumental with a lift, brushed drums, nylon guitar,
warm rhodes, faint field recording of wind, relaxed but forward-moving,
no vocals, 92 bpm
```

# epic — 웅장 (용·비행, 거대 존재, 부유섬, 신전)

```
epic cinematic orchestral instrumental, deep taiko drums, soaring horns,
wordless choir pad, vast and awe-inspiring, slow powerful build,
no vocals, no sudden drop, 80 bpm
```

```
hybrid trailer score instrumental, low brass swells, ticking percussion,
strings rising in layers, sense of enormous scale revealing itself,
soft intro, no vocals, 85 bpm
```

```
heroic flight theme instrumental, sweeping strings, French horn melody,
rolling timpani, wind and altitude, adventurous and warm,
no vocals, 96 bpm
```

```
ancient temple orchestral instrumental, low drone, stone-hall reverb,
sparse hand percussion, distant choir, solemn and enormous,
very soft intro, no vocals, 70 bpm
```

```
cinematic awe instrumental, slow piano over massive string pad,
subtle sub-bass pulse, one giant swell at the halfway point,
no vocals, no sudden drop, 74 bpm
```

# calm — 잔잔 (영혼의 길, 도서관, 숲, 기차)

```
ambient cinematic instrumental, soft felt piano, warm tape hiss,
long reverb tails, gentle cello underneath, peaceful and still,
no drums, no vocals, 68 bpm
```

```
japanese ambient instrumental, koto and shakuhachi over soft pad,
distant temple bell, night air, meditative and quiet,
no drums, no vocals, 64 bpm
```

```
warm library ambience instrumental, music box melody, soft strings,
faint vinyl crackle, nostalgic and safe, very gentle,
no vocals, 72 bpm
```

```
forest morning instrumental, acoustic guitar harmonics, light flute,
soft brushed percussion, birdsong texture, calm and green,
no vocals, 76 bpm
```

```
slow train instrumental, gentle rhodes chords, soft rhythmic pulse like
rails, warm bass, watching the window, wistful and steady,
no vocals, 80 bpm
```

# mystic — 신비 (크리스탈, 심해, 얼음, 우주, 터널)

```
ethereal ambient instrumental, glassy bell tones, deep sub pad,
slow breathing swells, underwater and weightless, mysterious,
no drums, no vocals, 62 bpm
```

```
deep space ambient instrumental, wide drone, sparse plucked synth,
distant wordless choir texture, cold and infinite,
no drums, no vocals, no sudden drop, 60 bpm
```

```
crystal cavern instrumental, resonant metallic bells, dripping water
texture, low cello drone, echoing and vast, quietly unsettling,
no vocals, 66 bpm
```

```
arctic ambient instrumental, icy shimmering pad, sparse piano notes,
faint wind, aurora feeling, cold and beautiful,
no drums, no vocals, 58 bpm
```

```
liminal tunnel instrumental, pulsing low synth, slow filtered arpeggio,
steady forward motion, hypnotic, gently building,
no vocals, 84 bpm
```

# city — 도시 밤 (마법 도시, 야간 드라이브, 골목)

```
night city lo-fi instrumental, rainy jazz chords on rhodes, soft swung
drums, upright bass, neon reflections, relaxed and moody,
no vocals, 86 bpm
```

```
retro night drive instrumental, analog synth bass, tight electronic drums,
sparse guitar echoes, empty highway at 3am, cool and steady,
no vocals, 104 bpm
```

```
rainy alley instrumental, soft piano, vinyl texture, brushed snare,
distant city hum, melancholy but warm, no vocals, 78 bpm
```

```
magical city instrumental, playful pizzicato strings, celesta, light
accordion, lantern-lit streets, whimsical and warm,
no vocals, 100 bpm
```

```
downtempo neon instrumental, filtered pads, deep bass pulse, glassy
plucks, slow motion through light, dreamy, no vocals, 90 bpm
```

---

## 조립해서 더 만들기

```
[장르] instrumental, [주요 악기 2~3개], [리듬], [느낌], [구조], no vocals, [bpm]
```

| 칸 | 고를 것 |
|---|---|
| **장르** | cinematic orchestral · ambient · lo-fi · synthwave · indie folk · hybrid trailer |
| **악기** | felt piano · warm strings · acoustic guitar · taiko · analog synth bass · koto · music box · glockenspiel |
| **리듬** | no drums · brushed drums · gentle four-on-the-floor · rolling timpani · steady pulse |
| **느낌** | uplifting · awe-inspiring · peaceful · mysterious · nostalgic · cold and infinite |
| **구조** | soft intro · slow build · one swell at the halfway point · no sudden drop |
| **bpm** | 잔잔 58~80 · 웅장 70~96 · 밝음 92~112 |

---

## 넣지 말 것

| 넣지 말 것 | 왜 |
|---|---|
| 가사 · 보컬 | 자막과 부딪히고 저작권 필터에 걸립니다 |
| 실제 아티스트·곡 이름 | 수노가 거부하거나, 플랫폼에서 걸립니다 |
| 강한 드롭 · 빌드업 폭발 | 30초 안에 한 번도 못 터지고 끝납니다 |
| 급격한 장르 전환 | 잘린 구간만 들어가서 이상해집니다 |

---

## 잘 붙었는지 확인하기

영상을 만들면 화면에 이렇게 찍힙니다.

```
음악   : bright_ride_02.mp3  (밝고 상쾌)
```

`music/ 에 곡이 없어 무음으로 만듭니다` 가 뜨면 폴더가 비어 있는 것입니다.
`music/bright` 처럼 **분위기 폴더 안에** 넣었는지 확인하세요.
