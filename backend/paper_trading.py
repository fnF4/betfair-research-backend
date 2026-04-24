"""Paper trading engine for Betfair Category-1 back/lay arbitrage.

Same public surface as the Polymarket backend: `maybe_open_position(opp_row)`,
`update_open_positions(snapshots_by_key)`, `dashboard_state()`.

NO wallets, NO real orders. Pure simulation; every position lives in SQLite.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

import config
from betfair_client import BookSnapshot


log = logging.getLogger(__name__)


def _conn() -> sqlite3.Connection:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(config.DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL;")
    return c


_REOPEN_COOLDOWN_SEC = 24 * 60 * 60


def _cash_available() -> float:
    con = _conn()
    try:
        row = con.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN status='open' THEN entry_cost ELSE 0 END),0) exposure,
                 COALESCE(SUM(CASE WHEN status='closed' THEN realized_pnl ELSE 0 END),0) realized
               FROM paper_positions"""
        ).fetchone()
        exposure = float(row["exposure"] or 0.0)
        realized = float(row["realized"] or 0.0)
        return max(0.0, config.PAPER_TOTAL_CAPITAL_USD + realized - exposure)
    finally:
        con.close()


def _already_open(legs_hash: str) -> bool:
    cutoff = time.time() - _REOPEN_COOLDOWN_SEC
    con = _conn()
    try:
        row = con.execute(
            """SELECT 1 FROM paper_positions
                WHERE legs_hash=?
                  AND (status='open'
                       OR (status='closed' AND COALESCE(closed_at, opened_at) >= ?))
                LIMIT 1""",
            (legs_hash, cutoff),
        ).fetchone()
        return row is not None
    finally:
        con.close()


def maybe_open_position(opp_row: dict[str, Any], run_id: int) -> int | None:
    """Open a paper position if the opportunity passes safety gates."""
    if opp_row.get("feasibility_class") == "ghost" and config.PAPER_ONLY_CATCHABLE:
        return None
    if float(opp_row.get("edge_net") or 0.0) < config.PAPER_MIN_EDGE_NET:
        return None

    lh = opp_row.get("legs_hash")
    if lh and _already_open(lh):
        return None

    cash = _cash_available()
    if cash <= 0:
        return None

    B = float(opp_row.get("back_odds") or 0.0)
    L = float(opp_row.get("lay_odds") or 0.0)
    if B <= 1.0 or L <= 1.0 or B < L:
        return None

    # Respect all caps when sizing
    requested = float(opp_row.get("max_back_stake") or 0.0)
    stake = min(requested, config.PAPER_PER_TRADE_USD, cash)
    if stake < config.PAPER_MIN_NOTIONAL_USD:
        return None

    lay_stake = stake * B / L
    lay_liability = lay_stake * (L - 1.0)
    entry_cost = max(stake, lay_liability)
    commission = float(opp_row.get("commission_rate") or config.BETFAIR_COMMISSION)
    edge_net = (B - L) / L * (1.0 - commission)
    expected_profit = stake * edge_net
    expected_payout = stake + expected_profit

    # Safety floor: expected profit must beat fee * safety_margin
    min_profit = max(1.0, config.SAFETY_MARGIN * commission * stake)
    if expected_profit < min_profit:
        return None

    con = _conn()
    try:
        cur = con.execute(
            """INSERT INTO paper_positions
               (legs_hash, kind,
                market_id, market_name, event_id, event_title, event_start_ts,
                selection_id, selection_name,
                feasibility_at_open, opened_at, opened_run_id,
                back_odds, back_stake, lay_odds, lay_stake, lay_liability,
                size_usd, entry_cost, entry_edge_net,
                expected_profit, expected_payout, commission_rate,
                status, mtm_value, mtm_ts)
               VALUES(?, 'cat1_crossed',
                      ?,?,?,?,?,
                      ?,?,
                      ?, ?, ?,
                      ?, ?, ?, ?, ?,
                      ?, ?, ?,
                      ?, ?, ?,
                      'open', 0.0, ?)""",
            (
                lh,
                opp_row.get("market_id"), opp_row.get("market_name"),
                opp_row.get("event_id"), opp_row.get("event_title"),
                opp_row.get("event_start_ts"),
                opp_row.get("selection_id"), opp_row.get("selection_name"),
                opp_row.get("feasibility_class"), time.time(), run_id,
                B, stake, L, lay_stake, lay_liability,
                stake, entry_cost, edge_net,
                expected_profit, expected_payout, commission,
                time.time(),
            ),
        )
        con.commit()
        pid = cur.lastrowid
        log.info(
            "PAPER OPEN pos=%d stake=$%.0f B=%.3f L=%.3f edge=%.3f%% sel=%s",
            pid, stake, B, L, edge_net * 100,
            (opp_row.get("selection_name") or "?")[:40],
        )
        # Mark source opportunity as opened for audit
        try:
            con2 = _conn()
            try:
                con2.execute(
                    "UPDATE opportunities SET opened=1 WHERE legs_hash=? AND opened=0",
                    (lh,),
                )
                con2.commit()
            finally:
                con2.close()
        except sqlite3.OperationalError:
            pass
        return pid
    finally:
        con.close()


