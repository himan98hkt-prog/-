"""설정 점검. 무엇이 준비됐고 무엇이 남았는지 한 화면에 보여준다.

돈을 쓰기 전에, 그리고 자동 업로드를 걸기 전에 이걸 먼저 돌린다.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

OK, WARN, FAIL = "ok", "warn", "fail"
_MARK = {OK: "✓", WARN: "!", FAIL: "✗"}


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    fix: str = ""

    def render(self) -> str:
        line = f"  {_MARK[self.status]} {self.name}"
        if self.detail:
            line += f" — {self.detail}"
        if self.fix and self.status != OK:
            line += f"\n      → {self.fix}"
        return line


@dataclass
class Section:
    title: str
    checks: list[Check]
    required_for: str = ""

    @property
    def ready(self) -> bool:
        return all(c.status != FAIL for c in self.checks)


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def check_core(root: Path) -> Section:
    checks = []

    py = shutil.which("python3") or shutil.which("python")
    checks.append(Check("Python", OK if py else FAIL, py or "",
                        "https://www.python.org/downloads/ 에서 설치"))

    ff = shutil.which("ffmpeg")
    checks.append(Check(
        "ffmpeg", OK if ff else FAIL, ff or "없음",
        "macOS: brew install ffmpeg / Windows: gyan.dev 에서 받아 PATH 추가"))

    try:
        import PIL, requests, yaml  # noqa: F401
        checks.append(Check("파이썬 패키지", OK, "설치됨"))
    except ImportError as exc:
        checks.append(Check("파이썬 패키지", FAIL, str(exc),
                            "pip install -r requirements.txt"))

    envf = root / ".env"
    checks.append(Check(
        ".env 파일", OK if envf.exists() else FAIL,
        str(envf) if envf.exists() else "없음",
        "cp .env.example .env 후 값을 채우세요"))

    return Section("기본 환경", checks, "필수")


def check_provider(root: Path, provider: str) -> Section:
    checks = []
    if provider == "fal":
        key = _env("FAL_API_KEY")
        checks.append(Check(
            "FAL_API_KEY", OK if key else FAIL,
            f"{key[:8]}…" if key else "없음",
            "https://fal.ai/dashboard/keys 에서 발급 후 .env 에 기록"))
    elif provider == "higgsfield":
        k, s = _env("HIGGSFIELD_API_KEY"), _env("HIGGSFIELD_API_SECRET")
        checks.append(Check(
            "HIGGSFIELD 키", OK if (k and s) else FAIL,
            "설정됨" if (k and s) else "없음",
            "https://cloud.higgsfield.ai/ → API keys"))
        if not _env("S3_ENDPOINT_URL") and not _env("PUBLIC_MEDIA_BASE_URL"):
            checks.append(Check(
                "이미지 공개 URL", FAIL, "없음",
                "higgsfield 는 입력 이미지를 공개 URL 로 받습니다. "
                "S3 를 설정하거나 provider 를 fal 로 바꾸세요"))
    return Section(f"영상 생성 ({provider})", checks, "필수")


def check_seeds(root: Path) -> Section:
    from .content import find_sidecar

    seeds = root / "seeds"
    checks = []
    if not seeds.is_dir():
        return Section("시드 이미지", [Check(
            "seeds/ 폴더", FAIL, "없음", "mkdir seeds 후 세로 이미지를 넣으세요")], "필수")

    exts = {".png", ".jpg", ".jpeg", ".webp"}
    images = [p for p in sorted(seeds.iterdir())
              if p.is_file() and p.suffix.lower() in exts]
    if images:
        checks.append(Check("시드 이미지", OK, f"{len(images)}장 대기 중"))
    else:
        checks.append(Check("시드 이미지", FAIL, "0장",
                            "seeds/ 에 9:16 세로 이미지를 넣으세요"))

    with_meta = sum(1 for p in images if find_sidecar(p))
    if images:
        status = OK if with_meta == len(images) else WARN
        checks.append(Check(
            "제목·설명 사이드카", status, f"{with_meta}/{len(images)}장",
            "python main.py plan 으로 빈 양식을 만들 수 있습니다. "
            "없으면 파일명이 제목이 됩니다"))

    # 하루 1편 기준 소진 예상
    if images:
        checks.append(Check("소진 예상", OK if len(images) >= 7 else WARN,
                            f"하루 1편이면 {len(images)}일치",
                            "일주일 이상 미리 채워두면 끊기지 않습니다"))
    return Section("시드 이미지", checks, "필수")


def check_youtube(root: Path, cfg: dict) -> Section:
    checks = []
    secret = Path(_env("YOUTUBE_CLIENT_SECRET_FILE") or "secrets/client_secret.json")
    if not secret.is_absolute():
        secret = root / secret
    checks.append(Check(
        "OAuth 클라이언트", OK if secret.exists() else FAIL,
        str(secret) if secret.exists() else "없음",
        "Google Cloud Console → OAuth 클라이언트 ID(데스크톱 앱) JSON 을 "
        "secrets/client_secret.json 로 저장"))

    token = Path(_env("YOUTUBE_TOKEN_FILE") or "secrets/youtube_token.json")
    if not token.is_absolute():
        token = root / token
    checks.append(Check(
        "인증 토큰", OK if token.exists() else WARN,
        "발급됨" if token.exists() else "아직 없음",
        "첫 업로드 때 브라우저 인증이 뜹니다. 자동 실행 전에 한 번 수동으로 "
        "업로드해 토큰을 만들어 두세요"))

    try:
        import googleapiclient  # noqa: F401
        checks.append(Check("업로드 패키지", OK, "설치됨"))
    except ImportError:
        checks.append(Check("업로드 패키지", FAIL, "없음",
                            "pip install google-api-python-client google-auth-oauthlib"))

    privacy = cfg.get("privacy", "private")
    checks.append(Check(
        "공개 설정", WARN if privacy == "private" else OK, privacy,
        "지금은 비공개로 올라갑니다. 바로 공개하려면 config.yaml 의 "
        "publish.youtube.privacy 를 public 으로"))
    return Section("유튜브 업로드", checks, "선택")


def check_instagram(root: Path) -> Section:
    checks = []
    uid, tok = _env("IG_USER_ID"), _env("IG_ACCESS_TOKEN")
    checks.append(Check(
        "IG_USER_ID", OK if uid else FAIL, uid or "없음",
        "인스타 비즈니스 계정 ID (숫자)"))
    checks.append(Check(
        "IG_ACCESS_TOKEN", OK if tok else FAIL,
        f"{tok[:10]}…" if tok else "없음",
        "Meta 개발자 앱에서 instagram_content_publish 권한으로 장기 토큰 발급"))

    bucket = _env("S3_BUCKET")
    checks.append(Check(
        "S3/R2 버킷", OK if bucket else FAIL, bucket or "없음",
        "인스타는 공개 URL 만 받습니다. Cloudflare R2 무료 티어를 권합니다"))

    if bucket:
        akey = _env("AWS_ACCESS_KEY_ID")
        checks.append(Check(
            "스토리지 자격증명", OK if akey else FAIL,
            "설정됨" if akey else "없음",
            "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY 를 .env 에"))
        try:
            import boto3  # noqa: F401
            checks.append(Check("boto3", OK, "설치됨"))
        except ImportError:
            checks.append(Check("boto3", FAIL, "없음", "pip install boto3"))
    return Section("인스타그램 업로드", checks, "선택")


def run_all(root: Path, cfg) -> tuple[list[Section], bool]:
    load_dotenv(root / ".env")
    pub = cfg.publish_cfg
    sections = [
        check_core(root),
        check_provider(root, cfg.provider),
        check_seeds(root),
        check_youtube(root, pub.get("youtube", {})),
        check_instagram(root),
    ]
    # 필수 항목만 통과하면 영상 제작은 가능하다
    can_generate = all(s.ready for s in sections[:3])
    return sections, can_generate
