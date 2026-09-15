"""Offline regression tests for broker ambiguity and recovery; no live credentials."""
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import Mock

import pytest

from logic.decision_maker import FinalDecision
from logic.portfolio import Portfolio
from tests.test_order_executor import make_executor, StubApi, SNAPSHOT, state, position
from trading.kis_api import Balance, KisApiError, RetryableKisError, OrderStatus
from utils.db import connect
from utils.runtime import StopFlag, stop_flag_path

BUY = FinalDecision(action='STRONG_BUY', weight_pct=20)
SELL = FinalDecision(action='SELL_ALL', sell_ratio=1)


def row(portfolio):
    conn = connect(portfolio.db_path)
    try:
        return dict(conn.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 1').fetchone())
    finally:
        conn.close()


def test_broker_id_durable_before_fill_poll(make_executor, monkeypatch):
    executor, api, portfolio = make_executor(dry_run=False)
    def poll(*args):
        assert row(portfolio)['order_no'] == 'ODNO1'
        assert row(portfolio)['status'] == 'PENDING'
        raise RuntimeError('simulated process interruption')
    monkeypatch.setattr(portfolio, 'wait_for_fill', poll)
    with pytest.raises(RuntimeError):
        executor.execute(BUY, SNAPSHOT, state())
    recovered = Portfolio(executor.settings, api, portfolio.db_path)
    assert recovered.has_open_orders()
    recovered.reconcile_open_orders()
    assert row(recovered)['status'] == 'FILLED'
    assert not recovered.has_open_orders()


@pytest.mark.parametrize('error', [RetryableKisError('timeout'), KisApiError('invalid JSON'), KisApiError('500', http_status=500)])
def test_transport_failure_blocks_resubmission_across_restart(make_executor, error):
    executor, api, portfolio = make_executor(dry_run=False, api=StubApi(error=error))
    first = executor.execute(BUY, SNAPSHOT, state())
    assert first.status == 'AMBIGUOUS' and first.qty == 0 and not first.ordered
    recovered = Portfolio(executor.settings, api, portfolio.db_path)
    assert recovered.has_open_orders()
    second = executor.execute(BUY, SNAPSHOT, state())
    assert second.status == 'SKIPPED' and len(api.orders) == 1
    assert row(portfolio)['status'] == 'AMBIGUOUS'


@pytest.mark.parametrize('side', [BUY, SELL])
def test_zero_fill_never_changes_cash_or_holdings(make_executor, side):
    executor, _, portfolio = make_executor(dry_run=False, api=StubApi(fill_qty=0))
    holdings = state([position()]) if side.is_sell else state()
    before = (holdings.cash, holdings.position_count, holdings.total_invested)
    result = executor.execute(side, SNAPSHOT, holdings)
    assert result.ordered and result.qty == 0 and result.status == 'PENDING'
    holdings.apply_execution('005930', 'test', result.side, result.qty, result.price)
    assert (holdings.cash, holdings.position_count, holdings.total_invested) == before
    assert portfolio.has_open_orders()


def test_partial_sell_does_not_release_unfilled_proceeds(make_executor):
    executor, _, _ = make_executor(dry_run=False, api=StubApi(fill_qty=4))
    holdings = state([position(qty=10)])
    cash = holdings.cash
    result = executor.execute(SELL, SNAPSHOT, holdings)
    holdings.apply_execution('005930', 'test', result.side, result.qty, result.price)
    assert holdings.get('005930').qty == 6
    assert holdings.cash == cash + 4 * 71300
    assert executor.execute(BUY, {**SNAPSHOT, 'code': '000660'}, holdings).status == 'SKIPPED'


def test_buying_power_query_caps_quantity(make_executor, monkeypatch):
    executor, api, _ = make_executor(dry_run=False)
    monkeypatch.setattr(api, 'get_orderable_cash', lambda *args: 150_000)
    executor.execute(BUY, SNAPSHOT, state())
    assert api.orders[0]['qty'] == 2


def test_buying_power_failure_never_submits(make_executor, monkeypatch):
    executor, api, _ = make_executor(dry_run=False)
    monkeypatch.setattr(api, 'get_orderable_cash', Mock(side_effect=KisApiError('offline')))
    with pytest.raises(KisApiError):
        executor.execute(BUY, SNAPSHOT, state())
    assert api.orders == []


@pytest.mark.parametrize('side', [BUY, SELL])
def test_stop_blocks_even_forced_exit(make_executor, side):
    executor, api, _ = make_executor(dry_run=False)
    StopFlag(stop_flag_path(executor.settings.paths['data'])).set('stop')
    assert executor.execute(side, SNAPSHOT, state([position()])).status == 'SKIPPED'
    assert not api.orders


def test_stop_arriving_during_buying_power_check_blocks_submission(make_executor, monkeypatch):
    executor, api, portfolio = make_executor(dry_run=False)
    def lookup(*args):
        StopFlag(stop_flag_path(executor.settings.paths['data'])).set('stop')
        return 5_000_000
    monkeypatch.setattr(api, 'get_orderable_cash', lookup)
    assert executor.execute(BUY, SNAPSHOT, state()).status == 'SKIPPED'
    assert not api.orders and not portfolio.has_open_orders()


def test_market_closed_blocks_order(make_executor, monkeypatch):
    executor, api, _ = make_executor(dry_run=False)
    monkeypatch.setattr('trading.order_executor.is_market_open', lambda: False)
    assert executor.execute(SELL, SNAPSHOT, state([position()])).status == 'SKIPPED'
    assert not api.orders


def test_live_mode_is_locked_by_default(make_executor):
    executor, api, _ = make_executor(dry_run=False)
    object.__setattr__(executor.settings.env, 'kis_env', 'REAL')
    assert '실전 주문 잠금' in executor.execute(SELL, SNAPSHOT, state([position()])).reason
    assert not api.orders


def test_database_refuses_different_account(make_executor):
    executor, api, portfolio = make_executor()
    settings = replace(executor.settings, env=replace(executor.settings.env, kis_account_no='12345678'))
    with pytest.raises(ValueError, match='다른 계좌'):
        Portfolio(settings, api, portfolio.db_path)


def test_daily_pnl_uses_net_assets_not_buying_power(make_executor, monkeypatch):
    executor, api, portfolio = make_executor(dry_run=False)
    balances = iter([Balance(orderable_cash=5_000_000, net_asset=5_000_000),
                     Balance(orderable_cash=0, net_asset=4_900_000)])
    monkeypatch.setattr(api, 'get_balance', lambda: next(balances))
    now = datetime(2026, 9, 8, 10, tzinfo=ZoneInfo('Asia/Seoul'))
    assert portfolio.sync(now=now).daily_pnl_pct == 0
    assert portfolio.sync(now=now).daily_pnl_pct == -2


def test_missing_net_assets_blocks_non_dry_sync(make_executor, monkeypatch):
    _, api, portfolio = make_executor(dry_run=False)
    monkeypatch.setattr(api, 'get_balance', lambda: Balance(orderable_cash=5_000_000))
    with pytest.raises(ValueError, match='순자산'):
        portfolio.sync()


def test_daily_loss_halt_survives_recovery_and_restart(make_executor, monkeypatch):
    executor, api, portfolio = make_executor(dry_run=False)
    balances = iter([Balance(net_asset=5_000_000), Balance(net_asset=4_800_000), Balance(net_asset=5_000_000)])
    monkeypatch.setattr(api, 'get_balance', lambda: next(balances))
    now = datetime(2026, 9, 8, 10, tzinfo=ZoneInfo('Asia/Seoul'))
    portfolio.sync(now=now)
    assert portfolio.sync(now=now).daily_buy_halted
    recovered = Portfolio(executor.settings, api, portfolio.db_path)
    holdings = recovered.sync(now=now)
    assert holdings.daily_buy_halted and holdings.daily_pnl_pct == 0
    assert not executor.risk.check_buy('005930', 200_000, holdings, now=now)


def test_reconcile_updates_increasing_partial_fill_same_status(make_executor, monkeypatch):
    executor, api, portfolio = make_executor(dry_run=False, api=StubApi(fill_qty=2))
    executor.execute(BUY, SNAPSHOT, state())
    api.fill_qty = 4
    portfolio.reconcile_open_orders()
    assert row(portfolio)['status'] == 'PARTIAL' and row(portfolio)['filled_qty'] == 4


def test_cancel_fill_race_records_final_fill(make_executor, monkeypatch):
    executor, api, portfolio = make_executor(dry_run=False, order_type='limit', api=StubApi(fill_qty=0))
    def cancel(*args):
        api.fill_qty = api.orders[-1]['qty']
        return True
    monkeypatch.setattr(api, 'cancel_order', cancel)
    result = executor.execute(BUY, SNAPSHOT, state())
    assert result.status == 'FILLED' and result.qty == api.orders[-1]['qty']
    assert not portfolio.has_open_orders()


def test_confirmed_partial_cancel_retains_executed_quantity(make_executor, monkeypatch):
    executor, api, portfolio = make_executor(dry_run=False, order_type='limit', api=StubApi(fill_qty=3))
    def cancel(*args):
        monkeypatch.setattr(api, 'get_order_status', lambda *a, **kw: OrderStatus(
            'ODNO1', '005930', 'test', 'BUY', api.orders[-1]['qty'], 3, 0, 71300, 213900, '취소'))
        return True
    monkeypatch.setattr(api, 'cancel_order', cancel)
    result = executor.execute(BUY, SNAPSHOT, state())
    assert result.status == 'CANCELED' and result.qty == 3
    assert row(portfolio)['filled_qty'] == 3 and not portfolio.has_open_orders()


def test_transaction_refuses_second_unresolved_submission(make_executor):
    _, _, portfolio = make_executor(dry_run=False)
    args = dict(cycle_id='x', code='005930', name='test', side='BUY', order_type='market',
                qty=1, price=71300, status='SUBMITTING', dry_run=False)
    portfolio.record_order(**args)
    with pytest.raises(ValueError, match='동시 주문 차단'):
        portfolio.record_order(**args)


@pytest.mark.parametrize('price', [float('nan'), float('inf'), -1, 0])
def test_invalid_quote_never_submits(make_executor, price):
    executor, api, _ = make_executor(dry_run=False)
    assert executor.execute(BUY, {**SNAPSHOT, 'price': {'current': price}}, state()).status == 'SKIPPED'
    assert not api.orders


@pytest.mark.parametrize('changes', [
    {'code': '000660'}, {'order_no': 'OTHER'}, {'filled_price': float('nan')},
    {'filled_price': 0}, {'filled_qty': 999}, {'order_qty': 0},
])
def test_malformed_fill_remains_unresolved(make_executor, monkeypatch, changes):
    executor, api, portfolio = make_executor(dry_run=False)
    lookup = api.get_order_status
    monkeypatch.setattr(api, 'get_order_status', lambda *a, **kw: replace(lookup(*a, **kw), **changes))
    result = executor.execute(BUY, SNAPSHOT, state())
    assert result.status == 'UNKNOWN' and result.qty == 0
    assert portfolio.has_open_orders()
