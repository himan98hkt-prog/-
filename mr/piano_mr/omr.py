# -*- coding: utf-8 -*-
"""OMR — PDF 악보를 MusicXML 로 (지시서 9장 4단계, 모듈 표의 유일한 외부 유료 요소).

세 가지를 갈아 끼울 수 있게 해 둔다.

    ManualProvider   신청제. 원장님이 올리면 사람이 1~2일 안에 MusicXML 을 넣어 준다.
                     지시서 8.3 ③ 이 권하는 방식이고, **오늘 당장 돌아가며 API 비용이 0원**이다.
    LocalProvider    원장님 PC 에서 Audiveris(오픈소스)를 돌린다. **돈이 안 들고
                     악보가 밖으로 안 나간다.** 인식 결과물은 인식한 쪽 것이라
                     남의 입력본 약정이 안 붙는다 (`piano_mr/provenance.py`).
    HttpProvider     REST OMR 서비스. 주소·헤더·필드 이름을 설정으로 받는다.
    FakeProvider     테스트용.

**HttpProvider 를 왜 설정으로 받는가.** 이 작업을 한 환경에서 `klang.io` 와
`api-docs.klang.io` 가 둘 다 조직 egress 정책에 막혀(프록시가 차단) 공식 API 문서를
확인할 수 없었다. 기억으로 엔드포인트 이름을 지어내 하드코딩하면, 그럴듯한데 틀린
코드가 남아 나중에 디버깅 비용이 된다. 그래서 **모양만 잡고 값은 설정으로 뺐다** —
키와 문서가 손에 들어오면 `OmrConfig` 한 곳만 채우면 된다. 코드는 안 고친다.

흐름은 어느 서비스나 같다:

    submit(pdf) -> job_id      멀티파트로 올린다
    poll(job_id) -> 상태        끝났는지 묻는다
    fetch(job_id) -> MusicXML   결과를 받는다
"""
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

# 작업 상태 — 제공자가 뭐라고 부르든 이 셋 중 하나로 옮긴다
PENDING = 'pending'      # 아직 하는 중
READY = 'ready'          # 결과가 나왔다
FAILED = 'failed'        # 실패했다
STATES = (PENDING, READY, FAILED)


class OmrError(RuntimeError):
    """OMR 을 돌릴 수 없었다."""


class OmrUnavailable(OmrError):
    """설정이 안 되어 있거나 서비스에 닿지 못했다."""


@dataclass
class OmrResult:
    state: str
    musicxml: Optional[bytes] = None
    detail: str = ''

    def __post_init__(self):
        if self.state not in STATES:
            raise ValueError(f'모르는 상태입니다: {self.state!r}')


# --------------------------------------------------------------------------
# 신청제 — 지시서 8.3 ③ "원장님이 악보를 보내면 1~2일 내 납품"
# --------------------------------------------------------------------------

class ManualProvider:
    """사람이 처리한다. API 비용 0원, 오늘 당장 돌아간다.

    지시서 8.3 이 그냥 대안으로 적어 둔 게 아니다 — *"품질 보장이 되고 기대치 관리가
    된다. 경험상 '무한 자동생성'보다 잘 팔린다."* 그리고 이 경로는 OMR 이 90~95%
    라는 사실(지시서 2.2)과도 맞는다. 어차피 사람이 화성 확인 화면을 봐야 한다면,
    악보 인식 단계에서 사람이 한 번 보는 것이 전체 품질에 더 낫다.
    """

    name = 'manual'
    needs_key = False
    blocking = False          # 즉시 결과가 나오지 않는다

    def __init__(self, turnaround_note: str = '1~2일 안에 처리됩니다'):
        self.turnaround_note = turnaround_note

    def submit(self, pdf_bytes: bytes, filename: str) -> str:
        # 사람이 집어 갈 수 있게 작업 번호만 끊어 준다. 파일 보관은 호출부(store)가
        # 한다 — 지시서 7장의 "영구 저장 금지"를 한 곳에서만 지키게 하려고.
        return f'manual-{uuid.uuid4().hex[:12]}'

    def poll(self, job_ref: str) -> OmrResult:
        return OmrResult(PENDING, detail=self.turnaround_note)

    def fetch(self, job_ref: str) -> bytes:
        raise OmrError('신청제 작업입니다 — 사람이 MusicXML 을 넣어 주면 이어집니다.')


# --------------------------------------------------------------------------
# REST OMR 서비스
# --------------------------------------------------------------------------

