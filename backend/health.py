"""Scanner health monitoring. Same contract as Polymarket /api/health."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from config import CYCLE_SECONDS, DB_PATH


def _conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def get_health() -> dict:
    expected_per_hour = max(1, 3600 // max(CYCLE_SECONDS, 1))
    expected_24h = max(1, 86400 // max(CYCLE_SECONDS, 1))

    if not Path(DB_PATH).exists():
        return {
            "status": "red", "label": "DB non inizializzato",
            "last_cycle_ago_sec": None,
            "cycles_last_hour": 0, "cycles_last_24h": 0,
            "expected_cycles_hour": expected_per_hour,
            "expected_cycles_24h": expected_24h,
            "last_run_markets": 0, "last_run_opps": 0,
            "uptime_pct_24h": 0.0,
        }

    con = _conn()
    try:
        last_run = con.execute(
            """SELECT run_id, started_at, finished_at, n_markets, n_opportunities
               FROM runs WHERE finished_at IS NOT NULL
               ORDER BY finished_at DESC LIMIT 1"""
        ).fetchone()
        cycles_1h = con.execute(
            "SELECT COUNT(*) c FROM runs WHERE finished_at >= ?", (time.time() - 3600,)
        ).fetchone()["c"]
        cycles_24h = con.execute(
            "SELECT COUNT(*) c FROM runs WHERE finished_at >= ?", (time.time() - 86400,)
        ).fetchone()["c"]
    finally:
        con.close()

    if not last_run:
        return {
            "status": "red", "label": "Nessun ciclo eseguito",
            "last_cycle_ago_sec": None,
            "cycles_last_hour": 0, "cycles_last_24h": 0,
            "expected_cycles_hour": expected_per_hour,
            "expected_cycles_24h": expected_24h,
            "last_run_markets": 0, "last_run_opps": 0,
            "uptime_pct_24h": 0.0,
        }

    last_finish = float(last_run["finished_at"] or 0.0)
    ago = time.time() - last_finish

    if ago < CYCLE_SECONDS * 2 and cycles_1h >= max(1, expected_per_hour // 2):
        status, label = "green", "OK"
    elif ago < CYCLE_SECONDS * 5:
        status, label = "yellow", "Cicli sotto frequenza attesa"
    else:
        status, label = "red", "Nessun ciclo recente"

    uptime_pct = min(1.0, cycles_24h / max(expected_24h, 1)) * 100.0

    return {
        "status": status, "label": label,
        "last_cycle_ago_sec": int(ago),
        "cycles_last_hour": cycles_1h,
        "cycles_last_24h": cycles_24h,
        "expected_cycles_hour": expected_per_hour,
        "expected_cycles_24h": expected_24h,
        "last_run_markets": int(last_run["n_markets"] or 0),
        "last_run_opps": int(last_run["n_opportunities"] or 0),
        "last_run_at": last_finish,
        "uptime_pct_24h": round(uptime_pct, 1),
    }
