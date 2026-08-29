"""올린 영상의 성적을 끌어와 **무엇이 통했는지** 로 바꾼다.

지금까지 이 프로그램은 만들고 올리는 데까지였다. 100편을 만들어도 어떤
테마·음악·움직임이 먹혔는지 알 방법이 없었다. 감으로 다음 시드를 고르게 된다.

필요한 것은 이미 다 저장돼 있다.

    state.json  테마 · 제목 · 훅 · 음악 · 카메라 움직임 · 모델 · 비용
                published.youtube.id   (video_id)
                published.instagram.id (media_id)

여기에 조회수만 붙이면

    골목 + city 음악 + 뒤에서 따라가기   평균 4,200회  (12편)
    얼음 + mystic 음악 + 상승             평균 1,100회  (9편)

가 나온다. 다음에 뭘 만들지가 감이 아니라 데이터로 정해진다.

**API 비용은 0원이다.** 유튜브 videos.list 는 1회 1유닛(하루 10,000),
인스타 insights 는 무료다. 50편을 한 번에 물어도 유튜브는 1유닛이다.
"""

from __future__ import annotations

import json
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# 유튜브는 한 번에 50개까지 물어볼 수 있다. 나눠서 부른다.
YT_CHUNK = 50
GRAPH = "https://graph.facebook.com/v21.0"


class InsightsError(Exception):
    pass


@dataclass
class Metric:
    """영상 한 편의 성적. 플랫폼마다 이름이 달라 여기서 통일한다."""

    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    reach: int = 0
    fetched_at: str = ""

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class Bucket:
    """같은 성질을 가진 영상들을 묶은 것. 성적표의 한 줄."""

    key: str
    videos: int = 0
    views: list[int] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.views)

    @property
    def average(self) -> float:
        return statistics.mean(self.views) if self.views else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self.views) if self.views else 0.0


# ══════════════════════════════════════════════════════════════════════
#  끌어오기
# ══════════════════════════════════════════════════════════════════════
def fetch_youtube(video_ids: list[str]) -> dict[str, Metric]:
    """유튜브 조회수·좋아요·댓글 수. 못 읽는 것은 그냥 빠진다."""
    if not video_ids:
        return {}
    from .youtube import UploadError, _credentials, _require_libs

    try:
        _, _, _, build, _ = _require_libs()
        creds = _credentials()
    except UploadError as exc:
        raise InsightsError(
            f"유튜브에 연결하지 못했습니다.\n  {exc}\n"
            "  [설정] 탭에서 [유튜브 연결하기] 를 다시 눌러 주세요 —\n"
            "  조회수를 읽으려면 예전에 없던 권한이 하나 더 필요합니다."
        ) from exc

    api = build("youtube", "v3", credentials=creds, cache_discovery=False)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out: dict[str, Metric] = {}
    for i in range(0, len(video_ids), YT_CHUNK):
        chunk = video_ids[i:i + YT_CHUNK]
        resp = api.videos().list(part="statistics", id=",".join(chunk)).execute()
        for item in resp.get("items", []):
            st = item.get("statistics", {})
            out[item["id"]] = Metric(
                views=_int(st.get("viewCount")),
                likes=_int(st.get("likeCount")),
                comments=_int(st.get("commentCount")),
                fetched_at=now,
            )
    return out


