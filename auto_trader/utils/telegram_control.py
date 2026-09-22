"""텔레그램으로 자동매매를 조회·정지한다 (폰에서 쓰는 리모컨).

매매는 PC 가 계속 돌리고, 폰은 상황을 보고 필요할 때 멈추는 역할만 한다.

**보안**: `TELEGRAM_CHAT_ID` 에 등록된 채팅에서 온 메시지만 받는다. 다른 사람이
봇 이름을 알아내 말을 걸어도 무시하고, 계좌·키 같은 값은 어떤 명령으로도
내보내지 않는다. 주문을 새로 내는 명령도 두지 않았다 — 폰으로 할 수 있는 건
'보기' 와 '멈추기' 뿐이다(재개는 이미 멈춰 둔 것을 되돌리는 것이라 허용한다).
"""

from __future__ import annotations

import threading
from typing import Any, Callable

import requests

from utils.logger import get_logger

logger = get_logger("telegram_control")

API = "https://api.telegram.org/bot{token}/{method}"
POLL_TIMEOUT_SEC = 30       # 롱폴링 — 메시지가 없으면 이만큼 매달려 있는다
HTTP_TIMEOUT_SEC = 45       # 롱폴링보다 넉넉해야 한다
ERROR_BACKOFF_SEC = 15      # 네트워크가 끊겼을 때 재시도 간격

HELP = """사용할 수 있는 명령:

/상태 — 지금 잘 돌고 있는지 한눈에
      모드·당일 손익·평가자산·오늘 주문·AI 비용·다음 사이클
/보유 — 보유 종목, 평단→현재, 손절·익절까지 남은 거리
/판단 — 최근 AI 판단과 그 결과 ("왜 안 샀지" 에 대한 답)
/주문 — 최근 주문. 거부됐다면 거래소가 뭐라고 했는지까지
/왜 — 매수가 어느 관문에서 막혔는지 (관문별 건수)
/오늘 — 당일 매매 요약과 리스크 규칙이 막은 것
/정지 — 긴급 정지 (새 사이클을 멈춥니다)
/재개 — 정지 해제
/도움말 — 이 안내

※ 폰으로는 주문을 새로 낼 수 없습니다. 보기와 멈추기만 됩니다.
※ 손절·익절은 정지 중에도 계속 동작합니다."""


class TelegramControl:
    """등록된 채팅에서 온 명령만 처리하는 롱폴링 루프."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        handlers: dict[str, Callable[[], str]],
        *,
        session: Any | None = None,
        poll_timeout: int = POLL_TIMEOUT_SEC,
    ) -> None:
        self.token = token
        self.chat_id = str(chat_id)
        self.handlers = handlers
        self.session = session or requests
        self.poll_timeout = poll_timeout
        self._offset: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- 네트워크 ---------------------------------------------------------- #

    def _call(self, method: str, **params) -> dict | None:
        try:
            response = self.session.post(
                API.format(token=self.token, method=method),
                json=params, timeout=HTTP_TIMEOUT_SEC,
            )
            data = response.json()
        except Exception as exc:  # 네트워크가 끊겨도 매매는 계속돼야 한다
            logger.debug("텔레그램 %s 실패: %s", method, exc)
            return None
        return data if data.get("ok") else None

    def reply(self, text: str) -> None:
        self._call("sendMessage", chat_id=self.chat_id, text=text,
                   disable_web_page_preview=True)

    # -- 명령 처리 --------------------------------------------------------- #

    @staticmethod
    def _command_of(text: str) -> str:
        """'/상태@내봇 추가인자' → '/상태'."""
        first = (text or "").strip().split()
        if not first or not first[0].startswith("/"):
            return ""
        return first[0].split("@", 1)[0]

    def handle(self, update: dict) -> str | None:
        """업데이트 하나를 처리하고 보낸 답을 돌려준다(테스트용)."""
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}

        # 등록된 채팅이 아니면 조용히 버린다. 답장조차 하지 않는다.
        if str(chat.get("id")) != self.chat_id:
            logger.warning("등록되지 않은 채팅의 메시지를 무시했습니다: %s", chat.get("id"))
            return None

        command = self._command_of(message.get("text", ""))
        if not command:
            return None

        handler = self.handlers.get(command)
        if handler is None:
            reply = f"모르는 명령입니다: {command}\n\n{HELP}"
        else:
            try:
                reply = handler()
            except Exception as exc:  # 명령 하나가 죽어도 루프는 산다
                logger.exception("명령 처리 실패: %s", command)
                reply = f"명령을 처리하지 못했습니다: {exc}"

        self.reply(reply)
        return reply

    # -- 루프 -------------------------------------------------------------- #

    def poll_once(self) -> int:
        """대기 중인 업데이트를 한 번 가져와 처리한다. 처리한 개수."""
        data = self._call("getUpdates", offset=self._offset, timeout=self.poll_timeout)
        if not data:
            return 0
        handled = 0
        for update in data.get("result") or []:
            self._offset = update.get("update_id", 0) + 1
            self.handle(update)
            handled += 1
        return handled

    def _run(self) -> None:
        logger.info("텔레그램 원격 조종 대기 시작")
        # 밀려 있던 옛 명령은 버린다 — 재기동하자마자 며칠 전 /정지 가 먹으면 곤란하다.
        pending = self._call("getUpdates", offset=-1, timeout=0)
        for update in (pending or {}).get("result") or []:
            self._offset = update.get("update_id", 0) + 1

        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:  # 어떤 이유로든 루프가 끊기면 안 된다
                logger.exception("텔레그램 폴링 오류 — 잠시 뒤 재시도")
                self._stop.wait(ERROR_BACKOFF_SEC)

    def start(self) -> threading.Thread:
        self._thread = threading.Thread(target=self._run, name="telegram-control", daemon=True)
        self._thread.start()
        return self._thread

    def stop(self) -> None:
        self._stop.set()
