# 그림 만들기 — 미드저니 프롬프트 모음

인쇄물과 무대 화면에 들어갈 **그림을 밖에서 만들어 넣기 위한** 문서입니다.

직접 그린 SVG 그림(피아노·건반·아치…)은 인쇄물에서 어설퍼 보여 **전부 걷어냈습니다.**
그 자리에 미드저니로 만든 그림을 넣었습니다. 지금 들어가 있는 것은 아래 「지금 들어가 있는
그림」 표에 있고, 더 넣으실 때는 여기 프롬프트를 그대로 복사해 쓰시면 됩니다.

---

## 먼저 알아 두실 것

**1. 그림에 글씨가 들어가면 안 됩니다.**
제목·날짜·장소·아이 이름은 프로그램이 그립니다. 그림에 글씨가 있으면 겹칩니다.
모든 프롬프트 끝에 `--no text, letters, words, watermark, signature` 를 붙여 두었습니다.

**2. 빈자리를 남겨야 합니다.**
포스터는 그림 위에 큰 제목이 올라갑니다. 프롬프트마다 어디를 비우라고 적어 두었습니다
(`generous empty space in the upper half` 같은 문장). 이 문장을 지우지 마세요.

**3. 얼굴은 넣지 않습니다.**
아이 얼굴은 학원이 찍은 실제 사진만 씁니다. 만든 얼굴이 섞이면 학부모가 헷갈리고,
인쇄하면 어색합니다. 손·뒷모습·실루엣으로 충분히 따뜻해집니다.

**4. 여덟 장이 한 벌로 보여야 합니다.**
첫 장(A1)을 마음에 드시게 뽑으신 다음, 그 이미지 주소를 복사해
나머지 프롬프트 끝에 `--sref <주소>` 로 붙이시면 화풍이 같아집니다.

**5. 크기**
- 포스터용 `--ar 5:7` (A4 에 가장 가까운 정수비)
- 무대 화면·감동영상용 `--ar 16:9`
- 장식 조각 `--ar 1:1`
- SNS 스토리 `--ar 9:16`

**6. 해상도**
뽑으신 뒤 **Upscale** 까지 눌러 주세요. A4 인쇄에 쓰려면 긴 변이 **2000px 이상**이어야
합니다. 그보다 작으면 인쇄에서 뭉갭니다.

**7. 버전**
`--v 7` 로 적어 두었습니다. 쓰시는 판이 다르면 그 부분만 바꾸시거나 지우셔도 됩니다.

---

## A. 포스터 주 그림 — 여기부터 8장 (`--ar 5:7`)

이 여덟 장만 있으면 **포스터 8종**이 바로 만들어집니다. 우선순위가 가장 높습니다.

### A1 · 무대 위 그랜드피아노 (기본 얼굴 · 어두운 테마)
```
a grand piano alone on a dark concert hall stage, one warm spotlight falling from above,
deep velvet darkness all around, faint golden dust in the beam of light, elegant classical
concert poster art, painterly and cinematic, the piano sits in the lower third, generous
empty dark space across the upper half
--ar 5:7 --v 7 --style raw --stylize 300 --no text, letters, words, watermark, signature, people, faces
```

### A2 · 건반 클로즈업 (어두운 테마)
```
close-up of grand piano keys receding into darkness, shallow depth of field, warm golden
rim light along the edge of the white keys, ivory and deep black, quiet and luxurious,
fine art photography, the top two thirds fade into solid darkness
--ar 5:7 --v 7 --style raw --stylize 300 --no text, letters, words, watermark, signature, people, faces
```

### A3 · 아이의 손 (따뜻한 테마)
```
a child's small hands resting on piano keys, seen from above and slightly behind, warm
late afternoon light through a window, soft focus background, tender and hopeful, no face
visible, muted ivory honey and cream tones, a large soft empty area at the top
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, faces
```

### A4 · 빈 콘서트홀 (격식 있는 테마)
```
an empty classical concert hall seen from the stage, rows of deep red velvet seats, warm
chandeliers glowing, perfectly symmetrical, the quiet before a recital begins, painterly
editorial illustration, wide empty ceiling space across the top
--ar 5:7 --v 7 --style raw --stylize 300 --no text, letters, words, watermark, signature, people, faces
```

### A5 · 수채 피아노 (밝은 테마)
```
elegant watercolour illustration of a grand piano, soft ivory paper background, delicate
gold ink line accents, minimal and airy, plenty of untouched white paper around the piano,
fine art gallery poster, the piano sits low in the frame
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### A6 · 꽃과 피아노 (봄 · 사랑스러운 테마)
```
watercolour grand piano surrounded by soft spring blossoms, cherry petals drifting through
the air, pastel rose cream and pale gold palette, delicate and romantic, generous white
space above the piano
--ar 5:7 --v 7 --style raw --stylize 300 --no text, letters, words, watermark, signature, people, faces
```

### A7 · 겨울 · 송년 음악회
```
a grand piano in a warm candlelit room in winter, frosted window behind it, pine branches
and small golden lights, deep green and burgundy palette, cosy and painterly, empty dark
space in the upper half
--ar 5:7 --v 7 --style raw --stylize 300 --no text, letters, words, watermark, signature, people, faces
```

### A8 · 실루엣과 빛 (콩쿠르 · 시상)
```
silhouette of a grand piano against a vast field of golden bokeh light, minimal and
luxurious, deep midnight blue fading to black, art hall gala poster, the piano occupies
only the lower third, everything above is soft glowing darkness
--ar 5:7 --v 7 --style raw --stylize 400 --no text, letters, words, watermark, signature, people, faces
```

---

## B. 무대 화면 · 감동영상 배경 (`--ar 16:9`)

연주회장 스크린에 띄우는 화면과 감동영상 뒤에 깔립니다. **아이 사진이 그 위에 올라가므로
가운데는 조용해야 합니다.**

### B1 · 무대 커튼과 조명 (어두움)
```
deep burgundy velvet stage curtains slightly parted, warm theatrical lights washing down
the folds, rich shadows, cinematic, the centre of the frame is calm and unobstructed
--ar 16:9 --v 7 --style raw --stylize 300 --no text, letters, words, watermark, signature, people, faces
```

### B2 · 건반 파노라마 (어두움)
```
a wide panorama of piano keys stretching across the bottom of the frame, warm golden light
grazing them, everything above dissolving into deep soft darkness
--ar 16:9 --v 7 --style raw --stylize 300 --no text, letters, words, watermark, signature, people, faces
```

### B3 · 금빛 보케 (사진 뒤에 깔 것)
```
soft out of focus golden bokeh lights on a deep warm dark background, gentle vignette,
completely abstract, nothing recognisable, calm and even across the centre
--ar 16:9 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### B4 · 밝은 종이 질감 (밝은 테마)
```
fine ivory cotton paper texture with a faint warm gradient and a whisper of gold leaf at
the edges, extremely subtle, almost plain, nothing in the centre
--ar 16:9 --v 7 --style raw --stylize 150 --no text, letters, words, watermark, signature, people, faces
```

---

## C. 장식 조각 (`--ar 1:1`)

상장·초대장·티켓 모서리에 얹는 작은 그림입니다.

미드저니는 배경이 비치는 그림을 주지 않으므로 **완전한 검정** 또는 **완전한 흰색** 바탕에
그리게 한 뒤, 프로그램이 그 바탕을 걷어내고 얹습니다. 프롬프트에 이미 넣어 두었습니다.

### C1 · 월계관 (콩쿠르 · 시상)
```
a delicate gold laurel wreath, thin elegant leaves, perfectly symmetrical, centred, drawn
in fine gold line art on a pure solid black background, nothing else in the frame
--ar 1:1 --v 7 --style raw --stylize 150 --no text, letters, words, watermark, signature, gradient background
```

