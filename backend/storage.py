"""SQLite storage layer con migrations semplici (Betfair variant).

Schema modellato su quello Polymarket, ma con tabelle adattate alla
semantica Betfair back/lay:
  - runs                per ciclo scheduler
  - market_snapshots    book snapshot per-ciclo per audit ex-post
  - opportunities       signals di arbitraggio Categoria 1 rilevati
  - paper_positions     trade simulati back+lay aperti/chiusi
  - paper_equity        equity curve
  - scanner_state       cycle counter per tiered scanner
  - kill_switch_state   kill switch persistente
  - config_audit        audit trail
  - job_runs            history di esecuzioni

Tutti gli indici sono IF NOT EXISTS per idempotenza.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    finished_at REAL,
    n_events INTEGER,
    n_markets INTEGER,
    n_opportunities INTEGER,
    n_tradeable INTEGER,
    cycle_number INTEGER,
    tier_plan TEXT,
    notes TEXT,
    error TEXT,
    memory_mb REAL
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    market_id TEXT NOT NULL,
    market_name TEXT,
    event_id TEXT,
    event_name TEXT,
    event_start_ts REAL,
    selection_id INTEGER NOT NULL,
    selection_name TEXT,
    best_back_odds REAL,
    best_back_size REAL,
    best_lay_odds REAL,
    best_lay_size REAL,
    total_matched REAL,
    tier INTEGER
);
CREATE INDEX IF NOT EXISTS idx_snap_market_ts ON market_snapshots(market_id, ts);
CREATE INDEX IF NOT EXISTS idx_snap_run ON market_snapshots(run_id);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    market_id TEXT NOT NULL,
    market_name TEXT,
    event_id TEXT,
    event_title TEXT,
    event_start_ts REAL,
    selection_id INTEGER NOT NULL,
    selection_name TEXT,
    back_odds REAL NOT NULL,
    back_size REAL,
    lay_odds REAL NOT NULL,
    lay_size REAL,
    edge_gross REAL NOT NULL,
    edge_net REAL NOT NULL,
    max_back_stake REAL,
    expected_profit REAL,
    expected_payout REAL,
    commission_rate REAL,
    feasibility_class TEXT,
    observed_ms INTEGER,
    legs_hash TEXT,
    opened INTEGER DEFAULT 0,
    simulated_only INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_opp_ts ON opportunities(ts);
CREATE INDEX IF NOT EXISTS idx_opp_market ON opportunities(market_id);
CREATE INDEX IF NOT EXISTS idx_opp_hash ON opportunities(legs_hash);
CREATE INDEX IF NOT EXISTS idx_opp_class ON opportunities(feasibility_class);

CREATE TABLE IF NOT EXISTS paper_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    legs_hash TEXT NOT NULL,
    kind TEXT NOT NULL,
    market_id TEXT NOT NULL,
    market_name TEXT,
    event_id TEXT,
    event_title TEXT,
    event_start_ts REAL,
    selection_id INTEGER NOT NULL,
    selection_name TEXT,
    feasibility_at_open TEXT,
    opened_at REAL NOT NULL,
    opened_run_id INTEGER,
    back_odds REAL NOT NULL,
    back_stake REAL NOT NULL,
    lay_odds REAL NOT NULL,
    lay_stake REAL NOT NULL,
    lay_liability REAL NOT NULL,
    size_usd REAL NOT NULL,
    entry_cost REAL NOT NULL,
    entry_edge_net REAL,
    expected_profit REAL,
    expected_payout REAL,
    commission_rate REAL,
    status TEXT NOT NULL,
    mtm_value REAL,
    mtm_ts REAL,
    closed_at REAL,
    closed_run_id INTEGER,
    exit_value REAL,
    realized_pnl REAL,
    close_reason TEXT,
    simulated_only INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_pp_hash ON paper_positions(legs_hash);
CREATE INDEX IF NOT EXISTS idx_pp_status ON paper_positions(status);
CREATE INDEX IF NOT EXISTS idx_pp_market ON paper_positions(market_id);

CREATE TABLE IF NOT EXISTS paper_equity (
    ts REAL PRIMARY KEY,
    run_id INTEGER,
    cash REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    realized_pnl_cumulative REAL NOT NULL,
    open_positions INTEGER NOT NULL,
    total_equity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS scanner_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated REAL
);

CREATE TABLE IF NOT EXISTS config_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    snapshot_json TEXT NOT NULL,
    actor TEXT
);

CREATE TABLE IF NOT EXISTS job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    source TEXT NOT NULL,
    duration_sec REAL,
    status TEXT,
    message TEXT
);
"""


