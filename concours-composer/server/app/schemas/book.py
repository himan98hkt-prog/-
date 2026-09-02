"""곡집 — 여러 곡을 한 권으로 묶는 단위.

낱장 악보 다섯 장과 표지가 붙은 한 권은 다른 물건이다. 학원 원장이 사는 것은
뒤쪽이고, 책장에 꽂는 것도 뒤쪽이다. 그래서 묶음을 **저장되는 것**으로 둔다 —
한 번 만들고 마는 목록이 아니라, 이름을 고치고 표지를 바꾸고 곡을 더 넣을 수 있는
물건이어야 한다.

곡 자체는 여기에 담지 않는다. 곡은 보관함에 있고 여기에는 **번호만** 둔다.
한 곡이 여러 곡집에 들어갈 수 있고(초급 모음과 행진곡 모음에 같은 곡), 곡을
고치면 그 곡이 든 모든 곡집에 반영되어야 하기 때문이다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class Songbook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str = Field(min_length=1, max_length=80)
    subtitle: str = Field(default="", max_length=120)
    cover_style: str = "classic"
    # 곡 번호. **순서가 곧 책의 차례다** — 목록이 아니라 차례이므로 순서를 지킨다.
    composition_ids: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=2000)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def with_pieces(self, ids: list[str]) -> Songbook:
        return self.model_copy(update={"composition_ids": ids})
