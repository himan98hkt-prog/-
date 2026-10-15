# -*- coding: utf-8 -*-
"""인증키 — 관리노트와 **같은 키 한 장**으로 연다 (지시서 9장 5단계 "번들 판매").

이 파일은 새 규칙이 아니다. `src/core/license.js` 와 `src/core/license-piano.js` 의
규칙을 파이썬으로 그대로 옮긴 것이다. 목적은 하나 — 이미 팔린 키가 반주 쪽에서도
그대로 열리는 것.

    **salt·문자표·해시식을 한 글자도 바꾸면 안 된다.** 바꾸는 순간 이미 판 키가
    전부 죽는다. `tests/test_license.py` 가 자바스크립트 쪽과 교차 검증한다.

**왜 제품 문자를 'K' 로 보는가.** 관리노트 라이선스에는 제품이 셋 있다 —
A(통합) · M(학원 전용) · K(피아노 전용). 반주(MR)는 피아노 학원 제품군의 기능이므로
**피아노 관리노트와 같은 문을 쓴다.** 그래서 통합키(A)와 피아노키(K)는 열리고,
학원 전용키(M)는 안 열린다. 이러면 JS 쪽을 한 줄도 고치지 않아도 되고, 따라서
이미 발급된 키가 위험해지지 않는다.

**무엇에 키를 요구하는가.** 카탈로그 제작·PDF 업로드·발표회 운영 같은 **관리 도구**만
본다. **집 연습 링크는 보지 않는다** — 지시서 ⑤-10 이 "설치·로그인 없이 재생"이라고
못 박았고, 학부모에게 인증키를 물어볼 수는 없다.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Optional

# --- src/core/license.js 에서 그대로 --------------------------------------
LICENSE_SALT = 'ACADEMY-NOTE::2026::a7f3-kQ9v-Zt2m::v1'
# Crockford base32 — 받아 적을 때 헷갈리는 I, L, O, U 제외
B32 = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
PLANS = {'L': 'lite', 'P': 'pro'}
PRODUCTS = {
    'A': {'code': 'A', 'label': '통합(피아노+학원)', 'accepts': ('M', 'K')},
    'M': {'code': 'M', 'label': '학원 관리노트', 'accepts': ('M',)},
    'K': {'code': 'K', 'label': '피아노 관리노트', 'accepts': ('K',)},
}

# 반주는 피아노 제품군의 기능이다 — 피아노 관리노트와 같은 문을 쓴다 (위 설명 참고)
PRODUCT_CODE = 'K'

# --- src/core/license-piano.js 에서 그대로 --------------------------------
PIANO_SALT = 'PAL-x7Qm3vK9nR-accelssam-2026'
# 원본 문자표. L·U 를 쓰고 0·1·2·5·8 은 쓰지 않는다 (우리 base32 와 다르다)
PIANO_CHARS = 'ACDEFGHJKLMNPQRTUVWXY34679'

MASK32 = 0xFFFFFFFF


@dataclass
class Verdict:
    ok: bool
    reason: str = ''
    plan: str = ''
    product: str = ''
    key: str = ''
    source: str = ''

    def __bool__(self) -> bool:
        return self.ok


# --- 해시 ------------------------------------------------------------------

def _hash32(text: str) -> int:
    """FNV-1a 32bit + 확산. `Math.imul` 은 32비트 곱이므로 마스크로 맞춘다."""
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch) & MASK32
        h = (h * 0x01000193) & MASK32
    h ^= h >> 15
    h = (h * 0x2545F491) & MASK32
    h ^= h >> 13
    return h & MASK32


def checksum_of(body: str, salt: str = LICENSE_SALT) -> str:
    h = _hash32(f'{salt}|{body}')
    out = ''
    for i in range(4):
        out = B32[(h >> (i * 5)) & 31] + out
    return out


def normalize(key: str) -> str:
    return re.sub(r'[^0-9A-Z]', '', str(key or '').upper())


def format_key(raw: str) -> str:
    k = normalize(raw)
    return '-'.join(k[i:i + 4] for i in range(0, len(k), 4))


# --- 피아노 관리노트가 먼저 팔아 온 키 ---------------------------------------

def _to_int32(n: int) -> int:
    """자바스크립트의 ToInt32 — 비트 연산의 결과는 **부호 있는** 32비트다."""
    n &= MASK32
    return n - 0x100000000 if n >= 0x80000000 else n


def _to_uint32(v: float) -> int:
    """자바스크립트의 `x >>> 0` — 0 쪽으로 버린 뒤 2^32 로 나눈 나머지."""
    if v != v or v in (float('inf'), float('-inf')):
        return 0
    return int(math.trunc(v)) % 0x100000000


def _piano_hash(text: str):
    """피아노 관리노트의 2중 해시.

    **여기는 자바스크립트의 수 연산을 글자 그대로 흉내 내야 한다.** 원본이
    `Math.imul` 이 아니라 그냥 `*` 를 쓰기 때문이다. 피연산자는 `^` 를 거치며
    **부호 있는** 32비트가 되고, 곱은 **float64** 로 계산되어 2^53 을 넘는 순간
    정밀도가 깎인다. 파이썬의 정확한 정수 곱으로 바꿔 쓰면 값이 달라지고,
    그러면 **이미 팔린 키가 안 열린다.**
    """
    h1 = 0x811C9DC5
    h2 = 0x1000193
    for ch in text:
        c = ord(ch)
        h1 = _to_uint32(float(_to_int32(h1) ^ _to_int32(c)) * 16777619.0)
        shifted = _to_int32(_to_int32(h2) << 5)
        h2 = _to_uint32(_to_int32(_to_uint32(float(h2) + c * 31.0)) ^ shifted)
    return h1, h2


def _piano_encode(h1: int, h2: int, length: int) -> str:
    n = h1 * 4294967296 + h2
    base = len(PIANO_CHARS)
    out = ''
    for _ in range(length):
        out += PIANO_CHARS[n % base]
        n //= base
    return out


def piano_normalize_name(s: str) -> str:
    s = re.sub(r'\s+', '', str(s or ''))
    return re.sub(r'[()（）·.,\-]', '', s).lower()


def piano_key_for_name(name: str) -> str:
    h1, h2 = _piano_hash(
        f'{PIANO_SALT}|{piano_normalize_name(name)}|{PIANO_SALT}')
    return format_key(_piano_encode(h1, h2, 12))


def piano_check_digits(head: str) -> str:
    h1, h2 = _piano_hash(f'{PIANO_SALT}#SV#{str(head).upper()}')
    return _piano_encode(h1, h2, 4)


def is_piano_self_valid(key: str) -> bool:
    k = normalize(key)
    return len(k) == 12 and piano_check_digits(k[:8]) == k[8:12]


def verify_piano(key: str, academy_name: str = '') -> Optional[dict]:
    k = normalize(key)
    if len(k) != 12:
        return None
    if is_piano_self_valid(k):
        return {'mode': 'self', 'key': format_key(k)}
    if academy_name and piano_key_for_name(academy_name) == format_key(k):
        return {'mode': 'name', 'key': format_key(k), 'name': academy_name}
    return None


# --- 판정 ------------------------------------------------------------------

def _classify(key: str, body: str, product_code: str) -> Verdict:
    head = body[0]
    # v1: 첫 글자가 플랜 문자 — 제품 구분이 없던 초기 발급분
    if head in PLANS and head not in PRODUCTS:
        return Verdict(True, plan=PLANS[head], product='A',
                       key=format_key(key), source='primary')
    product = PRODUCTS.get(head)
    if not product:
        return Verdict(False, reason='제품 문자가 올바르지 않습니다 (A·M·K 또는 L·P 로 시작)')
    plan = PLANS.get(body[1])
    if not plan:
        return Verdict(False, reason='플랜 문자가 올바르지 않습니다 (두 번째 자리는 L 또는 P)')
    if product_code not in product['accepts']:
        return Verdict(False,
                       reason=f"{product['label']} 전용 키입니다. 반주에서는 쓸 수 없습니다")
    return Verdict(True, plan=plan, product=head, key=format_key(key),
                   source='primary')


def verify(key: str, *, academy_name: str = '',
           product_code: str = PRODUCT_CODE) -> Verdict:
    """인증키를 본다. 관리노트와 같은 규칙이다."""
    k = normalize(key)
    if not k:
        return Verdict(False, reason='인증키를 입력해 주세요')
    if len(k) != 12:
        return Verdict(False, reason=f'인증키는 12자리입니다 (현재 {len(k)}자)')

    body, sumpart = k[:8], k[8:]
    if checksum_of(body) == sumpart:
        return _classify(k, body, product_code)

    piano = verify_piano(k, academy_name)
    if piano:
        where = ('학원명 방식' if piano['mode'] == 'name' else '피아노 관리노트 발급분')
        return Verdict(True, plan='pro', product='K', key=piano['key'],
                       source=where)

    allowed = set(B32) | set(PIANO_CHARS)
    for ch in k:
        if ch not in allowed:
            return Verdict(False, reason=f'쓸 수 없는 문자가 있습니다: {ch}')
    return Verdict(False, reason=(
        '검증번호가 맞지 않습니다. 피아노 관리노트에서 학원명으로 받은 키라면 '
        '학원명도 함께 넣어 주세요'))


# --- 이 설치본이 인증됐는가 -------------------------------------------------

ENV_KEY = 'MR_LICENSE_KEY'
ENV_NAME = 'MR_ACADEMY'


def from_env(env=None) -> Verdict:
    """환경변수에 넣어 둔 키를 본다. 없으면 '키 없음'.

    파일이 아니라 환경변수인 이유: 카탈로그 디렉터리를 통째로 복사해 옮길 때
    인증까지 따라가면 키 한 장으로 여러 학원이 쓰게 된다.
    """
    e = os.environ if env is None else env
    raw = e.get(ENV_KEY, '')
    if not raw:
        return Verdict(False, reason='인증키가 없습니다')
    return verify(raw, academy_name=e.get(ENV_NAME, ''))
