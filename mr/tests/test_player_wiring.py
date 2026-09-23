# -*- coding: utf-8 -*-
"""플레이어 화면과 엔진이 같은 말을 하는지.

여기서 잡는 고장은 둘 다 **우리 화면에서는 안 보이고 현장에서만 보인다.**

1. 편성 키가 어긋나면 그 편성만 조용히 빠진다. 고장 표시도 없이 단추 하나가
   안 그려지거나 그림이 빈다. 실제로 문서에 `fairy` 라고 적어 둔 적이 있는데
   엔진의 키는 `fairytale` 이었다.
2. 서비스워커가 미리 받아 두는 목록(SHELL_FILES)에 적힌 파일이 꾸러미에 없으면
   `cache.addAll` 이 **전부** 거부한다. 온라인에서는 멀쩡하고 **비행기 모드에서만**
   플레이어가 통째로 안 뜬다. 발표회장에서 겪으면 늦는다.
"""
import os
import re

import pytest

from conftest import score
from piano_mr import orchestration, store

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYER = os.path.join(HERE, '..', 'server', 'static', 'player')


def read(*parts):
    with open(os.path.join(PLAYER, *parts), encoding='utf-8') as f:
        return f.read()


def keys_in(pattern, text):
    """`[['strings', '…'], …]` 또는 `{ strings: …, }` 에서 키만."""
    return [m.group(1) for m in re.finditer(pattern, text, re.M)]


# --- 1. 편성 -------------------------------------------------------------------

def test_the_player_knows_every_style_the_engine_has():
    """엔진에 편성을 더하면 플레이어의 이름표와 그림도 같이 늘어야 한다."""
    app = read('js', 'app.js')

    labels = app.split('const STYLE_LABEL =')[1].split('];')[0]
    icons = app.split('const STYLE_ICON = {')[1].split('\n};')[0]

    want = set(orchestration.STYLES)
    assert set(keys_in(r"\['(\w+)',", labels)) == want, '이름표가 엔진과 다릅니다'
    assert set(keys_in(r"^\s{2}(\w+): I\(", icons)) == want, '그림이 엔진과 다릅니다'


def test_every_style_icon_is_drawn_not_empty():
    """빈 그림이면 단추가 이름만 남아 다른 여섯과 어긋나 보인다."""
    icons = read('js', 'app.js').split('const STYLE_ICON = {')[1].split('\n};')[0]
    for key in orchestration.STYLES:
        body = icons.split(f'{key}: I(`')[1].split('`)')[0]
        assert '<path' in body or '<circle' in body, f'{key} 그림이 비었습니다'


def test_the_level_names_match_too():
    """두께도 같은 방식으로 단추를 그린다."""
    app = read('js', 'app.js')
    labels = app.split('const LEVEL_LABEL =')[1].split('];')[0]
    assert set(keys_in(r"\['(\w+)',", labels)) == set(orchestration.LEVELS)


# --- 2. 서비스워커가 미리 받는 목록 ------------------------------------------------

def test_every_precached_file_is_really_in_the_package(tmp_path):
    """목록에 적었는데 파일이 없으면 오프라인이 통째로 죽는다.

    `cache.addAll` 은 하나라도 404 면 전부 거부한다. 그래서 목록에 파일을 더할
    때는 **파일이 먼저 있어야 한다.**
    """
    listed = read('sw.js').split('const SHELL_FILES = [')[1].split('];')[0]
    files = [m.group(1) for m in re.finditer(r"'\./([^']*)'", listed)]
    assert files, 'SHELL_FILES 를 못 읽었습니다'

    st = store.CatalogStore(str(tmp_path / 'catalog'))
    st.import_score(score('p05_waltz_c'), '작은 왈츠 (C장조)', song_id='waltz',
                    composer='자사 오리지널', book='오리지널 연습곡', level=2,
                    public_domain=True)
    out = str(tmp_path / 'pkg')
    st.export_static(out)

    for name in files:
        if not name:            # './' — 꾸러미의 index.html 이 받는다
            continue
        assert os.path.exists(os.path.join(out, name)), \
            f'{name} 이 SHELL_FILES 에 있는데 꾸러미에 없습니다'


def test_the_worker_version_is_bumped_when_the_shell_changes():
    """내용만 바꿔도 버전을 올려야 기존 기기의 캐시가 버려진다.

    여기서 값을 못 박지는 못한다 — 사람이 올렸는지는 사람만 안다. 대신 형식을
    지켜 두면 `sed` 로 올리다 오타가 나는 것은 막는다.
    """
    assert re.search(r"const VERSION = 'mr-player-v\d+';", read('sw.js'))