@dataclass
class OmrConfig:
    """어느 REST OMR 서비스를 어떻게 부를지.

    기본값은 비어 있다. **아무 주소도 지어내지 않는다** — 위 모듈 설명 참고.
    환경변수로 채운다:

        MR_OMR_BASE       https://api.example.com
        MR_OMR_KEY        발급받은 키
        MR_OMR_SUBMIT     /transcription            (POST, multipart)
        MR_OMR_STATUS     /transcription/{job}      (GET)
        MR_OMR_RESULT     /transcription/{job}/musicxml  (GET)
        MR_OMR_KEY_HEADER kl-api-key                (기본: Authorization Bearer)
        MR_OMR_FILE_FIELD file
        MR_OMR_JOB_FIELD  job_id
        MR_OMR_STATE_FIELD status
    """
    base: str = ''
    key: str = ''
    submit_path: str = ''
    status_path: str = ''
    result_path: str = ''
    key_header: str = ''
    file_field: str = 'file'
    job_field: str = 'job_id'
    state_field: str = 'status'
    ready_values: tuple = ('ready', 'done', 'completed', 'success', 'finished')
    failed_values: tuple = ('failed', 'error', 'cancelled', 'canceled')
    extra_fields: Dict[str, str] = field(default_factory=dict)
    timeout: float = 60.0

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> 'OmrConfig':
        e = os.environ if env is None else env
        extra = {}
        raw = e.get('MR_OMR_FIELDS', '')
        if raw:
            try:
                extra = json.loads(raw)
            except ValueError:
                raise OmrUnavailable('MR_OMR_FIELDS 가 JSON 이 아닙니다.')
        return cls(
            base=e.get('MR_OMR_BASE', '').rstrip('/'),
            key=e.get('MR_OMR_KEY', ''),
            submit_path=e.get('MR_OMR_SUBMIT', ''),
            status_path=e.get('MR_OMR_STATUS', ''),
            result_path=e.get('MR_OMR_RESULT', ''),
            key_header=e.get('MR_OMR_KEY_HEADER', ''),
            file_field=e.get('MR_OMR_FILE_FIELD', 'file'),
            job_field=e.get('MR_OMR_JOB_FIELD', 'job_id'),
            state_field=e.get('MR_OMR_STATE_FIELD', 'status'),
            extra_fields=extra,
            timeout=float(e.get('MR_OMR_TIMEOUT', '60')),
        )

    @property
    def configured(self) -> bool:
        return bool(self.base and self.submit_path and self.result_path)

    def missing(self) -> str:
        gaps = [n for n, v in (('MR_OMR_BASE', self.base),
                               ('MR_OMR_SUBMIT', self.submit_path),
                               ('MR_OMR_RESULT', self.result_path)) if not v]
        return ', '.join(gaps)


def _multipart(fields: Dict[str, str], filename: str, file_field: str,
               payload: bytes) -> tuple:
    """multipart/form-data 를 손으로 만든다 (requests 의존성을 피한다)."""
    boundary = '----mr' + uuid.uuid4().hex
    ctype = mimetypes.guess_type(filename)[0] or 'application/pdf'
    out = bytearray()
    for k, v in fields.items():
        out += (f'--{boundary}\r\n'
                f'Content-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
                ).encode('utf-8')
    out += (f'--{boundary}\r\n'
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{filename}"\r\n'
            f'Content-Type: {ctype}\r\n\r\n').encode('utf-8')
    out += payload
    out += f'\r\n--{boundary}--\r\n'.encode('utf-8')
    return bytes(out), f'multipart/form-data; boundary={boundary}'


