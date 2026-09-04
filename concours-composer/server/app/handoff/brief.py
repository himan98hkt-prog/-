"""**작곡 의뢰서** — 원장님이 성격만 고르시면 나머지는 프로그램이 채운다.

원장님 말씀:

    "프로픔트를 구체적으로 만드는 것이 문제인데..."

맞다. 그리고 그 문제는 원장님이 푸실 문제가 아니다. 급수마다 손 크기가 몇 도이고,
빠르기 상한이 얼마이고, 제한 시간이 몇 초이고, 검증기가 무엇을 떨어뜨리는지는
**코드 안에 이미 다 적혀 있다.** 원장님이 그걸 외워서 글로 옮기실 이유가 없다.

여기서 만드는 것은 **한 장짜리 의뢰서**다. 이 의뢰서 한 장이면 대화창 어디에
붙여 넣어도 같은 곡이 나온다 — 규정이 빠짐없이 들어 있기 때문이다.

의뢰서에 반드시 들어가는 것:

  1. **누가 치는가** — 손이 닿는 음정, 음역, 무대에서 흔들리지 않는 빠르기, 악보 읽기
  2. **대회 규정** — 부문, 제한 시간, 창작곡 허용 여부
  3. **성격** — 형식·박자·빠르기·조성 후보, 이 성격이 드러내는 것, 피할 것
  4. **하드 규칙** — 어기면 **저장되지 않는** 것들. 미리 알려 주어야 헛일이 없다
  5. **원장님의 바람** — 여기만 원장님이 쓰신다
  6. **돌려줄 형식** — 프로그램이 그대로 읽을 수 있는 JSON

마지막 항목이 중요하다. 곡이 아무리 좋아도 프로그램이 못 읽으면 곡집도 꾸러미도
저작권 서류도 못 만든다. 그래서 형식을 **예시까지 붙여** 못박는다.
"""
from __future__ import annotations

from app.generation.context import ComposerContext
from app.generation.presets import Preset

# 마디 하나의 생김새. 스키마를 글로 설명하는 것보다 **보여 주는 쪽**이 어긋나지 않는다.
EXAMPLE_MEASURE = """{
  "number": 1,
  "rh": [{"voice": 1, "events": [
      {"dur": 0.5, "pitches": ["G4"], "artic": "staccato"},
      {"dur": 0.5, "pitches": ["C5"]},
      {"dur": 1.0, "pitches": ["E5"], "slur": "start"},
      {"dur": 2.0, "pitches": ["D5"], "slur": "stop"}]}],
  "lh": [{"voice": 1, "events": [
      {"dur": 2.0, "pitches": ["C3", "G3"]},
      {"dur": 2.0, "pitches": ["E3"]}]}],
  "dynamics": "mf",
  "pedal": false
}"""


def _minutes(sec: int | None) -> str:
    if not sec:
        return "제한 없음"
    return f"{sec}초(약 {sec // 60}분 {sec % 60}초)"


