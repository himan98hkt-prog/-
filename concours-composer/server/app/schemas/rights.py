"""작곡가 신원과 저작권 — 예명은 밖으로, 실명은 등록에만.

곡을 팔려면 이름이 둘 필요하다.

- **예명(alias)** — 악보 표지·음원 태그·프로그램북에 나가는 이름. 여기서는 `accelssam`.
  콩쿨 심사표에도, 학원에 파는 악보에도 이것만 찍힌다.
- **실명(legal_name)** — 저작권 등록 신청서에만 쓰는 이름. 화면에도 악보에도 나가지
  않고, **프롬프트로도 절대 나가지 않는다**(tests/test_rights.py 가 지킨다).
  등록 서류를 만들 때만 꺼낸다.

편곡으로 등록할 때가 더 조심스럽다. 2차적저작물은 원곡의 권리가 정리돼 있어야
등록도 판매도 가능하다. 원곡이 보호 기간 중인데 허락이 없으면 등록은커녕 침해다.
그래서 `WorkRights` 는 원곡 상태를 반드시 적게 하고, 정리되지 않은 곡은
`clearance()` 가 막는다 — 모르고 파는 일이 없어야 한다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkType = Literal["original", "arrangement"]
SourceStatus = Literal["public_domain", "licensed", "own_work", "copyrighted", "unknown"]

SOURCE_STATUS_KO: dict[str, str] = {
    "public_domain": "보호 기간 만료(공유저작물)",
    "licensed": "원저작자 이용허락 받음",
    "own_work": "내가 쓴 곡",
    "copyrighted": "보호 기간 중 · 허락 없음",
    "unknown": "확인 안 됨",
}

# 등록도 판매도 할 수 있는 상태. 나머지는 손대면 안 된다.
CLEARED = frozenset({"public_domain", "licensed", "own_work"})


class ComposerIdentity(BaseModel):
    """한 사람의 두 이름. 실명 쪽은 등록 서류 밖으로 나가지 않는다."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(default="accelssam", min_length=1, description="악보·음원에 찍히는 예명")
    legal_name: str = Field(default="", description="저작권 등록에만 쓰는 실명")
    birth_date: str = Field(default="", description="YYYY-MM-DD. 등록 신청서 필수 항목")
    nationality: str = "대한민국"
    email: str = ""
    phone: str = ""
    address: str = Field(default="", description="등록 신청서의 주소")

    def display(self) -> str:
        """밖으로 나가는 이름. 언제나 예명이다."""
        return self.alias

    def missing_for_registration(self) -> list[str]:
        """저작권 등록 신청 전에 채워야 하는 칸."""
        need = {
            "legal_name": "실명",
            "birth_date": "생년월일",
            "address": "주소",
            "email": "이메일",
        }
        return [ko for field_name, ko in need.items() if not getattr(self, field_name).strip()]


class WorkRights(BaseModel):
    """곡 하나의 권리 상태. 편곡이면 원곡까지 적어야 한다."""

    model_config = ConfigDict(extra="forbid")

    work_type: WorkType = "original"
    original_title: str = Field(default="", description="편곡일 때 원곡 제목")
    original_composer: str = Field(default="", description="편곡일 때 원곡 작곡가")
    original_status: SourceStatus = "unknown"
    license_note: str = Field(default="", description="이용허락 근거(계약·메일·출처)")
    first_published: str = Field(default="", description="공표일 YYYY-MM-DD")
    note: str = ""

    def clearance(self) -> tuple[bool, list[str]]:
        """등록·판매해도 되는가, 안 된다면 무엇 때문인가.

        창작곡은 그냥 통과한다. 편곡은 원곡의 권리가 정리돼야만 통과한다 —
        여기서 막지 않으면 등록 반려로 끝나지 않고 침해가 된다.
        """
        if self.work_type == "original":
            return True, []

        blockers: list[str] = []
        if not self.original_title.strip():
            blockers.append("원곡 제목이 비어 있습니다")
        if not self.original_composer.strip():
            blockers.append("원곡 작곡가가 비어 있습니다")
        if self.original_status == "copyrighted":
            blockers.append(
                "원곡이 보호 기간 중인데 이용허락 근거가 없습니다 — 이대로 등록·판매하면 저작권 침해입니다"
            )
        elif self.original_status == "unknown":
            blockers.append(
                "원곡의 저작권 상태를 확인하지 않았습니다 — "
                "보호 기간이 끝났는지(작곡가 사후 70년) 먼저 확인하십시오"
            )
        elif self.original_status == "licensed" and not self.license_note.strip():
            blockers.append("이용허락을 받았다면 그 근거(계약·메일·출처)를 적어 두십시오")
        return not blockers, blockers


class RegistrationDraft(BaseModel):
    """저작권 등록 신청서 초안. 화면에 그대로 보여 주고 파일로도 받는다."""

    model_config = ConfigDict(extra="forbid")

    composition_id: str
    title: str
    ready: bool
    blockers: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    markdown: str
    checklist: list[str] = Field(default_factory=list)
