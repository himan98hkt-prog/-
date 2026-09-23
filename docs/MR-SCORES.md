# 악보를 어디서 구하나 — 그리고 무엇을 팔 수 있나

콩쿨 곡 목록은 [`MR-REPERTOIRE.md`](MR-REPERTOIRE.md) 에 있습니다. 이 문서는
**그 곡의 악보 파일을 어디서 구하고, 그중 무엇으로 만든 반주를 팔 수 있는지**를
다룹니다.

---

## 먼저 — 「무료 다운로드」와 「무료로 쓸 수 있다」는 다릅니다

악보 하나에 권리가 **세 겹**으로 붙습니다.

| 겹 | 무엇 | 부르크뮐러 25번의 경우 | 누가 보나 |
|---|---|---|---|
| ① **곡** | 작곡가의 저작권 | 1858년 사망 → **만료** | `piano_mr/repertoire.py` |
| ② **판본** | 운지·페달을 붙인 출판사 편집 | 헨레·피터스 판은 **살아 있음** | 사람 |
| ③ **입력본** | 그 악보를 컴퓨터에 쳐 넣은 사람 | 파일마다 다름 | `piano_mr/provenance.py` |

①만 보고 「만료된 곡이니 괜찮겠지」 하면 ③에서 걸립니다. **곡이 만료돼도 그
파일에 붙은 약정은 따로 돌아갑니다.**

## 그런데 우리가 파는 것은 악보가 아닙니다

우리가 파는 것은 **프로그램**과, 만료된 곡에 우리 엔진이 붙인 **반주**입니다.
그 반주의 화성·편곡은 우리 것입니다. 악보 원본은 꾸러미에 들어가지도 않습니다
(`export_static` 이 `scores/` 를 뺍니다 — 지시서 7장).

그래서 **입력본만 깨끗하면 나머지는 전부 우리 것**입니다. 이 문서가 다루는 것이
그 「입력본만 깨끗하면」입니다.

---

## 어디서 받나

### 팔 수 있는 것

| 곳 | 주는 형식 | 조건 | 메모 |
|---|---|---|---|
| **OpenScore** (openscore.cc) | MusicXML | **CC0 — 권리 포기** | 가장 깨끗합니다. 자원봉사자들이 만료곡을 쳐 넣고 권리를 아예 포기한 것 |
| **Mutopia** (mutopiaproject.org) | MIDI · LilyPond · PDF | **곡마다 표시** | 2천여 곡. 곡마다 라이선스가 적혀 있으니 보고 고르면 됩니다. MIDI 로 바로 들어갑니다 (아래) |
| **IMSLP** (imslp.org) | 대부분 **PDF 스캔** | 만료 판본은 자유 | 세상에서 제일 큰 창고. 체르니·바이엘·부르크뮐러 **원판이 다 있습니다.** 인식 단계가 필요합니다 (아래) |
| **공유마당** (gongu.copyright.or.kr) | 다양 | 만료저작물·공공저작물 | 한국저작권위원회 |
| **직접 인식** | MusicXML | **결과물이 원장님 것** | 라이선스로는 제일 깨끗합니다 |

### 개발·시험용으로만 (팔면 안 됨)

| 곳 | 왜 안 되나 |
|---|---|
| **kernScores** (github.com/craigsapp/…) | `CC BY-NC-SA` — **비영리.** 베토벤 소나타 전곡·모차르트·스카를라티·쇼팽 등 385곡이 있고 music21 이 `.krn` 을 바로 읽지만, 파는 제품에는 못 씁니다 |
| **music21 코퍼스** | 코퍼스 자신의 `license.txt` 가 *"Some encodings … may not be used for commercial uses"* 라고 하면서 **어느 것인지는 알려 주지 않습니다** |
| **MuseScore.com 커뮤니티 악보** | 올린 사람마다 조건이 다릅니다. 만료곡인데도 「All rights reserved」로 올려 둔 것이 많아 한 곡씩 확인해야 합니다 |
| **piano-midi.de · Kunst der Fuge** | 연주 MIDI 라 박자가 사람 손 그대로입니다. 마디 정렬이 틀어져 **엔진과 애초에 안 맞습니다** |

