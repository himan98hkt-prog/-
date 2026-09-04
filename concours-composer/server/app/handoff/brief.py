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
from app.handoff.character import describe
from app.handoff.example import example_json, example_measure_json
from app.handoff.wishes import names, tells


def eun_neun(word: str) -> str:
    """받침이 있으면 '은', 없으면 '는'.

    "행진곡는", "야상곡풍는" 처럼 적히면 원장님이 읽으실 글이 어색해진다. 의뢰서는
    사람이 읽는 글이고, 읽는 사람은 그 어색함을 곧 '대충 만든 것' 으로 읽는다.
    """
    if not word:
        return "는"
    ch = word.strip()[-1]
    if not ("가" <= ch <= "힣"):
        return "는"          # 한글이 아니면 건드리지 않는다
    return "은" if (ord(ch) - 0xAC00) % 28 else "는"


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
    wish_ids: list[str] | None = None,
    avoid: str = "",
    key_pref: str = "",
    measures_hint: int = 0,
    references: list[str] | None = None,
) -> str:
    """대화창에 그대로 붙여 넣을 의뢰서 한 장."""
    h = ctx.hard
    s = ctx.student
    c = ctx.competition
    lines: list[str] = []

    lines.append("# 콩쿨 독창곡 작곡 의뢰서")
    lines.append("")
    # **원장님이 고르신 것을 맨 위에 그대로 적는다.**
    # 원장님이 "세부 요청사항이 전혀 반영되지 않았다" 고 하셨다. 실제로 반영은 되고
    # 있었지만 **의뢰서 어디에도 "당신이 이렇게 고르셨습니다" 가 없었다.** 그러면
    # 반영됐는지 확인할 방법이 없다. 눈으로 보이지 않는 것은 없는 것과 같다.
    chosen: list[str] = []
    if tier_name:
        chosen.append(f"급수 **{tier_name}**")
    chosen.append(f"성격 **{preset.name}**" if preset else "성격 **맡김**")
    if key_pref:
        chosen.append(f"조성 **{key_pref}**")
    picked_names = names(wish_ids or [])
    chosen.append(f"고르신 항목 **{len(picked_names)}개**" if picked_names else "고르신 항목 없음")
    if wish.strip():
        chosen.append("직접 적으신 말씀 있음")
    if avoid.strip():
        chosen.append("피할 것 적으심")
    lines.append("> **원장님이 고르신 것:** " + " · ".join(chosen))
    if picked_names:
        lines.append(">")
        lines.append("> " + " / ".join(picked_names))
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
        # **여기가 이 의뢰서의 심장이다.**
        # 프리셋의 값(분위기·형식·조성 후보)은 프로그램이 검사에 쓰려고 만든 것이지
        # 사람에게 곡을 설명하려고 만든 것이 아니다. 그 값만 옮겨 적어 놓고
        # "작곡해 주세요" 라고 했더니 토카타 같지 않은 곡이 왔다. 당연한 일이다 —
        # **무엇을 하라는 말이 없었다.** 손이 무엇을 하는지 적는다.
        told = describe(preset.id)
        if told:
            what, how, breaks = told
            lines.append("")
            lines.append(f"**{preset.name}{eun_neun(preset.name)} 이런 곡입니다.** {what}")
            lines.append("")
            lines.append("**이렇게 쓰십시오:**")
            lines.append("")
            for one in how:          # `h` 는 위에서 ctx.hard 다 — 겹치면 안 된다
                lines.append(f"- {one}")
            lines.append("")
            lines.append(f"**이러면 이 성격이 무너집니다:** {breaks}")
    else:
        lines.append("- 성격은 맡깁니다 — 위 조건에 가장 잘 맞는 것으로 골라 주십시오")
    # **조성 지정과 성격 지정은 다른 이야기다.**
    # 이 둘을 if/else 로 묶어 두었더니, 조성을 안 고르셨을 때 토카타를 골라 놓고도
    # 의뢰서가 "성격은 맡깁니다" 라고 말했다. 작곡하는 쪽은 그 한 줄을 보고 아무 곡이나
    # 써도 된다고 읽는다. 원장님이 "하나도 토카타 스럽지 않다" 고 하신 이유의 절반이 이것이다.
    if key_pref:
        lines.append(f"- **조성은 {key_pref} 로 해 주십시오** (원장님이 정하셨습니다)")
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

    lines.append("## 5. 이 곡을 남다르게 만드는 것")
    lines.append("")
    picked = tells(wish_ids or [])
    if picked:
        lines.append("원장님이 고르신 것들입니다. **하나도 빠뜨리지 마십시오.**")
        lines.append("")
        for t in picked:
            lines.append(f"- {t}")
        lines.append("")
    if wish.strip():
        lines.append("그리고 원장님이 직접 적으신 말씀입니다:")
        lines.append("")
        lines.append(f"> {wish.strip()}")
        lines.append("")
    if avoid.strip():
        lines.append("**피해 주십시오:**")
        lines.append("")
        lines.append(f"> {avoid.strip()}")
        lines.append("")
    if not picked and not wish.strip() and not avoid.strip():
        lines.append("_(특별히 고르신 것 없음 — 위 조건 안에서 가장 좋은 곡으로)_")
        lines.append("")
    if references:
        lines.append("**원장님이 모아 두신 참고 악보의 성향** (통계만 씁니다 — 음표를 베끼지 마십시오):")
        lines.append("")
        for r in references[:8]:
            lines.append(f"- {r}")
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
    lines.append("5. **무늬를 여덟 가지 이상 쓰십시오.** 한 가지 음형을 화성 따라 조옮김만 하면 "
                 "규칙 검사는 통과하지만 **사람 귀에는 같은 마디가 계속되는 곡**입니다. "
                 "네 마디쯤마다 손이 하는 일이 바뀌어야 합니다 — 음계, 분산화음, 반복음, "
                 "양손 교대, 끊는 옥타브, 페달 위 축적, 화음, 노래하는 선율.")
    lines.append("6. **마디를 하나씩 직접 쓰십시오.** 규칙을 정해 놓고 기계적으로 찍어 내면 "
                 "반드시 밋밋해집니다. 각 마디에 '여기서 무슨 일이 일어나는가' 를 두십시오.")
    if preset and "달리" in (preset.mood or ""):
        lines.append("7. **토카타는 달리기가 멈추면 토카타가 아닙니다.** 종지 자리 말고는 "
                     "16분음표가 **어느 한 손에서든 계속 굴러야** 합니다. 가운데 단락에서 "
                     "오른손이 4분음표로 노래하게 하지 마십시오 — 그러면 찬송가가 됩니다. "
                     "역할을 바꾸시려면 **왼손이 선율을 맡고 오른손이 계속 구르게** 하십시오.")
    lines.append("")

    lines.append("## 7. 돌려주실 형식")
    lines.append("")
    lines.append("아래 JSON **하나만** 코드블록에 담아 주십시오. 설명은 코드블록 밖에 쓰셔도 됩니다.")
    lines.append("**이 본보기는 프로그램이 실제 스키마에서 지어낸 것**이라, 그대로 따르시면 반드시 읽힙니다.")
    lines.append("")
    lines.append("```json")
    lines.append(example_json())
    lines.append("```")
    lines.append("")
    lines.append("`measures` 자리에는 아래 생김새의 마디를 `total_measures` 개수만큼 넣으십시오"
                 " (4분음표 = 1.0):")
    lines.append("")
    lines.append("```json")
    lines.append(example_measure_json())
    lines.append("```")
    lines.append("")
    lines.append("**꼭 지켜야 할 것**")
    lines.append("")
    lines.append("- `motif` 는 음이름 목록이 아니라 **마디 2~4개**입니다(위 본보기 그대로).")
    lines.append("- `plan.form` 은 **구역 목록**입니다. `sections` 라는 이름은 없습니다.")
    lines.append("- `plan` 에는 `duration_est` · `climax` · `ending` · `difficulty_target` 이"
                 " **반드시** 있어야 합니다.")
    lines.append("- 적혀 있지 않은 이름을 새로 만들어 넣으면 통째로 거절됩니다.")
    lines.append("- `pitches` 가 빈 배열이면 **쉼표**입니다. 화음은 `[\"C3\",\"E3\",\"G3\"]`.")
    lines.append("- `artic`: none · staccato · accent · tenuto · marcato · "
                 "`slur`/`tie`: start · stop · null")
    lines.append("- `dynamics`: pp p mp mf f ff (바뀌는 마디에만)")
    lines.append("- 플랫은 `\"B-4\"` 처럼 **하이픈**, 샤프는 `\"F#4\"`.")
    lines.append("- `critic` 은 스스로 매기는 점수가 아니라 **심사위원의 눈**으로 냉정하게. "
                 "여기가 후하면 프로그램이 통과시키는 곡의 기준이 무너집니다. 각 항목 0~10.")
    lines.append("")
    lines.append("---")
    lines.append("")
    # 원장님이 물으셨다: "요청할때 어떤 문서를 만들어 달라고 해야 정확하게 프로그램에서
    # 인식이 될까?" — 따로 부탁하실 것이 없어야 맞다. 의뢰서가 스스로 말하면 된다.
    lines.append("## 돌려주실 것 — 이것 하나면 됩니다")
    lines.append("")
    lines.append("위 JSON 을 **`곡이름.json` 파일 하나로 저장해 주십시오.**")
    lines.append("")
    lines.append("- 악보(MusicXML)·MIDI·MP3·연주 해설·표지·판매 꾸러미·저작권 서류는 "
                 "**프로그램이 이 JSON 하나로 다 만듭니다.** 따로 주실 필요가 없습니다.")
    lines.append("- 파일 이름은 아무거나 괜찮습니다. 확장자만 `.json` 이면 됩니다.")
    lines.append("- 설명이나 해설을 곁들이고 싶으시면 파일 **밖에** 적어 주십시오. "
                 "JSON 파일 안에는 위에 적힌 것만 들어가야 합니다.")
    lines.append("")
    lines.append("그 파일을 프로그램의 **'② 받아온 곡 넣기 → 파일로 넣기'** 에서 고르면 됩니다. "
                 "그때 검증기·음악성 지표·표절 검사·모의 심사 3인이 그대로 돌고, "
                 "통과하지 못하면 무엇이 걸렸는지 알려 줍니다. 고쳐서 다시 넣는 데도 "
                 "비용이 들지 않습니다.")
    return "\n".join(lines)
