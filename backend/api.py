"""FastAPI backend — Betfair variant.

Endpoints (same shape as the Polymarket backend so the frontend
can be copied with minimal edits):
 - GET  /health                       liveness
 - GET  /api/status                   config snapshot + kill switch
 - GET  /api/health                   scanner health (verde/giallo/rosso)
 - GET  /api/metrics                  metriche aggregate 24h
 - GET  /api/markets                  lista mercati recenti
 - GET  /api/opportunities            lista opportunita'
 - GET  /api/opportunity/{id}         dettaglio singola opp
 - GET  /api/portfolio                paper trading portfolio state
 - GET  /api/timeline                 bucket temporale signal
 - POST /api/admin/scan               trigger on-demand (X-Admin-Secret)
 - POST /api/admin/kill               attiva kill switch
 - POST /api/admin/unkill             disattiva kill switch
 - POST /api/admin/reset-paper-trading (X-Admin-Secret + ?confirm=...)

CORS: limitato a BETFAIR_CORS_ORIGINS.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import health as health_mod
import killswitch
import storage
from logger_setup import setup_logging


setup_logging()
log = logging.getLogger("api")


# --- Init DB at module import so uvicorn imports cleanly. ----------------
try:
    storage.init_db()
    storage.migrate_schema()
    killswitch.init_killswitch_schema()
    log.info("module-level DB init complete")
except Exception as _init_err:  # noqa: BLE001
    log.exception("module-level DB init failed: %s", _init_err)


app = FastAPI(
    title="Betfair Research Backend",
    description="Research-only / paper-trading-only. No real orders.",
    version="0.1.0",
)


@app.on_event("startup")
def _startup_init_db() -> None:
    try:
        storage.init_db()
        storage.migrate_schema()
        killswitch.init_killswitch_schema()
    except Exception as e:  # noqa: BLE001
        log.exception("startup init failed: %s", e)


# --- Background scheduler thread -----------------------------------------
_scheduler_thread: threading.Thread | None = None
_scheduler_running: bool = False


def _scheduler_loop() -> None:
    from collector import run_once
    interval = max(10, config.CYCLE_SECONDS)
    initial_delay = 15
    log.info("scheduler thread starting: interval=%ds initial_delay=%ds",
             interval, initial_delay)

    slept = 0
    while slept < initial_delay and _scheduler_running:
        time.sleep(min(2, initial_delay - slept))
        slept += 2

    while _scheduler_running:
        cycle_start = time.time()
        try:
            log.info("scheduler triggering cycle")
            r = run_once(source="scheduler")
            log.info(
                "scheduler cycle done: cycle=%s markets=%s opps=%s opened=%s rss=%sMB",
                r.get("cycle_number"), r.get("markets_scanned"),
                r.get("opps_found"), r.get("positions_opened"),
                r.get("memory_mb"),
            )
        except Exception as e:  # noqa: BLE001
            log.exception("scheduler cycle failed: %s", e)

        elapsed = time.time() - cycle_start
        remaining = max(2.0, interval - elapsed)
        slept_f = 0.0
        while slept_f < remaining and _scheduler_running:
            chunk = min(2.0, remaining - slept_f)
            time.sleep(chunk)
            slept_f += chunk

    log.info("scheduler thread exiting")


@app.on_event("startup")
def _start_scheduler() -> None:
    global _scheduler_thread, _scheduler_running
    if os.environ.get("BETFAIR_DISABLE_SCHEDULER", "").strip().lower() in ("1", "true", "yes", "on"):
        log.warning("scheduler disabled via BETFAIR_DISABLE_SCHEDULER")
        return
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop, name="betfair-scheduler", daemon=True,
    )
    _scheduler_thread.start()
    log.info("scheduler started")


@app.on_event("shutdown")
def _stop_scheduler() -> None:
    global _scheduler_running
    _scheduler_running = False


# --- CORS -----------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


ADMIN_SECRET = os.environ.get("BETFAIR_ADMIN_SECRET", "")


def _require_admin(x_admin_secret: str | None) -> None:
    if not ADMIN_SECRET:
        raise HTTPException(503, "Admin disabled (BETFAIR_ADMIN_SECRET not set)")
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(401, "Unauthorized")


# --- Health / status ------------------------------------------------------

@app.get("/health")
def health_liveness():
    return {"status": "ok", "simulated_only": True}


@app.get("/api/health")
def api_health():
    return health_mod.get_health()


@app.get("/api/status")
def api_status():
    return {
        "config": config.config_snapshot(),
        "kill_switch": killswitch.get_state(),
        "execution_provider": {
            "name": "paper",
            "supports_live": False,
            "status": "active",
            "description": "Paper trading only (simulated). No real orders.",
        },
        "circuit_breakers": {"betfair": "ok"},
        "compliance": {
            "paper_only": True, "no_wallet": True, "no_order_submission": True,
            "no_geo_bypass": True, "official_apis_only": True,
        },
    }


# --- Data ----------------------------------------------------------------

@app.get("/api/metrics")
def api_metrics(hours: int = Query(24, ge=1, le=168)):
    return storage.aggregate_stats(hours=hours)


@app.get("/api/opportunities")
def api_opportunities(
    limit: int = Query(100, ge=1, le=500),
    only_tradeable: bool = Query(False),
    feasibility_class: str | None = Query(None, pattern=r"^(ghost|catchable|live)$"),
    kind: str | None = Query(None, pattern=r"^(cat1_crossed)$"),
    hours: int = Query(24, ge=1, le=168),
):
    if not Path(config.DB_PATH).exists():
        return []
    cutoff = time.time() - hours * 3600
    where = ["ts >= ?"]
    params: list[Any] = [cutoff]
    if only_tradeable:
        where.append("feasibility_class != 'ghost'")
    if feasibility_class:
        where.append("feasibility_class = ?")
        params.append(feasibility_class)
    if kind:
        where.append("kind = ?")
        params.append(kind)
    sql = (f"SELECT * FROM opportunities WHERE {' AND '.join(where)} "
           "ORDER BY ts DESC LIMIT ?")
    params.append(limit)
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()
    return rows


@app.get("/api/opportunity/{opp_id}")
def api_opportunity(opp_id: int):
    if not Path(config.DB_PATH).exists():
        raise HTTPException(404, "not found")
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        r = con.execute("SELECT * FROM opportunities WHERE id=?", (opp_id,)).fetchone()
    finally:
        con.close()
    if not r:
        raise HTTPException(404, "not found")
    return dict(r)


@app.get("/api/markets")
def api_markets(limit: int = Query(100, ge=1, le=500)):
    return storage.recent_markets(limit=limit)


@app.get("/api/portfolio")
def api_portfolio():
    import paper_trading
    return paper_trading.dashboard_state()


@app.get("/api/timeline")
def api_timeline(hours: int = Query(24, ge=1, le=168),
                 bucket_min: int = Query(15, ge=5, le=60)):
    return storage.opportunities_timeline(hours=hours, bucket_min=bucket_min)


# --- Admin ----------------------------------------------------------------

class KillSwitchIn(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


@app.post("/api/admin/scan")
def admin_scan(x_admin_secret: str = Header(None, alias="X-Admin-Secret")):
    _require_admin(x_admin_secret)
    from collector import run_once
    return run_once(source="api_admin")


@app.post("/api/admin/kill")
def admin_kill(body: KillSwitchIn,
               x_admin_secret: str = Header(None, alias="X-Admin-Secret")):
    _require_admin(x_admin_secret)
    killswitch.activate(reason=body.reason, actor="api_admin")
    return {"ok": True, "kill_switch": killswitch.get_state()}


@app.post("/api/admin/unkill")
def admin_unkill(x_admin_secret: str = Header(None, alias="X-Admin-Secret")):
    _require_admin(x_admin_secret)
    killswitch.deactivate(actor="api_admin")
    return {"ok": True, "kill_switch": killswitch.get_state()}


@app.post("/api/admin/reset-paper-trading")
def admin_reset_paper_trading(
    x_admin_secret: str = Header(None, alias="X-Admin-Secret"),
    confirm: str = Query("", description="Must equal 'YES_WIPE_ALL_PAPER_DATA'"),
    keep_scan_history: bool = Query(True),
):
    _require_admin(x_admin_secret)
    if confirm != "YES_WIPE_ALL_PAPER_DATA":
        return {"error": "confirmation required",
                "message": "pass ?confirm=YES_WIPE_ALL_PAPER_DATA"}

    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        pre_counts: dict[str, int | None] = {}
        tables_paper = ["paper_positions", "paper_equity"]
        tables_scan = ["runs", "opportunities", "market_snapshots", "scanner_state"]
        all_tables = tables_paper + (tables_scan if not keep_scan_history else [])

        for t in all_tables:
            try:
                r = con.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()
                pre_counts[t] = int(r["n"])
            except sqlite3.OperationalError:
                pre_counts[t] = None

        con.execute("DELETE FROM paper_positions")
        con.execute("DELETE FROM paper_equity")
        if not keep_scan_history:
            for t in tables_scan:
                try:
                    con.execute(f"DELETE FROM {t}")
                except sqlite3.OperationalError:
                    pass
        con.commit()

        post_counts: dict[str, int | None] = {}
        for t in all_tables:
            try:
                r = con.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()
                post_counts[t] = int(r["n"])
            except sqlite3.OperationalError:
                post_counts[t] = None

        return {
            "ok": True, "keep_scan_history": keep_scan_history,
            "pre_counts": pre_counts, "post_counts": post_counts,
            "message": (f"paper trading DB reset complete. Starts fresh with "
                        f"${config.PAPER_TOTAL_CAPITAL_USD:,.0f} capital, 0 positions."),
        }
    finally:
        con.close()


@app.exception_handler(Exception)
def _unhandled(_request, exc: Exception):
    log.exception("unhandled: %s", exc)
    return JSONResponse(status_code=500,
                        content={"error": "internal_error",
                                 "message": str(exc)[:300]})
