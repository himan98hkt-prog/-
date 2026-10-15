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
import shutil
import tempfile
import urllib.parse
import zipfile
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

from piano_mr import (catalog as cat, license as lic, omr,
                      orchestration as orch, pdf, render, roster, store, uploads)

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, 'static')

_MEDIA = {'.mid': 'audio/midi', '.mp3': 'audio/mpeg',
          '.wav': 'audio/wav', '.zip': 'application/zip'}


def _media(ext: str) -> str:
    return _MEDIA.get(ext.lower(), 'application/octet-stream')


def _attach(name: str) -> dict:
    """내려받을 파일 이름. **한글이 안 깨져야 한다.**

    `filename=` 에는 ASCII 만 들어가므로 한글 제목은 그대로 못 쓴다. RFC 5987 의
    `filename*=UTF-8''…` 를 같이 보내면 요즘 브라우저는 그쪽을 읽는다. 옛 브라우저를
    위해 ASCII 쪽도 남기되, 거기엔 못 쓰는 글자를 밑줄로 바꾼 이름을 둔다.
    """
    ascii_name = name.encode('ascii', 'replace').decode('ascii').replace('?', '_')
    quoted = urllib.parse.quote(name, safe='')
    return {'Content-Disposition':
            f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quoted}'}


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

    @app.get('/api/export/formats')
    def export_formats():
        """무엇으로 내보낼 수 있는지. 화면이 이 목록으로 고르는 자리를 그린다."""
        return {'formats': [{'key': k, 'label': v['label'], 'ext': v['ext'],
                             'desc': v.get('desc', '')}
                            for k, v in render.FORMATS.items()],
                'mixes': [{'key': k, 'label': v['label'], 'desc': v.get('desc', '')}
                          for k, v in render.MIXES.items()]}

    @app.get('/api/songs/{song_id}/export')
    def export(song_id: str, formats: str = 'midi',
               style: Optional[str] = None, level: Optional[str] = None,
               bpm: Optional[int] = None, mix: str = 'mr',
               count_in: Optional[int] = None, stems: bool = False):
        """고른 형식들로 구워서 내려보낸다.

        하나면 그 파일을, 여럿이거나 스템까지면 zip 으로 묶는다. 캐시에 안 남긴다 —
        편성·템포 조합마다 영상편집용 WAV 가 쌓이면 원장님 디스크가 먼저 찬다.
        받아 가면 지운다(`BackgroundTask`).
        """
        _song(song_id)
        want = [f.strip() for f in formats.split(',') if f.strip()]
        bad = [f for f in want if f not in render.FORMATS]
        if bad:
            raise HTTPException(400, f"모르는 형식입니다: {', '.join(bad)} "
                                     f"(가능: {', '.join(render.FORMATS)})")
        work = tempfile.mkdtemp(prefix='mr_export_')
        try:
            info = st.export(song_id, work, formats=want, style=style, level=level,
                             bpm=bpm, mix=mix, count_in=count_in, stems=stems)
        except (render.ToolMissingError, RuntimeError) as e:
            shutil.rmtree(work, ignore_errors=True)
            raise HTTPException(503, str(e))
        except (ValueError, KeyError) as e:
            shutil.rmtree(work, ignore_errors=True)
            raise HTTPException(400, str(e))

        base = st.export_tag(st.catalog.get(song_id), info['style'], info['level'],
                             info['bpm'], info['mix'])
        cleanup = BackgroundTask(shutil.rmtree, work, ignore_errors=True)

        # 파일 하나면 그대로. 이름에서 `_midi` 같은 꼬리를 떼고 사람이 읽는 이름으로.
        if len(info['files']) == 1 and not info['stems']:
            kind, path = next(iter(info['files'].items()))
            ext = render.FORMATS[kind]['ext']
            return FileResponse(path, media_type=_media(ext),
                                background=cleanup,
                                headers=_attach(f'{base} {render.FORMATS[kind]["label"]}{ext}'))

        zpath = os.path.join(work, '_bundle.zip')
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
            for kind, path in info['files'].items():
                spec = render.FORMATS[kind]
                z.write(path, f'{base} {spec["label"]}{spec["ext"]}')
            for name, path in info['stems'].items():
                z.write(path, f'파트별/{base} {name}.wav')
        return FileResponse(zpath, media_type='application/zip', background=cleanup,
                            headers=_attach(f'{base}.zip'))

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

    # --- 4단계 PDF 업로드 (지시서 9장 4단계) --------------------------------
    def _job(job_id: str):
        try:
            return st.ledger.get(job_id)
        except KeyError as e:
            raise HTTPException(404, str(e))

    def _guard(fn, *a, **kw):
        """업로드 경로의 거절 사유를 그대로 화면에 보낸다.

        왜 무엇이 거절됐는지 모르면 원장님은 같은 PDF 를 다시 올린다. 그때마다
        쿼터가 깎이지는 않지만(검사가 먼저다) 시간이 낭비되고 신뢰가 깎인다.
        """
        try:
            return fn(*a, **kw)
        except cat.CopyrightError as e:
            raise HTTPException(451, str(e))       # 법적 사유로 못 받는다
        except uploads.QuotaExceeded as e:
            raise HTTPException(429, str(e))
        except pdf.PdfError as e:
            raise HTTPException(415, str(e))
        except omr.OmrUnavailable as e:
            raise HTTPException(503, str(e))
        except (ValueError, KeyError) as e:
            raise HTTPException(400, str(e))

    @app.get('/api/uploads')
    def upload_list(account: str = ''):
        return st.uploads_view(account)

    @app.post('/api/uploads')
    async def upload_pdf(file: UploadFile = File(...), account: str = Form(...),
                         title: str = Form('')):
        # PDF 업로드는 **돈이 나가는 유일한 경로**다 (지시서 8.2 — OMR 이 유일한 변동비).
        # 인증되지 않은 설치본이 남의 크레딧을 태우면 안 되므로 여기만 키를 본다.
        # 카탈로그 제작·발표회 운영·집 연습 링크는 묻지 않는다.
        v = _license()
        if not v.ok:
            raise HTTPException(402, f'{v.reason} — PDF 업로드는 인증된 설치본에서만 '
                                     '됩니다. 관리노트와 같은 인증키를 '
                                     f'{lic.ENV_KEY} 환경변수에 넣어 주세요.')
        data = await file.read()
        return _guard(st.submit_pdf, data, file.filename or 'score.pdf',
                      account=account, title=title)

    @app.get('/api/uploads/{job_id}')
    def upload_one(job_id: str):
        _job(job_id)
        return _guard(st.job_view, job_id)

    @app.post('/api/uploads/{job_id}/poll')
    def upload_poll(job_id: str):
        _job(job_id)
        return _guard(st.poll_upload, job_id)

    @app.post('/api/uploads/{job_id}/musicxml')
    async def upload_adopt(job_id: str, file: UploadFile = File(...)):
        """신청제 투입구 — 사람이 만든 MusicXML 을 그 작업에 붙인다 (지시서 8.3 ③)."""
        _job(job_id)
        data = await file.read()
        return _guard(st.adopt_musicxml, job_id, data)

    @app.post('/api/uploads/{job_id}/finish')
    def upload_finish(job_id: str):
        _job(job_id)
        return _guard(st.finish_upload, job_id)

    @app.delete('/api/uploads/{job_id}')
    def upload_cancel(job_id: str):
        _job(job_id)
        return _guard(st.cancel_upload, job_id)

    @app.post('/api/uploads/sweep')
    def upload_sweep(hours: float = 72.0):
        """올라온 PDF 를 오래 들고 있지 않는다 (지시서 7장)."""
        return st.sweep(older_than_hours=hours)

    # --- 5단계 관리노트 연동 (지시서 9장 5단계) ------------------------------
    # --- 번들 인증 (지시서 9장 5단계 "번들 판매") ------------------------------
    def _license() -> lic.Verdict:
        """환경변수의 키를 본다. 학원명은 명단에서 받은 것을 기본으로 쓴다."""
        env = dict(os.environ)
        env.setdefault(lic.ENV_NAME, st.roster.academy or '')
        return lic.from_env(env)

    @app.get('/api/license')
    def license_state():
        v = _license()
        return {'ok': v.ok, 'plan': v.plan, 'product': v.product,
                'source': v.source, 'reason': v.reason,
                'academy': st.roster.academy,
                # 집 연습 링크는 인증을 묻지 않는다 (지시서 ⑤-10)
                'gated': ['upload']}

    @app.get('/api/roster')
    def roster_get():
        """반주 쪽이 들고 있는 학생 명단."""
        return st.roster.view()

    @app.post('/api/roster')
    async def roster_put(file: UploadFile = File(...)):
        """관리노트가 내보낸 명단을 받는다. **덮어쓰기다** — 관리노트가 원본이다."""
        data = await file.read()
        try:
            return st.import_roster(data)
        except roster.RosterError as e:
            raise HTTPException(400, str(e))

    app.mount('/static', StaticFiles(directory=STATIC, html=True), name='static')
    return app