def fetch_instagram(media_ids: list[str], token: str = "") -> dict[str, Metric]:
    """인스타 릴스 재생수·도달·저장. 토큰이 없으면 빈 결과."""
    if not media_ids:
        return {}
    import requests

    token = token or os.getenv("IG_ACCESS_TOKEN", "")
    if not token:
        raise InsightsError(
            "IG_ACCESS_TOKEN 이 없습니다. [설정] 탭에서 인스타를 연결하세요.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # 릴스에서 쓸 수 있는 지표. 계정 종류에 따라 일부가 빠질 수 있어
    # 없는 것은 그냥 0 으로 둔다 — 여기서 죽으면 성적표 전체가 안 나온다.
    wanted = "views,reach,likes,comments,shares,saved"
    out: dict[str, Metric] = {}
    for media_id in media_ids:
        try:
            resp = requests.get(f"{GRAPH}/{media_id}/insights",
                                params={"metric": wanted, "access_token": token},
                                timeout=30)
        except requests.RequestException:
            continue
        if resp.status_code >= 400:
            continue
        values = {row.get("name"): _first_value(row)
                  for row in resp.json().get("data", [])}
        out[media_id] = Metric(
            views=_int(values.get("views")),
            likes=_int(values.get("likes")),
            comments=_int(values.get("comments")),
            shares=_int(values.get("shares")),
            saves=_int(values.get("saved")),
            reach=_int(values.get("reach")),
            fetched_at=now,
        )
    return out


def _first_value(row: dict) -> int:
    vals = row.get("values") or []
    return _int(vals[0].get("value")) if vals and isinstance(vals[0], dict) else 0


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ══════════════════════════════════════════════════════════════════════
#  모으기
# ══════════════════════════════════════════════════════════════════════
def published_of(run_dir: Path, state: dict) -> dict:
    """이 영상이 어디에 올라갔는지.

    **예전에 올린 것들이 여기서 빠지면 성적표가 텅 빈다.** state.json 에
    `published` 를 적기 시작한 것은 나중이라, 그 전에 올린 영상은 상태
    파일만 봐서는 "안 올렸다" 로 보인다. 실제로는 유튜브에 올라가 있는데.

    log.jsonl 에는 처음부터 publish.* 사건이 남아 있다. 거기서 되살린다.
    작업실 화면이 쓰는 것과 같은 방식이다.
    """
    saved = state.get("published")
    if saved:
        return saved

    log = Path(run_dir) / "log.jsonl"
    if not log.exists():
        return {}
    found: dict[str, dict] = {}
    try:
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if "publish." not in line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("event") == "publish.youtube" and rec.get("video_id"):
                found["youtube"] = {"ok": True, "id": rec["video_id"]}
            elif rec.get("event") == "publish.instagram" and rec.get("media_id"):
                found["instagram"] = {"ok": True, "id": rec["media_id"]}
    except OSError:
        return {}
    return found


def published_ids(runs_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(유튜브 video_id -> run_id, 인스타 media_id -> run_id)."""
    yt: dict[str, str] = {}
    ig: dict[str, str] = {}
    for state, run_dir in _states(runs_dir):
        pub = published_of(run_dir, state)
        for key, table in (("youtube", yt), ("instagram", ig)):
            entry = pub.get(key) or {}
            ident = entry.get("id") or entry.get("video_id") or entry.get("media_id")
            if entry.get("ok", True) and ident:
                table[str(ident)] = run_dir.name
    return yt, ig


def _states(runs_dir: Path):
    if not Path(runs_dir).is_dir():
        return
    for d in sorted(Path(runs_dir).iterdir()):
        sp = d / "state.json"
        if not d.is_dir() or not sp.exists():
            continue
        try:
            yield json.loads(sp.read_text(encoding="utf-8")), d
        except (json.JSONDecodeError, OSError):
            continue


def collect(runs_dir: Path, *, youtube: bool = True,
            instagram: bool = True) -> dict[str, list[str]]:
    """성적을 끌어와 각 run 의 state.json 에 적어 둔다.

    한쪽이 안 되어도 다른 쪽은 가져온다. 인스타 토큰이 만료됐다고 유튜브
    성적까지 못 보게 되면 곤란하다.
    """
    runs_dir = Path(runs_dir)
    yt_ids, ig_ids = published_ids(runs_dir)
    report: dict[str, list[str]] = {"updated": [], "problems": []}
    metrics: dict[str, dict] = defaultdict(dict)

    if youtube and yt_ids:
        try:
            for vid, m in fetch_youtube(list(yt_ids)).items():
                metrics[yt_ids[vid]]["youtube"] = m.as_dict()
        except InsightsError as exc:
            report["problems"].append(f"유튜브: {exc}")
    if instagram and ig_ids:
        try:
            for mid, m in fetch_instagram(list(ig_ids)).items():
                metrics[ig_ids[mid]]["instagram"] = m.as_dict()
        except InsightsError as exc:
            report["problems"].append(f"인스타: {exc}")

    for run_id, payload in metrics.items():
        sp = runs_dir / run_id / "state.json"
        try:
            state = json.loads(sp.read_text(encoding="utf-8"))
            state.setdefault("metrics", {}).update(payload)
            sp.write_text(json.dumps(state, ensure_ascii=False, indent=2,
                                     default=str), encoding="utf-8")
            report["updated"].append(run_id)
        except (json.JSONDecodeError, OSError) as exc:
            report["problems"].append(f"{run_id}: {exc}")
    return report


# ══════════════════════════════════════════════════════════════════════
#  성적표
# ══════════════════════════════════════════════════════════════════════
# 무엇으로 묶어서 볼 것인가. state.json 에 이미 들어 있는 값들이다.
DIMENSIONS: dict[str, tuple[str, str]] = {
    "theme":  ("테마", "테마"),
    "mood":   ("음악 분위기", "분위기"),
    "motion": ("카메라 움직임", "움직임"),
    "grade":  ("색보정", "색보정"),
    "hook":   ("훅 자막", "자막"),
    "loop":   ("무한 루프", "루프"),
}


def _dimension_values(state: dict) -> dict[str, str]:
    """이 영상이 각 항목에서 어디에 속하는지."""
    from pipeline import motions, music

    content = state.get("content") or {}
    seed = Path(str(state.get("seed_image") or ""))
    theme = state.get("theme") or _theme_of(seed)
    prompt = (content.get("prompt") or "").strip()

    found = ""
    for m in motions.MOTIONS:
        if prompt and prompt == m.prompt:
            found = m.label
            break

    return {
        "theme": theme or "(모름)",
        "mood": music.MOOD_LABEL.get(music.mood_for(theme), "(모름)"),
        "motion": found or "(직접 쓴 프롬프트)",
        "grade": state.get("grade") or "none",
        "hook": "넣음" if state.get("hook_burned") else "안 넣음",
        "loop": "넣음" if state.get("looped") else "안 넣음",
    }


def _theme_of(seed: Path) -> str:
    if not seed.name:
        return ""
    try:
        from pipeline.curate import classify
        return classify(seed)
    except Exception:          # noqa: BLE001 — 분류 실패로 성적표를 막지 않는다
        return ""


def views_of(state: dict) -> int:
    """두 플랫폼 조회수 합계."""
    m = state.get("metrics") or {}
    return sum(_int((m.get(p) or {}).get("views")) for p in ("youtube", "instagram"))


def summarize(runs_dir: Path, *, min_videos: int = 2) -> dict:
    """항목별 성적표. 영상이 적은 묶음은 숫자가 흔들려서 따로 표시한다."""
    rows: list[dict] = []
    for state, d in _states(runs_dir):
        if not (state.get("metrics") or {}):
            continue
        views = views_of(state)
        dims = _dimension_values(state)
        rows.append({
            "run": d.name,
            "title": (state.get("content") or {}).get("title", ""),
            "views": views,
            "cost": float(state.get("cost_usd") or 0),
            **dims,
        })

    tables: dict[str, list[dict]] = {}
    for key, (label, _short) in DIMENSIONS.items():
        buckets: dict[str, Bucket] = {}
        for row in rows:
            b = buckets.setdefault(row[key], Bucket(row[key]))
            b.videos += 1
            b.views.append(row["views"])
        ranked = sorted(buckets.values(), key=lambda b: -b.average)
        tables[key] = [{
            "key": b.key, "label": label, "videos": b.videos,
            "total": b.total, "average": round(b.average, 1),
            "median": round(b.median, 1),
            "enough": b.videos >= min_videos,
        } for b in ranked]

    rows.sort(key=lambda r: -r["views"])
    total_views = sum(r["views"] for r in rows)
    total_cost = sum(r["cost"] for r in rows)
    return {
        "videos": len(rows),
        "total_views": total_views,
        "total_cost": round(total_cost, 2),
        # 조회수 1,000회당 얼마 들었나. 광고 단가와 바로 비교할 수 있는 숫자다.
        "cost_per_1k": round(total_cost / total_views * 1000, 2) if total_views else None,
        "best": rows[:5],
        "worst": rows[-3:][::-1] if len(rows) > 5 else [],
        "tables": tables,
    }


def render(summary: dict, *, min_videos: int = 2) -> str:
    """콘솔에 그대로 찍을 수 있는 성적표."""
    if not summary["videos"]:
        return ("아직 성적을 읽은 영상이 없습니다.\n"
                "  올린 영상이 있다면: python main.py stats --refresh\n"
                "  올린 게 없다면 먼저 유튜브·인스타에 올려주세요.")

    lines = [
        "┌─ 성적표 ────────────────────────────────────────────────",
        f"│ 영상 {summary['videos']}편 · 총 조회 {summary['total_views']:,}회"
        f" · 총 비용 ${summary['total_cost']:.2f}",
    ]
    if summary["cost_per_1k"] is not None:
        lines.append(f"│ 조회 1,000회당 ${summary['cost_per_1k']:.2f}")
    lines.append("└─────────────────────────────────────────────────────────")

    for key, (label, short) in DIMENSIONS.items():
        table = [r for r in summary["tables"].get(key, []) if r["enough"]]
        thin = [r for r in summary["tables"].get(key, []) if not r["enough"]]
        if not table and not thin:
            continue
        lines.append(f"\n  ── {label} ──")
        for r in table:
            lines.append(f"    {r['key']:<18} 평균 {r['average']:>8,.0f}회"
                         f"   ({r['videos']}편, 합계 {r['total']:,})")
        if thin:
            names = ", ".join(f"{r['key']}({r['videos']})" for r in thin[:6])
            lines.append(f"    · {min_videos}편 미만이라 아직 판단 보류: {names}")

    if summary["best"]:
        lines.append("\n  ── 가장 많이 본 영상 ──")
        for r in summary["best"]:
            lines.append(f"    {r['views']:>8,}회  {r['title'] or r['run']}"
                         f"   [{r['theme']} · {r['motion']}]")
    return "\n".join(lines)
