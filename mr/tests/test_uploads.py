# -*- coding: utf-8 -*-
"""업로드 원장 — 월 제한 (지시서 9장 4단계 필수 · 8.2 비용)."""
import json
import time

import pytest

from piano_mr import uploads


@pytest.fixture
def ledger(tmp_path):
    return uploads.UploadLedger(str(tmp_path / 'uploads.json'), monthly_pages=10)


def add(ledger, pages=1, account='학원', name='score.pdf'):
    return ledger.add(account=account, filename=name, pages=pages, provider='manual')


# --- 제한의 단위는 쪽이다 -------------------------------------------------------

def test_quota_counts_pages_not_documents():
    """지시서 8.2 는 스캔(=쪽) 단위로 과금한다. 문서 수로 세면 40쪽 한 편에 예산이 난다."""
    assert uploads.WON_PER_PAGE == 400
    assert uploads.DEFAULT_MONTHLY_PAGES == 10


def test_quota_spends_down_and_reports_money(ledger):
    add(ledger, pages=3)
    q = ledger.quota('학원')
    assert q['used'] == 3 and q['remaining'] == 7
    assert q['spent_won'] == 3 * 400


def test_quota_blocks_when_the_month_is_spent(ledger):
    add(ledger, pages=8)
    with pytest.raises(uploads.QuotaExceeded) as e:
        add(ledger, pages=3)
    assert '남은 몫이 2쪽' in str(e.value)
    add(ledger, pages=2)                      # 딱 맞는 건 통과
    assert ledger.remaining('학원') == 0


def test_one_upload_cannot_eat_the_whole_budget(ledger):
    ledger.monthly_pages = 500
    with pytest.raises(uploads.QuotaExceeded) as e:
        add(ledger, pages=uploads.MAX_PAGES_PER_UPLOAD + 1)
    assert '나눠서' in str(e.value)


def test_quota_is_per_account(ledger):
    add(ledger, pages=9, account='A학원')
    assert ledger.remaining('A학원') == 1
    assert ledger.remaining('B학원') == 10        # 남의 몫을 까먹지 않는다


def test_quota_refills_next_month(ledger):
    j = add(ledger, pages=10)
    assert ledger.remaining('학원') == 0
    ledger.update(j.id, month='2000-01')          # 지난달 것으로 돌린다
    assert ledger.remaining('학원') == 10


def test_cancelling_gives_the_pages_back_but_failing_does_not(ledger):
    """취소는 OMR 전에만 되니 돈이 안 나갔다. 실패는 이미 스캔했으니 과금됐다."""
    a = add(ledger, pages=4)
    b = add(ledger, pages=4)
    ledger.update(a.id, state=uploads.CANCELLED)
    ledger.update(b.id, state=uploads.FAILED)
    assert ledger.used_pages('학원') == 4
    assert ledger.remaining('학원') == 6


def test_unknown_page_count_is_refused(ledger):
    """PDF 검사기가 못 셌으면 추측하지 않는다 — 과금이 조용히 틀어진다."""
    with pytest.raises(ValueError):
        add(ledger, pages=0)


# --- 작업 ---------------------------------------------------------------------

def test_job_starts_received_and_carries_a_label(ledger):
    j = add(ledger)
    assert j.state == uploads.RECEIVED and j.label == '접수됨'
    assert j.open is True and j.view()['won'] == 400


def test_rows_are_newest_first_and_filterable(ledger):
    a = add(ledger, name='a.pdf')
    time.sleep(1.05)                          # created_at 이 초 단위라 갈라 준다
    b = add(ledger, name='b.pdf')
    assert [r['filename'] for r in ledger.rows('학원')] == ['b.pdf', 'a.pdf']
    ledger.update(a.id, state=uploads.REVIEW)
    assert [r['id'] for r in ledger.rows(state=uploads.REVIEW)] == [a.id]
    assert b.id not in [r['id'] for r in ledger.rows(state=uploads.REVIEW)]


def test_update_refuses_a_field_that_does_not_exist(ledger):
    j = add(ledger)
    with pytest.raises(KeyError):
        ledger.update(j.id, 상태='뭐라고')


def test_missing_job_says_so(ledger):
    with pytest.raises(KeyError):
        ledger.get('없는작업')


# --- 저장 ---------------------------------------------------------------------

def test_survives_a_reload(tmp_path):
    path = str(tmp_path / 'u.json')
    a = uploads.UploadLedger(path, monthly_pages=7)
    j = a.add(account='학원', filename='x.pdf', pages=2, provider='manual')
    b = uploads.UploadLedger(path)
    assert b.monthly_pages == 7
    assert b.get(j.id).filename == 'x.pdf'
    assert b.remaining('학원') == 5


def test_ignores_unknown_fields_from_a_newer_version(tmp_path):
    """원장을 나중 판이 써 놨어도 열려야 한다."""
    path = str(tmp_path / 'u.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'monthly_pages': 5, 'jobs': [{
            'id': 'x1', 'account': 'A', 'filename': 'a.pdf', 'pages': 1,
            'state': 'received', '미래항목': '무시해야 한다'}]}, f)
    led = uploads.UploadLedger(path)
    assert led.get('x1').filename == 'a.pdf'


# --- 지시서 7장: PDF 를 들고 있지 않는다 ------------------------------------------

def test_stale_finds_jobs_still_holding_a_pdf(ledger):
    fresh = add(ledger)
    old = add(ledger)
    now = time.strftime('%Y-%m-%dT%H:%M:%S')
    ledger.update(fresh.id, pdf_kept=True, pdf_at=now)
    ledger.update(old.id, pdf_kept=True, pdf_at='2020-01-01T00:00:00')
    ids = [j.id for j in ledger.stale(older_than_hours=1)]
    assert ids == [old.id]


def test_stale_ignores_jobs_that_already_let_go(ledger):
    j = add(ledger)
    ledger.update(j.id, pdf_kept=False, pdf_at='2020-01-01T00:00:00')
    assert ledger.stale(older_than_hours=1) == []


def test_stale_treats_an_unreadable_timestamp_as_old(ledger):
    j = add(ledger)
    ledger.update(j.id, pdf_kept=True, pdf_at='언제였더라')
    assert [x.id for x in ledger.stale()] == [j.id]


def test_polling_a_job_does_not_reset_its_retention_clock(ledger):
    """지시서 7장. `updated_at` 으로 시계를 재면, 오래 도는 작업일수록
    PDF 가 더 오래 남는 거꾸로 된 일이 벌어진다."""
    j = add(ledger)
    ledger.update(j.id, pdf_kept=True, pdf_at='2020-01-01T00:00:00')
    for _ in range(3):                        # 폴러가 계속 건드린다
        ledger.update(j.id, detail='인식 중…')
    assert ledger.get(j.id).updated_at > '2020'        # 손댄 시각은 새로워졌지만
    assert [x.id for x in ledger.stale(older_than_hours=1)] == [j.id]
