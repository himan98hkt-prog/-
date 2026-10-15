# -*- coding: utf-8 -*-
"""CLI — 지시서 9장 1단계 완료 항목.

    python mr.py score.mxl --style chamber --level normal --bpm 84 -o out.mp3
"""
import json
import os
import shutil

import pytest

from conftest import score
from piano_mr import cli

has_audio = shutil.which('fluidsynth') and shutil.which('ffmpeg')


def test_spec_command_line_works(tmp_path, capsys):
    """지시서에 적힌 그 명령이 그대로 돌아야 한다."""
    if not has_audio:
        pytest.skip('fluidsynth/ffmpeg 없음')
    out = str(tmp_path / 'out.mp3')
    rc = cli.main([score('p07_minuet_g'), '--style', 'chamber', '--level', 'normal',
                   '--bpm', '84', '-o', out])
    assert rc == 0 and os.path.exists(out)
    assert '실내악' in capsys.readouterr().out


def test_analyze_only_prints_the_grid(capsys):
    rc = cli.main([score('p01_block_c'), '--analyze-only'])
    assert rc == 0
    out = capsys.readouterr().out
    assert '조성: C major' in out and 'm1' in out


def test_analyze_only_json(capsys):
    rc = cli.main([score('p01_block_c'), '--analyze-only', '--json'])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data['key'] == 'C major' and data['measures'] == 8
    assert data['segments'][0]['label'] == 'C'


def test_harmony_json_roundtrip(tmp_path, capsys):
    """분석 -> (확인 화면에서 교정) -> 그 화성으로 반주 생성."""
    hj = str(tmp_path / 'h.json')
    assert cli.main([score('p01_block_c'), '--analyze-only', '--harmony-json', hj]) == 0
    with open(hj, encoding='utf-8') as f:
        data = json.load(f)
    for s in data['segments']:
        s['root'], s['qual'], s['label'] = 5, 'M', 'F'
    with open(hj, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    capsys.readouterr()
    out = str(tmp_path / 'x.mid')
    assert cli.main([score('p01_block_c'), '--use-harmony', hj, '-o', out,
                     '--out-dir', str(tmp_path)]) == 0
    assert os.path.exists(out)


def test_styles_listing(capsys):
    assert cli.main(['--styles']) == 0
    out = capsys.readouterr().out
    for name in ('strings', 'chamber', 'orchestra', 'fairytale', 'warm', 'march', 'pop'):
        assert name in out
    assert '간단' in out and '풍성' in out


def test_no_arguments_prints_help(capsys):
    assert cli.main([]) == 2
    assert 'usage' in capsys.readouterr().out.lower()


def test_missing_file_is_a_clean_error(capsys):
    assert cli.main(['없는파일.mxl', '--analyze-only']) == 1
    assert '오류' in capsys.readouterr().err


def test_key_override(capsys):
    cli.main([score('p17_two_four_pickup'), '--analyze-only', '--key', 'C'])
    assert '조성: C major' in capsys.readouterr().out


def test_transpose_changes_the_key(capsys):
    cli.main([score('p01_block_c'), '--analyze-only', '--transpose', '2'])
    assert '조성: D major' in capsys.readouterr().out


def test_bad_style_is_rejected():
    with pytest.raises(SystemExit):
        cli.main([score('p01_block_c'), '--style', '없는스타일'])
