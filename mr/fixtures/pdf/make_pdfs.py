# -*- coding: utf-8 -*-
"""검사기 시험용 PDF 를 손으로 만든다.

라이브러리 없이 만드는 이유는 piano_mr/pdf.py 와 같다. 그리고 여기서 중요한 건
**모양이 서로 다른 PDF** 다 — 평범한 것, 여러 장, 압축 객체 스트림(1.5+),
암호 표시, 그리고 PDF 가 아닌 것. 셋 다 실제로 다른 경로를 탄다.
"""
import os
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def build(objects, trailer_extra=b'', version=b'1.4'):
    """번호 붙인 객체들을 xref 까지 갖춘 PDF 로 엮는다."""
    out = bytearray(b'%PDF-' + version + b'\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b'%d 0 obj\n' % i + body + b'\nendobj\n'
    xref_at = len(out)
    out += b'xref\n0 %d\n' % (len(objects) + 1)
    out += b'0000000000 65535 f \n'
    for off in offsets[1:]:
        out += b'%010d 00000 n \n' % off
    out += (b'trailer\n<< /Size %d /Root 1 0 R ' % (len(objects) + 1)
            + trailer_extra + b'>>\nstartxref\n%d\n%%%%EOF\n' % xref_at)
    return bytes(out)


def plain(pages=1):
    """평범한 PDF. 페이지 트리 /Count 와 /Type /Page 가 둘 다 보인다."""
    kids = b' '.join(b'%d 0 R' % (3 + i) for i in range(pages))
    objs = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [ %s ] /Count %d >>' % (kids, pages),
    ]
    for _ in range(pages):
        objs.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>')
    return build(objs)


def compressed(pages=3):
    """PDF 1.5 압축 객체 스트림. 페이지 객체가 겉으로 안 보인다."""
    inner = []
    nums = []
    at = 0
    for i in range(pages):
        blob = b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>'
        nums.append(b'%d %d' % (3 + i, at))
        inner.append(blob)
        at += len(blob) + 1
    payload = b' '.join(nums) + b'\n' + b'\n'.join(inner)
    first = len(b' '.join(nums)) + 1
    packed = zlib.compress(payload)
    objs = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        # 일부러 /Count 를 빼서, 압축 스트림을 풀어야만 셀 수 있게 만든다
        b'<< /Type /Pages /Kids [ ] >>',
        (b'<< /Type /ObjStm /N %d /First %d /Length %d /Filter /FlateDecode >>\n'
         b'stream\n' % (pages, first, len(packed)) + packed + b'\nendstream'),
    ]
    return build(objs, version=b'1.5')


def encrypted():
    """트레일러에 /Encrypt 가 달린 PDF."""
    objs = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [ 3 0 R ] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R >>',
        b'<< /Filter /Standard /V 1 /R 2 /O <00> /U <00> /P -1 >>',
    ]
    return build(objs, trailer_extra=b'/Encrypt 4 0 R ')


def encrypt_word_in_stream():
    """본문 스트림에 '/Encrypt' 글자가 우연히 들어 있을 뿐인 멀쩡한 PDF.

    트레일러가 아니라 본문을 보고 판정하면 이 파일이 잘못 거절된다.
    """
    text = b'(this page mentions /Encrypt in its content) Tj'
    objs = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [ 3 0 R ] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /Contents 4 0 R >>',
        b'<< /Length %d >>\nstream\n' % len(text) + text + b'\nendstream',
    ]
    return build(objs)


def junk_prefix():
    """앞에 쓰레기가 붙은 PDF (일부 스캐너가 이렇게 뱉는다)."""
    return b'\n\n   scanned by somebody\n' + plain(2)


def headless():
    """%PDF 머리말이 없다 — PDF 가 아니다."""
    return b'\x89PNG\r\n\x1a\n' + b'\x00' * 64


FILES = {
    'one_page.pdf': plain(1),
    'three_pages.pdf': plain(3),
    'compressed_1_5.pdf': compressed(3),
    'encrypted.pdf': encrypted(),
    'encrypt_word_in_body.pdf': encrypt_word_in_stream(),
    'junk_prefix.pdf': junk_prefix(),
    'not_a_pdf.png': headless(),
}


def main():
    for name, blob in FILES.items():
        path = os.path.join(HERE, name)
        with open(path, 'wb') as f:
            f.write(blob)
        print(f'{name:28} {len(blob):6d} B')


if __name__ == '__main__':
    main()
