# -*- coding: utf-8 -*-
"""업로드 원장 — 월 제한과 작업 상태 (지시서 9장 4단계 · 7장 · 8.2).

지시서가 이 모듈에 못 박은 것이 셋이다.

**① 월 업로드 제한** (9장 4단계 필수 항목). 단위는 **페이지**다. 8.2 가
"Klangio Scan2Notes Pro = 월 50 스캔", "스캔 1장 ≈ 300~400원", "월 5~10장 제한을
걸면 변동비가 월 2~4천원으로 묶인다"라고 했으니 과금 단위가 곧 제한 단위여야 한다.
작업(문서) 수로 세면 40쪽짜리 한 편으로 한 달 예산이 날아간다.

**② PDF 를 영구 보관하지 않는다** (7장 "서버 영구 저장·재배포 금지"). 그래서 PDF 는
`incoming/` 격리 폴더에만 잠깐 두고, MusicXML 이 나오는 순간 지운다. 실패하거나
방치된 작업도 `sweep()` 이 쓸어낸다. 카탈로그로 들어가는 것은 MusicXML 뿐이다.

**③ 업로드본은 해당 계정 전용** (7장). 카탈로그 곡(`public_domain=True`)과 섞이면
안 된다. 작업마다 `account` 를 달고, 곡에도 표시를 남긴다.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional

# 작업 상태 — 화면에 그대로 보여 줄 수 있는 말로
RECEIVED = 'received'    # 받았다 (PDF 가 격리 폴더에 있다)
RUNNING = 'omr'          # 악보 인식 중 (또는 사람이 처리 중)
REVIEW = 'review'        # 화성 확인 화면에서 볼 차례
DONE = 'done'            # 확인까지 끝났다
FAILED = 'failed'        # 인식 실패
CANCELLED = 'cancelled'  # 원장님이 취소

OPEN_STATES = (RECEIVED, RUNNING)          # PDF 를 아직 들고 있을 수 있는 상태
CLOSED_STATES = (DONE, FAILED, CANCELLED)

STATE_LABEL = {
    RECEIVED: '접수됨',
    RUNNING: '악보 인식 중',
    REVIEW: '화성 확인 대기',
    DONE: '완료',
    FAILED: '인식 실패',
    CANCELLED: '취소됨',
}

# 지시서 8.3 ①: "PDF 업로드는 월 5~10장 제한을 걸면 변동비가 월 2~4천원으로 묶인다"
DEFAULT_MONTHLY_PAGES = 10
MAX_PAGES_PER_UPLOAD = 20        # 한 번에 통째로 예산을 태우지 못하게
MAX_BYTES = 32 * 1024 * 1024

# 지시서 8.2 — 화면에 비용을 그대로 보여 주기 위한 단가 (원/쪽)
WON_PER_PAGE = 400


class QuotaExceeded(RuntimeError):
    """이번 달 몫을 다 썼다."""


def month_key(at: Optional[float] = None) -> str:
    return time.strftime('%Y-%m', time.localtime(at if at else time.time()))


@dataclass
class UploadJob:
    id: str
    account: str
    filename: str
    pages: int
    state: str = RECEIVED
    provider: str = ''
    job_ref: str = ''
    song_id: str = ''
    title: str = ''
    detail: str = ''
    month: str = ''
    created_at: str = ''
    updated_at: str = ''
    pdf_kept: bool = False        # 격리 폴더에 PDF 가 아직 있는가
    # PDF 가 격리 폴더에 들어온 시각. **보관 시계는 이걸로 잰다.**
    # `updated_at` 으로 재면, 폴링이 작업을 건드릴 때마다 시계가 되감겨
    # 오래 도는 작업의 PDF 가 영영 안 지워진다 (지시서 7장 위반).
    pdf_at: str = ''

    @property
    def open(self) -> bool:
        return self.state in OPEN_STATES

    @property
    def label(self) -> str:
        return STATE_LABEL.get(self.state, self.state)

    def view(self) -> dict:
        d = asdict(self)
        d['label'] = self.label
        d['won'] = self.pages * WON_PER_PAGE
        return d


class UploadLedger:
    """작업 목록과 월별 사용량. JSON 한 파일."""

    def __init__(self, path: str, monthly_pages: int = DEFAULT_MONTHLY_PAGES):
        self.path = path
        self.monthly_pages = int(monthly_pages)
        self.jobs: Dict[str, UploadJob] = {}
        self.load()

    # --- 저장 ------------------------------------------------------------
    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, encoding='utf-8') as f:
            raw = json.load(f)
        self.monthly_pages = int(raw.get('monthly_pages', self.monthly_pages))
        known = set(UploadJob.__dataclass_fields__)
        self.jobs = {j['id']: UploadJob(**{k: v for k, v in j.items() if k in known})
                     for j in raw.get('jobs', [])}

    def save(self) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump({'monthly_pages': self.monthly_pages,
                       'jobs': [asdict(j) for j in self.jobs.values()]},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)          # 중간에 죽어도 원장이 깨지지 않게
        return self.path

    # --- 쿼터 ------------------------------------------------------------
    def used_pages(self, account: str = '', month: Optional[str] = None) -> int:
        """이번 달에 쓴 쪽수.

        취소한 작업은 빼 준다 — 취소는 OMR 을 돌리기 전에만 되므로 돈이 안 나갔다.
        **실패는 빼지 않는다.** 서비스는 이미 스캔을 했고 과금도 됐다.
        """
        m = month or month_key()
        return sum(j.pages for j in self.jobs.values()
                   if j.month == m and j.state != CANCELLED
                   and (not account or j.account == account))

    def remaining(self, account: str = '', month: Optional[str] = None) -> int:
        return max(0, self.monthly_pages - self.used_pages(account, month))

    def quota(self, account: str = '') -> dict:
        m = month_key()
        used = self.used_pages(account, m)
        return {'month': m, 'limit': self.monthly_pages, 'used': used,
                'remaining': max(0, self.monthly_pages - used),
                'won_per_page': WON_PER_PAGE,
                'spent_won': used * WON_PER_PAGE,
                'max_pages_per_upload': MAX_PAGES_PER_UPLOAD}

    def check(self, pages: int, account: str = '') -> None:
        """받아 줄 수 있는지. 안 되면 왜 안 되는지 말한다."""
        if pages <= 0:
            raise ValueError('페이지 수를 셀 수 없는 PDF 입니다.')
        if pages > MAX_PAGES_PER_UPLOAD:
            raise QuotaExceeded(
                f'한 번에 올릴 수 있는 것은 {MAX_PAGES_PER_UPLOAD}쪽까지입니다 '
                f'(올리신 것은 {pages}쪽). 곡 단위로 나눠서 올려 주세요.')
        left = self.remaining(account)
        if pages > left:
            raise QuotaExceeded(
                f'이번 달 남은 몫이 {left}쪽입니다 ({pages}쪽을 올리셨습니다). '
                f'매달 1일에 {self.monthly_pages}쪽으로 다시 채워집니다.')

    # --- 작업 ------------------------------------------------------------
    def add(self, *, account: str, filename: str, pages: int, provider: str,
            title: str = '') -> UploadJob:
        self.check(pages, account)
        now = time.strftime('%Y-%m-%dT%H:%M:%S')
        job = UploadJob(id=uuid.uuid4().hex[:12], account=account,
                        filename=filename, pages=pages, provider=provider,
                        title=title, month=month_key(),
                        created_at=now, updated_at=now)
        self.jobs[job.id] = job
        self.save()
        return job

    def get(self, job_id: str) -> UploadJob:
        try:
            return self.jobs[job_id]
        except KeyError:
            raise KeyError(f'그런 업로드 작업이 없습니다: {job_id}')

    def update(self, job_id: str, **changes) -> UploadJob:
        job = self.get(job_id)
        for k, v in changes.items():
            if k not in UploadJob.__dataclass_fields__:
                raise KeyError(f'모르는 항목입니다: {k}')
            setattr(job, k, v)
        if 'updated_at' not in changes:
            job.updated_at = time.strftime('%Y-%m-%dT%H:%M:%S')
        self.save()
        return job

    def rows(self, account: str = '', state: str = '') -> List[dict]:
        out = [j for j in self.jobs.values()
               if (not account or j.account == account)
               and (not state or j.state == state)]
        out.sort(key=lambda j: j.created_at, reverse=True)
        return [j.view() for j in out]

    def stale(self, older_than_hours: float = 72.0) -> List[UploadJob]:
        """PDF 를 너무 오래 들고 있는 작업 (지시서 7장 — 영구 보관 금지).

        시계는 `pdf_at`(PDF 가 들어온 시각)으로 잰다. `updated_at` 으로 재면
        폴링이 건드릴 때마다 되감겨서, 오래 도는 작업일수록 PDF 가 더 오래 남는다.
        """
        cutoff = time.time() - older_than_hours * 3600
        out = []
        for j in self.jobs.values():
            if not j.pdf_kept:
                continue
            try:
                t = time.mktime(time.strptime(j.pdf_at or j.created_at,
                                              '%Y-%m-%dT%H:%M:%S'))
            except ValueError:
                out.append(j)               # 시각을 못 읽으면 오래된 것으로 친다
                continue
            if t < cutoff:
                out.append(j)
        return out