### C2 · 금박 모서리 장식
```
an ornate art deco gold corner ornament, fine thin lines, classical concert programme
decoration, on a pure solid black background, only the top left corner is filled, the rest
is empty black
--ar 1:1 --v 7 --style raw --stylize 150 --no text, letters, words, watermark, signature, gradient background
```

### C3 · 음표와 오선 흐름
```
a flowing musical staff with a few scattered notes, drawn in fine gold line art, elegant
and sparse, on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 150 --no text, letters, words, watermark, signature, gradient background
```

### C4 · 리본 매듭 (초대장)
```
a soft satin ribbon tied in an elegant bow, cream and pale gold, delicate watercolour, on a
pure solid white background
--ar 1:1 --v 7 --style raw --stylize 200 --no text, letters, words, watermark, signature, gradient background
```

---

## 지금 들어가 있는 그림

64장을 받아 아래 열다섯 장을 골랐습니다. 고른 기준은 하나입니다 —
**제목이 들어갈 자리가 비어 있는가.** 예뻐도 위쪽이 차 있으면 포스터로 못 씁니다.

| 자리 | 파일 | 어느 장을 골랐나 |
|---|---|---|
| 포스터 | `poster/stage-piano.jpg` | A1-4 · 위쪽 3분의 1이 비어 막 없이 제목이 앉습니다 |
| 포스터 | `poster/oil-hall.jpg` | A1-2 · 유화 질감. 인쇄하면 AI 티가 가장 덜 납니다 |
| 포스터 | `poster/keys-close.jpg` | A2-2 · 위쪽 절반이 어둡고 검은건반 묶음이 자연스럽습니다 |
| 포스터 | `poster/child-hands.jpg` | A3-2 · 손가락이 자연스럽고 얼굴이 없습니다 |
| 포스터 | `poster/gala-bokeh.jpg` | A8-2 · 바닥 반사가 고급스럽고 위가 깨끗합니다 |
| 포스터 | `poster/light-field.jpg` | A8-3 · 빛의 들판. 송년·기념 연주회에 |
| 포스터 | `poster/watercolor-piano.jpg` | A5-2 · 흰 바탕 수채. 검은 피아노라 어느 테마에도 얹힙니다 |
| 포스터 | `poster/blossom-piano.jpg` | A6-2 · 오른쪽이 통째로 비어 제목 자리가 확실합니다 |
| 무대 | `stage/curtain.jpg` | B1-2 · 가운데가 조용해 아이 사진이 그 위에 올라갑니다 |
| 무대 | `stage/keys-wide.jpg` | B2-2 |
| 무대 | `stage/bokeh.jpg` | B3-2 |
| 무대 | `stage/paper.jpg` | B4-2 · 밝은 화면용 |
| 장식 | `ornament/laurel.png` | C1-3 · 두 가지가 아래에서 만나는 제대로 된 월계관 |
| 장식 | `ornament/corner.png` | C2-2 |
| 장식 | `ornament/staff.png` | C3-1 |

**떨어뜨린 것 중 눈여겨볼 것** — A2-3 과 B2-1 은 건반 뚜껑에 **글자 비슷한 얼룩**(가짜 브랜드명)이
생겼습니다. 화면에서는 안 보여도 A4 로 뽑으면 눈에 걸립니다. 다음에 뽑으실 때 `--no` 에
`brand name, logo on the piano` 를 더하시면 줄어듭니다.

---

## 다시 뽑아야 하는 둘 — A4 · A7

두 세트는 네 장 모두 못 썼습니다. **제 프롬프트가 잘못 쓰였습니다.**

### A4 · 빈 콘서트홀 — 넷 다 만화 배경 같은 선화로 나왔습니다

`painterly editorial illustration` 이라고 적은 것이 원인입니다. 미드저니가 이 말을
"선으로 그린 삽화" 로 받습니다. 사진 쪽 말로 바꿨습니다.

```
the interior of a grand classical concert hall photographed from the stage, rows of deep
red velvet seats receding into shadow, warm chandeliers glowing along the balconies, the
quiet moment before a recital begins, shot on a full frame camera with a wide lens, soft
volumetric light, the upper third of the frame is dark and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces, illustration, anime, line art, cartoon
```

### A7 · 겨울 — 넷 다 담쟁이 덩굴이 뒤덮인 청록색 방이 나왔습니다

`deep green and burgundy palette` 를 미드저니가 "방 전체를 초록으로, 피아노까지 초록으로"
로 받았습니다. 색은 **빛과 소품에만** 걸리게 고쳤습니다.

```
a black grand piano in a warm room on a winter evening, snow falling outside a frosted
window behind it, a few pine branches and small warm candles on top of the piano, deep
warm shadows, burgundy and gold light, photographed with a soft wide lens, the upper half
of the frame is dark and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces, green walls, ivy, vines, illustration, anime, line art
```

두 세트를 다시 뽑아 보내 주시면 **포스터 두 종이 더** 생깁니다. 급하지 않습니다 —
지금 여덟 장으로도 포스터는 이미 돌아갑니다.

---

## D. SNS 세로 (`--ar 9:16`) — 있으면 좋은 것

인스타그램 스토리 카드용입니다. A1 이나 A8 을 `--ar 9:16` 으로 다시 뽑으시면 됩니다.
따로 만드실 것 없이 비율만 바꾸세요.

---

## 다 만드신 뒤

이 대화창에 그대로 올려 주시면 됩니다. 파일 이름은 아무래도 괜찮습니다 —
어느 프롬프트로 만든 것인지만 알려 주시면 제가 자리에 넣고 이름을 붙입니다.

- **형식** JPG · PNG 아무거나
- **크기** 포스터용은 긴 변 2000px 이상
- **몇 장** A 세트 8장이 가장 급합니다. B·C 는 나중에 보내셔도 됩니다

받으면 이렇게 들어갑니다.

| 자리 | 무엇이 되나 |
|---|---|
| `public/art/poster/` | 포스터 양식 8종의 주 그림 |
| `public/art/stage/` | 무대 화면·감동영상 배경 |
| `public/art/ornament/` | 상장·초대장 모서리 장식 |

그림은 **프로그램 안에 같이 깔립니다.** 인터넷 없이도 뜨고, 학원 밖으로 나가지 않습니다.

---

# 2차 — 더 만들면 좋을 것

1차로 여덟 장이 들어가 포스터는 돌아갑니다. 그런데 **테마 108종에 견주면 그림이 한쪽으로
쏠려 있습니다.**

| 지금 | 문제 |
|---|---|
| 어두운 그림 6 · 밝은 그림 2 | 학원 프린터로 A4 를 까맣게 뽑으면 **잉크값이 몇 배**입니다 |
| 계절 테마 26종 · 계절 그림 1장 | 봄(벚꽃)뿐입니다. 여름·가을·겨울이 없습니다 |
| 사랑스러운 20 + 아이 8 = 28종 · 그 느낌 그림 1장 | 유아·저학년 발표회에 쓸 그림이 사실상 없습니다 |
| 바탕 질감 없음 | 그림은 **양식 하나**만 바꾸지만, 질감은 **테마 전체**를 바꿉니다 |

## 우선순위

| 순서 | 묶음 | 장수 | 무엇이 늘어나나 |
|---|---|---|---|
| **1** | G · 바탕 질감 | 6 | **테마 108종 전부**가 종이 결을 갖습니다. 한 장당 효과가 가장 큽니다 |
| **2** | D · 계절 | 4 | 포스터 4종 + 계절 테마 26종이 제 그림을 갖습니다 |
| **3** | H · 장식 조각 | 6 | 상장·초대장·입장권·프로그램 표지 |
| 4 | E · 밝은 판 | 4 | 포스터 4종. 잉크를 아낍니다 |
| 5 | F · 아이·사랑스러운 | 3 | 포스터 3종 |
| 6 | I · 무대 화면 | 4 | 무대 배경 14 → 18종 |
| 7 | J · SNS | 2 | 인스타 카드·스토리 |

