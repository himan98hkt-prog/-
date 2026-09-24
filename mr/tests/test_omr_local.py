# -*- coding: utf-8 -*-
"""원장님 PC 에서 도는 무료 인식기 (Audiveris).

**Audiveris 자체는 이 환경에 없다.** 릴리스 파일이 egress 정책에 막혀 있어
받지 못했다. 그래서 명령줄 규약은 소스에서 확인하고(github.com/Audiveris/
audiveris · `CLI.java`, `BookManager.java`), 여기서는 그 규약대로 움직이는
**대역**을 세워 우리 쪽 코드를 검사한다.

    audiveris -batch -export -output <폴더> -- <입력.pdf>
    → <폴더>/<이름>/<이름>.mxl

HttpProvider 와 같은 처지다 — 상대를 못 부르니 **우리가 지켜야 할 약속**만
못 박는다. 그 약속 중 제일 중요한 것은 지시서 7장이다: **PDF 를 들고 있지
않는다.**
"""
import os
import stat
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from piano_mr import omr  # noqa: E402

MXL = b'PK\x03\x04fake-compressed-musicxml'


def stub(tmp_path, body: str, name='audiveris'):
    """Audiveris 인 척하는 실행 파일을 만든다."""
    p = tmp_path / name
    p.write_text('#!/usr/bin/env python3\n'
                 'import os, sys, time\n'
                 'args = sys.argv[1:]\n'
                 'out = args[args.index("-output") + 1]\n'
                 'pdf = args[-1]\n'
                 'radix = os.path.splitext(os.path.basename(pdf))[0]\n'
                 + body, encoding='utf-8')
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IRWXU)
    return str(p)


def _logs(path):
    """받은 인자를 작업 폴더 **밖**에 적어 둔다 — 끝나면 작업 폴더는 지워진다."""
    return 'open(%r, "w").write(" ".join(args))\n' % str(path)


WRITES_MXL = (
    'd = os.path.join(out, radix)\n'
    'os.makedirs(d, exist_ok=True)\n'
    'open(os.path.join(d, radix + ".mxl"), "wb").write(%r)\n' % MXL)


def run(provider, ref, limit=10.0):
    """끝날 때까지 poll 한다 (실제 호출부가 하는 일)."""
    end = time.time() + limit
    while time.time() < end:
        res = provider.poll(ref)
        if res.state != omr.PENDING:
            return res
        time.sleep(0.02)
    raise AssertionError('끝나지 않았습니다')


# --------------------------------------------------------------------------
# 설치돼 있는지
# --------------------------------------------------------------------------

def test_it_is_registered_as_a_provider():
    assert 'local' in omr.PROVIDERS
    p = omr.make_provider('local')
    assert p.name == 'local'
    assert p.needs_key is False, '무료다 — 키를 요구하면 안 된다'


def test_it_does_not_claim_to_be_instant():
    """한 쪽에 10~60초 걸린다. `blocking=True` 면 호출부가 화면을 멈춰 세운다."""
    assert omr.make_provider('local').blocking is False


def test_a_missing_binary_says_how_to_install_it(tmp_path):
    p = omr.LocalProvider(cmd=str(tmp_path / '없는파일'))
    assert p.available() is False
    with pytest.raises(omr.OmrUnavailable) as e:
        p.resolve()
    msg = str(e.value)
    assert 'Audiveris' in msg and 'github.com' in msg
    assert omr.LOCAL_CMD_ENV in msg, '어느 환경변수에 넣는지 말해 줘야 한다'


def test_it_finds_a_binary_given_by_full_path(tmp_path):
    p = omr.LocalProvider(cmd=stub(tmp_path, 'pass\n'))
    assert p.available() is True


# --------------------------------------------------------------------------
# 제대로 도는 경우
# --------------------------------------------------------------------------

def test_a_successful_run_gives_back_the_musicxml(tmp_path):
    p = omr.LocalProvider(cmd=stub(tmp_path, WRITES_MXL))
    ref = p.submit(b'%PDF-1.4 ...', '체르니 100-5.pdf')
    assert run(p, ref).state == omr.READY
    assert p.fetch(ref) == MXL


def test_the_korean_filename_does_not_have_to_survive(tmp_path):
    """결과 파일 이름은 우리가 정한다 — 한글·공백이 섞여도 찾을 수 있어야 한다."""
    p = omr.LocalProvider(cmd=stub(tmp_path, WRITES_MXL))
    ref = p.submit(b'%PDF', '부르크뮐러 25 - 1번 (솔직한 마음).pdf')
    assert run(p, ref).state == omr.READY
    assert p.fetch(ref) == MXL


def test_fetching_twice_does_not_hand_out_a_stale_copy(tmp_path):
    p = omr.LocalProvider(cmd=stub(tmp_path, WRITES_MXL))
    ref = p.submit(b'%PDF', 'a.pdf')
    run(p, ref)
    p.fetch(ref)
    with pytest.raises(omr.OmrError):
        p.fetch(ref)


# --------------------------------------------------------------------------
# 지시서 7장 — 올린 PDF 를 들고 있지 않는다
# --------------------------------------------------------------------------

def test_the_pdf_is_gone_once_the_run_finishes(tmp_path):
    """**이 검사가 제일 중요하다.**

    인식이 끝나면 PDF 는 더 필요 없다. 남겨 두면 악보를 보관하는 모양이 된다.
    """
    p = omr.LocalProvider(cmd=stub(tmp_path, WRITES_MXL))
    ref = p.submit(b'%PDF-1.4 secret score', 'a.pdf')
    pdf_path = p._jobs[ref]['pdf']
    assert os.path.exists(pdf_path), '돌리는 동안에는 있어야 한다'
    run(p, ref)
    assert not os.path.exists(pdf_path), '인식이 끝났는데 PDF 가 남아 있습니다'


