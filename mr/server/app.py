# -*- coding: utf-8 -*-
"""화성 확인 화면 서버 — 지시서 9장 2단계 · 10장.

    "PDF 경로가 실용적이냐 아니냐가 이 화면 하나로 갈린다."
    "악보를 음표 단위로 교정하면 40분, 화성만 보면 3~5분"

그래서 이 API 는 **음표를 내보내지 않는다.** 화음 이름과, 그 화음을 얼마나
확신하는지만 내보낸다.

원장님께 파는 물건이 아니라 **카탈로그를 만드는 우리 쪽 작업 도구**다.
로컬에서 돌리는 것을 전제로 한다.
"""
from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from piano_mr import catalog as cat, orchestration as orch, render, store

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, 'static')


class Cell(BaseModel):
    bar: Optional[int] = None
    m: Optional[int] = None
    i: int
    label: str


class SavePayload(BaseModel):
    cells: List[Cell] = Field(default_factory=list)
    verified: Optional[bool] = None
    add_seconds: int = 0
    style: Optional[str] = None
    level: Optional[str] = None
    bpm: Optional[int] = None
    note: Optional[str] = None


def create_app(catalog_root: str) -> FastAPI:
    st = store.CatalogStore(catalog_root)
    app = FastAPI(title='화성 확인 화면', version='1.0')
    app.state.store = st

    def _song(song_id: str):
        try:
            return st.catalog.get(song_id)
        except KeyError:
            raise HTTPException(404, f'카탈로그에 없는 곡입니다: {song_id}')

    @app.get('/', include_in_schema=False)
    def index():
        return RedirectResponse('/static/index.html')

    @app.get('/api/stats')
    def stats():
        return {'root': st.root, **st.stats()}

    @app.get('/api/styles')
    def styles():
        return {
            'styles': [{'key': k, 'label': lab, 'desc': d}
                       for k, lab, d in orch.list_styles()],
            'levels': [{'key': k, 'label': orch.LEVEL_LABEL[k]} for k in orch.LEVELS],
            'mixes': [{'key': k, 'label': v['label'], 'desc': v['desc']}
                      for k, v in render.MIXES.items()],
        }

    @app.get('/api/songs')
    def songs():
        return {'songs': st.rows()}

    @app.get('/api/songs/{song_id}')
    def song(song_id: str):
        _song(song_id)
        return st.view(song_id)

    @app.put('/api/songs/{song_id}/harmony')
    def save(song_id: str, payload: SavePayload):
        _song(song_id)
        cells = []
        for c in payload.cells:
            if c.bar is None and c.m is None:
                raise HTTPException(400, 'bar 또는 m 이 필요합니다.')
            d = {'i': c.i, 'label': c.label}
            if c.bar is not None:
                d['bar'] = c.bar
            else:
                d['m'] = c.m
            cells.append(d)
        try:
            st.save_harmony(song_id, cells, verified=payload.verified,
                            add_seconds=payload.add_seconds, style=payload.style,
                            level=payload.level, bpm=payload.bpm, note=payload.note)
        except (ValueError, KeyError, cat.CopyrightError) as e:
            raise HTTPException(400, str(e))
        return st.view(song_id)

    @app.post('/api/songs/{song_id}/reanalyze')
    def reanalyze(song_id: str):
        _song(song_id)
        st.reanalyze(song_id)
        return st.view(song_id)

    @app.get('/api/songs/{song_id}/audio')
    def audio(song_id: str, style: Optional[str] = None, level: Optional[str] = None,
              bpm: Optional[int] = None, mix: str = 'full'):
        """mp3 를 (필요하면) 만들고 위치와 박-초 환산비를 알려준다.

        구간 재생은 서버를 다시 부르지 않는다. 한 번 받은 mp3 안에서
        `초 = 마디시작(4분음표) × 60 / bpm` 으로 건너뛴다.
        """
        _song(song_id)
        try:
            info = st.audio(song_id, style=style, level=level, bpm=bpm, mix=mix)
        except (render.ToolMissingError, RuntimeError) as e:
            raise HTTPException(503, str(e))
        except (ValueError, KeyError) as e:
            raise HTTPException(400, str(e))
        name = os.path.basename(info['path'])
        return {'url': f'/api/audio/{name}', 'cached': info['cached'],
                'seconds': info['seconds'], 'style': info['style'],
                'level': info['level'], 'bpm': info['bpm'], 'mix': info['mix'],
                'count_in': info['count_in'], 'lead_seconds': info['lead_seconds'],
                'sec_per_ql': 60.0 / info['bpm']}

    @app.get('/api/audio/{name}', include_in_schema=False)
    def audio_file(name: str):
        if '/' in name or '\\' in name or not name.endswith('.mp3'):
            raise HTTPException(400, '잘못된 파일 이름입니다.')
        path = os.path.join(st.cache_dir, name)
        if not os.path.exists(path):
            raise HTTPException(404, '만료된 음원입니다. 다시 요청하세요.')
        return FileResponse(path, media_type='audio/mpeg')

    @app.get('/api/stage')
    def stage():
        """무대 배경으로 쓸 파일이 있는지. 없으면 화면은 CSS 무대로 간다.

        `static/img/hall.mp4` 또는 `hall.jpg` 를 넣어 두면 자동으로 얹힌다.
        """
        img_dir = os.path.join(STATIC, 'img')
        def have(name):
            return f'img/{name}' if os.path.exists(os.path.join(img_dir, name)) else None
        return {'video': have('hall.mp4'), 'image': have('hall.jpg'),
                'keys': have('keys.jpg'), 'curtain': have('curtain.jpg')}

    @app.get('/api/programs')
    def programs():
        return {'programs': st.programs()}

    @app.get('/api/programs/{index}')
    def program(index: int):
        try:
            return st.program_view(index)
        except KeyError as e:
            raise HTTPException(404, str(e))

    # --- 3단계 플레이어 (지시서 모듈 ⑤) -----------------------------------
    @app.get('/api/player/bundle')
    def player_bundle(verified_only: bool = False):
        """플레이어가 통째로 받아 오프라인에 넣어 둘 목록. 오디오는 없다."""
        return st.player_bundle(only_verified=verified_only)

    @app.get('/api/player/midi/{song_id}')
    def player_midi(song_id: str, style: Optional[str] = None,
                    level: Optional[str] = None):
        """반주 MIDI 원본. 1 KB 안팎이라 카탈로그 전체를 캐시할 수 있다."""
        _song(song_id)
        try:
            data = st.accomp_midi_bytes(song_id, style=style, level=level)
        except (ValueError, KeyError) as e:
            raise HTTPException(400, str(e))
        return Response(content=data, media_type='audio/midi', headers={
            'Cache-Control': 'public, max-age=31536000',
            'Content-Disposition': f'inline; filename="{song_id}.mid"',
        })

    @app.post('/api/songs/{song_id}/midi')
    def midi(song_id: str):
        _song(song_id)
        path = st.build_midi(song_id)
        return {'path': os.path.relpath(path, st.root),
                'bytes': os.path.getsize(path)}

    app.mount('/static', StaticFiles(directory=STATIC, html=True), name='static')
    return app
