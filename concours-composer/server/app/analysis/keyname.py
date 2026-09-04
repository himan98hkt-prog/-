"""조성 이름을 **music21 이 받는 모양**으로 고친다.

원장님 화면에 이것이 떴다:

    AccidentalException: ajor is not a supported accidental type
    우리 코드 마지막 자리 — generation/assemble.py:126 에서 (assemble)

곡을 다 만들고 **악보로 조립하는 마지막 자리**에서 터진 것이다. 돈은 이미 다
나갔고 곡은 한 마디도 못 건졌다 — 원장님이 "비용만 날린 것 같다" 고 하신 그 자리다.

원인은 한 줄이다. music21 은 조성을 `"C"`(장조) 나 `"c"`(단조) 로 받는데, 모델은
사람이 쓰는 대로 `"C major"`·`"a minor"`·`"Bb major"` 로 준다. 그러면 music21 이
`"C"` 를 읽고 남은 `" major"` 를 임시표로 해석하려다 죽는다.

    key.Key("C major")   → AccidentalException: ' ajor' is not supported
    key.Key("Bb major")  → AccidentalException: 'b ajor' is not supported

모델에게 "짧게 쓰라" 고 프롬프트로 부탁하는 것만으로는 부족하다. 언젠가 또 길게
쓸 것이고, 그때 또 곡을 잃는다. **받는 쪽에서 고쳐 받는다** — 이것이 우리가
통제할 수 있는 유일한 자리다.
"""
from __future__ import annotations

import re

# 사람이 쓰는 조표 표기 → music21 표기. music21 은 플랫을 '-' 로 쓴다.
_FLAT = {"b": "-", "♭": "-", "-": "-"}
_SHARP = {"#": "#", "♯": "#"}

# 한국어 표기도 받는다. 원장님이나 프롬프트가 이렇게 쓸 수 있다.
_KO_MODE = {"장조": "major", "단조": "minor"}
# 다·라·마… 계이름. 콩쿨 서류에는 이렇게 적히는 일이 많다.
_KO_TONIC = {
    "다": "C", "라": "D", "마": "E", "바": "F", "사": "G", "가": "A", "나": "B",
}
_KO_ALTER = {"올림": "#", "내림": "-"}

_MAJOR = ("major", "maj", "dur", "장조")
_MINOR = ("minor", "min", "moll", "단조", "m")


def normalize_key(raw: str, *, default: str = "C") -> str:
    """무엇이 오든 music21 이 받는 조성 문자열로 바꾼다.

    장조는 대문자 으뜸음(`"C"`), 단조는 소문자(`"c"`) 다. 이것이 music21 의 규칙이다.

    >>> normalize_key("C major")
    'C'
    >>> normalize_key("a minor")
    'a'
    >>> normalize_key("Bb major")
    'B-'
    >>> normalize_key("F# minor")
    'f#'
    >>> normalize_key("내림마장조")
    'E-'

    읽을 수 없으면 `default` 를 돌려준다. **여기서 예외를 던지면 안 된다** —
    조성 이름 하나 때문에 다 만든 곡을 잃는 것이 바로 고치려는 문제이기 때문이다.
    """
    text = (raw or "").strip()
    if not text:
        return default

    # 한국어 표기를 먼저 영어로 옮긴다("내림마장조" → "E- minor" 꼴).
    ko = _from_korean(text)
    if ko:
        text = ko

    # **대소문자를 지우기 전에 원래 모양을 남긴다.**
    #
    # music21 은 `"a"` 를 가단조, `"A"` 를 가장조로 읽는다. 그것이 규칙이다. 그런데
    # 여기서 곧바로 소문자로 바꿔 버리고 마지막에 `.upper()` 를 하고 있었다. 그래서
    # 화면의 조성 목록에 있는 a·e·d·b(단조)를 고르셔도 **전부 장조로 바뀌어** 나갔다.
    # 단조를 부탁하고 장조를 받으면 곡의 성격이 통째로 달라진다.
    cased = text
    low = text.lower()
    # 장·단조를 먼저 떼어 낸다. 남는 것이 으뜸음이다.
    #
    # **떼어 내기 전에** 장조라고 적으셨는지를 먼저 본다. 떼어 낸 뒤에 찾으면 이미
    # 지워진 뒤라 못 찾는다 — 그러면 "a major" 가 소문자 a 때문에 단조로 뒤집힌다.
    has_major = any(
        re.search(rf"(?:\b|\s){re.escape(w)}\b|{re.escape(w)}$", low) for w in _MAJOR
    )
    is_minor = False
    for word in _MINOR:
        if re.search(rf"(?:\b|\s){re.escape(word)}\b", low) or low.endswith(word):
            # "C m" 처럼 한 글자 m 은 뒤에 붙었을 때만 단조로 본다.
            if word == "m" and not re.search(r"[a-g][#\-b♭♯]?\s*m$", low):
                continue
            is_minor = True
            break
    for word in (*_MAJOR, *_MINOR):
        low = re.sub(rf"(?:\b|\s){re.escape(word)}\b|{re.escape(word)}$", " ", low)
    head = low.strip()

    m = re.match(r"^([a-g])\s*([#♯b♭\-]?)", head)
    if not m:
        return default
    step, mark = m.group(1).upper(), m.group(2)
    alter = _SHARP.get(mark, "") or _FLAT.get(mark, "")

    # 장·단조를 글로 안 적으셨으면 **원래 대소문자**가 답이다(music21 규칙).
    #   "a" → 가단조 · "A" → 가장조 · "b-" → 내림나단조 · "B-" → 내림나장조
    if not is_minor and not has_major:
        head_at = cased.lower().find(m.group(1))
        if head_at >= 0 and cased[head_at].islower():
            is_minor = True

    # 단조는 소문자다 — music21 이 그렇게 구분한다.
    return (step.lower() if is_minor else step) + alter


def _from_korean(text: str) -> str:
    """'내림마장조' · '다단조' 같은 표기를 영어 꼴로."""
    if not any(ch in text for ch in "다라마바사가나"):
        return ""
    alter = ""
    body = text
    for word, mark in _KO_ALTER.items():
        if body.startswith(word):
            alter = mark
            body = body[len(word):]
            break
    if not body:
        return ""
    tonic = _KO_TONIC.get(body[0])
    if not tonic:
        return ""
    mode = ""
    for word, eng in _KO_MODE.items():
        if word in body:
            mode = eng
            break
    return f"{tonic}{alter} {mode}".strip()