한 번에 다 하실 것 없습니다. **1·2·3 만 하셔도** 확 달라집니다.

## 화풍을 묶는 법

- **사진 계열**(D · E1 · E3 · I) → 끝에 `--sref <A1-4 이미지 주소>`
- **수채 계열**(F · E2) → 끝에 `--sref <A5-2 이미지 주소>`
- **질감·장식**(G · H) → `--sref` 붙이지 마세요. 붙이면 질감에 피아노가 섞여 들어옵니다

---

## G. 바탕 질감 — 한 장이 테마 108종을 바꿉니다

지금 테마의 종이는 **단색**입니다. 여기에 결이 들어가면 인쇄물 전체가 한 단계 올라갑니다.
**아주 옅어야 합니다.** 질감이 눈에 띄면 실패입니다 — 글씨를 방해합니다.

### G1 · 미색 면 종이
```
fine ivory cotton paper texture, very subtle fibre grain, even lighting, almost plain, no
pattern, extremely low contrast, nothing in the centre
--ar 5:7 --v 7 --style raw --stylize 100 --no text, letters, words, watermark, signature, objects, shadows
```

### G2 · 리넨 결
```
pale warm linen fabric texture, soft woven grain, even lighting, extremely subtle and low
contrast, almost plain
--ar 5:7 --v 7 --style raw --stylize 100 --no text, letters, words, watermark, signature, objects, shadows
```

### G3 · 은은한 대리석
```
pale ivory marble surface with very faint soft grey veining, quiet and luxurious, extremely
low contrast, almost plain, nothing in the centre
--ar 5:7 --v 7 --style raw --stylize 100 --no text, letters, words, watermark, signature, objects, shadows
```

### G4 · 금박 (제목 글씨를 이 질감으로 칠합니다)
```
a sheet of real gold leaf foil, crinkled metallic surface with warm highlights and darker
folds, macro texture, rich and even across the whole frame
--ar 1:1 --v 7 --style raw --stylize 120 --no text, letters, words, watermark, signature, objects
```

### G5 · 검은 벨벳 (어두운 테마 바탕)
```
deep black velvet fabric texture, soft even sheen, subtle folds, luxurious, very dark and
quiet, nothing in the centre
--ar 5:7 --v 7 --style raw --stylize 100 --no text, letters, words, watermark, signature, objects
```

### G6 · 음표 무늬 (이어 붙는 무늬)
```
a seamless pattern of tiny sparse gold musical notes on a pure solid black background,
minimal, evenly spaced, very small motifs
--tile --ar 1:1 --v 7 --style raw --stylize 120 --no text, letters, words, watermark, signature
```

---

## D. 계절 — 계절 테마 26종이 제 그림을 갖습니다

### D1 · 여름 (밝은 판)
```
a black grand piano beside tall open windows with white linen curtains lifting in a summer
breeze, bright green trees outside, clear daylight, airy and cool, pale blue and ivory
tones, the upper third of the frame is bright and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### D2 · 가을
```
a grand piano in a room filled with warm autumn afternoon light, maple leaves in amber and
rust tones scattered on the floor and on the lid, long soft shadows, deep warm palette, the
upper half of the frame is dark and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### D3 · 크리스마스·송년
```
a black grand piano decorated with a simple pine garland and small warm lights, a decorated
christmas tree softly out of focus behind it, deep burgundy and gold, warm candlelight, the
upper half of the frame is dark and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces, green walls, ivy, vines
```

### D4 · 새해·졸업·수료
```
a black grand piano on a stage with soft golden confetti drifting in the air, warm
celebratory light, deep navy and gold, elegant and restrained not childish, the upper half
of the frame is dark and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

---

## H. 장식 조각 (`--ar 1:1`, 순검정 바탕)

검은 바탕에 금선으로 그리시면 프로그램이 **검정을 뚫어 내고 테마 색으로 칠합니다.**
그래서 남색 테마에서는 남색으로, 금색 테마에서는 금색으로 나옵니다.

### H1 · 리본 매듭 (1차 것은 실크 스카프 사진으로 나와 못 썼습니다)
```
a delicate ribbon bow drawn in fine gold line art, symmetrical, centred, elegant thin
lines, on a pure solid black background, flat line drawing not a photograph
--ar 1:1 --v 7 --style raw --stylize 130 --no text, letters, words, watermark, signature, photograph, fabric, gradient background
```

### H2 · 구분선
```
an elegant horizontal gold divider ornament with a small central motif and thin tapering
flourishes, fine line art, centred, on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 130 --no text, letters, words, watermark, signature, gradient background
```

### H3 · 높은음자리표
```
an elegant treble clef in fine gold line art, single centred motif, generous empty space
around it, on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 130 --no text, letters, words, watermark, signature, gradient background
```

### H4 · 반짝임
```
a sparse scatter of tiny gold sparkles and thin four point starbursts, delicate and airy,
on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 130 --no text, letters, words, watermark, signature, gradient background
```

### H5 · 상장 테두리 (A4 **가로** 라 비율이 다릅니다)
```
an ornate art deco gold border frame running around the four edges, fine thin lines,
classical certificate border, the entire centre is empty pure black
--ar 7:5 --v 7 --style raw --stylize 130 --no text, letters, words, watermark, signature, gradient background
```

### H6 · 작은 피아노 표식 (입장권·이름표에 씁니다)
```
a small elegant grand piano seen from above, drawn in fine gold line art as a single simple
icon, centred with generous empty space, on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 130 --no text, letters, words, watermark, signature, gradient background
```

---

## E. 밝은 판 — 잉크를 아끼는 포스터

A4 를 까맣게 채우면 학원 프린터의 잉크가 몇 배로 듭니다. 밝은 포스터가 필요한 진짜 이유입니다.

### E1 · 흰 홀
```
a black grand piano alone in a bright white minimalist concert hall, tall windows, soft even
daylight, calm and modern, mostly white and pale grey, the piano sits low in the frame, the
upper half is plain and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### E2 · 금색 한 줄 그림
```
a single continuous fine gold line drawing of a grand piano, minimal one line art, placed
low and centred on a plain ivory paper background, elegant and modern, vast empty space above
--ar 5:7 --v 7 --style raw --stylize 150 --no text, letters, words, watermark, signature, shading, colour fill
```

### E3 · 흑백 사진
```
a black and white fine art photograph of a grand piano in an empty hall, high key, soft
film grain, mostly white, the piano small in the lower third, vast empty space above
--ar 5:7 --v 7 --style raw --stylize 200 --no text, letters, words, watermark, signature, people, faces
```

### E4 · 대리석과 그림자
```
a pale marble surface with delicate gold veining, the soft shadow of a grand piano falling
across the lower half, extremely subtle, luxurious and quiet, the upper half almost empty
--ar 5:7 --v 7 --style raw --stylize 200 --no text, letters, words, watermark, signature, people, faces
```

---

## F. 아이 · 사랑스러운 — 28종 테마가 쓸 그림

