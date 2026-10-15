# -*- coding: utf-8 -*-
"""OMR 제공자 — 지시서 9장 4단계 "OMR API 연동".

`HttpProvider` 는 공급사 서비스를 상대로 돌려 본 적이 없다 (작업 환경에서 klang.io 가
egress 정책에 막혀 문서를 볼 수 없었다). 그래서 **확인할 수 있는 것만 확인한다** —
멀티파트를 제대로 싸는지, 폴링이 상태를 옳게 옮기는지, 실패를 삼키지 않는지.
이건 진짜 HTTP 서버를 띄워서 본다. 공급사 필드 이름은 설정이므로 시험 대상이 아니다.
"""
import http.server
import json
import threading

import pytest

from piano_mr import omr


class _Handler(http.server.BaseHTTPRequestHandler):
    """진짜 OMR 서비스인 척하는 최소 서버."""

    jobs = {}
    seen = {}
    polls_before_ready = 0

    def log_message(self, *a):        # 테스트 출력이 지저분해지지 않게
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(n)
        if self.path == '/boom':
            body = b'out of credits'
            self.send_response(402)                    # 예: 크레딧 소진
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        _Handler.seen = {
            'content_type': self.headers.get('Content-Type', ''),
            'auth': self.headers.get('kl-api-key') or self.headers.get('Authorization'),
            'body': raw,
        }
        _Handler.jobs['job-7'] = 0
        self._json(200, {'job_id': 'job-7'})

    def do_GET(self):
        if self.path.startswith('/status/'):
            ref = self.path.rsplit('/', 1)[-1]
            hits = _Handler.jobs.get(ref, 0)
            _Handler.jobs[ref] = hits + 1
            state = 'done' if hits >= _Handler.polls_before_ready else 'running'
            self._json(200, {'status': state})
            return
        if self.path.startswith('/result/'):
            body = b'<score-partwise/>'
            self.send_response(200)
            self.send_header('Content-Type', 'application/xml')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(404, {'error': 'nope'})


@pytest.fixture
def omr_server():
    _Handler.jobs = {}
    _Handler.seen = {}
    _Handler.polls_before_ready = 0
    srv = http.server.HTTPServer(('127.0.0.1', 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f'http://127.0.0.1:{srv.server_port}', _Handler
    srv.shutdown()
    srv.server_close()


def config_for(base: str) -> omr.OmrConfig:
    return omr.OmrConfig(
        base=base, key='secret-key', key_header='kl-api-key',
        submit_path='/submit', status_path='/status/{job}',
        result_path='/result/{job}', timeout=10)


# --- 신청제 ------------------------------------------------------------------

def test_manual_is_the_default_because_it_costs_nothing():
    """지시서 8.3 ③. 키가 없어도 4단계가 굴러가야 한다."""
    p = omr.make_provider()
    assert p.name == 'manual' and p.needs_key is False


def test_manual_parks_the_job_for_a_human():
    p = omr.ManualProvider()
    ref = p.submit(b'%PDF-1.4', 'czerny5.pdf')
    assert ref.startswith('manual-')
    r = p.poll(ref)
    assert r.state == omr.PENDING and '1~2일' in r.detail
    with pytest.raises(omr.OmrError):
        p.fetch(ref)


# --- REST 클라이언트 ------------------------------------------------------------

def test_http_submit_sends_a_real_multipart_with_the_key(omr_server):
    base, handler = omr_server
    p = omr.HttpProvider(config_for(base))
    assert p.submit(b'%PDF-1.4 fake bytes', 'score.pdf') == 'job-7'
    assert handler.seen['auth'] == 'secret-key'
    assert handler.seen['content_type'].startswith('multipart/form-data; boundary=')
    body = handler.seen['body']
    assert b'name="file"; filename="score.pdf"' in body
    assert b'Content-Type: application/pdf' in body
    assert b'%PDF-1.4 fake bytes' in body


def test_http_defaults_to_bearer_when_no_header_name_is_given(omr_server):
    base, handler = omr_server
    cfg = config_for(base)
    cfg.key_header = ''
    omr.HttpProvider(cfg).submit(b'%PDF', 'a.pdf')
    assert handler.seen['auth'] == 'Bearer secret-key'


def test_http_polls_until_ready_then_fetches(omr_server):
    base, handler = omr_server
    handler.polls_before_ready = 2
    p = omr.HttpProvider(config_for(base))
    ref = p.submit(b'%PDF', 'a.pdf')
    assert p.poll(ref).state == omr.PENDING
    assert p.poll(ref).state == omr.PENDING
    assert p.poll(ref).state == omr.READY
    assert p.fetch(ref) == b'<score-partwise/>'


def test_http_reports_a_failed_job_instead_of_hanging(omr_server):
    base, handler = omr_server
    cfg = config_for(base)
    cfg.ready_values = ()
    cfg.failed_values = ('done',)             # 서버의 'done' 을 실패로 읽게 한다
    p = omr.HttpProvider(cfg)
    ref = p.submit(b'%PDF', 'a.pdf')
    r = p.poll(ref)
    assert r.state == omr.FAILED and r.detail


def test_http_surfaces_an_http_error_body(omr_server):
    """크레딧 소진 같은 건 조용히 넘기면 안 된다 — 돈이 걸린 경로다."""
    base, _ = omr_server
    cfg = config_for(base)
    cfg.submit_path = '/boom'
    with pytest.raises(omr.OmrError) as e:
        omr.HttpProvider(cfg).submit(b'%PDF', 'a.pdf')
    assert '402' in str(e.value) and 'credits' in str(e.value)


def test_http_says_what_is_missing_rather_than_guessing_a_url():
    """주소를 지어내지 않는다 — 공급사 문서를 확인할 수 없었다 (omr.py 설명)."""
    p = omr.HttpProvider(omr.OmrConfig())
    with pytest.raises(omr.OmrUnavailable) as e:
        p.submit(b'%PDF', 'a.pdf')
    for name in ('MR_OMR_BASE', 'MR_OMR_SUBMIT', 'MR_OMR_RESULT'):
        assert name in str(e.value)


def test_http_reports_an_unreachable_service(omr_server):
    base, _ = omr_server
    cfg = config_for(base.replace(base.rsplit(':', 1)[-1], '1'))   # 닫힌 포트
    with pytest.raises(omr.OmrUnavailable):
        omr.HttpProvider(cfg).submit(b'%PDF', 'a.pdf')


def test_config_reads_the_environment():
    cfg = omr.OmrConfig.from_env({
        'MR_OMR_BASE': 'https://api.example.com/',
        'MR_OMR_SUBMIT': '/t', 'MR_OMR_RESULT': '/t/{job}/xml',
        'MR_OMR_KEY': 'k', 'MR_OMR_FIELDS': '{"model":"sheet"}',
    })
    assert cfg.base == 'https://api.example.com'      # 끝 슬래시를 떼 준다
    assert cfg.configured and cfg.extra_fields == {'model': 'sheet'}


def test_config_rejects_broken_extra_fields():
    with pytest.raises(omr.OmrUnavailable):
        omr.OmrConfig.from_env({'MR_OMR_FIELDS': 'not json'})


def test_unknown_provider_is_refused():
    with pytest.raises(omr.OmrUnavailable):
        omr.make_provider('망상')
