"""곡 하나를 **탐색기에서 보이는 폴더로** 풀어 놓는다.

원장님:

    "클로드에 만들고 다운받은 곡에 대한 전체 내용들을 저장할 수 있는
     폴더 설정도 할 수 있었으면 좋겠어."
    "실질적인 작곡 작업은 집pc로 진행할 계획이니..."

곡이 저장 파일(store.sqlite3) 안에만 있으면 **프로그램을 켜야만 보인다.** 집 PC 와
학원 PC 를 오가시려면 파일로 눈에 보이고, 복사되고, 동기화 폴더에 얹힐 수 있어야 한다.

그래서 곡 하나를 들이는 그 자리에서 폴더 하나를 만들어 전부 풀어 놓는다:

    <정하신 폴더>/<제목> (comp-0001)/
        읽어보세요.txt · 악보.musicxml · 악보.mid · 음원.wav
        곡 정보.md · 연주법 해설.md · 지도용 악보.musicxml ...

'판매 꾸러미 ZIP' 과 **같은 함수(write_piece)** 로 담는다. 갈라지면 한쪽에만 파일이
빠지고, 그것은 학원에 보낸 뒤에야 드러난다.
"""
from __future__ import annotations

import logging
import zipfile

log = logging.getLogger(__name__)


def spill_to_folder(store: object, composition_id: str) -> str:
    """곡 하나를 폴더로 풀어 놓고 그 경로를 돌려준다. 이미 있으면 덮어쓴다.

    덮어쓰는 것이 맞다 — 같은 곡을 고쳐서 다시 넣으셨을 때, 옛 파일이 남아 있으면
    어느 것이 지금 곡인지 알 수 없다.
    """
    from app.api.compositions import package_input
    from app.api.folder import chosen_dir
    from app.export.package import _safe, write_piece

    title = _safe(store.title_of(composition_id)) or composition_id  # type: ignore[attr-defined]
    folder = chosen_dir() / f"{title} ({composition_id})"
    folder.mkdir(parents=True, exist_ok=True)

    data = package_input(store, composition_id)  # type: ignore[arg-type]
    # ZIP 으로 한 번 담았다가 풀어 쓴다 — 꾸러미와 같은 목록을 쓰기 위해서다.
    tmp = folder / "_tmp.zip"
    try:
        with zipfile.ZipFile(tmp, "w") as z:
            write_piece(z, "x", data)
            for info in z.infolist():
                out = folder / info.filename.split("/", 1)[1]
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(info))
    finally:
        tmp.unlink(missing_ok=True)
    return str(folder)