### F1
```
a warm children's book watercolour illustration of a small upright piano with a few musical
notes floating above it, soft pastel palette, gentle and hand painted, on a plain cream
background with plenty of empty space at the top
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### F2
```
a cheerful watercolour illustration of a grand piano surrounded by colourful balloons and
paper streamers, soft pastel colours, hand painted, plain white background, empty space at
the top
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### F3
```
a soft watercolour illustration of a piano keyboard turning into a winding path of small
flowers and stars, whimsical and gentle, pastel palette, plain white background, empty space
at the top
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

---

## I. 무대 화면 (`--ar 16:9`) — 가운데는 아이 사진 자리라 조용해야 합니다

### I1 · 별밤
```
a deep navy night sky with tiny scattered stars and a very soft glow near the horizon,
minimal and quiet, the centre of the frame is calm and even
--ar 16:9 --v 7 --style raw --stylize 200 --no text, letters, words, watermark, signature, people, faces
```

### I2 · 흰 홀 (밝은 화면용)
```
a bright white minimalist concert hall interior, soft even daylight, pale grey and white,
very calm, nothing in the centre of the frame
--ar 16:9 --v 7 --style raw --stylize 200 --no text, letters, words, watermark, signature, people, faces
```

### I3 · 객석에서 본 무대
```
an empty stage seen from the middle of a dark auditorium, warm lights washing the stage
floor, the audience seats in silhouette along the bottom edge, the centre is calm and open
--ar 16:9 --v 7 --style raw --stylize 220 --no text, letters, words, watermark, signature, people, faces
```

### I4 · 은은한 그라데이션
```
a smooth deep gradient from midnight blue to warm gold at the bottom edge, completely
abstract, no objects, very subtle grain, calm and even across the centre
--ar 16:9 --v 7 --style raw --stylize 150 --no text, letters, words, watermark, signature, objects
```

---

## J. SNS

### J1 · 정사각 카드 (`--ar 1:1`)
```
a black grand piano in warm stage light on a deep dark background, elegant and simple, the
piano in the lower half, the upper half dark and empty
--ar 1:1 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### J2 · 스토리 (`--ar 9:16`)
```
a black grand piano in warm stage light on a deep dark background, tall vertical
composition, the piano near the bottom, the upper two thirds dark and empty
--ar 9:16 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

---

## 보내실 때

1차와 같습니다. 압축해서 **릴리스**에 올려 주세요 (태그는 `art2` 처럼 새로 하나).
파일 이름은 이번에도 `G1` `G1(2)` … 식으로 해 주시면 그대로 알아봅니다.

https://github.com/himan98hkt-prog/-/releases/new


---

## 2차 결과 — 68장 중 16장

| 자리 | 파일 | 고른 것 · 이유 |
|---|---|---|
| 질감 | `texture/paper-cotton.jpg` | G1-2 · 평균밝기 227, 결 편차 4.1. 넷 중 가장 밝고 가장 옅습니다 |
| 질감 | `texture/paper-linen.jpg` | G2-4 |
| 질감 | `texture/paper-marble.jpg` | G3-4 |
| 질감 | `texture/velvet.jpg` | G5-2 · 어두운 테마에 화면(screen)으로 얹습니다 |
| 질감 | `texture/gold-foil.jpg` | G4-1 · **제목 글씨를 이걸로 칠합니다** |
| 질감 | `texture/gold-flecks.png` | G6-3 · 음표가 아니라 금가루로 나왔지만 그대로 씁니다 |
| 포스터 | `poster/summer-window.jpg` | D1-3 |
| 포스터 | `poster/autumn-leaves.jpg` | D2-3 |
| 포스터 | `poster/christmas-pine.jpg` | D3-4 |
| 포스터 | `poster/confetti-night.jpg` | D4-1 |
| 장식 | `ornament/ribbon.png` | H1-2 |
| 장식 | `ornament/divider.png` | H2-3 |
| 장식 | `ornament/clef.png` | H3-4 |
| 장식 | `ornament/sparkle.png` | H4-4 |
| 장식 | `ornament/cert-border.png` | H5-1 · **금테두리 상장** |
| 장식 | `ornament/piano-mark.png` | H6-**3** |

**떨어뜨린 것 중 알아 두실 것**

- **D3-2** 건반 뚜껑에 `ROMITHOFI` 같은 **가짜 브랜드 글자**. 1차 A2-3 과 같은 실패입니다
- **H6-1** 오른쪽 아래에 **가짜 서명**. 예뻤지만 남의 이름처럼 보이는 것을 팔 수는 없습니다
- **H3-3 · H4-1** 검은 바탕이 아니라 밝은 바탕으로 나왔습니다. 마스크로 못 씁니다

장식은 넣기 전에 **검정을 완전히 눌렀습니다**(`lutyuv` 로 45 아래를 0 으로).
미드저니의 "검정"은 실제로는 아주 어두운 회색이라, 그대로 마스크로 쓰면 종이 전체에
옅은 얼룩이 집니다.

**아직 안 만드신 것** — E(밝은 판 4) · F(아이 3) · I(무대 화면 4) · J(SNS 2),
그리고 다시 뽑기로 한 A4(빈 콘서트홀) · A7(겨울). 위 프롬프트 그대로 있습니다.


---

# 3차 — 아직 안 만드신 것 + 더 만들면 좋을 것

## 아직 안 만드신 것 (2차 때 남긴 것)

| 묶음 | 장수 | 무엇이 늘어나나 |
|---|---|---|
| **E · 밝은 판** | 4 | 포스터 4종. A4 를 까맣게 안 뽑아도 되니 **잉크값이 몇 배 줄어듭니다** |
| **F · 아이 · 사랑스러운** | 3 | 포스터 3종. 유아·저학년 발표회에 쓸 그림이 아직 벚꽃 하나뿐입니다 |
| **I · 무대 화면** | 4 | 무대 배경 14 → 18종 |
| **J · SNS** | 2 | 인스타 카드·스토리 |
| **A4 다시** | 4 | 빈 콘서트홀. 1차에서 만화 선화로 나왔습니다 |
| **A7 다시** | 4 | 겨울. 1차에서 청록색 방으로 나왔습니다 |

프롬프트는 위 「A. 포스터 주 그림」 · 「E」 · 「F」 · 「I」 · 「J」 절과
「다시 뽑아야 하는 둘」 절에 그대로 있습니다. 복사해 쓰시면 됩니다.

---

# 더 만들면 좋을 것 — K · L · M · N

지금 그림이 **포스터에만 몰려 있습니다.** 입장권·프로그램 표지·상장·무대 화면에는
쓸 그림이 거의 없습니다. 아래 넷이 그 자리를 메웁니다.

## 우선순위

| 순서 | 묶음 | 장수 | 왜 |
|---|---|---|---|
| **1** | M · 질감 2차 | 4 | 은박이 들어오면 **금박 한 줄만 있던 고급 라인이 두 줄**이 됩니다 |
| **2** | N · 표식 | 4 | **로고 없는 학원**이 많습니다. 기본 표식이 그 자리를 채웁니다 |
| 3 | K · 인쇄물 조각 | 3 | 입장권·프로그램 표지·X배너 |
| 4 | L · 무대 장면 | 3 | 대기 화면과 마지막 인사 화면 |

---

## M. 질감 2차 (`--ar 5:7`, 장식은 `--ar 1:1`)

### M1 · 은박 — 금박과 짝이 됩니다
```
a sheet of real silver leaf foil, crinkled metallic surface with cool bright highlights and
darker folds, macro texture, rich and even across the whole frame
--ar 1:1 --v 7 --style raw --stylize 120 --no text, letters, words, watermark, signature, objects
```

### M2 · 크라프트 종이 — 아이·자연 느낌 테마에
```
warm kraft paper texture, soft fibre grain, even lighting, extremely subtle and low
contrast, almost plain, nothing in the centre
--ar 5:7 --v 7 --style raw --stylize 100 --no text, letters, words, watermark, signature, objects, shadows
```

### M3 · 파스텔 종이 — 유아·저학년 인쇄물에
```
very pale blush pink paper with the faintest cloudlike gradient, soft and clean, extremely
low contrast, almost plain, nothing in the centre
--ar 5:7 --v 7 --style raw --stylize 100 --no text, letters, words, watermark, signature, objects, shadows
```

### M4 · 고운 리넨 — 1차 리넨은 결이 굵어 글씨를 방해했습니다
```
finely woven pale ivory linen, very tight even weave, soft diffused light, extremely subtle,
almost plain, no visible threads standing out
--ar 5:7 --v 7 --style raw --stylize 100 --no text, letters, words, watermark, signature, objects, shadows
```

---

## N. 표식 (`--ar 1:1`, 순검정 바탕)

**로고가 없는 학원이 많습니다.** 지금은 빈자리로 두거나 학원 이름만 적힙니다.
아래 표식이 그 자리에 들어가면 인쇄물이 완성돼 보입니다.

### N1 · 피아노 모노그램 — 기본 로고 자리를 채웁니다
```
an elegant minimal monogram mark, a grand piano silhouette enclosed in a thin circle, fine
gold line art, perfectly centred with generous empty space, on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 120 --no text, letters, words, watermark, signature, gradient background
```

### N2 · 메트로놈
```
an elegant metronome drawn in fine gold line art as a single simple icon, centred with
generous empty space, on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 120 --no text, letters, words, watermark, signature, gradient background
```

### N3 · 펼친 악보
```
an open sheet music book drawn in fine gold line art, simple and symmetrical, centred, on a
pure solid black background
--ar 1:1 --v 7 --style raw --stylize 120 --no text, letters, words, watermark, signature, notes on the staff, gradient background
```

### N4 · 음표 세 개
```
three simple musical notes in fine gold line art, sparse and elegant, arranged loosely in
the centre with empty space around, on a pure solid black background
--ar 1:1 --v 7 --style raw --stylize 120 --no text, letters, words, watermark, signature, gradient background
```

---

## K. 인쇄물 조각

### K1 · 입장권 띠 (`--ar 3:1`)
```
a slim horizontal band of dark polished piano wood with a single thin gold pinstripe running
along its length, extremely simple and elegant, nothing in the centre
--ar 3:1 --v 7 --style raw --stylize 150 --no text, letters, words, watermark, signature, people, faces
```

### K2 · 프로그램 표지 (`--ar 5:7`)
포스터와 달라야 합니다. 표지는 **물건 하나**가 조용히 놓여 있어야 합니다.
```
a closed grand piano lid seen from directly above, polished black lacquer with one soft
reflected highlight, minimal and abstract, the upper half is deep even darkness
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### K3 · X배너 (`--ar 1:3`)
```
a very tall narrow composition, a grand piano at the very bottom under a single warm
spotlight, the upper two thirds is deep empty darkness
--ar 1:3 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

---

## L. 무대 장면 (`--ar 16:9`)

### L1 · 대기 화면 — 연주회 시작 전 스크린에 띄웁니다
```
closed theatre curtains in deep burgundy seen straight on, warm footlights glowing along the
bottom edge, calm and symmetrical, the centre of the frame is even and unobstructed
--ar 16:9 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### L2 · 마지막 인사 — 폐회 화면
```
an empty stage after a performance, a single bouquet of flowers left on the piano bench,
warm fading light, tender and quiet, the centre of the frame calm
--ar 16:9 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### L3 · 봄 (사진) — 봄은 아직 수채 하나뿐입니다 (`--ar 5:7`)
```
a black grand piano beside a window with cherry blossom branches just outside, soft pink
morning light, fresh and gentle, the upper third of the frame is bright and empty
--ar 5:7 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

