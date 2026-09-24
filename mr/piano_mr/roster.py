# -*- coding: utf-8 -*-
"""학생 명단 — 관리노트에서 받아 온다 (지시서 9장 5단계 "학생 정보 공유").

**왜 필요한가.** 지금까지 반주 쪽은 학생을 **자유 입력 이름**으로 들고 있었다.
원장님은 같은 명단을 관리노트에 한 번, 반주에 또 한 번 친다. 명단이 두 벌이 되면
표기가 갈리고("김지우" / "김 지우"), 동명이인이 들어오면 누구 반주인지 알 수 없다.

**왜 이름이 아니라 id 인가.** 관리노트에서 개명하거나 동명이인이 들어와도 연결이
끊기지 않게, 관리노트의 학생 id 를 그대로 물고 간다. 화면에 뿌리는 이름은 명단에서
그때그때 찾아 쓴다 — 관리노트에서 고치면 반주 쪽도 따라 바뀐다.

**무엇이 넘어오지 않는가.** 연락처·메모·수납 정보는 애초에 내보내지 않는다
(`src/core/roster-piano.js`). 여기서도 모르는 항목은 버린다 — 관리노트 쪽이 실수로
더 넣어도 반주 쪽 디스크에 남지 않게.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

ROSTER_FORMAT = 'academy-note-piano-roster'
ROSTER_VERSION = 1

# 받아서 보관하는 항목. 이 목록에 없는 건 버린다.
KEEP = ('id', 'name', 'class', 'active')

# 넘어오면 안 되는 항목. 관리노트 쪽이 실수로 넣어도 여기서 막는다.
NEVER_KEEP = ('phone', 'parent_phone', 'memo', 'custom', 'discount',
              'school', 'grade', 'joined_at', 'siblings_group')


class RosterError(ValueError):
    """명단 파일로 받아들일 수 없다."""


@dataclass
class Student:
    id: str
    name: str
    cls: str = ''
    active: bool = True

    def view(self) -> dict:
        return {'id': self.id, 'name': self.name, 'class': self.cls,
                'active': self.active}


def parse(data) -> dict:
    """관리노트가 내보낸 명단을 읽는다. 형식이 아니면 일찍 거절한다."""
    if isinstance(data, (bytes, bytearray)):
        data = data.decode('utf-8', 'replace')
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            raise RosterError('명단 파일을 읽을 수 없습니다 (JSON 형식이 아닙니다).')
    if not isinstance(data, dict):
        raise RosterError('명단 파일이 아닙니다.')
    if data.get('format') != ROSTER_FORMAT:
        raise RosterError(
            '피아노 반주 연동 명단 파일이 아닙니다. 관리노트 설정 → '
            '「피아노 반주(MR) 연동」에서 내보낸 파일을 올려 주세요.')
    if int(data.get('version', 1)) > ROSTER_VERSION:
        raise RosterError('더 최신 관리노트에서 만든 명단입니다. 반주 쪽을 업데이트하세요.')
    rows = data.get('students')
    if not isinstance(rows, list):
        raise RosterError('명단이 비어 있습니다.')
    return data


def students_from(data: dict) -> List[Student]:
    """명단 줄을 Student 로. 모르는 항목은 버린다."""
    out = []
    for row in data.get('students', []):
        if not isinstance(row, dict):
            continue
        sid = str(row.get('id', '')).strip()
        name = str(row.get('name', '')).strip()
        if not sid or not name:
            continue
        out.append(Student(id=sid, name=name,
                           cls=str(row.get('class', '') or ''),
                           active=bool(row.get('active', True))))
    return out


class Roster:
    """반주 쪽이 들고 있는 학생 명단. JSON 한 파일."""

    def __init__(self, path: str):
        self.path = path
        self.academy = ''
        self.imported_at = ''
        self.students: Dict[str, Student] = {}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding='utf-8') as f:
            raw = json.load(f)
        self.academy = raw.get('academy', '')
        self.imported_at = raw.get('imported_at', '')
        self.students = {s['id']: Student(id=s['id'], name=s['name'],
                                          cls=s.get('class', ''),
                                          active=s.get('active', True))
                         for s in raw.get('students', [])}

    def save(self) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'academy': self.academy, 'imported_at': self.imported_at,
                       'students': [s.view() for s in self.sorted()]},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        return self.path

    def replace_with(self, data) -> dict:
        """명단을 통째로 갈아 끼운다.

        **덮어쓰기지 병합이 아니다.** 관리노트에서 퇴원 처리한 학생이 반주 쪽에
        영영 남아 있으면 발표회 명단에 유령이 낀다. 관리노트가 원본이다.
        """
        parsed = parse(data)
        before = set(self.students)
        self.students = {s.id: s for s in students_from(parsed)}
        self.academy = str(parsed.get('academy', '') or '')
        self.imported_at = time.strftime('%Y-%m-%dT%H:%M:%S')
        self.save()
        now = set(self.students)
        return {'count': len(now), 'added': sorted(now - before),
                'removed': sorted(before - now), 'academy': self.academy}

    # --- 읽기 ------------------------------------------------------------
    def get(self, student_id: str) -> Optional[Student]:
        return self.students.get(str(student_id))

    def name_of(self, student_id: str, fallback: str = '') -> str:
        """화면에 뿌릴 이름. 명단에 없으면 저장해 둔 이름을 그대로 쓴다.

        명단을 아직 안 받았거나 그 학생이 빠진 경우에도 발표회 화면이 비면 안 된다.
        """
        s = self.get(student_id)
        return s.name if s else (fallback or '')

    def find_by_name(self, name: str) -> List[Student]:
        """이름으로 찾기 — 동명이인이면 여러 명이 나온다. 부를 때 그걸 감안할 것."""
        want = (name or '').replace(' ', '')
        return [s for s in self.students.values() if s.name.replace(' ', '') == want]

    def sorted(self) -> List[Student]:
        return sorted(self.students.values(), key=lambda s: (not s.active, s.name))

    def view(self) -> dict:
        return {'academy': self.academy, 'imported_at': self.imported_at,
                'count': len(self.students),
                'active': sum(1 for s in self.students.values() if s.active),
                'students': [s.view() for s in self.sorted()]}

    @property
    def loaded(self) -> bool:
        return bool(self.students)
