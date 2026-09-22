# -*- coding: utf-8 -*-
"""인증키 — 관리노트와 같은 키 한 장 (지시서 9장 5단계 "번들 판매").

이 파일에서 제일 중요한 건 맨 아래 **교차 시험**이다. 파이썬 쪽 규칙이 자바스크립트
쪽과 한 비트라도 어긋나면 **이미 팔린 키가 죽는다.** 그래서 양쪽에 손으로 쓴 기대값을
두고 맞춰 보는 대신, 진짜 node 로 `src/core/license.js` 를 돌려서 같은 답이 나오는지 본다.
"""
import json
import os
import shutil
import subprocess

import pytest

from piano_mr import license as lic

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
needs_node = pytest.mark.skipif(shutil.which('node') is None, reason='node 가 없습니다')


def make(body: str) -> str:
    """본문 8자에 우리 규칙의 체크섬을 붙여 완성한 키."""
    return lic.format_key(body + lic.checksum_of(body))


# --- 규칙이 바뀌지 않았는지 -------------------------------------------------------

def test_salt_and_charset_are_untouched():
    """바꾸는 순간 이미 판 키가 전부 죽는다. 값 자체를 못 박는다."""
    assert lic.LICENSE_SALT == 'ACADEMY-NOTE::2026::a7f3-kQ9v-Zt2m::v1'
    assert lic.B32 == '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
    assert lic.PIANO_SALT == 'PAL-x7Qm3vK9nR-accelssam-2026'
    assert lic.PIANO_CHARS == 'ACDEFGHJKLMNPQRTUVWXY34679'


def test_mr_uses_the_piano_door():
    """반주는 피아노 제품군의 기능이다 — 통합키와 피아노키가 열고, 학원 전용키는 안 연다."""
    assert lic.PRODUCT_CODE == 'K'


# --- 어떤 키가 열리는가 -----------------------------------------------------------

def test_a_bundle_key_opens_the_accompaniment():
    v = lic.verify(make('ALABCDEF'))
    assert v.ok and v.product == 'A' and v.plan == 'lite'


def test_a_pro_bundle_key_reports_pro():
    assert lic.verify(make('APABCDEF')).plan == 'pro'


def test_a_piano_only_key_opens_it():
    v = lic.verify(make('KLABCDEF'))
    assert v.ok and v.product == 'K'


def test_an_academy_only_key_does_not():
    """학원 관리노트만 사신 분에게 반주까지 열어 주면 번들을 팔 수 없다."""
    v = lic.verify(make('MLABCDEF'))
    assert not v.ok and '학원 관리노트 전용' in v.reason


def test_an_old_v1_key_still_opens():
    """제품 구분이 없던 초기 발급분. 회수하지 않는다."""
    v = lic.verify(make('LABCDEFG'))
    assert v.ok and v.product == 'A' and v.plan == 'lite'


# --- 거절할 때 이유를 말한다 -------------------------------------------------------

def test_empty_key():
    assert '입력해' in lic.verify('').reason


def test_wrong_length_says_how_many():
    v = lic.verify('ABCD-EFGH')
    assert not v.ok and '12자리' in v.reason and '8자' in v.reason


def test_a_typo_is_reported_as_a_checksum_failure():
    good = lic.normalize(make('ALABCDEF'))
    typo = good[:11] + ('Z' if good[11] != 'Z' else 'Y')
    v = lic.verify(typo)
    assert not v.ok and '검증번호' in v.reason


def test_an_impossible_character_is_named():
    v = lic.verify('ILOU-ILOU-ILOU')       # I·O 는 어느 문자표에도 없다
    assert not v.ok and '쓸 수 없는 문자' in v.reason


def test_formatting_and_case_do_not_matter():
    key = make('ALABCDEF')
    for variant in (key, key.lower(), key.replace('-', ''), f' {key} '):
        assert lic.verify(variant).ok, variant


# --- 피아노 관리노트가 먼저 팔아 온 키 ---------------------------------------------

def test_a_self_validating_piano_key_opens_without_an_academy_name():
    key = lic.format_key('ACDEFGHJ' + lic.piano_check_digits('ACDEFGHJ'))
    assert lic.is_piano_self_valid(key)
    v = lic.verify(key)
    assert v.ok and v.product == 'K' and v.plan == 'pro'


