"""새로 받은 미드저니 이미지를 seeds/ 로 들여오고, 이미 있는 것을 다시 분류한다.

`curate` 와 목적이 다르다.

  curate   수백 장을 한 번에 훑어 테마마다 상위 N장만 남긴다. 처음 세팅할 때.
  intake   받을 때마다 조금씩. **이미 들여온 것은 건너뛰고 새 것만** 붙인다.

미드저니는 계속 다운로드된다. 매번 전체를 다시 고르면 이미 만든 영상의
시드가 사라지거나 이름이 바뀐다. 그래서 들여온 파일의 내용 해시를
`seeds/.intake.json` 에 적어두고 같은 그림은 두 번 넣지 않는다.

원본 파일명은 사이드카의 `source:` 에 남긴다. 테마 분류가 파일명으로
이루어지므로, 나중에 키워드 사전이 늘어났을 때 이것만 있으면 **다시 분류**
할 수 있다. 원본 이름을 버리면 되돌릴 방법이 없다.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .copywriter import write as write_copy
from .curate import (IMAGE_EXT, analyze, classify, prompt_from_filename,
                     prompt_signature)

INDEX_NAME = ".intake.json"

# 같은 프롬프트에서 나온 4장은 거의 같다. 이 거리 이하면 한 장만 쓴다.
DEDUPE_THRESHOLD = 24


@dataclass
class Item:
    """들여온(또는 건너뛴) 이미지 한 장."""
    source: str                 # 원본 파일명
    name: str = ""              # seeds/ 안에서의 이름
    theme: str = ""
    title: str = ""
    score: float = 0.0
    reason: str = ""            # 건너뛴 이유. 비어 있으면 들여온 것.


@dataclass
class Report:
    scanned: int = 0
    added: list[Item] = field(default_factory=list)
    skipped: list[Item] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.added or self.renamed or self.fixed)


# ── 인덱스 ────────────────────────────────────────────────────────────
def _index_path(seeds: Path) -> Path:
    return seeds / INDEX_NAME


def load_index(seeds: Path) -> dict[str, dict]:
    path = _index_path(seeds)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_index(seeds: Path, index: dict[str, dict]) -> None:
    seeds.mkdir(parents=True, exist_ok=True)
    _index_path(seeds).write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def file_hash(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 사이드카 ──────────────────────────────────────────────────────────
def write_sidecar(image: Path, theme: str, source_name: str) -> str:
    """제목·훅·움직임 프롬프트를 지어 이미지 옆 .yaml 에 넣는다. 제목을 돌려준다."""
    copy = write_copy(theme, prompt_from_filename(Path(source_name)),
                      seed_key=image.stem)
    image.with_suffix(".yaml").write_text(
        "# 제목과 훅은 조회수에 직접 영향을 줍니다. 마음에 안 들면 고치세요.\n"
        f"title:  {copy.title}\n"
        f"hook:   {copy.hook}\n"
        "\n"
        "# 영상의 카메라 움직임. 비우면 config.yaml 의 motion_prompt 를 씁니다.\n"
        f"prompt: {copy.prompt}\n"
        "\nscene_prompts: []\n"
        "\n"
        "# 아래 두 줄은 자동으로 다시 분류할 때 씁니다. 지우지 마세요.\n"
        f"theme:  {theme}\n"
        f"source: {source_name}\n",
        encoding="utf-8")
    return copy.title


def read_sidecar(image: Path) -> dict:
    """사이드카에서 title/hook/theme/source 만 얕게 읽는다.

    yaml 로 파싱하지 않는다. 사용자가 손으로 고치다 들여쓰기를 깨도
    source 한 줄만 살아 있으면 다시 분류할 수 있어야 하기 때문이다.
    """
    path = image.with_suffix(".yaml")
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in lines:
        if line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in ("title", "hook", "theme", "source") and key not in out:
            out[key] = value.strip()
    return out


# ── 들여오기 ──────────────────────────────────────────────────────────
def _next_name(seeds: Path, theme: str, ext: str) -> Path:
    n = 1
    while (seeds / f"{theme}_{n:02d}{ext}").exists():
        n += 1
    return seeds / f"{theme}_{n:02d}{ext}"


def existing_hashes(seeds: Path) -> dict[str, list[int]]:
    """이미 들여온 이미지의 dhash 를 **프롬프트 서명별로** 모은다.

    서명을 무시하고 전부 비교하면 안 된다. 밝은 하늘 풍경끼리는 장면이
    전혀 달라도 dhash 가 가깝게 나온다. curate.dedupe 도 같은 이유로
    서명 안에서만 비교한다. 여기서만 다르게 하면 새 그림이 소리 없이
    "이미 있는 것과 거의 같음" 으로 버려진다.
    """
    out: dict[str, list[int]] = {}
    index = load_index(seeds)
    by_name = {v.get("name"): v.get("source", "") for v in index.values()}
    for p in sorted(seeds.glob("*")):
        if p.suffix.lower() not in IMAGE_EXT:
            continue
        shot = analyze(p)
        if shot is None:
            continue
        source = by_name.get(p.name) or read_sidecar(p).get("source") or ""
        key = prompt_signature(Path(source)) if source else shot.signature
        out.setdefault(key, []).append(shot.dhash)
    return out


def _too_similar(dhash: int, signature: str,
                 known: dict[str, list[int]], threshold: int) -> bool:
    return any(bin(dhash ^ k).count("1") <= threshold
               for k in known.get(signature, ()))


def import_folder(source: Path, seeds: Path, *, min_score: float = 0.0,
                  recursive: bool = True, limit: int = 0,
                  dedupe_threshold: int = DEDUPE_THRESHOLD,
                  move: bool = False) -> Report:
    """폴더의 이미지 중 **아직 안 들여온 것만** seeds/ 에 넣는다."""
    source, seeds = Path(source).expanduser(), Path(seeds)
    report = Report()
    if not source.is_dir():
        raise NotADirectoryError(f"폴더를 찾을 수 없습니다: {source}")
    seeds.mkdir(parents=True, exist_ok=True)

    index = load_index(seeds)
    known = existing_hashes(seeds)

    walk = source.rglob("*") if recursive else source.glob("*")
    files = [p for p in sorted(walk)
             if p.is_file() and p.suffix.lower() in IMAGE_EXT]
    # seeds/ 자신을 가리키면 이미 들여온 것을 또 읽게 된다
    files = [p for p in files if p.parent.resolve() != seeds.resolve()]
    report.scanned = len(files)

    for path in files:
        if limit and len(report.added) >= limit:
            break
        try:
            digest = file_hash(path)
        except OSError as exc:
            report.skipped.append(Item(path.name, reason=f"읽을 수 없음 ({exc})"))
            continue
        if digest in index:
            report.skipped.append(
                Item(path.name, name=index[digest].get("name", ""),
                     reason="이미 들여온 그림"))
            continue

        shot = analyze(path)
        if shot is None:
            report.skipped.append(Item(path.name, reason="이미지를 열 수 없음"))
            continue
        if shot.disqualified:
            report.skipped.append(
                Item(path.name, score=shot.score,
                     reason=shot.reasons[0] if shot.reasons else "규격 미달"))
            continue
        if shot.score < min_score:
            report.skipped.append(
                Item(path.name, score=shot.score,
                     reason=f"점수 {shot.score:.0f} — 기준 {min_score:.0f} 미만"))
            continue
        signature = prompt_signature(path)
        if _too_similar(shot.dhash, signature, known, dedupe_threshold):
            report.skipped.append(
                Item(path.name, reason="같은 프롬프트에서 나온 거의 같은 그림"))
            continue

        theme = classify(path)
        dest = _next_name(seeds, theme, path.suffix.lower())
        if move:
            shutil.move(str(path), dest)
        else:
            shutil.copy2(path, dest)
        title = write_sidecar(dest, theme, path.name)

        known.setdefault(signature, []).append(shot.dhash)
        index[digest] = {"name": dest.name, "source": path.name, "theme": theme}
        report.added.append(Item(path.name, name=dest.name, theme=theme,
                                 title=title, score=shot.score))

    save_index(seeds, index)
    return report


# ── 다시 분류 ─────────────────────────────────────────────────────────
def reclassify(seeds: Path, *, rewrite_copy: bool = False) -> Report:
    """seeds/ 안을 전부 다시 살펴 분류·사이드카를 맞춘다.

    - 사이드카가 없으면 만든다
    - 원본 이름이 남아 있고 테마가 달라졌으면 파일 이름을 고친다
    - 제목·훅은 그대로 둔다. 사용자가 고쳐 놓았을 수 있다.
      (`rewrite_copy=True` 면 다시 짓는다)
    """
    seeds = Path(seeds)
    report = Report()
    if not seeds.is_dir():
        raise NotADirectoryError(f"폴더를 찾을 수 없습니다: {seeds}")

    index = load_index(seeds)
    by_name = {v.get("name"): (k, v) for k, v in index.items() if v.get("name")}

    images = [p for p in sorted(seeds.glob("*")) if p.suffix.lower() in IMAGE_EXT]
    report.scanned = len(images)

    for image in images:
        if analyze(image) is None:
            report.skipped.append(Item(image.name, reason="이미지를 열 수 없음"))
            continue

        side = read_sidecar(image)
        digest, entry = by_name.get(image.name, (None, {}))
        source = side.get("source") or entry.get("source") or ""

        # 원본 이름이 있으면 그것으로 분류한다. 없으면 지금 이름으로 —
        # 지금 이름은 이미 'theme_01' 꼴이라 같은 테마가 다시 나온다.
        # 되돌릴 수는 없어도 최소한 잘못 바꾸지는 않는다.
        theme = classify(Path(source) if source else image)
        old_theme = (side.get("theme") or entry.get("theme")
                     or _theme_of_name(image))

        keep = {k: side[k] for k in ("title", "hook") if side.get(k)}
        moved = False
        if source and theme != old_theme:
            dest = _next_name(seeds, theme, image.suffix.lower())
            old_side = image.with_suffix(".yaml")
            was = image.name
            image.rename(dest)
            if old_side.exists():
                old_side.unlink()
            report.renamed.append((was, dest.name))
            image, moved = dest, True

        if moved or rewrite_copy or not image.with_suffix(".yaml").exists():
            write_sidecar(image, theme, source or image.name)
            # 테마가 바뀌면 훅도 바뀌어야 한다. 제목만 되살린다.
            if not rewrite_copy and keep.get("title"):
                _restore(image, {"title": keep["title"]})
            report.fixed.append(image.name)
        elif old_theme != theme:
            _restore(image, {"theme": theme})
            report.fixed.append(image.name)

        if digest:
            index[digest] = {"name": image.name, "source": source, "theme": theme}

    save_index(seeds, index)
    return report


def _theme_of_name(image: Path) -> str:
    """'downhill_03.png' -> 'downhill'. 번호가 없으면 이름 전체."""
    stem = image.stem
    head, sep, tail = stem.rpartition("_")
    return head if sep and tail.isdigit() else stem


def _restore(image: Path, values: dict) -> None:
    """사이드카의 특정 줄만 사용자가 고쳐 둔 값으로 되돌린다."""
    path = image.with_suffix(".yaml")
    if not path.exists():
        return
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        key = line.partition(":")[0].strip()
        if key in values and values[key]:
            out.append(f"{key}:{' ' * max(1, 7 - len(key))}{values[key]}")
        else:
            out.append(line)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
