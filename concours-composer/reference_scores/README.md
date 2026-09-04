# 참고 콩쿨곡 폴더

여기에 **MusicXML(.musicxml/.xml/.mxl)** 이나 **MIDI(.mid/.midi)** 를 넣어 두면
서버가 시작할 때 자동으로 읽어 코퍼스에 등록한다. 등록된 곡은

- 요청마다 비슷한 곡을 찾아 작곡 프롬프트에 **스타일 컨텍스트**로 들어가고,
- 표절 n-gram 검사의 대조 대상이 되며,
- 원장이 매긴 난이도가 있으면 난이도 보정 표본이 된다.

수동으로 다시 훑으려면:

```bash
.venv/bin/python scripts/import_scores.py            # 새 파일만
.venv/bin/python scripts/import_scores.py --all      # 전부 다시
```

## 저작권 — 기본값이 안전한 쪽이다

파일 옆에 같은 이름의 `.json` 을 두지 않으면 **`copyrighted` 로 간주**한다.
저작권곡은 통계(StyleProfile)만 뽑고 **음표열을 보관하지 않으며 어떤 프롬프트에도
넣지 않는다**(CLAUDE.md 절대 규칙 3, tests/test_copyright_guard.py 로 고정).

퍼블릭 도메인임이 확실한 악보만 다음처럼 표시한다.

```
burgmuller_op100_no2.musicxml
burgmuller_op100_no2.json
```

```json
{
  "title": "아라베스크",
  "composer": "Burgmüller",
  "copyright_status": "public_domain",
  "era": "romantic",
  "division_tags": ["초등 저학년부"],
  "teacher_difficulty": 3.5,
  "source": "IMSLP"
}
```

`copyright_status` 는 `public_domain` · `licensed` · `copyrighted` 중 하나다.
확실하지 않으면 적지 마라 — 적지 않는 것이 안전한 쪽이다.

## 폴더로 부문을 나눠도 된다

```
data/reference_scores/
  초등저학년부/…
  중등부/…
```

하위 폴더 이름은 `division_tags` 에 자동으로 들어간다.