def build_brief(
    ctx: ComposerContext,
    preset: Preset | None,
    *,
    tier_name: str = "",
    wish: str = "",
    measures_hint: int = 0,
) -> str:
    """대화창에 그대로 붙여 넣을 의뢰서 한 장."""
    h = ctx.hard
    s = ctx.student
    c = ctx.competition
    lines: list[str] = []

    lines.append("# 콩쿨 독창곡 작곡 의뢰서")
    lines.append("")
    lines.append("아래 조건으로 피아노 독주곡 한 곡을 작곡해 주십시오. "
                 "이 의뢰서는 ConcoursComposer 프로그램이 자동으로 만든 것이고, "
                 "**맨 아래 형식 그대로** 돌려주시면 프로그램이 곧바로 읽어 들입니다.")
    lines.append("")

    lines.append("## 1. 누가 치는 곡인가")
    if tier_name:
        lines.append(f"- **급수**: {tier_name} — 이 급수 아이들이 **모두** 칠 수 있어야 합니다"
                     " (한 명이라도 손이 안 닿으면 팔 수 없는 곡입니다)")
    # 판매용 표준 학생은 '배운 기간' 이 0 이다 — 0.0년이라고 적으면 거짓이 된다.
    if s.grade and s.years_of_study:
        lines.append(f"- 학년: {s.grade} · 배운 기간 {s.years_of_study}년")
    lines.append(f"- **손이 닿는 최대 음정: {h.max_span_semitones}반음** — "
                 "한 손이 동시에 이보다 벌어지면 안 됩니다")
    lines.append(f"- **음역: MIDI {h.lowest_midi}~{h.highest_midi}** (이 밖의 음은 쓰지 마십시오)")
    lines.append(f"- **빠르기 상한: ♩={h.max_tempo_bpm}** — 무대에서 흔들리지 않는 선입니다")
    lines.append(f"- 악보 읽기 수준: {s.reading_level}/10 · "
                 f"**임시표는 전체 음표의 {h.max_accidental_ratio:.0%} 이내로**")
    if s.strengths:
        lines.append(f"- 드러내 줄 강점: {', '.join(s.strengths)}")
    if s.weaknesses:
        lines.append(f"- 피해 줄 약점: {', '.join(s.weaknesses)}")
    lines.append("")

    lines.append("## 2. 대회")
    if c:
        lines.append(f"- {c.name} · {c.division}")
        lines.append(f"- **제한 시간: {_minutes(c.time_limit_sec)}** — "
                     "이 시간의 **70~85%** 를 채우십시오. 짧으면 심사에서 손해입니다")
        lines.append(f"- 창작곡 허용: {'예' if c.original_allowed else '아니오'}"
                     f" · 암보 {'필수' if c.memorization_required else '아님'}"
                     f" · 도돌이표 {'가능' if c.repeats_allowed else '불가'}")
    else:
        lines.append("- 특정 대회 없음 — 일반적인 콩쿨 기준으로")
    lines.append(f"- **목표 난이도: {h.target_difficulty} / 10** "
                 f"(허용 범위 {h.difficulty_min}~{h.difficulty_max}, ±1 안에 드십시오)")
    if h.difficulty_key_advice:
        lines.append(f"- 난이도 조언: {h.difficulty_key_advice}")
    lines.append("")

    lines.append("## 3. 곡의 성격")
    if preset:
        lines.append(f"- **{preset.name}** — {preset.blurb}")
        lines.append(f"- 분위기: {preset.mood}")
        lines.append(f"- 형식: {preset.form} · 박자: {preset.meter} · "
                     f"빠르기: ♩={preset.tempo[0]}~{preset.tempo[1]}")
        lines.append(f"- 조성 후보: {', '.join(preset.keys)}")
        if preset.shows_off:
            lines.append(f"- 이 성격이 드러내는 것: {', '.join(preset.shows_off)}")
        if preset.avoid_if:
            lines.append(f"- 학생의 약점이 다음이면 이 성격은 위험합니다: {', '.join(preset.avoid_if)}")
        if preset.texture_options:
            lines.append(f"- 왼손 짜임새 후보: {', '.join(preset.texture_options)}")
    else:
        lines.append("- 성격은 맡깁니다 — 위 조건에 가장 잘 맞는 것으로 골라 주십시오")
    if measures_hint:
        lines.append(f"- 마디 수는 **{measures_hint}마디 안팎**이 제한 시간에 맞습니다")
    lines.append("")

    lines.append("## 4. 어기면 저장되지 않는 것 (검증기가 그대로 돌립니다)")
    lines.append("")
    lines.append("- 마디 길이가 박자표와 **정확히** 맞을 것 (성부마다 합이 같아야 합니다)")
    lines.append("- 기보 가능한 음길이만 (4분음표=1.0 기준: 0.25/0.5/0.75/1.0/1.5/2.0/3.0/4.0)")
    lines.append(f"- 한 손 동시 음정 {h.max_span_semitones}반음 이내 · "
                 f"음역 MIDI {h.lowest_midi}~{h.highest_midi}")
    lines.append("- 손이 교차하지 않을 것 (이 급수에서는 위험합니다)")
    lines.append("- **병행 5도·8도 금지** — 같은 시점에 두 성부가 5도/8도로 나란히 움직이면 실격입니다")
    lines.append("- 마지막은 **분명한 종지**로 (으뜸음에 도달하고, 마디가 온전히 채워질 것)")
    lines.append(f"- 임시표 비율 {h.max_accidental_ratio:.0%} 이내")
    lines.append("- **표절 검사**: 기존 곡의 선율 6음 이상이 그대로 겹치면 떨어집니다. "
                 "기억나는 곡을 옮겨 적지 마십시오")
    lines.append("")

    lines.append("## 5. 원장님이 바라시는 것")
    lines.append("")
    lines.append(wish.strip() if wish.strip()
                 else "_(특별히 적으신 바람 없음 — 위 조건 안에서 가장 좋은 곡으로)_")
    lines.append("")

    lines.append("## 6. 이렇게 만들어 주십시오")
    lines.append("")
    lines.append("1. **모티브 먼저** — 2마디 안팎의 얼굴이 될 선율을 정하고, 그것을 곡 전체에 "
                 "변형해 가며 심으십시오. 심사표에서 가장 크게 보는 것이 이것입니다.")
    lines.append("2. **설계 먼저, 음표 나중** — 형식(A-B-A 등), 마디별 화성, 클라이맥스 위치, "
                 "이 학생이 돋보일 구간을 먼저 정하십시오.")
    lines.append("3. **첫 8마디·클라이맥스·마무리에 힘을 쓰십시오** — 심사위원이 기억하는 곳입니다.")
    lines.append("4. **섹션이 바뀌면 왼손도 바뀌어야 합니다** — 오른손만 바뀌고 왼손이 같은 일을 "
                 "계속하면 '대비 없음' 으로 깎입니다.")
    lines.append("")

    lines.append("## 7. 돌려주실 형식")
    lines.append("")
    lines.append("아래 JSON **하나만** 코드블록에 담아 주십시오. 설명은 코드블록 밖에 쓰셔도 됩니다.")
    lines.append("")
    lines.append("```json")
    lines.append("""{
  "title": "곡 제목",
  "plan": {
    "form": "ABA",
    "key": "C",
    "meter": "4/4",
    "tempo": 108,
    "total_measures": 48,
    "sections": [
      {"name": "A", "start": 1, "end": 16, "role": "제시", "harmony": "I-V-vi-IV",
       "texture": "왼손 알베르티", "dynamics": "mf"}
    ],
    "climax_measure": 34,
    "title_candidates": ["곡 제목", "다른 후보"]
  },
  "motif": {"name": "모티브 이름", "pitches": ["G4","C5","E5"],
            "rhythm": [0.5,0.5,1.0], "why": "이 모티브를 고른 이유"},
  "measures": [ <마디 객체들 — 아래 생김새> ],
  "critic": {
    "scores": {"motif_development": 8, "form_clarity": 8, "harmony": 8,
               "voice_leading": 8, "phrasing": 8, "climax_ending": 8,
               "student_fit": 8, "competition_effect": 8, "notation": 9,
               "originality": 7},
    "overall_comment": "곡을 다 쓴 뒤, 심사위원의 눈으로 냉정하게 본 총평"
  }
}""")
    lines.append("```")
    lines.append("")
    lines.append("**마디 하나의 생김새** (4분음표 = 1.0):")
    lines.append("")
    lines.append("```json")
    lines.append(EXAMPLE_MEASURE)
    lines.append("```")
    lines.append("")
    lines.append("- `pitches` 가 빈 배열이면 **쉼표**입니다. 화음은 `[\"C3\",\"E3\",\"G3\"]`.")
    lines.append("- `artic`: none · staccato · accent · tenuto · marcato")
    lines.append("- `slur`: start · stop · null · `tie`: start · stop · null")
    lines.append("- `dynamics`: pp p mp mf f ff (바뀌는 마디에만 적으십시오)")
    lines.append("- 플랫은 `\"B-4\"` 처럼 **하이픈**, 샤프는 `\"F#4\"`.")
    lines.append("")
    lines.append("- `critic` 은 **스스로 매기는 점수가 아니라 심사위원의 눈**으로 냉정하게. "
                 "여기가 후하면 프로그램이 통과시키는 곡의 기준이 무너집니다. "
                 "각 항목 0~10.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("받은 JSON 은 프로그램의 **'받아온 곡 넣기'** 에 붙여 넣습니다. "
                 "그때 검증기·음악성 지표·표절 검사·모의 심사 3인이 그대로 돌고, "
                 "통과하지 못하면 무엇이 걸렸는지 알려 줍니다.")
    return "\n".join(lines)