---

## 보내실 때

**파일 이름은 미드저니가 붙인 그대로 두시는 게 가장 좋습니다.** 2차 때 확인했는데,
프롬프트 내용이 이름에 들어 있어서 제가 자동으로 갈라 담습니다. 바꾸실 것 없습니다.

압축해서 릴리스에 올려 주세요. 태그만 `art3` 으로 새로 하나 만드시면 됩니다.

https://github.com/himan98hkt-prog/-/releases/new


---

# 4차 — 프로그램 화면용 그림 (P)

점검해 보니 **한 범주가 통째로 비어 있습니다.** 지금까지 만든 31장은 전부
**인쇄물·무대용**입니다. 프로그램 화면 자체를 위한 그림은 하나도 없습니다.

첫 화면을 웹사이트처럼 다시 짜면서 무대 배경(`stage/keys-wide.jpg`)을 빌려 썼는데,
그건 16:9 라 넓은 모니터에서 위아래가 잘립니다. 제자리 그림이 필요합니다.

그리고 **프로그램 아이콘이 아직 제가 코드로 그린 3KB 짜리**입니다. 바탕화면에 놓이는
그 아이콘이 제품의 첫인상인데, 지금은 거기서 티가 납니다.

| 순서 | 무엇 | 왜 |
|---|---|---|
| **1** | P6 앱 아이콘 | **바탕화면·시작 메뉴·작업 표시줄**에 놓입니다. 제품의 첫인상입니다 |
| **2** | P1 초광각 히어로 | 첫 화면. 지금은 16:9 를 늘려 쓰는 중입니다 |
| **3** | P7 설치 화면 배너 | 설치할 때 왼쪽에 세로로 들어갑니다. 지금은 회색 기본 그림입니다 |
| 4 | P8 시작 화면 | 프로그램이 켜지는 20초 동안 보여 드립니다. 지금은 빈 창입니다 |
| 5 | P2 · P3 히어로 | 밝은 판 · 시즌 특강 화면 |
| 6 | P4 · P5 | 「행사가 없습니다」 화면과 완료 축하 화면 |

---

### P6 · 앱 아이콘 — 가장 급합니다
작게 줄여도 알아볼 수 있어야 합니다. 가는 선과 잔 무늬는 32px 에서 뭉개집니다.
```
a flat vector app icon, one simple grand piano silhouette in warm gold centred on a deep
navy rounded square, extremely simple bold shapes, no gradients, no fine detail, designed
to stay readable at 32 pixels, generous margin around the shape
--ar 1:1 --v 7 --style raw --stylize 80 --no text, letters, words, watermark, signature, photorealism, thin lines, small details, drop shadow
```

### P1 · 초광각 히어로 (어두움)
```
an ultra wide cinematic view of a grand piano on a dark concert stage, warm side light,
deep shadows, the left half is vast empty dark space, quiet and premium
--ar 21:9 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### P7 · 설치 화면 세로 배너
```
a tall narrow vertical banner, deep navy background with a soft warm glow rising from the
bottom and a small grand piano silhouette near the bottom edge, the top two thirds is calm
empty dark space
--ar 1:2 --v 7 --style raw --stylize 200 --no text, letters, words, watermark, signature, people, faces
```

### P8 · 시작 화면 (프로그램이 켜지는 동안)
```
a calm dark image, a single warm spotlight falling on a closed grand piano seen from a
distance, very simple, the piano sits in the lower third and everything above is quiet
darkness
--ar 4:3 --v 7 --style raw --stylize 220 --no text, letters, words, watermark, signature, people, faces
```

### P2 · 초광각 히어로 (밝음)
```
an ultra wide bright airy music room, a black grand piano on the right, tall windows with
white curtains, soft daylight, the left half is bright and almost empty
--ar 21:9 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### P3 · 시즌 특강 히어로
```
an ultra wide warm view of a small piano classroom in soft afternoon light, an upright piano
on the right, simple and inviting, the left half quiet and empty
--ar 21:9 --v 7 --style raw --stylize 250 --no text, letters, words, watermark, signature, people, faces
```

