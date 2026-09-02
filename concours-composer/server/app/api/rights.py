"""작곡가 신원·저작권 API.

곡을 만드는 것과 곡으로 돈을 버는 것은 다른 일이다. 후자는 **이름과 권리**가 정리돼
있어야 시작된다. 이 라우터가 그 둘을 맡는다.

- `GET/PUT /api/composer` — 예명·실명·연락처. 실명은 등록 서류에만 쓰인다.
- `GET/PUT /api/compositions/{id}/rights` — 이 곡이 창작인지 편곡인지, 편곡이면 원곡은
  어떤 상태인지.
- `GET /api/compositions/{id}/registration` — 저작권 등록 신청서 초안. 권리가 정리되지
  않았으면 초안 대신 **무엇이 막고 있는지**를 먼저 낸다.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import Store, get_store
from app.identity import set_alias
from app.schemas.rights import (
    SOURCE_STATUS_KO,
    ComposerIdentity,
    RegistrationDraft,
    WorkRights,
)

router = APIRouter(prefix="/api", tags=["rights"])

COMPOSER_KEY = "composer_identity"


def get_composer(store: Store) -> ComposerIdentity:
    raw = store.rights.get(COMPOSER_KEY)
    return ComposerIdentity.model_validate(raw) if raw else ComposerIdentity()


def get_rights(store: Store, composition_id: str) -> WorkRights:
    raw = store.rights.get(f"work:{composition_id}")
    return WorkRights.model_validate(raw) if raw else WorkRights()


@router.get("/composer", response_model=ComposerIdentity)
def read_composer(store: Store = Depends(get_store)) -> ComposerIdentity:
    return get_composer(store)


@router.put("/composer", response_model=ComposerIdentity)
def write_composer(body: ComposerIdentity, store: Store = Depends(get_store)) -> ComposerIdentity:
    """예명과 실명을 저장한다. 실명은 이 PC 를 떠나지 않는다."""
    store.rights[COMPOSER_KEY] = body.model_dump()
    store.save()
    set_alias(body.alias)   # 다음에 만드는 악보부터 이 이름이 찍힌다
    return body


@router.get("/compositions/{composition_id}/rights", response_model=WorkRights)
def read_rights(composition_id: str, store: Store = Depends(get_store)) -> WorkRights:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    return get_rights(store, composition_id)


@router.put("/compositions/{composition_id}/rights", response_model=WorkRights)
def write_rights(composition_id: str, body: WorkRights, store: Store = Depends(get_store)) -> WorkRights:
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")
    store.rights[f"work:{composition_id}"] = body.model_dump()
    store.save()
    return body


def _title(store: Store, composition_id: str) -> str:
    res = store.compositions[composition_id]
    return res.plan.title_candidates[0] if res.plan.title_candidates else composition_id


@router.get("/compositions/{composition_id}/registration", response_model=RegistrationDraft)
def registration_draft(composition_id: str, store: Store = Depends(get_store)) -> RegistrationDraft:
    """저작권 등록 신청서 초안.

    한국저작권위원회 등록 신청에 들어가는 항목을 채워 둔 문서다. 그대로 제출하는
    서식은 아니고 **옮겨 적을 내용**이다 — 서식은 위원회 쪽이 바뀌므로 여기서 흉내
    내지 않는다.
    """
    if composition_id not in store.compositions:
        raise HTTPException(404, f"곡을 찾을 수 없다: {composition_id}")

    res = store.compositions[composition_id]
    who = get_composer(store)
    rights = get_rights(store, composition_id)
    ok, blockers = rights.clearance()
    missing = who.missing_for_registration()
    title = _title(store, composition_id)

    lines = [
        f"# 저작권 등록 신청 초안 — {title}",
        "",
        f"작성일 {date.today().isoformat()} · 곡 번호 `{composition_id}`",
        "",
        "## 1. 저작자",
        "",
        f"- 성명(실명): **{who.legal_name or '(비어 있음)'}**",
        f"- 이명·예명: **{who.alias}** — 악보·음원·공표물에는 이 이름만 씁니다",
        f"- 생년월일: {who.birth_date or '(비어 있음)'}",
        f"- 국적: {who.nationality}",
        f"- 주소: {who.address or '(비어 있음)'}",
        f"- 연락처: {who.email or '(이메일 없음)'} / {who.phone or '(전화 없음)'}",
        "",
        "## 2. 저작물",
        "",
        f"- 제호: {title}",
        "- 종별: 음악저작물(악곡)",
        f"- 형태: 조성 {res.plan.key} · 박자 {res.plan.meter} · ♩={res.plan.tempo} · "
        f"{len(res.measures)}마디 · 피아노 독주",
        f"- 창작 구분: {'창작물' if rights.work_type == 'original' else '2차적저작물(편곡)'}",
        f"- 공표일: {rights.first_published or '(미공표)'}",
    ]

    if rights.work_type == "arrangement":
        lines += [
            "",
            "## 3. 원저작물 (2차적저작물이므로 필수)",
            "",
            f"- 원곡 제목: {rights.original_title or '(비어 있음)'}",
            f"- 원곡 작곡가: {rights.original_composer or '(비어 있음)'}",
            f"- 원곡 권리 상태: {SOURCE_STATUS_KO.get(rights.original_status, rights.original_status)}",
            f"- 이용허락 근거: {rights.license_note or '(없음)'}",
        ]

    if rights.note:
        lines += ["", "## 비고", "", rights.note]

    lines += [
        "",
        "## 첨부할 것",
        "",
        "- 악보 파일 (MusicXML 또는 PDF)",
        "- 음원 파일 (MP3)",
        "- 신분 확인 서류",
    ]
    if rights.work_type == "arrangement":
        lines.append("- 원곡의 권리 상태를 보여 주는 자료(만료 근거 또는 이용허락 증빙)")

    checklist = [
        "악보를 MusicXML 로 내려받아 두었습니까",
        "음원(MP3)을 내려받아 두었습니까",
        "예명 accelssam 과 실명이 모두 정확합니까",
    ]
    if rights.work_type == "arrangement":
        checklist.append("원곡의 보호 기간이 끝났거나 이용허락을 받았음을 증빙할 수 있습니까")

    return RegistrationDraft(
        composition_id=composition_id,
        title=title,
        ready=ok and not missing,
        blockers=blockers,
        missing_fields=missing,
        markdown="\n".join(lines),
        checklist=checklist,
    )


@router.get("/compositions/{composition_id}/registration.md")
def registration_markdown(composition_id: str, store: Store = Depends(get_store)) -> Response:
    """초안을 파일로 받는다 — 등록 신청할 때 옆에 띄워 두고 옮겨 적으라고."""
    draft = registration_draft(composition_id, store)
    return Response(
        content=draft.markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{composition_id}-registration.md"'},
    )
