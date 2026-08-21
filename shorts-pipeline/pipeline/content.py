"""영상 1편의 콘텐츠 정보 (제목·훅·프롬프트).

시드 이미지 옆에 같은 이름의 .yaml 을 두면 그 내용이 쓰인다.

    seeds/neon_alley.png
    seeds/neon_alley.yaml
        title:  비 내리는 네온 골목을 끝없이 달리다
        hook:   이 길 끝에 뭐가 있을까
        prompt: smooth forward motion through a rain-soaked neon alley, ...

사이드카가 없으면 파일명에서 제목을 만든다. 업로드가 막히지는 않지만,
제목·설명은 조회수에 직접 영향을 주므로 채워두는 편이 좋다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# 플랫폼 상한
YOUTUBE_TITLE_MAX = 100
YOUTUBE_DESC_MAX = 5000
INSTAGRAM_CAPTION_MAX = 2200

_SIDECAR_EXT = (".yaml", ".yml", ".txt")


@dataclass
class Content:
    """업로드에 필요한 문구 묶음."""

    title: str
    hook: str = ""
    prompt: str = ""
    scene_prompts: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: Path | None = None

    @property
    def description(self) -> str:
        """설명 본문. 훅이 있으면 훅을, 없으면 제목을 쓴다."""
        return self.hook or self.title

    # ── 렌더링 ────────────────────────────────────────────────────────
    def youtube_title(self, template: str, part: int | None = None) -> str:
        title = self.title
        if part is not None and "{n}" in template:
            return _clip(template.format(title=title, n=part), YOUTUBE_TITLE_MAX)
        return _clip(template.format(title=title), YOUTUBE_TITLE_MAX)

    def youtube_description(self, template: str) -> str:
        return _clip(template.format(description=self.description, title=self.title),
                     YOUTUBE_DESC_MAX)

    def instagram_caption(self, template: str) -> str:
        return _clip(template.format(description=self.description, title=self.title),
                     INSTAGRAM_CAPTION_MAX)


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _title_from_filename(path: Path) -> str:
    """neon_alley_02.png -> Neon Alley 02. 한글 파일명은 그대로 둔다."""
    stem = re.sub(r"[_\-]+", " ", path.stem).strip()
    if re.search(r"[가-힣]", stem):
        return stem
    return stem.title()


def find_sidecar(image: Path) -> Path | None:
    for ext in _SIDECAR_EXT:
        candidate = image.with_suffix(ext)
        if candidate.exists():
            return candidate
    return None


def load_content(image: Path) -> Content:
    """시드 이미지에 딸린 콘텐츠 정보를 읽는다. 없으면 파일명으로 만든다."""
    image = Path(image)
    sidecar = find_sidecar(image)
    if sidecar is None:
        return Content(title=_title_from_filename(image))

    raw = sidecar.read_text(encoding="utf-8")
    data: dict = {}
    if sidecar.suffix in (".yaml", ".yml"):
        try:
            parsed = yaml.safe_load(raw)
            if isinstance(parsed, dict):
                data = parsed
        except yaml.YAMLError as exc:
            print(f"    ⚠ {sidecar.name} 을 읽지 못했습니다 ({exc}). 파일명을 씁니다.")
    else:
        # .txt 는 첫 줄이 제목, 둘째 줄이 훅
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if lines:
            data = {"title": lines[0]}
            if len(lines) > 1:
                data["hook"] = lines[1]

    scenes = data.get("scene_prompts") or []
    if isinstance(scenes, str):
        scenes = [scenes]

    return Content(
        title=str(data.get("title") or _title_from_filename(image)).strip(),
        hook=str(data.get("hook") or "").strip(),
        prompt=str(data.get("prompt") or "").strip(),
        scene_prompts=[str(s).strip() for s in scenes if str(s).strip()],
        tags=[str(t).strip() for t in (data.get("tags") or []) if str(t).strip()],
        source=sidecar,
    )


def write_template(image: Path) -> Path:
    """시드 옆에 채워 넣기 좋은 사이드카 뼈대를 만든다."""
    dest = image.with_suffix(".yaml")
    dest.write_text(
        "# 이 영상의 제목과 설명. 비워두면 파일명이 제목이 된다.\n"
        f"title:  {_title_from_filename(image)}\n"
        "hook:   \n"
        "\n"
        "# 영상 생성 프롬프트. 비우면 config.yaml 의 motion_prompt 를 쓴다.\n"
        "prompt: \n"
        "\n"
        "# montage 모드에서 장면별로 다른 프롬프트를 주고 싶을 때\n"
        "scene_prompts: []\n",
        encoding="utf-8",
    )
    return dest
