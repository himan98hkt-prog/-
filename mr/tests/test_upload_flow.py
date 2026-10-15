# -*- coding: utf-8 -*-
"""PDF 업로드 파이프라인 — 지시서 9장 4단계.

여기서 지켜야 하는 것 셋 (지시서 7장·8.2·2.2):
  * PDF 를 영구 보관하지 않는다
  * 쪽수만큼 쿼터를 깎는다
  * 화성 확인 화면을 건너뛰고 완료가 되지 않는다
"""
import os

import pytest

from conftest import FIXTURES, score
from piano_mr import catalog as cat, omr, store, uploads

PDFS = os.path.join(FIXTURES, 'pdf')


def pdf_bytes(name: str = 'three_pages.pdf') -> bytes:
    with open(os.path.join(PDFS, name), 'rb') as f:
        return f.read()


@pytest.fixture
def st(tmp_path):
    return store.CatalogStore(str(tmp_path / 'catalog'))


@pytest.fixture
def prov():
    with open(score('p05_waltz_c'), 'rb') as f:
        return omr.FakeProvider(musicxml=f.read())


def submit(st, prov, name='체르니 100-5.pdf', account='행복피아노',
           blob=None, title='체르니 100번 5번'):
    return st.submit_pdf(blob if blob is not None else pdf_bytes(), name,
                         account=account, title=title, provider=prov)


# --- 한 바퀴 -------------------------------------------------------------------

def test_a_pdf_becomes_a_song_waiting_for_review(st, prov):
    job = submit(st, prov)
    assert job['state'] == uploads.RUNNING and job['pages'] == 3

    job = st.poll_upload(job['id'], provider=prov)
    assert job['state'] == uploads.REVIEW and job['label'] == '화성 확인 대기'
    song = st.catalog.get(job['song_id'])
    assert song.measures == 8 and song.key == 'C major'
    # 목록이 아니라 **그 곡의 확인 화면**으로 바로 가야 한다
    assert job['verify_url'] == f"/static/verify.html?id={job['song_id']}"


def test_the_uploaded_song_belongs_to_the_account_not_the_catalog(st, prov):
    """지시서 7장 — 업로드본은 해당 계정에서만."""
    job = st.poll_upload(submit(st, prov)['id'], provider=prov)
    song = st.catalog.get(job['song_id'])
    assert song.owner == '행복피아노' and song.source == 'upload'
    assert song.public_domain is False          # 카탈로그로 팔 수 있는 곡이 아니다


def test_review_cannot_be_skipped(st, prov):
    """지시서 2.2 — OMR 90~95%. 확인 없이 완료로 넘어가면 안 된다."""
    job = st.poll_upload(submit(st, prov)['id'], provider=prov)
    with pytest.raises(ValueError) as e:
        st.finish_upload(job['id'])
    assert '화성 확인' in str(e.value)

    st.save_harmony(job['song_id'], [], verified=True)
    assert st.finish_upload(job['id'])['state'] == uploads.DONE


# --- 지시서 7장: PDF 를 들고 있지 않는다 ------------------------------------------

def test_the_pdf_is_deleted_the_moment_the_musicxml_arrives(st, prov):
    job = submit(st, prov)
    held = os.listdir(st.incoming_dir)
    assert held == [f"{job['id']}.pdf"], 'OMR 중에는 격리 폴더에 있어야 한다'

    st.poll_upload(job['id'], provider=prov)
    assert os.listdir(st.incoming_dir) == [], 'MusicXML 이 왔는데 PDF 가 남아 있다'
    assert st.ledger.get(job['id']).pdf_kept is False


def test_a_failed_job_does_not_keep_the_pdf(st):
    bad = omr.FakeProvider(fail='악보를 못 읽었습니다')
    job = submit(st, bad)
    st.poll_upload(job['id'], provider=bad)
    assert st.ledger.get(job['id']).state == uploads.FAILED
    assert os.listdir(st.incoming_dir) == []


def test_cancelling_removes_the_pdf_and_refunds_the_pages(st, prov):
    job = submit(st, prov)
    assert st.ledger.remaining('행복피아노') == 7
    st.cancel_upload(job['id'])
    assert os.listdir(st.incoming_dir) == []
    assert st.ledger.remaining('행복피아노') == 10


def test_cancelling_twice_is_refused(st, prov):
    job = submit(st, prov)
    st.cancel_upload(job['id'])
    with pytest.raises(ValueError):
        st.cancel_upload(job['id'])


def test_sweep_clears_abandoned_pdfs(st, prov):
    job = submit(st, prov)
    st.ledger.update(job['id'], pdf_at='2020-01-01T00:00:00')
    out = st.sweep(older_than_hours=1)
    assert out['swept'] == [job['id']] and out['held'] == 0
    assert os.listdir(st.incoming_dir) == []
    assert st.ledger.get(job['id']).state == uploads.FAILED


def test_sweep_removes_orphan_files_with_no_job(st):
    stray = os.path.join(st.incoming_dir, 'nobody.pdf')
    with open(stray, 'wb') as f:
        f.write(b'%PDF-1.4')
    assert st.sweep()['orphans'] == 1
    assert not os.path.exists(stray)