def test_a_name_based_piano_key_needs_the_academy_name():
    key = lic.piano_key_for_name('행복피아노학원')
    assert not lic.verify(key).ok                      # 이름 없이는 못 본다
    v = lic.verify(key, academy_name='행복피아노학원')
    assert v.ok and '학원명' in v.source


def test_academy_name_spacing_and_punctuation_are_absorbed():
    key = lic.piano_key_for_name('행복피아노학원')
    for written in ('행복 피아노 학원', '행복(피아노)학원', '행복·피아노·학원'):
        assert lic.verify(key, academy_name=written).ok, written


# --- 환경변수 ------------------------------------------------------------------

def test_no_key_in_the_environment():
    v = lic.from_env({})
    assert not v.ok and '인증키가 없습니다' in v.reason


def test_key_from_the_environment():
    assert lic.from_env({lic.ENV_KEY: make('ALABCDEF')}).ok


def test_name_based_key_from_the_environment():
    assert lic.from_env({
        lic.ENV_KEY: lic.piano_key_for_name('행복피아노학원'),
        lic.ENV_NAME: '행복피아노학원',
    }).ok


# --- 교차 시험: 자바스크립트와 같은 답이 나오는가 ------------------------------------

JS_PROBE = r"""
import { checksumOf, generateKey, verifyKey, normalizeKey } from '%s/src/core/license.js'
import { pianoKeyForName, pianoCheckDigits } from '%s/src/core/license-piano.js'

const out = { checksums: {}, piano: {}, verdicts: [] }
for (const body of ['ALABCDEF', 'APABCDEF', 'KLABCDEF', 'MLABCDEF', 'LABCDEFG',
                    '00000000', 'ZZZZZZZZ', 'A1B2C3D4']) {
  out.checksums[body] = checksumOf(body)
}
for (const name of ['행복피아노학원', '아첼쌤', 'a b c']) {
  out.piano[name] = pianoKeyForName(name)
}
for (const head of ['ACDEFGHJ', 'KKKKKKKK', '3467ACDE']) {
  out.piano['#SV#' + head] = pianoCheckDigits(head)
}
// 피아노 관리노트 빌드(제품 문자 K)에서 이 키들이 어떻게 판정되는가
for (let i = 0; i < 12; i++) {
  const key = generateKey(i %% 2 ? 'pro' : 'lite', ['A', 'M', 'K'][i %% 3])
  const v = verifyKey(key, { productCode: 'K' })
  out.verdicts.push({ key: normalizeKey(key), ok: !!v.ok,
                      plan: v.plan || '', product: v.product || '' })
}
process.stdout.write(JSON.stringify(out))
"""


@pytest.fixture(scope='module')
def js(tmp_path_factory):
    # 마크는 fixture 에 못 붙이므로 여기서 직접 건너뛴다
    if shutil.which('node') is None:
        pytest.skip('node 가 없습니다')
    path = tmp_path_factory.mktemp('js') / 'probe.mjs'
    path.write_text(JS_PROBE % (REPO, REPO), encoding='utf-8')
    proc = subprocess.run(['node', str(path)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@needs_node
def test_checksums_match_javascript(js):
    """체크섬이 한 글자라도 다르면 이미 판 키가 전부 죽는다."""
    for body, expected in js['checksums'].items():
        assert lic.checksum_of(body) == expected, f'{body} 의 체크섬이 다릅니다'


@needs_node
def test_piano_keys_match_javascript(js):
    for name, expected in js['piano'].items():
        if name.startswith('#SV#'):
            assert lic.piano_check_digits(name[4:]) == expected, name
        else:
            assert lic.piano_key_for_name(name) == expected, name


@needs_node
def test_verdicts_match_javascript(js):
    """같은 키를 놓고 JS 와 파이썬이 같은 답(열림/플랜/제품)을 내야 한다."""
    assert len(js['verdicts']) == 12
    for row in js['verdicts']:
        mine = lic.verify(row['key'])
        assert mine.ok == row['ok'], f"{row['key']} — JS {row['ok']} / 파이썬 {mine.ok}"
        if row['ok']:
            assert mine.plan == row['plan'], row['key']
            assert mine.product == row['product'], row['key']


@needs_node
def test_javascript_generated_bundle_keys_open_the_accompaniment(js):
    """실제로 발급기가 뽑은 통합키가 반주에서 열려야 번들이 성립한다."""
    opened = [r for r in js['verdicts'] if r['ok'] and r['product'] == 'A']
    assert opened, '통합키가 하나도 안 나왔습니다'
    for row in opened:
        assert lic.verify(row['key']).ok
