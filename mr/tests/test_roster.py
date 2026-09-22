# -*- coding: utf-8 -*-
"""학생 명단 연동 — 지시서 9장 5단계 "학생 정보 공유".

제일 중요한 건 맨 아래 교차 시험이다: **관리노트(JS)가 실제로 내보낸 파일을
반주(파이썬)가 읽는가.** 양쪽에 손으로 쓴 fixture 를 두고 서로 맞춰 보면, 한쪽
형식이 바뀌어도 둘 다 초록인 채로 현장에서만 깨진다.
"""
import json
import os
import shutil
import subprocess

import pytest

from piano_mr import catalog as cat, roster, store

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def roster_blob(students=None, **over):
    body = {
        'format': roster.ROSTER_FORMAT,
        'version': 1,
        'academy': '행복피아노',
        'exported_at': '2026-09-22T00:00:00.000Z',
        'students': students if students is not None else [
            {'id': 's1', 'name': '김지우', 'class': '월수금 4시', 'active': True},
            {'id': 's2', 'name': '박서준', 'class': '화목 5시', 'active': True},
            {'id': 's3', 'name': '이하은', 'class': '', 'active': False},
        ],
    }
    body.update(over)
    return json.dumps(body, ensure_ascii=False)


@pytest.fixture
def st(tmp_path):
    return store.CatalogStore(str(tmp_path / 'catalog'))


# --- 받기 ---------------------------------------------------------------------

def test_import_reads_the_roster(st):
    out = st.import_roster(roster_blob())
    assert out['count'] == 3 and out['academy'] == '행복피아노'
    v = st.roster.view()
    assert v['active'] == 2
    assert [s['name'] for s in v['students']] == ['김지우', '박서준', '이하은']


def test_休원_students_sort_last_but_stay(st):
    """빼 버리면 "왜 그 아이가 안 보이지" 가 된다. 뒤로 보내고 표시만 한다."""
    st.import_roster(roster_blob())
    names = [s['name'] for s in st.roster.view()['students']]
    assert names[-1] == '이하은'


def test_import_replaces_rather_than_merges(st):
    """관리노트가 원본이다. 퇴원한 학생이 반주 쪽에 남으면 발표회 명단에 유령이 낀다."""
    st.import_roster(roster_blob())
    out = st.import_roster(roster_blob(students=[
        {'id': 's1', 'name': '김지우', 'class': '월수금 4시', 'active': True}]))
    assert out['count'] == 1
    assert sorted(out['removed']) == ['s2', 's3']
    assert st.roster.get('s2') is None


def test_import_reports_who_came_and_went(st):
    st.import_roster(roster_blob())
    out = st.import_roster(roster_blob(students=[
        {'id': 's1', 'name': '김지우', 'class': '', 'active': True},
        {'id': 's9', 'name': '최서아', 'class': '', 'active': True}]))
    assert out['added'] == ['s9'] and sorted(out['removed']) == ['s2', 's3']


def test_roster_survives_a_reload(st, tmp_path):
    st.import_roster(roster_blob())
    again = store.CatalogStore(str(tmp_path / 'catalog'))
    assert again.roster.get('s1').name == '김지우'
    assert again.roster.academy == '행복피아노'


# --- 개인정보는 안 받는다 --------------------------------------------------------

def test_contact_details_are_dropped_even_if_sent(st):
    """관리노트 쪽이 실수로 더 넣어도 반주 쪽 디스크에 남으면 안 된다."""
    blob = roster_blob(students=[{
        'id': 's1', 'name': '김지우', 'class': '월수금', 'active': True,
        'phone': '010-1234-5678', 'parent_phone': '010-9876-5432',
        'memo': '왼손이 약함', 'discount': {'memo': '장기 등록'},
    }])
    st.import_roster(blob)
    saved = open(st.roster.path, encoding='utf-8').read()
    for leak in roster.NEVER_KEEP:
        assert leak not in saved, f'{leak} 가 디스크에 남았습니다'
    assert '010-' not in saved and '왼손이' not in saved


# --- 거절 ---------------------------------------------------------------------

def test_a_backup_file_is_refused(st):
    with pytest.raises(roster.RosterError) as e:
        st.import_roster('{"format":"academy-note-backup","students":[]}')
    assert '명단 파일이 아닙니다' in str(e.value)


def test_garbage_is_refused(st):
    with pytest.raises(roster.RosterError):
        st.import_roster('이건 파일이 아니다')


def test_a_newer_version_is_refused_with_advice(st):
    with pytest.raises(roster.RosterError) as e:
        st.import_roster(roster_blob(version=99))
    assert '업데이트' in str(e.value)