def _mtm_for_row(row: sqlite3.Row, snap: BookSnapshot | None) -> float:
    """Mark-to-market by hedging out at the current book."""
    if snap is None or snap.best_back_odds is None or snap.best_lay_odds is None:
        return 0.0
    B_open = float(row["back_odds"])
    L_open = float(row["lay_odds"])
    back_stake = float(row["back_stake"])
    lay_stake = float(row["lay_stake"])
    B_now = float(snap.best_back_odds)
    L_now = float(snap.best_lay_odds)
    try:
        pnl = back_stake * (B_open - L_now) / L_now \
            - lay_stake * (B_now - L_open) / L_open
    except ZeroDivisionError:
        return 0.0
    return pnl * (1.0 - float(row["commission_rate"] or config.BETFAIR_COMMISSION))


def update_open_positions(
    snapshots_by_key: dict[tuple[str, int], BookSnapshot],
    run_id: int,
) -> dict[str, Any]:
    """MTM all open positions; auto-close on take-profit or max-hold.

    Note: for Category-1, the "settle at resolution" path is not used
    (we hedge out as soon as the spread allows). Max-hold is a pure
    safety net for stale positions we couldn't re-price.
    """
    con = _conn()
    try:
        rows = con.execute(
            "SELECT * FROM paper_positions WHERE status='open'"
        ).fetchall()
    finally:
        con.close()

    now = time.time()
    updates: list[tuple] = []
    closes: list[tuple] = []

    max_hold_sec = config.PAPER_MAX_HOLD_HOURS * 3600

    for pos in rows:
        key = (str(pos["market_id"]), int(pos["selection_id"]))
        snap = snapshots_by_key.get(key)
        mtm = _mtm_for_row(pos, snap)

        entry = float(pos["entry_cost"])
        realizable_pnl = mtm  # mtm is already a PnL, not a NAV
        hours_open = (now - float(pos["opened_at"])) / 3600.0
        size = float(pos["back_stake"])
        min_profit_close = max(1.0, 0.002 * size)

        should_close = False
        reason = None

        if realizable_pnl >= min_profit_close and snap is not None:
            should_close, reason = True, "take_profit"
        elif hours_open >= config.PAPER_MAX_HOLD_HOURS:
            should_close, reason = True, "max_hold"

        if should_close:
            realized = realizable_pnl
            closes.append((mtm, now, run_id, mtm, realized, reason, now, pos["id"]))
        else:
            updates.append((mtm, now, pos["id"]))

    if updates or closes:
        con = _conn()
        try:
            if updates:
                con.executemany(
                    "UPDATE paper_positions SET mtm_value=?, mtm_ts=? WHERE id=?",
                    updates,
                )
            if closes:
                con.executemany(
                    """UPDATE paper_positions SET
                          mtm_value=?, mtm_ts=?, closed_run_id=?,
                          exit_value=?, realized_pnl=?, close_reason=?,
                          status='closed', closed_at=?
                       WHERE id=?""",
                    closes,
                )
            con.commit()
        finally:
            con.close()

    _snapshot_equity(run_id)
    return {"updated": len(updates), "closed": len(closes)}


