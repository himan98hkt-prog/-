#!/usr/bin/env python3
"""계좌에 돈이 있는지 지금 바로 확인한다.

대시보드의 '평가 자산' 은 사이클이 한 번 돌아야 채워진다. 장이 닫힌 뒤에
띄웠다면 다음 날 09:05 까지 빈 화면을 보게 되는데, 그 사이에 계좌가
정말 비어 있는 건지 프로그램이 아직 안 읽은 건지 구분할 방법이 없었다.

이 스크립트는 AI 도 스케줄러도 거치지 않고 KIS 잔고 하나만 조회한다.
주문은 절대 내지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.loader import ConfigError, load  # noqa: E402
from trading.kis_api import KisApi, KisApiError  # noqa: E402
from trading.kis_auth import KisAuthError, TokenManager  # noqa: E402

LINE = "-" * 62


def _won(amount: float) -> str:
    return f"{amount:,.0f}원"


def main() -> int:
    try:
        settings = load()
    except ConfigError as exc:
        print(f"[설정 오류]\n{exc}")
        return 1

    env = settings.env
    mode = "실전 (REAL — 실제 자금)" if env.is_real else "모의투자 (VTS)"

    print(LINE)
    print("  계좌 조회")
    print(LINE)
    print(f"  거래 환경 : {mode}")
    print(f"  서버      : {env.base_url}")
    print(f"  계좌번호  : {env.kis_account_no}-{env.kis_account_product_cd}")
    print()

    auth = TokenManager(env, settings.paths["token"])
    try:
        api = KisApi(env, auth)
        balance = api.get_balance()
    except (KisApiError, KisAuthError) as exc:
        print(f"[X] 잔고를 읽지 못했습니다: {exc}")
        print()
        print("  · 계좌번호가 이 거래 환경의 것인지 확인하세요.")
        print("    모의투자 계좌번호는 실전 계좌번호와 다릅니다.")
        return 1

    print(f"  예수금        : {_won(balance.deposit)}")
    print(f"  주문가능 현금 : {_won(balance.orderable_cash)}")
    print(f"  주식 평가금액 : {_won(balance.total_eval_amount)}")
    print(f"  순자산        : {_won(balance.net_asset)}")
    print()

    if balance.holdings:
        print(f"  보유 종목 {len(balance.holdings)}개")
        for holding in balance.holdings:
            print(f"    · {holding.name}({holding.code}) {holding.qty:,}주 "
                  f"{holding.pnl_pct:+.2f}%  평가 {_won(holding.eval_amount)}")
    else:
        print("  보유 종목 없음")
    print()

    if balance.deposit <= 0 and balance.total_eval_amount <= 0:
        print(LINE)
        print("  [!] 계좌가 비어 있습니다. 돈이 없으면 매수할 수 없습니다.")
        print(LINE)
        if env.is_real:
            print("  실전 계좌입니다 — 증권사 앱에서 입금하세요.")
        else:
            print("  모의투자는 앱키 발급과 별개로 '모의투자 참가신청' 을 해야")
            print("  초기 자금이 들어옵니다. 신청하지 않았거나 참가 기간이")
            print("  끝나면 잔고가 0 으로 나옵니다.")
            print()
            print("  1) 한국투자증권 홈페이지 → 모의투자 → 참가신청")
            print("  2) 신청하면 받은 '모의투자 전용 계좌번호' 를 확인")
            print("  3) 위에 찍힌 계좌번호와 다르면 대시보드 설정에서 바꾸세요")
        return 2

    print("  [OK] 계좌에 자금이 있습니다. 다음 사이클부터 매매 대상이 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
