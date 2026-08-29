# 그림 만들기 — 미드저니 프롬프트 모음

인쇄물과 무대 화면에 들어갈 **그림을 밖에서 만들어 넣기 위한** 문서입니다.

직접 그린 SVG 그림(피아노·건반·아치…)은 인쇄물에서 어설퍼 보여 **전부 걷어냈습니다.**
그 자리에 미드저니로 만든 그림을 넣습니다. 아래 프롬프트를 그대로 복사해 쓰시면 됩니다.

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
