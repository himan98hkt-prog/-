"""Stage 4 — 절대 규칙 1(LLM 은 XML 을 만들지 않는다)·4(모든 note 에 안정적 id)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.generation.assemble import (
    AssembleOptions,
    measures_to_musicxml,
    measures_to_note_events,
)
from app.schemas.music import Measure, ScoreEvent, Voice
from helpers import simple_measure
from music21 import converter


def _measures() -> list[Measure]:
    return [
        Measure(
            number=1,
            rh=[Voice(events=[
                ScoreEvent(dur=1, pitches=["C5"], slur="start"),
                ScoreEvent(dur=1, pitches=["E5"]),
                ScoreEvent(dur=2, pitches=["G5", "C6"], slur="stop", artic="staccato"),
            ])],
            lh=[Voice(events=[
                ScoreEvent(dur=2, pitches=["C3", "G3"]),
                ScoreEvent(dur=2, pitches=[]),
            ])],
            dynamics="mf", pedal=True,
        ),
        simple_measure(2, ["C5", "D5", "E5", "F5"], ["C3"]),
    ]


def test_every_note_has_a_stable_id():
    xml = measures_to_musicxml(_measures(), AssembleOptions())
    notes = re.findall(r"<note\b[^>]*>", xml)
    assert notes
    assert all("id=" in n for n in notes), "id 없는 <note> 가 있다 (절대 규칙 4)"


def test_ids_are_deterministic_across_runs():
    a = measures_to_musicxml(_measures(), AssembleOptions())
    b = measures_to_musicxml(_measures(), AssembleOptions())
    assert a == b


def test_output_reparses_with_music21():
    xml = measures_to_musicxml(_measures(), AssembleOptions(key_sig="G", meter="4/4", tempo=96))
    score = converter.parse(xml, format="musicxml")
    assert len(score.parts) == 2
    assert len(score.parts[0].getElementsByClass("Measure")) == 2


def test_two_staves_with_treble_and_bass_clefs():
    xml = measures_to_musicxml(_measures(), AssembleOptions())
    root = ET.fromstring(xml)
    signs = [s.text for s in root.iter("sign")]
    assert "G" in signs and "F" in signs


def test_note_events_use_absolute_seconds():
    ne = measures_to_note_events(_measures(), tempo_bpm=120, meter="4/4")
    assert ne.notes
    first = min(ne.notes, key=lambda n: n.onset)
    assert first.onset == 0.0
    # 4/4 · 120bpm → 한 마디 2초. 2마디 = 4초.
    assert abs(ne.duration - 4.0) < 0.51
    assert ne.pedal and ne.pedal[0].onset == 0.0


def test_staccato_shortens_sounding_length_deterministically():
    ne = measures_to_note_events(_measures(), tempo_bpm=120, meter="4/4")
    stacc = [n for n in ne.notes if abs(n.onset - 1.0) < 1e-6]
    assert stacc
    assert all(abs(n.duration - 0.5) < 1e-6 for n in stacc)


def test_dynamics_become_velocity():
    ne = measures_to_note_events(_measures(), tempo_bpm=100)
    assert all(n.velocity == 80 for n in ne.notes)   # mf


def test_rest_preserves_measure_length():
    xml = measures_to_musicxml(_measures(), AssembleOptions())
    assert "<rest" in xml