def test_rows_without_an_id_or_name_are_skipped(st):
    out = st.import_roster(roster_blob(students=[
        {'id': '', 'name': '이름만'}, {'id': 's5', 'name': ''},
        {'id': 's6', 'name': '최서아'}, '문자열이 섞임']))
    assert out['count'] == 1


# --- 발표회 큐가 명단을 따라간다 ---------------------------------------------------

def program_with(st, student_id='s1', student='옛날이름'):
    from conftest import score
    st.import_score(score('p05_waltz_c'), '작은 왈츠', song_id='waltz',
                    composer='자사 오리지널', book='오리지널 연습곡',
                    public_domain=True)
    st.catalog.add_program(cat.Program(
        id='winter', event='2026 겨울 발표회',
        queue=[cat.QueueItem(order=1, student=student, student_id=student_id,
                             song_id='waltz', bpm=84)]))
    st.save()
    return st.program_view(0)


def test_the_queue_shows_the_name_from_the_roster(st):
    """관리노트에서 개명하면 발표회 화면도 따라 바뀌어야 한다."""
    st.import_roster(roster_blob())
    item = program_with(st, 's1', '옛날이름')['items'][0]
    assert item['student'] == '김지우' and item['linked'] is True
    assert item['cue'].startswith('1. 김지우 —')


def test_the_queue_falls_back_when_the_roster_is_missing(st):
    """명단을 아직 안 받았어도 발표회 화면이 비면 안 된다."""
    item = program_with(st, 's1', '김지우')['items'][0]
    assert item['student'] == '김지우' and item['linked'] is False


def test_a_student_dropped_from_the_roster_keeps_the_stored_name(st):
    st.import_roster(roster_blob(students=[
        {'id': 's2', 'name': '박서준', 'class': '', 'active': True}]))
    item = program_with(st, 's1', '김지우')['items'][0]
    assert item['student'] == '김지우' and item['linked'] is False


def test_a_queue_without_a_student_id_still_works(st):
    """예전에 만든 프로그램(이름만 있는 것)이 그대로 열려야 한다."""
    st.import_roster(roster_blob())
    item = program_with(st, '', '손으로 적은 이름')['items'][0]
    assert item['student'] == '손으로 적은 이름' and item['linked'] is False


# --- 같은 이름이 둘일 때 -----------------------------------------------------------

def test_find_by_name_returns_everyone_with_that_name(st):
    """동명이인이 있으면 이름으로는 못 고른다 — 그래서 id 로 연결한다."""
    st.import_roster(roster_blob(students=[
        {'id': 's1', 'name': '김지우', 'class': 'A', 'active': True},
        {'id': 's2', 'name': '김 지우', 'class': 'B', 'active': True}]))
    assert len(st.roster.find_by_name('김지우')) == 2      # 공백도 흡수한다


# --- 교차 시험: 관리노트(JS) 가 실제로 내보낸 파일을 읽는다 ---------------------------

@pytest.mark.skipif(shutil.which('node') is None, reason='node 가 없습니다')
def test_reads_what_the_academy_note_actually_exports(st, tmp_path):
    """양쪽에 손으로 쓴 fixture 를 두면, 형식이 갈려도 둘 다 초록인 채로 현장에서 깨진다.

    그래서 관리노트의 `buildRoster` 를 **진짜로 실행해서** 나온 파일을 읽는다.
    """
    js = tmp_path / 'export.mjs'
    js.write_text(f"""
import {{ buildRoster }} from '{REPO}/src/core/roster-piano.js'
const students = [
  {{ id: 's1', name: '김지우', school: '행복초', grade: '3학년',
     phone: '010-1234-5678', parent_phone: '010-9876-5432',
     memo: '왼손이 약함', status: '재원',
     discount: {{ memo: '장기 등록', amount: 20000 }} }},
  {{ id: 's2', name: '박서준', phone: '010-0000-1111', status: '휴원' }}
]
const enrollments = [{{ student_id: 's1', class_id: 'c1', ended_at: null }}]
const classes = [{{ id: 'c1', name: '월수금 4시' }}]
process.stdout.write(JSON.stringify(
  buildRoster(students, enrollments, classes, {{ academy: '행복피아노' }})))
""", encoding='utf-8')
    proc = subprocess.run(['node', str(js)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    exported = proc.stdout

    # ① 내보낸 파일 자체에 연락처가 없다
    assert '010-' not in exported and '왼손이' not in exported

    # ② 반주 쪽이 그대로 읽는다
    out = st.import_roster(exported)
    assert out['count'] == 2 and out['academy'] == '행복피아노'
    assert st.roster.get('s1').name == '김지우'
    assert st.roster.get('s1').cls == '월수금 4시'
    assert st.roster.get('s2').active is False
