# -*- coding: utf-8 -*-
"""PDF 검사기 — 페이지 수가 OMR 과금 단위다 (지시서 8.2).

틀리면 원장님이 돈을 더 내거나 월 제한이 헐거워진다. 그래서 여기는 빡빡하게 본다.
"""
import glob
import os

import pytest

from conftest import FIXTURES
from piano_mr import pdf

PDFS = os.path.join(FIXTURES, 'pdf')


def blob(name: str) -> bytes:
    with open(os.path.join(PDFS, name), 'rb') as f:
        return f.read()


def test_counts_a_plain_pdf():
    assert pdf.inspect(blob('one_page.pdf')).pages == 1
    assert pdf.inspect(blob('three_pages.pdf')).pages == 3


def test_counts_pages_hidden_in_a_compressed_object_stream():
    """PDF 1.5+ 는 페이지 객체를 압축해 넣는다. 겉만 보면 0장으로 보인다."""
    info = pdf.inspect(blob('compressed_1_5.pdf'))
    assert info.version == '1.5'
    assert info.pages == 3


def test_rejects_a_file_that_is_not_a_pdf():
    with pytest.raises(pdf.NotAPdf):
        pdf.inspect(blob('not_a_pdf.png'))
    with pytest.raises(pdf.NotAPdf):
        pdf.inspect(b'hello')


def test_rejects_an_encrypted_pdf():
    with pytest.raises(pdf.EncryptedPdf):
        pdf.inspect(blob('encrypted.pdf'))


def test_does_not_confuse_the_word_encrypt_in_the_body():
    """본문에 '/Encrypt' 글자가 있을 뿐인 멀쩡한 악보를 거절하면 안 된다."""
    assert pdf.inspect(blob('encrypt_word_in_body.pdf')).pages == 1


def test_tolerates_junk_before_the_header():
    """일부 스캐너가 %PDF 앞에 쓰레기를 붙인다."""
    assert pdf.inspect(blob('junk_prefix.pdf')).pages == 2


def test_does_not_count_the_pages_node_as_a_page():
    """`/Type /Pages` 는 중간 노드다. 페이지로 세면 장수가 부풀어 과금이 틀어진다."""
    body = blob('three_pages.pdf')
    assert b'/Type /Pages' in body
    assert pdf._count_page_objects(body) == 3


def test_says_it_does_not_know_rather_than_guessing():
    """셀 수 없으면 None. '아마 1장'으로 넘기면 과금이 조용히 틀어진다."""
    headerless = b'%PDF-1.7\n' + b'noise ' * 100 + b'\n%%EOF\n'
    info = pdf.inspect(headerless)
    assert info.pages is None and info.countable is False


def test_refuses_an_absurdly_large_file_without_scanning_it():
    with pytest.raises(pdf.PdfError):
        pdf.inspect(b'%PDF-1.4' + b'\0' * (pdf.MAX_SCAN + 1))


@pytest.mark.parametrize('path,expected', [
    ('/mnt/skills/examples/theme-factory/theme-showcase.pdf', 10),
    ('/usr/local/lib/python3.11/dist-packages/music21/mei/test/test_file.pdf', 1),
])
def test_agrees_with_real_pdfs_we_did_not_write(path, expected):
    """우리가 만든 fixture 만 통과하는 검사기는 의미가 없다."""
    if not os.path.exists(path):
        pytest.skip(f'이 환경에 없는 파일: {path}')
    with open(path, 'rb') as f:
        assert pdf.inspect(f.read()).pages == expected


def test_reads_every_real_pdf_lying_around_this_machine():
    """남의 PDF 를 긁어 모아 터지지 않는지만 본다 (장수는 각자 다르다)."""
    found = glob.glob('/usr/local/lib/python3.11/dist-packages/matplotlib/'
                      'mpl-data/images/*.pdf')
    if not found:
        pytest.skip('matplotlib 샘플 PDF 가 없습니다')
    for p in found:
        with open(p, 'rb') as f:
            info = pdf.inspect(f.read())
        assert info.pages == 1, f'{p} 가 {info.pages}장으로 읽힙니다'