> **`SA`(동일조건변경허락)는 팔 수는 있지만 값이 따릅니다.** 그것으로 만든
> 반주도 같은 조건으로 풀어야 해서, 남이 그대로 재배포해도 막을 수 없습니다.
> 꾸러미를 만들 때 경고가 뜹니다.
>
> **`ND`(변경금지)는 상업적 사용을 허용해도 우리한테는 막힌 것입니다.** 반주를
> 붙이는 행위 자체가 2차적 저작물이라서입니다.

---

## 프로그램이 이걸 기억합니다

악보를 넣을 때 출처를 같이 적습니다.

```bash
python3 catalog_cli.py import burgmuller01.musicxml \
    --title "부르크뮐러 25-1 솔직한 마음" --book "부르크뮐러 25" --public-domain \
    --score-source "OpenScore" --score-license cc0
```

`--score-license` 를 안 적으면 **`unknown`** 이고, `unknown` 은 **판매용 꾸러미에
안 들어갑니다.** 모르는 것을 넘겨주는 쪽이 위험하기 때문입니다.

쓸 수 있는 값: `own` `omr` `cc0` `pd` `cc-by` `cc-by-sa` `cc-by-nd`
`cc-by-nc` `cc-by-nc-sa` `cc-by-nc-nd` `unknown`

꾸러미를 만들면 무엇이 빠졌는지 말해 줍니다.

```
$ python3 catalog_cli.py package ../dist/반주
  곡 20개 · 파일 33개 · 전체 134 KB

  판매용이라 9곡을 뺐습니다 — 입력본(악보 파일) 출처 때문입니다. 곡 자체는 만료됐습니다.
    · 바흐 평균율 1권 1번 전주곡 — 출처 확인 안 됨 (music21 코퍼스)
    …
    학원에서만 쓰실 거면 --personal 을 붙이면 전부 담깁니다.
```

**`--personal`** 은 파는 게 아니라 이 학원에서만 쓸 때입니다. 전부 담깁니다.

---

## IMSLP 원판을 직접 인식하기 (무료)

교재류(체르니·바이엘·부르크뮐러)는 콩쿨에서 제일 많이 쓰이는데 **하필 무료
MusicXML 이 제일 없는 쪽**입니다. 국내 출판사 편집판으로 도는 게 대부분이라
그건 ②에 걸립니다.

그래서 **IMSLP 에서 만료된 원판 PDF 를 받아 직접 인식하는 것**이 제일 깨끗합니다.
인식 결과물은 원장님 것이라 ③이 안 생깁니다.

**Audiveris** 는 오픈소스 악보 인식기이고 무료입니다. 원장님 PC 에서 돌고,
악보가 밖으로 안 나갑니다.

### ① 설치