### P4 · 「아직 행사가 없습니다」 화면
```
a simple elegant watercolour of an empty piano bench beside a closed piano, plenty of
untouched white paper, gentle and hopeful, plain white background
--ar 4:3 --v 7 --style raw --stylize 200 --no text, letters, words, watermark, signature, people, faces
```

### P5 · 완료 축하 화면
```
a watercolour of a grand piano with a few soft golden sparkles rising from it, celebratory
but restrained, plain white background, plenty of empty space
--ar 4:3 --v 7 --style raw --stylize 220 --no text, letters, words, watermark, signature, people, faces
```

---

## 지금까지 남아 있는 것 정리

| 묶음 | 장수 | 상태 |
|---|---|---|
| A1 · A2 · A3 · A5 · A6 · A8 | 8 | ✅ 들어감 |
| B · C | 7 | ✅ 들어감 |
| D · G · H | 16 | ✅ 들어감 |
| **A4 · A7 다시** | 8 | ⏳ 프롬프트 고쳐 드렸습니다 |
| **E · F · I · J** | 13 | ⏳ |
| **K · L · M · N** | 14 | ⏳ |
| **P** | 8 | ⏳ 새로 제안 |

전부 하실 것 없습니다. **P6(앱 아이콘) 한 장만 해도** 바탕화면에서 티가 납니다.


---

# 5차 — 실사 (R · T · U · S)

## 왜 AI 티가 났나 — 제 프롬프트 탓입니다

지금까지 드린 프롬프트를 세어 봤습니다.

| 무엇 | 몇 번 | 왜 문제인가 |
|---|---|---|
| `--stylize 250` | 23번 | 미드저니 기본값은 **100**입니다. 250 은 「예쁘게 꾸며라」를 두 배 반으로 올린 것입니다 |
| `--stylize 300` 이상 | 8번 | 더 심합니다 |
| `cinematic` `painterly` `glowing` `volumetric` | 12번 | 미드저니가 이 말들을 **「그림처럼 그려라」**로 받습니다 |

「고급스럽게」를 노리고 올린 값이 그대로 「AI 그림처럼」이 됐습니다.

---

## 실사 공식

실사는 **꾸미는 말을 빼고, 사진 찍는 말을 넣는 것**입니다.

```
[무엇이 어디에] , [어떤 빛],
shot on [카메라] with [렌즈], [필름], available light only, unretouched,
fine natural grain, [빈자리 지시]
--ar 5:7 --v 7 --style raw --stylize 50
--no illustration, digital art, painting, drawing, render, 3d, cgi, hdr,
oversaturated, glow, bloom, halo, plastic, airbrushed, text, letters, words,
watermark, signature, people, faces
```

**바꿔 쓸 말**

| 쓰지 마세요 | 대신 이렇게 |
|---|---|
| cinematic | documentary photograph · editorial photograph |
| painterly · artistic | shot on Kodak Portra 400 · colour negative scan |
| glowing · volumetric light | soft window light · late afternoon sun through a window |
| beautiful · stunning · epic | quiet · ordinary · plain |
| dramatic lighting | one lamp, available light only |
| perfect · flawless | unretouched · slight dust on the lid |

**세 가지 설정**

- `--stylize 50` (실사) · `--stylize 100` (약간 다듬음). **250 이상은 쓰지 마세요**
- `--style raw` 는 반드시 붙입니다 — 미드저니의 기본 「예쁨」을 끕니다
- **개인화(personalization, `--p`)가 켜져 있으면 끄세요.** 켜져 있으면 취향 쪽으로 끌려갑니다

**업스케일** — 뽑은 뒤 업스케일하실 때 **Subtle** 쪽을 쓰세요. Creative 는 없던
무늬를 만들어 넣어서 다시 AI 티가 납니다.

**`--sref` 주의** — 지금 들어가 있는 A1-4 를 `--sref` 로 쓰면 **그 AI 느낌이 그대로
따라옵니다.** 실사 세트는 R 중에서 가장 마음에 드는 것 하나를 골라 그것을 새 `--sref`
로 쓰세요.

**건반 요령** — 미드저니가 가장 자주 틀리는 것이 검은건반 묶음입니다. 건반을 **비스듬히,
또는 얕은 심도로 흐리게, 또는 화면 밖으로 잘리게** 두면 틀려도 티가 안 납니다.
정면에서 또렷하게 찍는 구도는 피하세요.

---

## R. 실사 포스터 (`--ar 5:7`)

기존 그림을 **버리는 게 아닙니다.** 수채·유화는 그 나름대로 쓸 자리가 있습니다.
실사판이 들어오면 「사진 쪽 / 그림 쪽」을 고르실 수 있게 됩니다.

공통 꼬리표를 `[실사]` 로 줄여 적습니다. 실제로는 이걸 붙이세요:

```
[실사] = --ar 5:7 --v 7 --style raw --stylize 50 --no illustration, digital art, painting, drawing, render, 3d, cgi, hdr, oversaturated, glow, bloom, halo, plastic, airbrushed, text, letters, words, watermark, signature, people, faces
```

### R1 · 무대 위 피아노
```
a grand piano standing alone on an empty concert hall stage, one stage light on from
above, the rest of the hall dark, shot on Canon EOS R5 with a 35mm f/1.4 lens at f/2,
available light only, unretouched, fine natural grain, the upper half of the frame is
plain darkness
[실사]
```

### R2 · 건반 (비스듬히, 얕은 심도)
```
close up of piano keys photographed from a low oblique angle, only a few keys in focus and
the rest falling out of focus, warm lamp light from the side, shot on Leica M11 with a 50mm
lens at f/1.4, Kodak Portra 400, unretouched, the top of the frame is plain dark wood
[실사]
```

### R3 · 아이의 손 (얼굴 없음)
```
a child's hands resting on piano keys photographed from behind and above, plain knitted
sleeve, afternoon window light only, shot on Fujifilm X-T5 with a 56mm lens at f/1.8,
Fujifilm Pro 400H, unretouched, no face in frame, soft empty area at the top
[실사] --no faces
```

### R4 · 빈 콘서트홀 — 1차·2차에서 계속 만화로 나왔던 것
```
the inside of an ordinary community concert hall photographed from the edge of the stage,
rows of empty seats, house lights half on, plain and undramatic, shot on Sony A7 IV with a
24mm lens at f/4, available light only, unretouched, slight noise in the shadows, the
ceiling area at the top is plain and empty
[실사]
```

### R5 · 무대 옆 커튼 틈
```
a gap between heavy stage curtains seen from the wings, a sliver of the lit stage beyond,
dust in the still air, shot on Canon EOS R5 with a 50mm lens at f/2, available light only,
unretouched, the left two thirds is plain dark fabric
[실사]
```

### R6 · 악보와 연필 (정물)
```
an open sheet music book on a piano music desk with a pencil laid across it, worn paper,
plain daylight from a window on the left, shot on Hasselblad 907X with an 80mm lens at
f/4, unretouched, quiet and ordinary, generous empty space above
[실사] --no notes on the staff, printed text
```

### R7 · 피아노 위 꽃다발
```
a small bunch of white flowers laid on the closed lid of a black upright piano, plain
daylight from a window, shot on Canon EOS R5 with an 85mm lens at f/2, Kodak Portra 400,
unretouched, the upper half of the frame is plain dark wall
[실사]
```

### R8 · 겨울 창가 — 1차에서 청록색 방으로 나왔던 것
```
a black upright piano beside a window on a winter afternoon, bare branches and snow
outside the glass, one warm lamp on in the room, plain white wall, shot on Sony A7 IV with
a 35mm lens at f/2, available light only, unretouched, the upper half is plain wall
[실사] --no green walls, ivy, vines, christmas decorations
```