def _conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con


def init_db() -> None:
    con = _conn()
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def migrate_schema() -> None:
    """Backward-compatible column additions for an existing DB."""
    con = _conn()
    try:
        # Columns that may be added later live here. Keep idempotent.
        run_cols = {r[1] for r in con.execute("PRAGMA table_info(runs)").fetchall()}
        if "memory_mb" not in run_cols:
            try:
                con.execute("ALTER TABLE runs ADD COLUMN memory_mb REAL")
            except sqlite3.OperationalError:
                pass
        con.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        con.close()


# --- runs -----------------------------------------------------------------

def start_run(notes: str | None = None, cycle_number: int | None = None,
              tier_plan: str | None = None) -> int:
    con = _conn()
    try:
        cur = con.execute(
            "INSERT INTO runs(started_at, notes, cycle_number, tier_plan) VALUES(?, ?, ?, ?)",
            (time.time(), notes, cycle_number, tier_plan),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def finish_run(run_id: int, *, n_events: int, n_markets: int, n_opps: int,
               n_tradeable: int = 0, error: str | None = None,
               memory_mb: float | None = None) -> None:
    con = _conn()
    try:
        con.execute(
            """UPDATE runs SET finished_at=?, n_events=?, n_markets=?,
                               n_opportunities=?, n_tradeable=?, error=?, memory_mb=?
               WHERE run_id=?""",
            (time.time(), n_events, n_markets, n_opps, n_tradeable,
             error, memory_mb, run_id),
        )
        con.commit()
    finally:
        con.close()


# --- snapshots ------------------------------------------------------------

def insert_market_snapshot(run_id: int, row: dict[str, Any]) -> None:
    con = _conn()
    try:
        con.execute(
            """INSERT INTO market_snapshots
               (run_id, ts, market_id, market_name, event_id, event_name, event_start_ts,
                selection_id, selection_name,
                best_back_odds, best_back_size, best_lay_odds, best_lay_size,
                total_matched, tier)
               VALUES(?,?,?,?,?,?,?, ?,?, ?,?,?,?, ?,?)""",
            (
                run_id, time.time(),
                row.get("market_id"), row.get("market_name"),
                row.get("event_id"), row.get("event_name"), row.get("event_start_ts"),
                row.get("selection_id"), row.get("selection_name"),
                row.get("best_back_odds"), row.get("best_back_size"),
                row.get("best_lay_odds"), row.get("best_lay_size"),
                row.get("total_matched"), row.get("tier"),
            ),
        )
        con.commit()
    finally:
        con.close()


# --- opportunities --------------------------------------------------------

def insert_opportunity(run_id: int, opp: dict[str, Any]) -> int:
    con = _conn()
    try:
        cur = con.execute(
            """INSERT INTO opportunities
               (run_id, ts, kind, market_id, market_name, event_id, event_title,
                event_start_ts, selection_id, selection_name,
                back_odds, back_size, lay_odds, lay_size,
                edge_gross, edge_net, max_back_stake,
                expected_profit, expected_payout, commission_rate,
                feasibility_class, observed_ms, legs_hash, opened, simulated_only)
               VALUES(?,?,?,?,?,?,?, ?,?,?, ?,?,?,?, ?,?,?, ?,?,?, ?,?,?, 0, 1)""",
            (
                run_id, time.time(),
                opp.get("kind"), opp.get("market_id"), opp.get("market_name"),
                opp.get("event_id"), opp.get("event_title"), opp.get("event_start_ts"),
                opp.get("selection_id"), opp.get("selection_name"),
                opp.get("back_odds"), opp.get("back_size"),
                opp.get("lay_odds"), opp.get("lay_size"),
                opp.get("edge_gross"), opp.get("edge_net"), opp.get("max_back_stake"),
                opp.get("expected_profit"), opp.get("expected_payout"),
                opp.get("commission_rate"),
                opp.get("feasibility_class"), opp.get("observed_ms"),
                opp.get("legs_hash"),
            ),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def recent_opportunities(limit: int = 200, only_tradeable: bool = False) -> list[dict[str, Any]]:
    where = "WHERE feasibility_class != 'ghost'" if only_tradeable else ""
    con = _conn()
    try:
        rows = con.execute(
            f"SELECT * FROM opportunities {where} ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def aggregate_stats(hours: int = 24) -> dict[str, Any]:
    cutoff = time.time() - hours * 3600
    con = _conn()
    try:
        total = con.execute(
            "SELECT COUNT(*) c FROM opportunities WHERE ts >= ?", (cutoff,)
        ).fetchone()["c"]
        unique_legs = con.execute(
            "SELECT COUNT(DISTINCT legs_hash) c FROM opportunities WHERE ts >= ?",
            (cutoff,),
        ).fetchone()["c"]
        by_kind = con.execute(
            """SELECT kind, COUNT(*) c, AVG(edge_net) avg_edge, MAX(edge_net) max_edge
               FROM opportunities WHERE ts >= ? GROUP BY kind""",
            (cutoff,),
        ).fetchall()
        by_class = con.execute(
            """SELECT COALESCE(feasibility_class,'?') cls, COUNT(*) c
               FROM opportunities WHERE ts >= ? GROUP BY cls""",
            (cutoff,),
        ).fetchall()
        runs = con.execute(
            """SELECT COUNT(*) c, AVG(n_markets) avg_markets, SUM(n_opportunities) total_opps
               FROM runs WHERE finished_at >= ?""",
            (cutoff,),
        ).fetchone()
        tradeable = con.execute(
            "SELECT COUNT(*) c FROM opportunities WHERE ts >= ? AND feasibility_class != 'ghost'",
            (cutoff,),
        ).fetchone()["c"]
        return {
            "hours": hours,
            "total_signals": total,
            "unique_opportunities": unique_legs,
            "tradeable_signals": tradeable,
            "by_kind": [dict(r) for r in by_kind],
            "by_feasibility": [dict(r) for r in by_class],
            "runs": dict(runs) if runs else {},
        }
    finally:
        con.close()


def opportunities_timeline(hours: int = 24, bucket_min: int = 15) -> list[dict[str, Any]]:
    cutoff = time.time() - hours * 3600
    con = _conn()
    try:
        rows = con.execute(
            f"""SELECT CAST(ts / ({bucket_min}*60) AS INTEGER) * {bucket_min}*60 bucket,
                       COUNT(*) c, AVG(edge_net) avg_edge,
                       SUM(CASE WHEN feasibility_class != 'ghost' THEN 1 ELSE 0 END) n_tradeable
                FROM opportunities WHERE ts >= ? GROUP BY bucket ORDER BY bucket""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# --- markets summary ------------------------------------------------------

def recent_markets(limit: int = 100) -> list[dict[str, Any]]:
    con = _conn()
    try:
        rows = con.execute(
            """SELECT market_id, MAX(market_name) market_name,
                      MAX(event_name) event_name,
                      MAX(ts) last_ts, MAX(total_matched) total_matched,
                      MAX(tier) tier
               FROM market_snapshots
               GROUP BY market_id
               ORDER BY total_matched DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# --- audit ----------------------------------------------------------------

def append_config_audit(snapshot: dict[str, Any], actor: str = "system") -> None:
    con = _conn()
    try:
        con.execute(
            "INSERT INTO config_audit(ts, snapshot_json, actor) VALUES(?,?,?)",
            (time.time(), json.dumps(snapshot, default=str), actor),
        )
        con.commit()
    finally:
        con.close()


def record_job_run(source: str, duration_sec: float, status: str, message: str = "") -> None:
    con = _conn()
    try:
        con.execute(
            "INSERT INTO job_runs(ts, source, duration_sec, status, message) VALUES(?,?,?,?,?)",
            (time.time(), source, duration_sec, status, message),
        )
        con.commit()
    finally:
        con.close()