[releases 페이지](https://github.com/Audiveris/audiveris/releases)의 **Assets** 에서
내려받습니다. 파일 이름은 `Audiveris-<판>-<OS>-<아키텍처>` 꼴입니다.

**자바는 따로 안 깔아도 됩니다.** 5.5판부터 설치 파일에 JRE 가 같이 들어 있습니다
(소스에서 직접 빌드할 때만 JDK 25 가 필요합니다 — `gradle.properties` 의
`theMinJavaVersion`).

| OS | 파일 | 명령으로 설치하려면 |
|---|---|---|
| **윈도** | `.msi` (x86_64) | `winget install Audiveris` · `scoop install audiveris` |
| **맥** | `.dmg` — `arm64` 와 `x86_64` 가 **따로** 있습니다 | — |
| **리눅스** | `.deb` — 우분투 22.04 / 24.04 용이 따로 | Flathub 의 flatpak |

> **윈도는 `windowsConsole` 이 든 `.msi` 를 고르세요.** 설치 파일이 두 가지인데,
> 그냥 `windows` 쪽은 화면만 띄우고 콘솔이 없습니다. 우리는 이걸 **명령줄로 돌려
> 그 출력을 읽어** 실패 이유를 보여 주므로, 콘솔 없는 쪽을 깔면 안 될 때 이유가
> 안 보입니다.
>
> `.msi` 를 직접 받아 설치하면 윈도가 「알 수 없는 앱」 경고를 냅니다. `winget`
> 으로 설치하면 그 경고가 안 뜹니다.

**글자 인식(OCR) 언어는 설치 파일에 안 들어 있습니다.** 처음 실행하면 Audiveris
가 직접 물어보고 받아 옵니다 — 우리가 할 일은 없습니다.

### ② 프로그램에 알려 주기

```bash
export MR_OMR_PROVIDER=local
export MR_OMR_LOCAL_CMD="<설치된 실행 파일>"   # 경로에 이미 잡혀 있으면 생략
```

설치 뒤 실행 파일이 놓이는 자리:

| OS | 경로 |
|---|---|
| 윈도 | `C:\Program Files\Audiveris\Audiveris.exe` |
| 리눅스 | `/opt/audiveris/bin/Audiveris` |
| 맥 | `/Applications/Audiveris.app` 안의 실행 파일 |

### ③ 쓸 수 있는 상태인지 먼저 확인

```bash
python3 catalog_cli.py omr
```

실행 파일을 찾고 `-version` 을 물어봐서 판까지 알려 줍니다. **여기서 통과해야
올리기 화면이 이걸 씁니다.** 못 찾으면 어디에 경로를 넣어야 하는지 말해 줍니다.

그 다음부터는 PDF 올리기 화면이 그대로 돌아갑니다. 인식이 끝나면 **PDF 는 바로
지웁니다** (지시서 7장 — 검사가 못 박습니다).

인식된 곡을 넣을 때는 `--score-license omr` 로 적으면 판매용 꾸러미에 들어갑니다.

| | |
|---|---|
| 비용 | **0원** (신청제·유료 API 와 달리) |
| 속도 | 한 쪽에 10~60초 |
| 정확도 | 90~95% (지시서 2.2) — 어차피 화성 확인 화면을 보셔야 합니다 |
| 악보 유출 | **없음** — 이 PC 밖으로 안 나갑니다 |

> `MR_OMR_LOCAL_ARGS` 로 Audiveris 에 인자를 더 넘길 수 있습니다
> (예: `-sheets 1-4` 로 쪽 고르기). `MR_OMR_LOCAL_TIMEOUT` 은 기본 900초.

---

## MIDI 로 받기

Mutopia 처럼 **곡마다 라이선스를 밝히는** 사이트가 MusicXML 이 아니라 MIDI 로
주는 경우가 많습니다. LilyPond 에서 기계적으로 뽑은 MIDI 라 박자가 정확해서
엔진에 잘 맞습니다 — 사람이 친 연주 MIDI 와 다릅니다.

실측: 같은 왈츠를 MusicXML 과 MIDI 로 읽었을 때 화성이 **완전히 같았습니다.**
온셋을 ±0.25박 흔들어도 8/8 일치했습니다 (music21 이 양자화합니다).

### 박자표가 없는 MIDI 는 거절합니다

**music21 은 박자표가 없는 MIDI 에 4/4 를 지어 넣습니다.** 3/4 왈츠를 그렇게
받으면

```
박자 4/4 · 8마디 → 6마디
화성 C G7 C F C G7 C C  →  C Bdim C Em F Am Am C Bdim C C
```

이 되는데 **오류가 하나도 안 납니다.** 반주는 멀쩡하게 만들어지고 틀린 것은
발표회 당일에 드러납니다.

파싱된 결과만 봐서는 진짜 4/4 와 지어낸 4/4 를 구분할 수 없어서, 원본 바이트를
직접 읽는 검사기를 따로 썼습니다 (`piano_mr/midifile.py` — `pdf.py` 가 쪽수를
「못 세면 추측하지 않고 거절」하는 것과 같은 이유입니다).

박자를 아시면 알려 주시면 됩니다.

```bash
python3 catalog_cli.py import waltz.mid --title "왈츠" --public-domain --time 3/4
```

한 번 알려 준 박자는 카탈로그에 남아서(`time_locked`) 다시 분석할 때 또 묻지
않습니다.

---

## 요약 — 곡 하나를 넣는 경로

```
만료된 곡인가?  ──아니오──→  안 넣습니다 (repertoire.check 가 막습니다)
     │예
     ▼
악보 파일이 있나?
     │
     ├─ OpenScore / Mutopia 에 있다   → 받아서 --score-license cc0 (또는 곡에 적힌 값)
     ├─ IMSLP 에 PDF 만 있다          → Audiveris 로 인식 → --score-license omr
     └─ 아무 데도 없다                 → 직접 입력 → --score-license own
```

관련 파일: [`piano_mr/provenance.py`](../mr/piano_mr/provenance.py) ·
[`piano_mr/midifile.py`](../mr/piano_mr/midifile.py) ·
[`piano_mr/omr.py`](../mr/piano_mr/omr.py) ·
검사 `tests/test_provenance.py` · `tests/test_midifile.py` · `tests/test_omr_local.py`