class HttpProvider:
    """설정으로 주소를 받는 REST OMR 클라이언트.

    **이 클래스는 실제 서비스를 상대로 돌려 본 적이 없다.** 작업 환경에서 공급사
    문서 호스트가 egress 정책에 막혀 있었기 때문이다. 모양(멀티파트 업로드 →
    작업 번호 → 폴링 → 다운로드)은 이 바닥에서 보편적이지만, 필드 이름까지 맞는지는
    키를 받아 한 번 돌려 봐야 안다. 그래서 전부 설정이다.
    """

    name = 'http'
    needs_key = True
    blocking = False

    def __init__(self, config: Optional[OmrConfig] = None,
                 opener: Optional[Callable] = None):
        self.config = config or OmrConfig.from_env()
        self._open = opener or urllib.request.urlopen

    def _require(self) -> OmrConfig:
        c = self.config
        if not c.configured:
            raise OmrUnavailable(
                f'OMR 서비스 설정이 비어 있습니다 ({c.missing()}). '
                '신청제(manual)로 두거나 환경변수를 채우세요 — piano_mr/omr.py 참고.')
        return c

    def _headers(self) -> Dict[str, str]:
        c = self.config
        if not c.key:
            return {}
        if c.key_header:
            return {c.key_header: c.key}
        return {'Authorization': f'Bearer {c.key}'}

    def _call(self, url: str, data: Optional[bytes] = None,
              content_type: str = '') -> bytes:
        headers = self._headers()
        if content_type:
            headers['Content-Type'] = content_type
        req = urllib.request.Request(url, data=data, headers=headers,
                                     method='POST' if data else 'GET')
        try:
            with self._open(req, timeout=self.config.timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8', 'replace')[:300]
            except Exception:                        # noqa: BLE001 - 읽기 실패는 무시
                pass
            raise OmrError(f'OMR 서비스가 {e.code} 를 돌려줬습니다. {body}')
        except urllib.error.URLError as e:
            raise OmrUnavailable(f'OMR 서비스에 닿지 못했습니다: {e.reason}')

    def submit(self, pdf_bytes: bytes, filename: str) -> str:
        c = self._require()
        body, ctype = _multipart(c.extra_fields, filename, c.file_field, pdf_bytes)
        raw = self._call(c.base + c.submit_path, body, ctype)
        try:
            data = json.loads(raw.decode('utf-8', 'replace'))
        except ValueError:
            raise OmrError('OMR 서비스 응답이 JSON 이 아닙니다.')
        job = data.get(c.job_field) or data.get('id') or data.get('job')
        if not job:
            raise OmrError(
                f'응답에서 작업 번호({c.job_field})를 못 찾았습니다: {sorted(data)}')
        return str(job)

    def poll(self, job_ref: str) -> OmrResult:
        c = self._require()
        if not c.status_path:                        # 상태 주소가 없으면 바로 받아 본다
            try:
                return OmrResult(READY, musicxml=self.fetch(job_ref))
            except OmrError as e:
                return OmrResult(PENDING, detail=str(e))
        raw = self._call(c.base + c.status_path.replace('{job}', job_ref))
        try:
            data = json.loads(raw.decode('utf-8', 'replace'))
        except ValueError:
            raise OmrError('OMR 상태 응답이 JSON 이 아닙니다.')
        state = str(data.get(c.state_field, '')).lower()
        if state in c.failed_values:
            return OmrResult(FAILED, detail=str(data.get('message') or state))
        if state in c.ready_values:
            return OmrResult(READY)
        return OmrResult(PENDING, detail=state or '처리 중')

    def fetch(self, job_ref: str) -> bytes:
        c = self._require()
        return self._call(c.base + c.result_path.replace('{job}', job_ref))


# --------------------------------------------------------------------------
# 테스트용
# --------------------------------------------------------------------------

class FakeProvider:
    """미리 정해 둔 MusicXML 을 돌려준다. 지연·실패도 흉내 낸다."""

    name = 'fake'
    needs_key = False
    blocking = True

    def __init__(self, musicxml: bytes = b'', *, delay: float = 0.0,
                 fail: str = ''):
        self.musicxml = musicxml
        self.delay = delay
        self.fail = fail
        self.submitted = []
        self._at = {}

    def submit(self, pdf_bytes: bytes, filename: str) -> str:
        ref = f'fake-{len(self.submitted)}'
        self.submitted.append((filename, len(pdf_bytes)))
        self._at[ref] = time.time()
        return ref

    def poll(self, job_ref: str) -> OmrResult:
        if self.fail:
            return OmrResult(FAILED, detail=self.fail)
        if time.time() - self._at.get(job_ref, 0) < self.delay:
            return OmrResult(PENDING, detail='흉내 내는 중')
        return OmrResult(READY)

    def fetch(self, job_ref: str) -> bytes:
        if self.fail:
            raise OmrError(self.fail)
        return self.musicxml


# --------------------------------------------------------------------------
# 원장님 PC 에서 도는 무료 인식기 (Audiveris)
# --------------------------------------------------------------------------

# Audiveris 배치 실행 규약. **추측이 아니라 소스에서 확인한 값이다**
# (github.com/Audiveris/audiveris · app/src/main/java/org/audiveris/omr/CLI.java).
#
#     audiveris -batch -export -output <폴더> -- <입력.pdf>
#
# 결과는 `<폴더>/<이름>/<이름>.mxl` 로 떨어진다. 악장이 여럿인 책이면
# `<이름>.opus.mxl` 이나 `<폴더>/<이름>/mvt1.mxl` 이 된다 (BookManager 주석).
LOCAL_CMD_ENV = 'MR_OMR_LOCAL_CMD'
LOCAL_ARGS_ENV = 'MR_OMR_LOCAL_ARGS'
LOCAL_TIMEOUT_ENV = 'MR_OMR_LOCAL_TIMEOUT'
DEFAULT_LOCAL_CMD = 'audiveris'
DEFAULT_LOCAL_TIMEOUT = 900.0          # 한 권을 통째로 넣는 경우가 있다
EXPORT_EXT = ('.mxl', '.musicxml', '.xml')

INSTALL_HINT = (
    'Audiveris 가 안 보입니다. 오픈소스 악보 인식기이고 **무료**입니다.\n'
    '  1) https://github.com/Audiveris/audiveris/releases 의 Assets 에서 내려받아 설치\n'
    '     자바는 따로 안 깔아도 됩니다 — 설치 파일에 같이 들어 있습니다.\n'
    '     윈도는 파일 이름에 **Console** 이 든 .msi 를 고르세요. 우리가 명령줄로\n'
    '     돌려 그 출력을 읽기 때문에, 콘솔 없는 쪽은 실패해도 이유가 안 보입니다.\n'
    f'  2) 실행 파일 경로를 {LOCAL_CMD_ENV} 에 넣으세요 (경로에 잡혀 있으면 생략)\n'
    '       윈도   C:\\Program Files\\Audiveris\\Audiveris.exe\n'
    '       리눅스 /opt/audiveris/bin/Audiveris\n'
    '       맥     /Applications/Audiveris.app/Contents/MacOS/Audiveris')


class LocalProvider:
    """원장님 PC 에서 Audiveris 를 돌려 PDF 를 MusicXML 로 바꾼다.

    **왜 이걸 만드는가.** 콩쿨에서 제일 많이 쓰는 교재(체르니·바이엘·부르크뮐러)
    는 곡이 만료된 지 백 년이 넘었는데도 **무료 MusicXML 이 거의 없다.** 남이
    쳐 넣은 파일은 대개 비영리 조건이 붙어 있어 파는 제품에 못 쓴다
    (`piano_mr/provenance.py`).

    IMSLP 에서 만료된 원판 PDF 를 받아 **직접 인식하면 그 결과물은 인식한 쪽
    것**이라 남의 약정이 안 붙는다. 이 경로가 라이선스로는 제일 깨끗하고,
    Audiveris 는 무료라 돈도 안 든다.

    **PDF 를 오래 들고 있지 않는다** (지시서 7장). 임시 폴더에 썼다가 인식이
    끝나는 즉시 지운다. 결과 MusicXML 만 메모리에 들고 있다가 `fetch()` 에서
    넘겨주고 그것도 버린다.

    시간이 걸리는 작업이라 `blocking = False` 다. 한 쪽에 10~60초쯤 걸린다.
    """

    name = 'local'
    needs_key = False
    blocking = False

    def __init__(self, cmd: Optional[str] = None, *,
                 extra_args: Optional[list] = None,
                 timeout: Optional[float] = None):
        self.cmd = cmd or os.environ.get(LOCAL_CMD_ENV) or DEFAULT_LOCAL_CMD
        raw = os.environ.get(LOCAL_ARGS_ENV, '')
        self.extra_args = list(extra_args if extra_args is not None else raw.split())
        self.timeout = float(timeout if timeout is not None
                             else os.environ.get(LOCAL_TIMEOUT_ENV,
                                                 DEFAULT_LOCAL_TIMEOUT))
        self._jobs: Dict[str, dict] = {}

    # --- 있는지 확인 ------------------------------------------------------
    def resolve(self) -> str:
        """실행 파일 경로. 없으면 **설치법을 말하고** 멈춘다."""
        found = shutil.which(self.cmd) or (
            self.cmd if os.path.isfile(self.cmd) and
            os.access(self.cmd, os.X_OK) else None)
        if not found:
            raise OmrUnavailable(INSTALL_HINT)
        return found

    def available(self) -> bool:
        try:
            self.resolve()
            return True
        except OmrUnavailable:
            return False

    # --- 작업 -------------------------------------------------------------
    def submit(self, pdf_bytes: bytes, filename: str) -> str:
        exe = self.resolve()
        ref = f'local-{uuid.uuid4().hex[:12]}'
        work = tempfile.mkdtemp(prefix='mr-omr-')
        # 파일 이름이 결과 파일 이름이 된다. 한글·공백이 섞이면 찾기 어려워지고
        # 윈도에서 깨지기도 하므로 **작업 번호로 바꿔서** 넣는다.
        pdf = os.path.join(work, f'{ref}.pdf')
        with open(pdf, 'wb') as f:
            f.write(pdf_bytes)
        out = os.path.join(work, 'out')
        os.makedirs(out, exist_ok=True)

        argv = [exe, '-batch', '-export', '-output', out,
                *self.extra_args, '--', pdf]
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        self._jobs[ref] = {'proc': proc, 'work': work, 'out': out, 'pdf': pdf,
                           'started': time.time(), 'name': filename,
                           'result': None, 'detail': ''}
        return ref

    def poll(self, job_ref: str) -> OmrResult:
        job = self._jobs.get(job_ref)
        if job is None:
            return OmrResult(FAILED, detail=f'모르는 작업입니다: {job_ref}')
        if job['result'] is not None:
            return OmrResult(READY)
        if job['detail'] and job['proc'] is None:
            return OmrResult(FAILED, detail=job['detail'])

        proc = job['proc']
        if proc.poll() is None:
            if time.time() - job['started'] > self.timeout:
                proc.kill()
                return self._fail(job, f'{self.timeout:.0f}초를 넘겨 멈췄습니다. '
                                       '쪽수가 많으면 나눠서 넣어 보세요.')
            return OmrResult(PENDING, detail='인식하는 중입니다')

        log = (proc.stdout.read() or b'').decode('utf-8', 'replace') if proc.stdout else ''
        job['proc'] = None
        # 인식이 끝났으면 PDF 는 더 필요 없다 — 지시서 7장, 바로 지운다.
        self._drop(job['pdf'])

        if proc.returncode != 0:
            return self._fail(job, f'인식에 실패했습니다 (코드 {proc.returncode}).\n'
                                   + _tail(log))
        found = _find_export(job['out'])
        if not found:
            return self._fail(job, '인식은 끝났는데 MusicXML 이 안 나왔습니다. '
                                   '악보가 아닌 PDF 이거나 너무 흐릴 수 있습니다.\n'
                                   + _tail(log))
        with open(found, 'rb') as f:
            job['result'] = f.read()
        shutil.rmtree(job['work'], ignore_errors=True)
        return OmrResult(READY)

    def fetch(self, job_ref: str) -> bytes:
        job = self._jobs.get(job_ref)
        if job is None:
            raise OmrError(f'모르는 작업입니다: {job_ref}')
        if job['result'] is None:
            raise OmrError(job['detail'] or '아직 결과가 없습니다 — poll() 을 먼저 보세요.')
        data = job['result']
        # 결과까지 넘겼으면 우리가 들고 있을 이유가 없다.
        self._jobs.pop(job_ref, None)
        return data

    # --- 뒷정리 -----------------------------------------------------------
    def _fail(self, job: dict, detail: str) -> OmrResult:
        job['detail'] = detail
        job['proc'] = None
        shutil.rmtree(job['work'], ignore_errors=True)
        return OmrResult(FAILED, detail=detail)

    @staticmethod
    def _drop(path: str) -> None:
        try:
            os.remove(path)
        except OSError:
            pass


def _tail(log: str, lines: int = 6) -> str:
    rows = [r for r in (log or '').splitlines() if r.strip()]
    return '\n'.join(rows[-lines:])


def _find_export(out_dir: str) -> Optional[str]:
    """Audiveris 가 떨어뜨린 MusicXML 을 찾는다.

    `<out>/<이름>/<이름>.mxl` 이 보통이지만 악장이 여럿이면 `mvt1.mxl` 처럼
    나뉘고 `.opus.mxl` 로 묶이기도 한다. 그래서 자리를 못 박지 않고 훑는다.
    여럿이면 **가장 큰 것** — 악장이 다 들어 있는 opus 쪽이다.
    """
    hits = []
    for root, _, files in os.walk(out_dir):
        for n in files:
            if n.lower().endswith(EXPORT_EXT):
                p = os.path.join(root, n)
                hits.append((os.path.getsize(p), p))
    if not hits:
        return None
    hits.sort(reverse=True)
    return hits[0][1]


PROVIDERS = {'manual': ManualProvider, 'local': LocalProvider,
             'http': HttpProvider, 'fake': FakeProvider}
DEFAULT_PROVIDER = 'manual'


def make_provider(name: Optional[str] = None, **kw):
    """이름으로 제공자를 만든다. 기본은 신청제 — 돈이 안 든다."""
    name = (name or os.environ.get('MR_OMR_PROVIDER') or DEFAULT_PROVIDER).lower()
    if name not in PROVIDERS:
        raise OmrUnavailable(
            f'모르는 OMR 제공자입니다: {name!r} (가능: {", ".join(sorted(PROVIDERS))})')
    return PROVIDERS[name](**kw)
