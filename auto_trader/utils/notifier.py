"""텔레그램/디스코드 알림.

**알림 실패는 매매를 막지 않는다** — 로그만 남기고 조용히 넘어간다.
"""

from __future__ import annotations

import time
import traceback
from datetime import datetime
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests

from config.loader import EnvConfig
from utils.logger import get_logger, register_secret

KST = ZoneInfo("Asia/Seoul")
logger = get_logger("notifier")

TELEGRAM_LIMIT = 4096  # 텔레그램 메시지 길이 제한
ERROR_COOLDOWN_SEC = 600  # 같은 오류 재알림 억제 간격
DISCORD_LIMIT = 2000
HTTP_TIMEOUT = 10


def split_message(text: str, limit: int) -> list[str]:
    """길이 제한에 맞춰 자른다. 줄 단위를 최대한 보존한다."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:  # 한 줄이 통째로 제한을 넘는 경우
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


class Notifier:
    def __init__(self, env: EnvConfig, session: Any | None = None,
                 error_cooldown_sec: int = ERROR_COOLDOWN_SEC) -> None:
        self.env = env
        self.session = session or requests
        self.error_cooldown_sec = error_cooldown_sec
        # 같은 오류가 매 종목·매 사이클 반복될 때 알림이 폭주하지 않도록 억제한다.
        self._error_seen: dict[str, float] = {}
        register_secret(env.telegram_bot_token, env.discord_webhook_url)

    # -- 전송 -------------------------------------------------------------- #

    def send(self, text: str) -> bool:
        """분할 전송. 하나라도 실패하면 False (예외는 던지지 않는다)."""
        if not text.strip():
            return True
        limit = TELEGRAM_LIMIT if self.env.notifier == "telegram" else DISCORD_LIMIT
        sender = self._send_telegram if self.env.notifier == "telegram" else self._send_discord
        return all([sender(chunk) for chunk in split_message(text, limit)])

    def _send_telegram(self, text: str) -> bool:
        if not (self.env.telegram_bot_token and self.env.telegram_chat_id):
            logger.warning("텔레그램 설정이 없어 알림을 건너뜁니다")
            return False
        url = f"https://api.telegram.org/bot{self.env.telegram_bot_token}/sendMessage"
        return self._post(url, {"chat_id": self.env.telegram_chat_id, "text": text,
                                "disable_web_page_preview": True})

    def _send_discord(self, text: str) -> bool:
        if not self.env.discord_webhook_url:
            logger.warning("디스코드 웹훅이 없어 알림을 건너뜁니다")
            return False
        return self._post(self.env.discord_webhook_url, {"content": text})

    def _post(self, url: str, payload: dict[str, Any]) -> bool:
        try:
            response = self.session.post(url, json=payload, timeout=HTTP_TIMEOUT)
        except Exception as exc:  # 알림 실패가 매매를 막아선 안 된다
            logger.warning("알림 전송 실패(%s) — 매매는 계속합니다", exc)
            return False
        if response.status_code >= 300:
            logger.warning("알림 전송 실패 (HTTP %s) — 매매는 계속합니다", response.status_code)
            return False
        return True

    # -- 메시지 포맷 ------------------------------------------------------- #

    def send_startup(self, universe_size: int) -> bool:
        mode = "실전(REAL)" if self.env.is_real else "모의(VTS)"
        lines = [
            "🚀 자동매매 기동 완료",
            f"• 모드: {mode} / DRY_RUN: {'on' if self.env.dry_run else 'off'}",
            f"• 유니버스: {universe_size}종목",
            f"• AI: {self.env.claude_model} + {self.env.gemini_model}",
        ]
        if self.env.is_real:
            lines.insert(0, "⚠️ 실전 모드 시작 — 실제 자금이 사용됩니다 ⚠️")
        if not self.env.dry_run:
            lines.append("• 실주문이 전송됩니다.")
        return self.send("\n".join(lines))

    def send_trade(self, order: dict[str, Any]) -> bool:
        icon = "🟢" if order.get("side") == "BUY" else "🔴"
        prefix = "[DRY_RUN] " if order.get("dry_run") else ""
        label = "매수" if order.get("side") == "BUY" else "매도"
        price = order.get("filled_price") or order.get("price") or 0
        lines = [
            f"{icon} {prefix}{label} {order.get('name', '')}({order.get('code', '')})",
            f"• {order.get('qty', 0):,}주 @ {price:,.0f}원 (약 {order.get('qty', 0) * price:,.0f}원)",
            f"• 상태: {order.get('status', '-')}",
        ]
        if order.get("reason"):
            lines.append(f"• 사유: {order['reason']}")
        return self.send("\n".join(lines))

    def send_cycle_summary(self, cycle_label: str, results: Iterable[dict[str, Any]]) -> bool:
        rows = list(results)
        order_count = sum(1 for row in rows if row.get("ordered"))
        lines = [f"📊 [{cycle_label} 사이클] 대상 {len(rows)}종목 / 주문 {order_count}건"]
        for row in rows:
            lines.append(f"• {self._format_row(row)}")
        return self.send("\n".join(lines))

    @staticmethod
    def _format_row(row: dict[str, Any]) -> str:
        name = f"{row.get('name') or row.get('code', '?')}"
        if row.get("error"):
            return f"(오류) {name}: {row['error']}"
        if row.get("risk_blocked"):
            return f"(리스크 거부) {name}: {row.get('risk_reason', '')}"

        agents = row.get("agents", "")
        final = row.get("final_action", "HOLD")
        text = f"{name}: {agents} → {final}" if agents else f"{name}: {final}"
        if row.get("weight_pct"):
            text += f" {row['weight_pct']}%"
        if row.get("ordered"):
            side = "매수" if row.get("side") == "BUY" else "매도"
            text += f" → {side} {row.get('qty', 0):,}주 @{row.get('price', 0):,.0f}"
        return text

    def send_error(self, exc: BaseException, context: str = "", *, dedupe: bool = True) -> bool:
        """오류 알림. 같은 유형이 쿨다운 안에 반복되면 보내지 않는다."""
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        if dedupe and self._suppressed(f"{type(exc).__name__}:{detail}"):
            logger.debug("동일 오류 알림 억제(%ds): %s", self.error_cooldown_sec, detail[:80])
            return True
        lines = ["⚠️ 오류 발생"]
        if context:
            lines.append(f"• 위치: {context}")
        lines.append(f"• 내용: {detail}")
        return self.send("\n".join(lines))

    def _suppressed(self, key: str) -> bool:
        """쿨다운 안에 이미 보낸 적 있으면 True (그리고 시각을 갱신하지 않는다)."""
        now = time.monotonic()
        last = self._error_seen.get(key)
        if last is not None and now - last < self.error_cooldown_sec:
            return True
        self._error_seen[key] = now
        # 오래된 항목 정리
        self._error_seen = {
            k: t for k, t in self._error_seen.items() if now - t < self.error_cooldown_sec * 2
        }
        return False

    def send_alert(self, title: str, lines: list[str], *, key: str = "") -> bool:
        """상태 변화 알림(손실 한도 도달 등). key 를 주면 쿨다운이 적용된다."""
        if key and self._suppressed(f"alert:{key}"):
            return True
        return self.send("\n".join([title, *(f"• {line}" for line in lines)]))

    def send_fatal(self, message: str) -> bool:
        return self.send(f"🛑 치명적 오류 — 스케줄러를 중단합니다\n• {message}")

    def send_daily_report(self, report: dict[str, Any], *, now: datetime | None = None) -> bool:
        moment = now or datetime.now(KST)
        lines = [
            f"📅 {moment:%Y-%m-%d} 일간 리포트",
            f"• 당일 손익: {report.get('total_pnl_pct', 0):+.2f}% "
            f"({report.get('end_equity', 0):,.0f}원)",
            f"• 주문: 매수 {report.get('buy_count', 0)}건 / 매도 {report.get('sell_count', 0)}건",
            f"• 보유 종목: {report.get('position_count', 0)}개",
        ]
        for position in report.get("positions", []):
            lines.append(
                f"  · {position.get('name')}({position.get('code')}) "
                f"{position.get('qty', 0):,}주 {position.get('pnl_pct', 0):+.2f}%"
            )
        return self.send("\n".join(lines))