### R9 · 여름 창가
```
a black grand piano beside an open window on a summer morning, thin white curtain moving,
green leaves outside, plain bright room, shot on Fujifilm X-T5 with a 23mm lens at f/2.8,
Fujifilm Pro 400H, available light only, unretouched, the upper third is bright and plain
[실사]
```

### R10 · 가을 오후
```
an upright piano in a plain room in late autumn afternoon light, a few dry leaves on the
floor near the window, long ordinary shadows, shot on Leica M11 with a 35mm lens at f/2,
Kodak Portra 400, unretouched, the upper half is plain wall in shadow
[실사]
```

---

## T. 실사 무대·영상 배경 (`--ar 16:9`)

가운데는 아이 사진과 이름 자리라 **비어 있어야** 합니다.

```
[실사16] = --ar 16:9 --v 7 --style raw --stylize 50 --no illustration, digital art, painting, render, 3d, cgi, hdr, oversaturated, glow, bloom, text, letters, words, watermark, signature, people, faces
```

### T1 · 무대 커튼 (실사)
```
heavy dark red stage curtains photographed straight on from the auditorium, house lights
low, plain and still, shot on Sony A7 IV with a 35mm lens at f/4, available light only,
unretouched, the centre of the frame is plain and unobstructed
[실사16]
```

### T2 · 건반 파노라마 (실사)
```
a piano keyboard running along the bottom of a wide frame, photographed from above at a
shallow angle so most keys fall out of focus, one warm lamp, shot on Canon EOS R5 with a
50mm lens at f/1.8, unretouched, everything above the keys is plain dark
[실사16]
```

### T3 · 객석 (실사)
```
rows of empty auditorium seats photographed from the stage, house lights half on, plain
and ordinary, shot on Sony A7 IV with a 24mm lens at f/4, available light only,
unretouched, the centre of the frame is calm
[실사16]
```

### T4 · 흰 벽과 빛 (밝은 화면용)
```
a plain white plastered wall with soft daylight falling across it from the left, nothing
else in the frame, shot on Hasselblad 907X with an 80mm lens at f/5.6, available light
only, unretouched, extremely simple
[실사16]
```

---

## U. 실사 정물 — 상장 · 입장권 · 프로그램 표지에 씁니다 (`--ar 5:7` 또는 `1:1`)

### U1 · 메트로놈 (정물)
```
an old wooden metronome standing on a plain wooden surface, plain grey wall behind, soft
daylight from the left, shot on Hasselblad 907X with an 80mm lens at f/5.6, unretouched,
generous empty space above
[실사]
```

### U2 · 피아노 페달 (발치)
```
the three brass pedals of a grand piano photographed close from the floor, worn brass and
dark wood, plain floor, one lamp, shot on Canon EOS R5 with a 50mm lens at f/2.8,
unretouched, the upper half is plain dark
[실사]
```

### U3 · 닫힌 피아노 뚜껑 (프로그램 표지용)
```
the closed lid of a black grand piano photographed from directly above, one soft reflection
of a window on the lacquer, nothing else, shot on Hasselblad 907X with an 80mm lens at f/8,
available light only, unretouched, extremely plain
[실사]
```

### U4 · 현과 해머 (안쪽)
```
the strings and hammers inside an open grand piano photographed from above, plain and
technical, one lamp, shot on Canon EOS R5 with a 100mm macro lens at f/5.6, unretouched,
no dramatic light
[실사] --ar 1:1
```

---

## S. 목업 — 상세페이지용 (있으면 좋은 것)

**빈 종이를 찍은 사진**입니다. 그 위에 우리가 만든 포스터를 제가 얹습니다.
「이렇게 나옵니다」를 평평한 JPG 로 보여 주는 것보다 **벽에 붙은 사진**이 훨씬 팔립니다.

프롬프트에서 가장 중요한 것은 **종이가 완전히 비어 있어야 한다**는 것입니다.

### S1 · 벽에 붙은 빈 A4
```
a completely blank white A4 sheet of paper taped flat on a plain painted wall,
photographed straight on, soft even daylight, shot on Sony A7 IV with a 50mm lens at f/5.6,
unretouched, the paper is empty white with nothing printed on it
--ar 4:5 --v 7 --style raw --stylize 50 --no text, letters, words, printing, pattern, illustration, drawing, watermark, signature, people
```

### S2 · 이젤 위 빈 액자
```
a plain wooden easel holding a simple frame with a completely blank white sheet inside,
standing in a plain room, soft daylight, shot on Canon EOS R5 with a 35mm lens at f/2.8,
unretouched, the sheet is empty white
--ar 4:5 --v 7 --style raw --stylize 50 --no text, letters, words, printing, pattern, illustration, drawing, watermark, signature, people
```

### S3 · 손에 든 빈 책자
```
two hands holding an open blank white booklet, plain background, soft daylight, shot on
Canon EOS R5 with a 50mm lens at f/2.8, unretouched, both pages are completely empty white
--ar 4:5 --v 7 --style raw --stylize 50 --no text, letters, words, printing, faces, illustration, watermark, signature
```

### S4 · 좌석 위에 놓인 빈 종이
```
a single blank white sheet of paper resting on a red auditorium seat, house lights low,
shot on Sony A7 IV with a 35mm lens at f/2, available light only, unretouched, the paper is
completely empty
--ar 4:5 --v 7 --style raw --stylize 50 --no text, letters, words, printing, pattern, illustration, watermark, signature, people
```

---

## 우선순위

| 순서 | 묶음 | 장수 | 왜 |
|---|---|---|---|
| **1** | R1 · R2 · R3 | 3 | 가장 많이 쓰이는 세 장의 실사판. 이것만으로 「사진 쪽」 포스터 세 종이 생깁니다 |
| **2** | R4 · R8 | 2 | 두 번 실패한 것들입니다. 실사 공식이면 나옵니다 |
| **3** | T1 · T2 | 2 | 무대 화면이 사진이 되면 연주회장 스크린에서 확 다릅니다 |
| 4 | R5~R7 · R9 · R10 | 5 | 포스터 다섯 종 더 |
| 5 | U1~U4 | 4 | 상장 · 입장권 · 프로그램 표지 |
| 6 | S1~S4 | 4 | 상세페이지 목업 |

**R1·R2·R3 세 장만 먼저 보내 주셔도** 차이를 바로 보실 수 있습니다.
그 셋을 보고 나서 나머지를 뽑으시는 편이, 스물두 장을 한 번에 뽑고 나서
「전부 다시」가 되는 것보다 낫습니다.


---

# 6차 — 일러스트 컨셉 (V · W)

지금 포스터 그림 12장 중 **일러스트는 3장뿐**입니다(수채 둘, 밝은 사진 하나).
사진 쪽이 아홉 장이라 한쪽으로 크게 기울어 있습니다.

일러스트는 사진과 달리 **AI 티가 원천적으로 안 납니다.** 사람이 그린 것과 구분할
이유가 없기 때문입니다. 그래서 실사와 함께 가는 반대편 기둥으로 세우면 좋습니다.

아래 열둘은 **서로 확실히 다른 그림체**입니다. 한 컨셉이 곧 한 갈래의 얼굴이 됩니다.

공통 꼬리표:

```
[일러] = --ar 5:7 --v 7 --style raw --stylize 180
--no photo, photograph, photorealistic, 3d, render, cgi, text, letters, words,
watermark, signature, people, faces
```

---

## W. 테마 색을 입는 선화 — 이것부터 하세요

**한 장이 테마 108종 색으로 다 나옵니다.**

검은 바탕에 금선으로 그리면, 프로그램이 검정을 뚫어 내고 **그 자리를 테마 강조색으로
칠합니다.** 남색 테마에서는 남색 피아노가, 버건디 테마에서는 버건디 피아노가 됩니다.
상장 월계관에 이미 쓰고 있는 방식인데, 포스터 크기로 키우면 훨씬 큽니다.