def test_sweep_leaves_a_fresh_job_alone(st, prov):
    job = submit(st, prov)
    assert st.sweep(older_than_hours=72)['swept'] == []
    assert os.listdir(st.incoming_dir) == [f"{job['id']}.pdf"]


# --- 받기 전에 거절하는 것들 -------------------------------------------------------

def test_a_blacklisted_title_never_touches_the_disk(st, prov):
    """지시서 7장 블랙리스트는 업로드에도 예외가 없다."""
    with pytest.raises(cat.CopyrightError):
        submit(st, prov, title='피아노 어드벤처 1급')
    assert os.listdir(st.incoming_dir) == []
    assert st.ledger.rows() == []            # 쿼터도 안 깎였다


def test_a_blacklisted_filename_is_caught_too(st, prov):
    with pytest.raises(cat.CopyrightError):
        submit(st, prov, name='지브리 메들리.pdf', title='')
    assert st.ledger.rows() == []


def test_a_file_that_is_not_a_pdf_is_refused(st, prov):
    from piano_mr import pdf as pdfmod
    with pytest.raises(pdfmod.NotAPdf):
        submit(st, prov, blob=pdf_bytes('not_a_pdf.png'), name='x.png')
    assert st.ledger.rows() == []


def test_an_encrypted_pdf_is_refused_with_advice(st, prov):
    from piano_mr import pdf as pdfmod
    with pytest.raises(pdfmod.EncryptedPdf) as e:
        submit(st, prov, blob=pdf_bytes('encrypted.pdf'))
    assert '암호' in str(e.value)


def test_a_pdf_whose_pages_cannot_be_counted_is_refused(st, prov):
    """쪽수가 과금 단위다 (지시서 8.2). 모르면 추측하지 않는다."""
    with pytest.raises(ValueError) as e:
        submit(st, prov, blob=b'%PDF-1.7\n' + b'noise ' * 50 + b'\n%%EOF\n')
    assert '페이지 수' in str(e.value)
    assert st.ledger.rows() == []


def test_an_upload_without_an_account_is_refused(st, prov):
    with pytest.raises(ValueError):
        submit(st, prov, account='')


def test_an_oversized_file_is_refused_before_parsing(st, prov):
    with pytest.raises(ValueError) as e:
        submit(st, prov, blob=b'%PDF-1.4' + b'\0' * (uploads.MAX_BYTES + 1))
    assert 'MB' in str(e.value)


def test_the_monthly_limit_actually_stops_uploads(st, prov):
    """지시서 9장 4단계 필수 항목. 8.3 ① 이 변동비를 묶는 방법으로 든 것."""
    st.ledger.monthly_pages = 4
    submit(st, prov)                                   # 3쪽
    with pytest.raises(uploads.QuotaExceeded):
        submit(st, prov)                               # 3쪽 더 — 1쪽 남았다
    assert len(os.listdir(st.incoming_dir)) == 1       # 두 번째는 디스크에 안 닿았다


# --- 신청제 (지시서 8.3 ③) -------------------------------------------------------

def test_manual_provider_waits_for_a_human_then_adopts(st):
    man = omr.ManualProvider()
    job = submit(st, man)
    assert job['state'] == uploads.RUNNING and job['provider'] == 'manual'

    again = st.poll_upload(job['id'], provider=man)
    assert again['state'] == uploads.RUNNING        # 사람을 기다린다
    assert os.listdir(st.incoming_dir) == [f"{job['id']}.pdf"]

    with open(score('p05_waltz_c'), 'rb') as f:
        done = st.adopt_musicxml(job['id'], f.read())
    assert done['state'] == uploads.REVIEW
    assert os.listdir(st.incoming_dir) == []


def test_adopting_twice_is_refused(st, prov):
    job = st.poll_upload(submit(st, prov)['id'], provider=prov)
    st.save_harmony(job['song_id'], [], verified=True)
    st.finish_upload(job['id'])
    with open(score('p05_waltz_c'), 'rb') as f:
        with pytest.raises(ValueError):
            st.adopt_musicxml(job['id'], f.read())


def test_a_broken_musicxml_fails_the_job_and_drops_the_pdf(st):
    man = omr.ManualProvider()
    job = submit(st, man)
    with pytest.raises(Exception):
        st.adopt_musicxml(job['id'], b'<not really music xml>')
    assert st.ledger.get(job['id']).state == uploads.FAILED
    assert os.listdir(st.incoming_dir) == []


# --- 화면이 받아 갈 것 -------------------------------------------------------------

def test_uploads_view_warns_that_omr_is_not_perfect(st):
    """지시서 3장 — "PDF 넣으면 바로 완성"을 약속하지 말 것."""
    v = st.uploads_view('행복피아노')
    assert '90~95%' in v['accuracy_note'] and '확인 화면' in v['accuracy_note']
    assert v['quota']['limit'] == uploads.DEFAULT_MONTHLY_PAGES
    assert v['provider'] == 'manual'            # 키가 없으면 신청제


def test_uploads_view_lists_only_this_account(st, prov):
    submit(st, prov, account='A학원')
    submit(st, prov, account='B학원')
    assert len(st.uploads_view('A학원')['jobs']) == 1
    assert len(st.uploads_view()['jobs']) == 2