def _snapshot_equity(run_id: int) -> None:
    con = _conn()
    try:
        agg = con.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN status='open' THEN back_stake ELSE 0 END),0) cash_used,
                 COALESCE(SUM(CASE WHEN status='open' THEN COALESCE(mtm_value,0) ELSE 0 END),0) unrealized,
                 COALESCE(SUM(CASE WHEN status='closed' THEN realized_pnl ELSE 0 END),0) realized_cum,
                 COALESCE(SUM(CASE WHEN status='open' THEN 1 ELSE 0 END),0) n_open
               FROM paper_positions"""
        ).fetchone()
        cash_used = float(agg["cash_used"] or 0)
        unrealized = float(agg["unrealized"] or 0)
        realized_cum = float(agg["realized_cum"] or 0)
        n_open = int(agg["n_open"] or 0)
        cash = config.PAPER_TOTAL_CAPITAL_USD - cash_used + realized_cum
        equity = cash + cash_used + unrealized
        con.execute(
            """INSERT OR REPLACE INTO paper_equity
               (ts, run_id, cash, unrealized_pnl, realized_pnl_cumulative,
                open_positions, total_equity)
               VALUES(?,?,?,?,?,?,?)""",
            (time.time(), run_id, cash, unrealized, realized_cum, n_open, equity),
        )
        con.commit()
    finally:
        con.close()


def dashboard_state() -> dict[str, Any]:
    con = _conn()
    try:
        summary = con.execute(
            """SELECT
                 COALESCE(SUM(CASE WHEN status='open' THEN back_stake ELSE 0 END),0) cash_used,
                 COALESCE(SUM(CASE WHEN status='open' THEN entry_cost ELSE 0 END),0) exposure_usd,
                 COALESCE(SUM(CASE WHEN status='open' THEN COALESCE(mtm_value,0) ELSE 0 END),0) unrealized,
                 COALESCE(SUM(CASE WHEN status='closed' THEN realized_pnl ELSE 0 END),0) realized,
                 COALESCE(SUM(CASE WHEN status='open' THEN 1 ELSE 0 END),0) n_open,
                 COALESCE(SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END),0) n_closed
               FROM paper_positions"""
        ).fetchone()

        open_pos = con.execute(
            """SELECT id, kind, market_name, event_title, selection_name,
                      back_odds, back_stake, lay_odds, lay_stake,
                      size_usd, entry_cost, entry_edge_net,
                      expected_profit, expected_payout,
                      mtm_value, opened_at, feasibility_at_open,
                      COALESCE(mtm_value,0) AS unrealized
               FROM paper_positions WHERE status='open'
               ORDER BY opened_at DESC LIMIT 50"""
        ).fetchall()
        closed_pos = con.execute(
            """SELECT id, kind, market_name, event_title, selection_name,
                      back_odds, lay_odds, size_usd, entry_cost,
                      exit_value, realized_pnl, close_reason,
                      opened_at, closed_at, feasibility_at_open
               FROM paper_positions WHERE status='closed'
               ORDER BY closed_at DESC LIMIT 50"""
        ).fetchall()
        equity_curve = con.execute(
            """SELECT ts, total_equity, realized_pnl_cumulative, unrealized_pnl,
                      open_positions
               FROM paper_equity ORDER BY ts ASC LIMIT 2000"""
        ).fetchall()

        s = dict(summary)
        s["total_capital"] = config.PAPER_TOTAL_CAPITAL_USD
        exposure = float(s.get("exposure_usd") or 0.0)
        realized = float(s["realized"])
        s["exposure_usd"] = exposure
        s["exposure_cap_usd"] = config.PAPER_TOTAL_CAPITAL_USD + realized
        s["exposure_pct"] = (exposure / s["exposure_cap_usd"]) if s["exposure_cap_usd"] > 0 else 0.0
        s["cash_free"] = max(0.0, s["exposure_cap_usd"] - exposure)
        s["total_equity"] = config.PAPER_TOTAL_CAPITAL_USD + realized + float(s["unrealized"])
        s["total_pnl"] = realized + float(s["unrealized"])
        s["total_pnl_pct"] = (s["total_pnl"] / config.PAPER_TOTAL_CAPITAL_USD) \
            if config.PAPER_TOTAL_CAPITAL_USD > 0 else 0

        # Annualized pace
        earliest = con.execute(
            "SELECT MIN(opened_at) t FROM paper_positions"
        ).fetchone()
        earliest_ts = float(earliest["t"] or 0.0) if earliest else 0.0
        now_ts = time.time()
        days_active = max(0.0, (now_ts - earliest_ts) / 86400.0) if earliest_ts > 0 else 0.0
        n_closed = int(s["n_closed"])

        if days_active > 0 and n_closed > 0:
            daily_rate_usd = realized / days_active
            annualized_usd = daily_rate_usd * 365.0
            annualized_pct = annualized_usd / config.PAPER_TOTAL_CAPITAL_USD
        else:
            daily_rate_usd = 0.0
            annualized_usd = 0.0
            annualized_pct = 0.0

        if days_active >= 7 and n_closed >= 10:
            confidence = "high"
        elif days_active >= 1 and n_closed >= 3:
            confidence = "medium"
        elif days_active > 0 and n_closed > 0:
            confidence = "low"
        else:
            confidence = "insufficient_data"

        s["days_active"] = round(days_active, 2)
        s["daily_rate_usd"] = round(daily_rate_usd, 4)
        s["annualized_usd"] = round(annualized_usd, 2)
        s["annualized_pct"] = round(annualized_pct, 4)
        s["annualized_confidence"] = confidence

        return {
            "summary": s,
            "open_positions": [dict(r) for r in open_pos],
            "closed_positions": [dict(r) for r in closed_pos],
            "equity_curve": [dict(r) for r in equity_curve],
        }
    finally:
        con.close()
