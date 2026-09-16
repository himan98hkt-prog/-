#!/usr/bin/env python3
"""업로드 경로 스모크 점검 — **실제 업로드를 하지 않는다.**

Phase 0 요구사항: 실제 credential 이 필요한 검증을 자동으로 돌리지 않고,
사람이 확인할 수 있는 절차와 사전 점검만 제공한다.

이 스크립트가 하는 일
  1. 인증 파일과 토큰 상태 확인 (토큰 값은 출력하지 않는다)
  2. 업로드 요청 본문이 규격에 맞는지 dry-run 으로 조립
  3. 쇼츠 적격성(길이·세로) 사전 검사
  4. 할당량 정책 표시

이 스크립트가 하지 않는 일
  - videos.insert 호출
  - public/unlisted 전환
  - OAuth 브라우저 플로 자동 실행

실제 업로드 1건 검증은 docs/PHASE0_PRODUCTIZATION_REPORT.md 의
"private 업로드 실기 검증 절차" 를 사람이 직접 수행한다.

사용법:
    python scripts/smoke_upload.py output/output_01_제목.mp4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autoshorts import ffmpeg_tools, uploader  # noqa: E402
from autoshorts.quota import QUOTA_SOURCE_NOTE, load_quota_policy  # noqa: E402


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"  {'✅' if ok else '❌'} {label}{(' — ' + detail) if detail else ''}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="업로드 경로 스모크 점검 (실제 업로드 없음)")
    parser.add_argument("video", nargs="?", help="점검할 MP4 경로 (선택)")
    parser.add_argument("--token-path", default=None)
    parser.add_argument("--client-secret", default=None)
    args = parser.parse_args()

    print("\n=== 업로드 스모크 점검 (실제 업로드 없음) ===\n")
    problems = 0

    print("1. 인증 자산")
    secret = Path(args.client_secret or uploader.default_client_secret_path()).expanduser()
    token = Path(args.token_path or uploader.default_token_path()).expanduser()
    if not check("OAuth 클라이언트 JSON", secret.exists(), str(secret)):
        problems += 1
        print("      → Google Cloud Console 에서 '데스크톱 앱' 클라이언트를 만들어 위 경로에 두세요.")
    if not check("갱신 토큰", token.exists(), str(token) if token.exists() else "`autoshorts login` 필요"):
        problems += 1
    if token.exists():
        try:
            mode = oct(token.stat().st_mode & 0o777)
            check("토큰 파일 권한 0600", mode == "0o600", mode)
        except OSError:
            pass

    print("\n2. 라이브러리")
    for module, label in (
        ("googleapiclient", "google-api-python-client"),
        ("google_auth_oauthlib", "google-auth-oauthlib"),
    ):
        try:
            __import__(module)
            check(label, True)
        except ImportError:
            problems += 1
            check(label, False, f"pip install {label}")

    print("\n3. 할당량 정책")
    policy = load_quota_policy()
    print(f"  · 업로드 1건 비용: {policy.upload.cost_per_call} 유닛")
    print(f"  · 한도: {policy.describe_upload_limit()}")
    print(f"  · 출처: {policy.source}")
    print(f"  · {QUOTA_SOURCE_NOTE}")
    if not policy.verified:
        print("  ⚠️  공식 문서 대조가 아직 안 됐습니다. 보고서의 확인 절차를 수행하세요.")

    if args.video:
        print("\n4. 업로드 요청 조립 (dry-run)")
        path = Path(args.video)
        if not check("파일 존재", path.exists(), str(path)):
            return 1
        request = uploader.UploadRequest(
            video_path=path,
            title=path.stem.replace("_", " "),
            description="스모크 점검용 dry-run",
            privacy="private",
        )
        body = uploader.build_body(request)
        check("공개 범위 private", body["status"]["privacyStatus"] == "private")
        check("제목 100자 이내", len(body["snippet"]["title"]) <= 100,
              f"{len(body['snippet']['title'])}자")
        check("제목에 금지문자 없음", "<" not in body["snippet"]["title"])

        try:
            info = ffmpeg_tools.probe_media(path)
            warnings = uploader.check_shorts_eligibility(info.duration, info.width, info.height)
            check("쇼츠 적격", not warnings, "; ".join(warnings) if warnings else
                  f"{info.width}x{info.height}, {info.duration:.0f}초")
            if warnings:
                problems += 1
        except Exception as exc:
            check("미디어 정보 확인", False, str(exc))

    print()
    if problems:
        print(f"❌ {problems}건을 먼저 해결하세요. 실제 업로드는 수행하지 않았습니다.")
        return 1
    print("✅ 사전 점검 통과. 실제 private 업로드 1건은 보고서의 수동 절차로 진행하세요.")
    print("   (이 스크립트는 어떤 업로드도 수행하지 않았습니다.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