```
[테마색] = --ar 5:7 --v 7 --style raw --stylize 120
--no text, letters, words, watermark, signature, gradient background, photo, 3d,
shading, colour fill, people, faces
```

### W1 · 그랜드피아노 정면
```
a large elegant grand piano drawn in fine gold line art seen from the front, symmetrical,
occupying the lower half of the frame, on a pure solid black background, the upper half
completely empty black
[테마색]
```

### W2 · 건반과 흐르는 음표
```
a piano keyboard drawn in fine gold line art running across the lower third of the frame,
a few musical notes drifting upward from it, on a pure solid black background, the upper
two thirds completely empty black
[테마색]
```

### W3 · 아치와 피아노
```
a tall classical arch drawn in fine gold line art framing an empty space, a small grand
piano in the same fine gold line at its base, on a pure solid black background, everything
inside the arch is empty black
[테마색]
```

---

## V. 일러스트 컨셉 열둘

대부분 **흰 바탕**으로 그리게 했습니다. 흰 바탕이면 프로그램이 종이색을 비쳐 보이게
겹칠 수 있어서, 미색 테마에서는 미색 종이에 그린 것처럼 나옵니다.

### V1 · 한 줄 선화
```
a single continuous line drawing of a grand piano, one unbroken elegant black line, no
shading and no fill, on a plain white background, the piano sits low in the frame with
generous empty space above
[일러] --stylize 100
```

### V2 · 펜화 해칭
```
a detailed pen and ink drawing of a grand piano with fine cross hatching, black ink on
white paper, engraving style linework, no colour, the piano in the lower half, plain empty
white above
[일러]
```

### V3 · 빈티지 동판화
```
a nineteenth century copperplate engraving of a grand piano, fine parallel line shading,
sepia ink on aged cream paper, antique concert programme illustration, the piano centred
low, plain empty space above
[일러]
```

### V4 · 아르데코 (1920년대 공연 포스터)
```
a 1920s art deco concert poster illustration of a grand piano, flat geometric shapes, only
three colours — deep navy, gold and cream, strong symmetry, bold simple forms, a generous
empty band across the top
[일러] --stylize 220
```

### V5 · 아르누보
```
an art nouveau illustration of a grand piano framed by flowing organic lines and stylised
lilies, muted olive gold and cream, elegant curved border, flat colour, empty space at the
top
[일러] --stylize 220
```

### V6 · 리소그래프 2도 인쇄
```
a two colour risograph print of a grand piano, warm red and deep blue inks slightly
misregistered, visible paper grain and ink texture, flat simple shapes, plain paper
background, empty space above
[일러]
```

### V7 · 미니멀 기하 (바우하우스)
```
a minimal geometric illustration of a grand piano built from simple flat shapes, bauhaus
style, three flat colours on a plain off white background, no gradients and no outlines, a
large empty area at the top
[일러] --stylize 150
```

### V8 · 수묵담채 — 우리 시장에서 가장 차별됩니다
```
a korean ink wash painting of a grand piano, soft grey brush strokes with a single touch of
pale colour, wet brush bleeding into rice paper, plenty of untouched white paper, minimal
and calm
[일러] --no black outline, cartoon, heavy detail
```

### V9 · 종이 오리기
```
a layered paper cut illustration of a grand piano, cream and soft gold papers with subtle
shadows between the layers, clean cut edges, plain white background, empty space at the top
[일러]
```

### V10 · 크레용 (유아·저학년)
```
a children's crayon and coloured pencil drawing of a small piano with a few notes floating
above it, waxy crayon texture, soft pastel colours, plain cream paper, simple and warm,
empty space at the top
[일러]
```

### V11 · 스테인드글라스
```
a stained glass window design showing a grand piano, bold black leading lines and jewel
toned glass in amber blue and green, symmetrical, completely flat, plain dark surround
[일러] --stylize 220
```

### V12 · 보태니컬 라인
```
a botanical illustration of a grand piano surrounded by delicately line drawn leaves and
small flowers, fine ink lines with soft muted watercolour washes, plain white background,
empty space at the top
[일러]
```

---

## 우선순위

| 순서 | 무엇 | 왜 |
|---|---|---|
| **1** | **W1 · W2 · W3** | **한 장이 테마 108종 색으로 나옵니다.** 장당 효과가 압도적입니다 |
| **2** | V1 · V3 · V8 | 서로 가장 멀리 떨어진 셋 — 현대 선화 / 고전 동판화 / 수묵 |
| **3** | V4 · V6 · V10 | 아르데코(격식) · 리소(트렌디) · 크레용(아이) |
| 4 | V2 · V5 · V7 · V9 · V11 · V12 | 갈래가 더 필요할 때 |

**W 셋만 먼저** 보내 주셔도 좋습니다. 테마를 바꿀 때마다 포스터 색이 같이 바뀌는 것을
보시면, 나머지를 어디에 쓸지 감이 훨씬 빨리 잡히실 겁니다.

## 보내실 때

지금까지와 같습니다. **파일 이름은 미드저니가 붙인 그대로** 두시고, 압축해서 릴리스에
`art4` 같은 새 태그로 올려 주세요. 이름에 프롬프트가 들어 있어 제가 자동으로 갈라 담습니다.

https://github.com/himan98hkt-prog/-/releases/new


---

## 4차 결과 — 63장 중 15장

| 자리 | 파일 | 고른 것 · 이유 |
|---|---|---|
| 선화 | `line/piano-front.png` | W1-3 · 위 38% 가 비어 제목이 앉습니다 |
| 선화 | `line/keys-notes.png` | W2-1 · W2-4 는 가짜 서명이 있어 뺐습니다 |
| 선화 | `line/arch.png` | W3-1 · 아치 안이 통째로 비어 제목이 그 안에 들어갑니다 |
| 일러스트 | `poster/line-piano.jpg` | V1-1 |
| 일러스트 | `poster/engraving.jpg` | V3-1 · 19세기 동판화. 악보가 비어 있어 글자 걱정이 없습니다 |
| 일러스트 | `poster/riso.jpg` | V6-2 |
| 일러스트 | `poster/ink-wash.jpg` | V8-2 · **V8-1·3·4 는 가짜 한글 낙관**(「일러스코툴」)이 찍혀 뺐습니다 |
| 일러스트 | `poster/deco.jpg` | V4-1 · V4-2 에는 피아노에 실제 상표명이 읽혀 뺐습니다 |
| 사진 | `poster/real-stage.jpg` | R1-2 |
| 사진 | `poster/real-keys.jpg` | R2-2 |
| 사진 | `poster/real-hands.jpg` | R3-1 |
| 프로그램 | `app/hero-wide.jpg` | P1-1 · 첫 화면 |
| 프로그램 | `app/icon.png` | P6-2 · **앱 아이콘** |
| 프로그램 | `app/installer-side.jpg` | P7-2 · 설치 창 왼쪽 |
| 프로그램 | `app/splash.jpg` | P8-2 · 켜지는 동안 (아직 화면에는 안 붙였습니다) |

**해상도가 1648×2944 로 왔습니다** — 업스케일까지 해 주셔서 A4 199dpi 입니다.
인쇄소에 넘기셔도 됩니다.

**만들면서 배운 것** — 일러스트를 「담아서」 넣었더니 그림의 종이 질감 때문에
**네모 이음매**가 보였습니다. 흰색으로 밀어 봐도 남아서, 결국 **통째로 채우는** 쪽으로
바꿨습니다. 그림의 종이가 곧 포스터 종이가 되고 글 자리만 흰 막으로 눌러 줍니다.