def test_nothing_is_left_on_disk_afterwards(tmp_path):
    p = omr.LocalProvider(cmd=stub(tmp_path, WRITES_MXL))
    ref = p.submit(b'%PDF', 'a.pdf')
    work = p._jobs[ref]['work']
    run(p, ref)
    p.fetch(ref)
    assert not os.path.exists(work), f'임시 폴더가 남았습니다: {work}'


def test_a_failed_run_also_cleans_up(tmp_path):
    """실패했을 때가 더 위험하다 — 실패한 작업이 PDF 를 안고 쌓인다."""
    p = omr.LocalProvider(cmd=stub(tmp_path, 'sys.exit(3)\n'))
    ref = p.submit(b'%PDF', 'a.pdf')
    work = p._jobs[ref]['work']
    assert run(p, ref).state == omr.FAILED
    assert not os.path.exists(work)


# --------------------------------------------------------------------------
# 안 되는 경우
# --------------------------------------------------------------------------

def test_a_nonzero_exit_is_reported_with_the_log(tmp_path):
    p = omr.LocalProvider(cmd=stub(
        tmp_path, 'print("Could not decode image")\nsys.exit(2)\n'))
    res = run(p, p.submit(b'%PDF', 'a.pdf'))
    assert res.state == omr.FAILED
    assert '코드 2' in res.detail
    assert 'Could not decode image' in res.detail, '왜 실패했는지 보여 줘야 한다'


def test_a_run_that_produces_nothing_says_so_plainly(tmp_path):
    """인식기가 0으로 끝났는데 결과가 없는 경우 — 악보가 아닌 PDF 일 때 그렇다."""
    p = omr.LocalProvider(cmd=stub(tmp_path, 'pass\n'))
    res = run(p, p.submit(b'%PDF', 'a.pdf'))
    assert res.state == omr.FAILED
    assert 'MusicXML' in res.detail and '흐릴' in res.detail


def test_a_hung_run_is_killed(tmp_path):
    p = omr.LocalProvider(cmd=stub(tmp_path, 'time.sleep(30)\n'), timeout=0.4)
    res = run(p, p.submit(b'%PDF', 'a.pdf'), limit=8.0)
    assert res.state == omr.FAILED
    assert '넘겨 멈췄습니다' in res.detail


def test_an_unknown_job_does_not_blow_up(tmp_path):
    p = omr.LocalProvider(cmd=stub(tmp_path, WRITES_MXL))
    assert p.poll('local-없는것').state == omr.FAILED


# --------------------------------------------------------------------------
# 결과 파일 찾기 — Audiveris 는 자리를 하나로 안 둔다
# --------------------------------------------------------------------------

def test_it_finds_the_export_in_the_usual_place(tmp_path):
    d = tmp_path / 'out' / 'czerny'
    d.mkdir(parents=True)
    (d / 'czerny.mxl').write_bytes(MXL)
    assert omr._find_export(str(tmp_path / 'out')).endswith('czerny.mxl')


def test_with_several_movements_it_takes_the_whole_book(tmp_path):
    """악장이 여럿이면 `.opus.mxl` 에 전부 들어 있다 — 한 악장만 집으면 안 된다."""
    d = tmp_path / 'out' / 'sonata'
    d.mkdir(parents=True)
    (d / 'mvt1.mxl').write_bytes(b'x' * 100)
    (d / 'mvt2.mxl').write_bytes(b'x' * 120)
    (tmp_path / 'out' / 'sonata.opus.mxl').write_bytes(b'x' * 900)
    assert omr._find_export(str(tmp_path / 'out')).endswith('sonata.opus.mxl')


def test_no_export_means_none(tmp_path):
    (tmp_path / 'out').mkdir()
    (tmp_path / 'out' / 'log.txt').write_text('아무것도 아님')
    assert omr._find_export(str(tmp_path / 'out')) is None


# --------------------------------------------------------------------------
# 설정
# --------------------------------------------------------------------------

def test_the_command_can_come_from_the_environment(tmp_path, monkeypatch):
    path = stub(tmp_path, WRITES_MXL)
    monkeypatch.setenv(omr.LOCAL_CMD_ENV, path)
    assert omr.make_provider('local').available() is True


def test_extra_arguments_reach_the_command(tmp_path):
    """`-sheets 1-4` 처럼 쪽을 골라 넣는 경우가 있다."""
    log = tmp_path / 'argv.txt'          # 작업 폴더 밖 — 끝나면 지워지므로
    p = omr.LocalProvider(cmd=stub(tmp_path, _logs(log) + WRITES_MXL),
                          extra_args=['-sheets', '1-4'])
    run(p, p.submit(b'%PDF', 'a.pdf'))
    assert '-sheets 1-4' in log.read_text()


def test_it_passes_the_flags_audiveris_actually_takes(tmp_path):
    """소스에서 확인한 규약 — 틀리면 원장님 PC 에서 안 돈다.

    `CLI.java` 의 옵션은 `-batch` `-export` `-output` 이고, 입력 파일은
    `--` 뒤에 온다 (`@Option(name = "--", handler = StopOptionHandler.class)`).
    """
    log = tmp_path / 'argv.txt'
    p = omr.LocalProvider(cmd=stub(tmp_path, _logs(log) + WRITES_MXL))
    ref = p.submit(b'%PDF', 'a.pdf')
    out = p._jobs[ref]['out']
    run(p, ref)
    argv = log.read_text().split()
    assert argv[0] == '-batch'
    assert '-export' in argv
    assert argv[argv.index('-output') + 1] == out
    assert argv[-2] == '--', '입력 파일 앞에 -- 가 있어야 한다'
