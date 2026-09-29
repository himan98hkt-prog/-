"""'다시 실행하세요' 띠가 안 사라지던 문제 검사.

    python tests/test_restart.py

사용자 신고: 업데이트를 받고 검은 창을 닫았다 다시 켰는데도 노란 띠가
계속 떠 있다.

원인은 둘이었다.
  1) 먼저 떠 있던 작업실이 포트를 물고 있으면 새로 켜는 쪽이
     'Address already in use' 로 죽는다. 그런데 브라우저는 **옛 서버에
     그대로 붙어 있으므로** 화면은 멀쩡해 보인다. 그래서 아무리 다시 켜도
     띠가 그대로다.
  2) update.ps1 이 사용자 config.yaml 을 지키느라 새 기본값은
     config.yaml.new 로만 들어간다. 비용을 30% 낮추는 설정이 적용 안 된 채
     계속 쓰이고 있었다 (화면 견적이 $3.82 = 옛 모델 값이었다).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_restart"


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append(name)
    print(f"  [{'OK  ' if cond else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def up(port: int, timeout: float = 30.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), 0.4):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def state(port: int) -> dict:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


def launch(work: Path, port: int):
    return subprocess.Popen(
        [sys.executable, "main.py", "ui", "--port", str(port), "--no-browser"],
        cwd=work, env={**os.environ, "PYTHONUNBUFFERED": "1"},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def make_work() -> Path:
    work = TMP / "work"
    work.mkdir(parents=True)
    for name in ("main.py", "config.yaml"):
        shutil.copy2(ROOT / name, work / name)
    for d in ("pipeline", "publish", "ui", "brand"):
        shutil.copytree(ROOT / d, work / d,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (work / "seeds").mkdir()
    (work / "runs").mkdir()
    return work


# ══════════════════════════════════════════════════════════════════════
def test_takeover() -> None:
    print("\n[포트를 넘겨받기] 옛 창이 살아 있어도 다시 켜지면 된다")

    work = make_work()
    port = free_port()

    a = launch(work, port)
    if not up(port):
        check("첫 작업실이 뜬다", False, (a.stdout.read()[-800:] if a.stdout else ""))
        return
    check("첫 작업실이 뜬다", True)
    check("막 켠 뒤에는 띠가 없다", state(port)["needs_restart"] is False)

    # 업데이트를 흉내낸다 — 코드 파일이 새것이 된다
    time.sleep(1.5)
    for f in (work / "pipeline").glob("*.py"):
        f.touch()
    check("업데이트를 받으면 띠가 뜬다", state(port)["needs_restart"] is True)

    # 사용자가 [작업실] 을 다시 실행 — 옛 창은 아직 살아 있다
    b = launch(work, port)
    try:
        # **옛 서버가 완전히 죽은 뒤에** 물어봐야 한다. 그 전에 물으면 아직
        # 살아 있는 A 가 대답해서, 새 서버를 본 것처럼 착각하게 된다.
        check("옛 작업실은 스스로 닫힌다", _wait_dead(a, 40), f"종료코드 {a.poll()}")
        if not up(port, 40):
            check("두 번째 작업실이 자리를 넘겨받는다", False, "시간 초과")
            return
        got = None
        end = time.time() + 30
        while time.time() < end:
            try:
                got = state(port)
                break
            except (urllib.error.URLError, OSError):
                time.sleep(0.3)
        check("두 번째 작업실이 자리를 넘겨받는다", got is not None)
        check("넘겨받은 뒤에는 띠가 사라진다",
              bool(got) and got["needs_restart"] is False,
              str(got and got["needs_restart"]))
        out = ""
        if b.poll() is not None and b.stdout:
            out = b.stdout.read()
        check("빨간 Traceback 이 안 뜬다", "Traceback" not in out, out[-300:])
    finally:
        for proc in (a, b):
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


def _wait_dead(proc, timeout: float = 12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return True
        time.sleep(0.25)
    return False


def test_busy_port() -> None:
    print("\n[남의 프로그램이 포트를 쓸 때] 사람이 읽을 수 있는 말이 나온다")

    work = TMP / "work"
    port = free_port()
    blocker = socket.socket()
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    try:
        p = launch(work, port)
        out = p.stdout.read() if p.stdout else ""
        p.wait(timeout=30)
        check("그냥 죽지 않고 안내한다", "포트를 다른 프로그램이" in out, out[-300:])
        check("다른 번호로 여는 법을 알려준다", "--port" in out)
        check("빨간 Traceback 이 안 뜬다", "Traceback" not in out)
    finally:
        blocker.close()


def test_montage_needs_two() -> None:
    """화면을 거치지 않고 API 를 직접 불러도 1장짜리 장면 전환은 막아야 한다."""
    print("\n[장면 전환 최소 장 수] 서버도 스스로 막는다")

    work = make_work_at(TMP / "w2")
    (work / "seeds" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (work / "seeds" / "b.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    port = free_port()
    p = launch(work, port)
    try:
        if not up(port):
            check("작업실이 뜬다", False, "시간 초과")
            return

        def post(payload):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/generate",
                data=json.dumps(payload).encode(), method="POST",
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    return r.status, json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode())

        code, body = post({"seed": "a.png", "mode": "montage", "scenes": ["a.png"]})
        check("장면 1장은 거절한다", code == 400, f"{code} {body}")
        check("무엇을 하라고 알려준다",
              "2장 이상" in body.get("error", ""), body.get("error", ""))

        code, body = post({"seed": "a.png", "mode": "montage", "scenes": []})
        check("장면 0장도 거절한다", code == 400, f"{code} {body}")

        # chain 은 1장으로도 정상이다 — 막아버리면 안 된다
        code, body = post({"seed": "a.png", "mode": "chain", "clips": 2})
        check("이어지는 영상은 1장으로도 된다", code == 200, f"{code} {body}")
    finally:
        p.terminate()
        try:
            p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            p.kill()


def make_work_at(dest: Path) -> Path:
    dest.mkdir(parents=True)
    for name in ("main.py", "config.yaml"):
        shutil.copy2(ROOT / name, dest / name)
    for d in ("pipeline", "publish", "ui", "brand"):
        shutil.copytree(ROOT / d, dest / d,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (dest / "seeds").mkdir()
    (dest / "runs").mkdir()
    return dest


def test_config_diff() -> None:
    print("\n[새 권장 설정] 업데이트가 config.yaml 을 안 덮어써서 안 닿던 것")

    from pipeline import configdiff

    work = TMP / "work"
    cur, new = work / "config.yaml", work / "config.yaml.new"

    cur.write_text(
        "mode: chain\n"
        "provider: fal              # fal | higgsfield\n"
        "model: kling_25_turbo_pro  # providers 섹션의 키\n"
        "clip_duration: 5           # 초\n"
        "num_clips: 6\n"
        "upscale_between_clips: false\n"
        "\n"
        "output:\n"
        "  width: 1080\n"
        "  height: 1920\n", encoding="utf-8")
    new.write_text(
        "mode: chain\n"
        "provider: fal\n"
        "model: hailuo_23_pro\n"
        "clip_duration: 10\n"
        "num_clips: 3\n"
        "upscale_between_clips: true\n"
        "\n"
        "output:\n"
        "  width: 1080\n"
        "  height: 1920\n", encoding="utf-8")

    changes = configdiff.compare(cur, new)
    keys = {c.key for c in changes}
    check("바뀐 것만 골라낸다", keys == {"model", "clip_duration", "num_clips",
                                        "upscale_between_clips"}, str(keys))
    check("같은 값은 안 내민다", "mode" not in keys and "provider" not in keys)
    model = next(c for c in changes if c.key == "model")
    check("주석은 값에서 걷어낸다", model.current == "kling_25_turbo_pro",
          model.current)
    check("사람이 읽을 이름을 붙인다", model.label == "영상 모델")

    changed = configdiff.apply(cur, {c.key: c.incoming for c in changes})
    text = cur.read_text(encoding="utf-8")
    check("값이 실제로 바뀐다", "model: hailuo_23_pro" in text, text.splitlines()[2])
    check("바꾼 키를 알려준다", set(changed) == keys, str(changed))
    check("값 옆 주석은 살린다", "# providers 섹션의 키" in text)
    check("하위 설정은 안 건드린다", "  width: 1080" in text)
    check("적용 뒤에는 차이가 없다", configdiff.compare(cur, new) == [])

    # 허용 목록 밖은 손대지 않는다
    before = cur.read_text(encoding="utf-8")
    configdiff.apply(cur, {"output": "망가뜨리기", "hard_cap_usd": "999"})
    check("허용 목록 밖 키는 무시한다", cur.read_text(encoding="utf-8") == before)

    # 한쪽이 없으면 조용히 빈 목록
    check(".new 가 없으면 알림 없음",
          configdiff.compare(cur, work / "config.yaml.없음") == [])


def test_stamp_sees_providers() -> None:
    print("\n[코드 감시 범위] provider 만 바뀐 업데이트도 알아채야 한다")

    work = TMP / "work"
    sys.path.insert(0, str(work))
    from ui import server as srv

    # srv.ROOT 가 진짜 사본을 가리키는지부터 확인한다. 아니면 아래 검사가
    # 엉뚱한 폴더를 만지면서 통과해버린다.
    check("사본을 보고 있다", srv.ROOT == work.resolve(), str(srv.ROOT))

    before = srv._code_stamp()
    time.sleep(1.2)
    (work / "pipeline" / "providers" / "fal.py").touch()
    check("하위 폴더(providers)도 본다", srv._code_stamp() > before)

    before = srv._code_stamp()
    time.sleep(1.2)
    (work / "ui" / "app.html").touch()
    check("화면 파일(app.html)도 본다", srv._code_stamp() > before)


def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    try:
        test_takeover()
        test_busy_port()
        test_montage_needs_two()
        test_config_diff()
        test_stamp_sees_providers()
    finally:
        shutil.rmtree(TMP, ignore_errors=True)

    print(f"\n{'=' * 60}")
    print(f"통과 {len(PASSED)} · 실패 {len(FAILED)}")
    for f in FAILED:
        print(f"  실패: {f}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
