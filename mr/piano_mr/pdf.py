# -*- coding: utf-8 -*-
"""PDF 를 들여다본다 — 의존성 없이.

**왜 직접 쓰는가.** 페이지 수가 OMR 과금 단위다. 지시서 8.2 는 "스캔 1장 ≈ 300~400원",
9장 4단계는 "월 업로드 제한"을 요구한다. 즉 페이지 수를 틀리면 원장님이 돈을 더 내거나
제한이 헐거워진다. 외부 라이브러리(pypdf)는 이 컨테이너에서 `cryptography` 가 깨져
import 조차 안 되고, 그 한 줄을 위해 무거운 의존성을 requirements 에 넣고 싶지도 않다.

**못 세면 추측하지 않는다.** `pages` 가 None 이면 호출부가 업로드를 거절한다.
"아마 1장이겠지"로 넘기면 과금이 조용히 틀어진다.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from typing import Optional

MAGIC = b'%PDF-'
MAX_SCAN = 64 * 1024 * 1024          # 이보다 큰 파일은 아예 보지 않는다


class PdfError(ValueError):
    """PDF 로 받아들일 수 없는 파일."""


class NotAPdf(PdfError):
    pass


class EncryptedPdf(PdfError):
    pass


@dataclass
class PdfInfo:
    pages: Optional[int]                 # 못 셌으면 None
    version: str
    size: int

    @property
    def countable(self) -> bool:
        return self.pages is not None and self.pages > 0


def inspect(data: bytes) -> PdfInfo:
    """PDF 인지 보고 페이지 수를 센다. 아니면 `PdfError`."""
    if not isinstance(data, (bytes, bytearray)):
        raise NotAPdf('PDF 파일이 아닙니다.')
    data = bytes(data)
    if len(data) > MAX_SCAN:
        raise PdfError(f'파일이 너무 큽니다 ({len(data) // 1024 // 1024} MB).')
    # 일부 스캐너가 앞에 쓰레기를 붙인다. 앞 1 KB 안에 있으면 봐 준다.
    head = data[:1024]
    at = head.find(MAGIC)
    if at < 0:
        raise NotAPdf('PDF 파일이 아닙니다 (%PDF 머리말이 없습니다).')
    body = data[at:]
    version = body[5:8].decode('latin-1', 'replace').strip()

    if _is_encrypted(body):
        raise EncryptedPdf(
            '암호가 걸린 PDF 입니다. 암호를 풀어서 다시 올려 주세요 — '
            '악보를 읽을 수 없습니다.')

    return PdfInfo(pages=count_pages(body), version=version, size=len(data))


def _is_encrypted(body: bytes) -> bool:
    """트레일러의 `/Encrypt` 만 본다.

    본문 아무 데나 있는 `/Encrypt` 를 세면, 그 글자가 우연히 들어간 스트림에서도
    걸린다. 암호화는 트레일러 사전에 선언된다.
    """
    for m in re.finditer(rb'trailer', body):
        chunk = body[m.end():m.end() + 2048]
        if re.search(rb'/Encrypt\b', chunk):
            return True
    # 압축 xref(PDF 1.5+)는 trailer 키워드 없이 /Type /XRef 스트림 사전에 적는다
    for m in re.finditer(rb'/Type\s*/XRef', body):
        start = body.rfind(b'<<', 0, m.start())
        if start >= 0 and re.search(rb'/Encrypt\b', body[start:m.end() + 512]):
            return True
    return False


def count_pages(body: bytes) -> Optional[int]:
    """페이지 수. 셋 다 실패하면 None.

    세 가지를 이 순서로 본다.

    1. 페이지 트리 뿌리의 `/Count` — 가장 믿을 만하다. PDF 명세가 여기에
       전체 페이지 수를 적게 되어 있다.
    2. `/Type /Page` 객체 세기 — 1이 없거나 이상할 때. 단 `/Type /Pages`
       (중간 노드)와 헷갈리면 안 되므로 뒤에 `s` 가 오지 않는 것만 센다.
    3. 압축 객체 스트림(`/Type /ObjStm`)을 풀어서 다시 1·2 — PDF 1.5+ 는
       페이지 객체를 압축해 넣어 두기 때문에 겉만 봐서는 0개로 보인다.
    """
    n = _count_from_pages_node(body)
    if n:
        return n
    n = _count_page_objects(body)
    if n:
        return n

    for raw in _object_streams(body):
        n = _count_from_pages_node(raw) or _count_page_objects(raw)
        if n:
            return n
    return None


def _count_from_pages_node(blob: bytes) -> Optional[int]:
    """`/Type /Pages` 사전의 `/Count`. 중첩 트리에서는 제일 큰 값이 뿌리다."""
    best = 0
    for m in re.finditer(rb'/Type\s*/Pages\b', blob):
        start = blob.rfind(b'<<', 0, m.start())
        if start < 0:
            continue
        window = blob[start:m.end() + 512]
        c = re.search(rb'/Count\s+(\d+)', window)
        if c:
            best = max(best, int(c.group(1)))
    return best or None


def _count_page_objects(blob: bytes) -> Optional[int]:
    """`/Type /Page` 객체 수. `/Pages` 는 세지 않는다."""
    n = len(re.findall(rb'/Type\s*/Page(?![sA-Za-z])', blob))
    return n or None


def _object_streams(body: bytes, limit: int = 64):
    """압축 객체 스트림을 풀어서 내놓는다. 못 푸는 건 조용히 건너뛴다."""
    done = 0
    for m in re.finditer(rb'/Type\s*/ObjStm', body):
        if done >= limit:
            return
        s = body.find(b'stream', m.end())
        if s < 0:
            continue
        p = s + len(b'stream')
        if body[p:p + 2] == b'\r\n':
            p += 2
        elif body[p:p + 1] in (b'\n', b'\r'):
            p += 1
        e = body.find(b'endstream', p)
        if e < 0:
            continue
        try:
            yield zlib.decompress(body[p:e])
            done += 1
        except zlib.error:
            continue
