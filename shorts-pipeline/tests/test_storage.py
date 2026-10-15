"""S3 업로드 검증. moto 로 실제 S3 프로토콜을 흉내내 실호출 없이 검사한다.

  pip install "moto[s3]"
  python tests/test_storage.py
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASSED, FAILED = [], []
TMP = ROOT / "tests" / "_tmp_s3"


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(name)
    print(f"  {'✓' if condition else '✗'} {name}" + (f"  — {detail}" if detail else ""))


def _fake_creds() -> None:
    os.environ.update(
        AWS_ACCESS_KEY_ID="testing",
        AWS_SECRET_ACCESS_KEY="testing",
        AWS_SECURITY_TOKEN="testing",
        AWS_SESSION_TOKEN="testing",
        AWS_DEFAULT_REGION="us-east-1",
    )


def make_file(name: str, size_kb: int = 64) -> Path:
    TMP.mkdir(parents=True, exist_ok=True)
    p = TMP / name
    p.write_bytes(b"\0" * (size_kb * 1024))
    return p


def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP)
    _fake_creds()

    import boto3
    from moto import mock_aws

    from publish.storage import S3Storage, StorageError

    print("═" * 62)
    print(" S3 업로드 검증 (moto — 실제 AWS 호출 0회)")
    print("═" * 62)

    # ── 설정 검증 (네트워크 불필요) ──────────────────────────────────
    print("\n[설정 가드]")
    try:
        S3Storage(bucket="b", url_strategy="nonsense")
        check("잘못된 url_strategy 거부", False)
    except StorageError:
        check("잘못된 url_strategy 거부", True)

    try:
        S3Storage(bucket="b", expiry_seconds=10)
        check("만료 60초 미만 거부", False)
    except StorageError:
        check("만료 60초 미만 거부", True)

    try:
        S3Storage(bucket="b", expiry_seconds=999_999)
        check("만료 7일 초과 거부", False)
    except StorageError:
        check("만료 7일 초과 거부", True)

    try:
        S3Storage(bucket="b", url_strategy="public",
                  endpoint_url="https://x.r2.cloudflarestorage.com")
        check("커스텀 엔드포인트 + public 인데 도메인 없으면 거부", False)
    except StorageError:
        check("커스텀 엔드포인트 + public 인데 도메인 없으면 거부", True)

    st = S3Storage(bucket="b", prefix="reels")
    check("키 조합", st.key_for(Path("final.mp4"), "20260821_1930")
          == "reels/20260821_1930/final.mp4", st.key_for(Path("final.mp4"), "20260821_1930"))

    st_noprefix = S3Storage(bucket="b", prefix="")
    check("prefix 없으면 생략", st_noprefix.key_for(Path("a.mp4"), "r1") == "r1/a.mp4")

    # ── from_env ──────────────────────────────────────────────────
    print("\n[from_env]")
    os.environ.pop("S3_BUCKET", None)
    try:
        S3Storage.from_env({})
        check("버킷 없으면 오류", False)
    except StorageError as exc:
        check("버킷 없으면 오류", "S3_BUCKET" in str(exc))

    os.environ["S3_BUCKET"] = "from-env-bucket"
    check("환경변수에서 버킷", S3Storage.from_env({}).bucket == "from-env-bucket")
    check("config 가 환경변수보다 우선",
          S3Storage.from_env({"bucket": "from-cfg"}).bucket == "from-cfg")
    check("빈 문자열은 무시되고 환경변수로 폴백",
          S3Storage.from_env({"bucket": ""}).bucket == "from-env-bucket")

    # ── 버킷 이름 규격 ────────────────────────────────────────────
    # R2 대시보드는 한글 이름을 만들게 해주지만 S3 프로토콜은 못 받는다.
    # 실사용에서 '쇼츠-미디어' 버킷을 만들어 놓고 막힌 적이 있다.
    for bad in ("쇼츠-미디어", "내 버킷", "버킷!"):
        os.environ["S3_BUCKET"] = bad
        try:
            S3Storage.from_env()
            check(f"버킷 이름 거부: {bad}", False, "통과돼버림")
        except StorageError as exc:
            check(f"버킷 이름 거부: {bad}", "S3 규격에 맞지 않습니다" in str(exc))
            if bad == "쇼츠-미디어":
                check("한글은 안 된다고 알려줌", "한글은 안 됩니다" in str(exc))
                check("고치는 방법도 알려줌", "ai-deokhu" in str(exc))
    for good in ("ai-deokhu", "my.bucket-1", "AB_c"):
        os.environ["S3_BUCKET"] = good
        try:
            S3Storage.from_env()
            check(f"버킷 이름 허용: {good}", True)
        except StorageError as exc:
            check(f"버킷 이름 허용: {good}", False, str(exc)[:60])
    os.environ["S3_BUCKET"] = "test-bucket"

    # ── 실제 업로드 (moto) ────────────────────────────────────────
    print("\n[업로드 — presigned]")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="reel-bucket")
        storage = S3Storage(bucket="reel-bucket", region="us-east-1",
                            prefix="reels", expiry_seconds=3600)
        video = make_file("final.mp4", 128)
        obj = storage.upload(video, run_id="20260821_1930", show_progress=False)

        check("키 경로", obj.key == "reels/20260821_1930/final.mp4", obj.key)
        check("크기 기록", obj.size_bytes == 128 * 1024, f"{obj.size_mb:.2f}MB")
        check("presigned 는 만료가 있다", obj.is_temporary)

        q = parse_qs(urlparse(obj.url).query)
        check("SigV4 서명 포함", q.get("X-Amz-Algorithm") == ["AWS4-HMAC-SHA256"],
              str(q.get("X-Amz-Algorithm")))
        check("만료 3600초", q.get("X-Amz-Expires") == ["3600"], str(q.get("X-Amz-Expires")))

        # 실제로 객체가 올라갔는지, content-type 이 맞는지
        head = boto3.client("s3", region_name="us-east-1").head_object(
            Bucket="reel-bucket", Key=obj.key)
        check("S3 에 실제 존재", head["ContentLength"] == 128 * 1024)
        check("Content-Type video/mp4", head["ContentType"] == "video/mp4",
              head["ContentType"])

        # 삭제
        storage.delete(obj.key)
        remaining = boto3.client("s3", region_name="us-east-1").list_objects_v2(
            Bucket="reel-bucket").get("KeyCount", 0)
        check("delete 로 객체 제거", remaining == 0, f"{remaining}개 남음")

    print("\n[업로드 — public]")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="pub-bucket")
        storage = S3Storage(bucket="pub-bucket", region="us-east-1",
                            url_strategy="public",
                            public_base_url="https://cdn.example.com")
        obj = storage.upload(make_file("clip.mp4"), run_id="r2", show_progress=False)
        check("커스텀 도메인 URL",
              obj.url == "https://cdn.example.com/reels/r2/clip.mp4", obj.url)
        check("public 은 만료 없음", not obj.is_temporary)

    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="plain-bucket")
        storage = S3Storage(bucket="plain-bucket", region="us-east-1",
                            url_strategy="public")
        obj = storage.upload(make_file("x.mp4"), run_id="r3", show_progress=False)
        check("도메인 없으면 s3.amazonaws.com",
              obj.url == "https://plain-bucket.s3.amazonaws.com/reels/r3/x.mp4", obj.url)

    # ── 오류 처리 ─────────────────────────────────────────────────
    print("\n[오류 처리]")
    with mock_aws():
        storage = S3Storage(bucket="does-not-exist", region="us-east-1")
        try:
            storage.upload(make_file("y.mp4"), run_id="r4", show_progress=False)
            check("없는 버킷은 안내 메시지", False)
        except StorageError as exc:
            check("없는 버킷은 안내 메시지",
                  "NoSuchBucket" in str(exc) and "확인하세요" in str(exc))

    storage = S3Storage(bucket="b")
    try:
        storage.upload(TMP / "nope.mp4", show_progress=False)
        check("없는 파일은 오류", False)
    except StorageError as exc:
        check("없는 파일은 오류", "없습니다" in str(exc))

    empty = TMP / "empty.mp4"
    empty.write_bytes(b"")
    try:
        storage.upload(empty, show_progress=False)
        check("빈 파일은 오류", False)
    except StorageError as exc:
        check("빈 파일은 오류", "비어" in str(exc))

    # ── R2 (커스텀 엔드포인트) ────────────────────────────────────
    print("\n[R2 설정]")
    R2_EP = "https://acct.r2.cloudflarestorage.com"
    r2 = S3Storage(bucket="r2b", region="auto", endpoint_url=R2_EP)
    check("region auto 허용", r2.region == "auto")
    check("path-style 주소 지정", r2._client().meta.config.s3["addressing_style"] == "path")

    # botocore 1.36+ 는 CRC32 체크섬을 기본 전송한다. R2 는 이를 거부하므로
    # 커스텀 엔드포인트에서는 반드시 꺼져 있어야 한다.
    r2_cfg = r2._client().meta.config
    aws_cfg = S3Storage(bucket="b", region="us-east-1")._client().meta.config
    check("R2 는 체크섬 계산 when_required",
          getattr(r2_cfg, "request_checksum_calculation", None) == "when_required",
          str(getattr(r2_cfg, "request_checksum_calculation", "n/a")))
    check("AWS 는 기본 동작 유지",
          getattr(aws_cfg, "request_checksum_calculation", None) == "when_supported",
          str(getattr(aws_cfg, "request_checksum_calculation", "n/a")))

    try:
        S3Storage(bucket="b", endpoint_url=R2_EP, acl="public-read")
        check("R2 + ACL 조합 거부", False)
    except StorageError as exc:
        check("R2 + ACL 조합 거부", "ACL" in str(exc))

    tc = S3Storage(bucket="b", multipart_threshold_mb=100)._transfer_config()
    check("멀티파트 임계값 100MB", tc.multipart_threshold == 100 * 1024 * 1024,
          f"{tc.multipart_threshold / 1048576:.0f}MB")

    # ── 실제 HTTP: 체크섬 헤더가 나가지 않는지 ─────────────────────
    print("\n[R2 실제 업로드 — 체크섬 헤더 검사]")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="hdr-bucket")
        storage = S3Storage(bucket="hdr-bucket", region="us-east-1")
        sent = []
        base = storage._client

        def spy():
            c = base()
            c.meta.events.register(
                "before-send.s3.*",
                lambda request, **kw: sent.append(dict(request.headers)) or None,
            )
            return c

        storage._client = spy
        storage.upload(make_file("big.mp4", 12 * 1024), run_id="r5", show_progress=False)
        check("12MB 는 단일 PUT (멀티파트 아님)", len(sent) == 1, f"{len(sent)}건 요청")

    # ── 무료 티어 사용량 ──────────────────────────────────────────
    print("\n[무료 티어 사용량]")
    from publish.storage import BucketUsage, R2_FREE_STORAGE_GB

    u = BucketUsage("b", 3, 12 * 1024 * 1024 * 3)
    check("총 용량 계산", abs(u.total_gb - 0.0352) < 0.001, f"{u.total_gb:.4f}GB")
    check("무료 티어 비율", abs(u.free_tier_pct - 0.352) < 0.01, f"{u.free_tier_pct:.3f}%")
    check("여유 있으면 경고 없음", "⚠" not in u.render())
    check("80% 넘으면 경고",
          "⚠" in BucketUsage("b", 1, int(8.5 * 1024 ** 3)).render())
    check("무료 티어 상수 10GB", R2_FREE_STORAGE_GB == 10)

    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="usage-bucket")
        storage = S3Storage(bucket="usage-bucket", region="us-east-1")
        check("빈 버킷 사용량 0", storage.usage().object_count == 0)
        storage.upload(make_file("u1.mp4", 512), run_id="u1", show_progress=False)
        storage.upload(make_file("u2.mp4", 512), run_id="u2", show_progress=False)
        usage = storage.usage()
        check("객체 2개 집계", usage.object_count == 2, f"{usage.object_count}개")
        check("바이트 합산", usage.total_bytes == 2 * 512 * 1024,
              f"{usage.total_bytes}B")

    # ── config.yaml 기본값이 R2 무료 티어에 맞는지 ─────────────────
    print("\n[config.yaml 기본값]")
    import yaml

    sc = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    sc = sc["publish"]["storage"]
    check("presigned 기본", sc["url_strategy"] == "presigned", sc["url_strategy"])
    check("발행 후 삭제 기본 on", sc["delete_after_publish"] is True)
    check("ACL 비어 있음 (R2 미지원)", not sc["acl"])
    check("멀티파트 임계값 100MB", sc["multipart_threshold_mb"] == 100)
    check("region 비움 -> auto 로 폴백", sc["region"] == "")
    os.environ.pop("S3_ENDPOINT_URL", None)
    os.environ["S3_BUCKET"] = "cfg-bucket"
    check("기본 config 로 region auto", S3Storage.from_env(sc).region == "auto")

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n" + "═" * 62)
    print(f" 통과 {len(PASSED)} / 실패 {len(FAILED)}")
    for name in FAILED:
        print(f"   ✗ {name}")
    print("═" * 62)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
