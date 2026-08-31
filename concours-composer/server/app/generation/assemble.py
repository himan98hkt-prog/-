"""Stage 4 — Assemble. LLM JSON → music21 → MusicXML 3.1 (결정적).

CLAUDE.md 절대 규칙 1(LLM 이 XML 을 만들지 않는다)과 4(모든 <note> 에 안정적 id)
를 강제하는 지점. id 는 `m{마디}-{손}{성부}-{인덱스}` 로 결정적으로 부여하므로
같은 입력이면 항상 같은 id 가 나온다 — 편집·해설 앵커·시각화 매핑이 여기에 의존한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from music21 import (
    articulations,
    clef,
    dynamics,
    expressions,
    key,
    layout,
    metadata,
    meter as m21meter,
    note as m21note,
    spanner,
    stream,
    tempo as m21tempo,
)

from app.schemas.music import Measure, NoteEvent, NoteEvents, PedalSpan, Voice

HAND_STAFF = {"rh": 1, "lh": 2}


@dataclass(frozen=True)
class AssembleOptions:
    title: str = "무제"
    composer: str = "AI 초안 · 원장 편곡"
    key_sig: str = "C"
    meter: str = "4/4"
    tempo: int = 100


def note_id(measure_number: int, hand: str, voice: int, index: int) -> str:
    return f"m{measure_number}-{hand}{voice}-{index}"


def _make_chord_or_note(ev_pitches: list[str], ql: float) -> m21note.GeneralNote:
    from music21 import chord as m21chord

    if len(ev_pitches) == 1:
        return m21note.Note(ev_pitches[0], quarterLength=ql)
    return m21chord.Chord(ev_pitches, quarterLength=ql)


def _apply_articulation(n: m21note.GeneralNote, artic: str) -> None:
    mapping = {
        "staccato": articulations.Staccato,
        "accent": articulations.Accent,
        "tenuto": articulations.Tenuto,
        "marcato": articulations.StrongAccent,
    }
    cls = mapping.get(artic)
    if cls is not None:
        n.articulations.append(cls())


def _fill_voice(
    m21m: stream.Measure, v: Voice, measure_number: int, hand: str
) -> tuple[list[m21note.GeneralNote], list[spanner.Slur]]:
    """한 성부를 마디에 채우고 (붙인 음표들, 슬러들) 을 돌려준다."""
    made: list[m21note.GeneralNote] = []
    slurs: list[spanner.Slur] = []
    open_slur: spanner.Slur | None = None
    v21 = stream.Voice(id=str(v.voice))

    for i, ev in enumerate(v.events):
        if ev.is_rest:
            obj: m21note.GeneralNote = m21note.Rest(quarterLength=ev.dur)
        else:
            obj = _make_chord_or_note(ev.pitches, ev.dur)
            _apply_articulation(obj, ev.artic)
            if ev.tie:
                from music21 import tie as m21tie

                obj.tie = m21tie.Tie(ev.tie)
        obj.id = note_id(measure_number, hand, v.voice, i)
        # music21 의 .id 는 MusicXML 로 새어나가지 않으므로 editorial 에도 남긴다.
        obj.editorial.noteId = obj.id
        v21.append(obj)
        made.append(obj)

        if ev.slur == "start" and not ev.is_rest:
            open_slur = spanner.Slur()
            open_slur.addSpannedElements(obj)
        elif ev.slur == "stop" and open_slur is not None and not ev.is_rest:
            open_slur.addSpannedElements(obj)
            slurs.append(open_slur)
            open_slur = None
        elif open_slur is not None and not ev.is_rest:
            open_slur.addSpannedElements(obj)

    m21m.insert(0, v21)
    return made, slurs


def assemble(measures: list[Measure], opts: AssembleOptions) -> stream.Score:
    """마디 리스트를 2단 보표 Score 로 조립한다."""
    score = stream.Score()
    score.insert(0, metadata.Metadata(title=opts.title, composer=opts.composer))

    rh_part = stream.Part(id="RH")
    lh_part = stream.Part(id="LH")
    rh_part.insert(0, clef.TrebleClef())
    lh_part.insert(0, clef.BassClef())
    staff_group = layout.StaffGroup([rh_part, lh_part], symbol="brace", barTogether=True)

    for idx, m in enumerate(sorted(measures, key=lambda x: x.number)):
        for hand, part in (("rh", rh_part), ("lh", lh_part)):
            m21m = stream.Measure(number=m.number)
            if idx == 0:
                m21m.insert(0, key.Key(opts.key_sig))
                m21m.insert(0, m21meter.TimeSignature(opts.meter))
                if hand == "rh":
                    m21m.insert(0, m21tempo.MetronomeMark(number=opts.tempo))
            voices = m.rh if hand == "rh" else m.lh
            if not voices:
                # 빈 손은 온쉼표로 채워 마디 길이를 보존한다(§6.4 편집 규칙과 동일).
                ts = m21meter.TimeSignature(opts.meter)
                m21m.append(m21note.Rest(quarterLength=ts.barDuration.quarterLength))
            else:
                for v in voices:
                    _, slurs = _fill_voice(m21m, v, m.number, hand)
                    for s in slurs:
                        part.insert(0, s)
            if hand == "rh":
                if m.dynamics:
                    m21m.insert(0, dynamics.Dynamic(m.dynamics))
                if m.text:
                    m21m.insert(0, expressions.TextExpression(m.text))
            part.append(m21m)

    score.insert(0, rh_part)
    score.insert(0, lh_part)
    score.insert(0, staff_group)
    return score


def _ensure_note_ids(xml: str) -> str:
    """모든 <note> 에 id 를 보장한다(절대 규칙 4).

    music21 은 화음을 객체 하나로 다루므로 화음의 둘째 음부터는 id 가 비어 나온다.
    비어 있으면 직전 음의 id 에 `+n` 을 붙여 결정적으로 채운다.
    """
    import xml.etree.ElementTree as ET

    root = ET.fromstring(xml)

    # music21 은 파트 id 를 매번 새 해시로 만든다. 골든 회귀·스냅샷 비교가 가능하도록
    # P1/P2 로 정규화한다(내보내기 결과가 입력에만 의존해야 한다).
    part_ids = [p.get("id") for p in root.iter("part") if p.get("id")]
    remap = {old_id: f"P{i + 1}" for i, old_id in enumerate(part_ids)}
    for el in root.iter():
        for attr in ("id",):
            if el.tag in ("part", "score-part") and el.get(attr) in remap:
                el.set(attr, remap[el.get(attr)])

    # 파트 순서는 assemble() 이 정한다: 0 = 오른손, 1 = 왼손. music21 이 파트 id 를
    # 해시로 바꾸므로 파트 이름 대신 순서를 쓴다 — 같은 입력이면 항상 같은 id.
    for p_idx, part in enumerate(root.iter("part")):
        hand = "rh" if p_idx == 0 else "lh"
        for measure in part.iter("measure"):
            mno = measure.get("number", "0")
            last_id: str | None = None
            chord_n = 0
            for i, n in enumerate(measure.iter("note")):
                nid = n.get("id")
                if nid:
                    last_id, chord_n = nid, 0
                    continue
                if n.find("chord") is not None and last_id:
                    chord_n += 1
                    n.set("id", f"{last_id}+{chord_n}")
                else:
                    generated = f"m{mno}-{hand}c-{i}"
                    n.set("id", generated)
                    last_id, chord_n = generated, 0
    return ET.tostring(root, encoding="unicode")


def to_musicxml(score: stream.Score) -> str:
    from music21.musicxml.m21ToXml import GeneralObjectExporter

    xml = GeneralObjectExporter().parse(score).decode("utf-8")
    return _ensure_note_ids(xml)


def measures_to_musicxml(measures: list[Measure], opts: AssembleOptions) -> str:
    return to_musicxml(assemble(measures, opts))


# ── 작곡 축 → 시각화 축 변환 (NoteEvents SoT) ────────────────────────────────


def measures_to_note_events(
    measures: list[Measure], tempo_bpm: int, meter: str = "4/4"
) -> NoteEvents:
    """마디 JSON 을 절대 시간 NoteEvents 로. 시각화·하이라이트가 이것만 쓴다."""
    from app.analysis.pitch import pitch_to_midi

    ts = m21meter.TimeSignature(meter)
    bar_ql = ts.barDuration.quarterLength
    sec_per_ql = 60.0 / tempo_bpm

    dyn_velocity = {
        "ppp": 20, "pp": 33, "p": 49, "mp": 64, "mf": 80, "f": 96, "ff": 112, "fff": 126,
    }

    notes: list[NoteEvent] = []
    pedal: list[PedalSpan] = []
    current_vel = 80

    ordered = sorted(measures, key=lambda m: m.number)
    first = ordered[0].number if ordered else 1
    for m in ordered:
        bar_start = (m.number - first) * bar_ql * sec_per_ql
        if m.dynamics:
            current_vel = dyn_velocity[m.dynamics]
        if m.pedal:
            pedal.append(PedalSpan(onset=bar_start, offset=bar_start + bar_ql * sec_per_ql))
        for hand, voices in (("R", m.rh), ("L", m.lh)):
            for v in voices:
                t = 0.0
                for ev in v.events:
                    if ev.pitches:
                        onset = bar_start + t * sec_per_ql
                        offset = onset + ev.dur * sec_per_ql
                        # 스타카토는 실제 울림을 절반으로 — 프리뷰와 렌더가 같아야 하므로 결정적으로.
                        if ev.artic == "staccato":
                            offset = onset + (ev.dur * sec_per_ql) * 0.5
                        for p in ev.pitches:
                            notes.append(
                                NoteEvent(
                                    onset=round(onset, 6),
                                    offset=round(offset, 6),
                                    pitch=pitch_to_midi(p),
                                    velocity=current_vel,
                                    hand=hand,  # type: ignore[arg-type]
                                )
                            )
                    t += ev.dur

    return NoteEvents(
        notes=notes, pedal=pedal, tempo_bpm=float(tempo_bpm), meter=meter, source="composition"
    )
