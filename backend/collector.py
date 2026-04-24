"""One scan cycle: catalogue → book snapshots → opportunities → DB → paper trading.

Exposed entry point: `run_once(source: str) -> dict`.

Called from:
- the in-process scheduler (see api.py)
- the /api/admin/scan endpoint (manual trigger)

Identical to the Polymarket `collector.run_once()` signature so the
caller never has to branch.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import config
import killswitch
import paper_trading
import storage
from arbitrage import Cat1Opportunity, detect_category_1
from betfair_client import BookSnapshot, client

try:
    import psutil
    def _rss_mb() -> float:
        try:
            return psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:  # noqa: BLE001
            return 0.0
except ImportError:
    def _rss_mb() -> float:
        return 0.0


log = logging.getLogger(__name__)

# In-process caches survive across cycles.
_catalogue_cache: dict[str, dict] = {}
_catalogue_cache_ts: float = 0.0
_CATALOGUE_TTL_S: float = 300.0
_spread_ms: dict[str, int] = {}
_cycle_counter: int = 0


def _known_open_hashes() -> set[str]:
    import sqlite3
    from pathlib import Path
    if not Path(config.DB_PATH).exists():
        return set()
    con = sqlite3.connect(str(config.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT legs_hash FROM paper_positions WHERE status='open'"
        ).fetchall()
        return {r["legs_hash"] for r in rows if r["legs_hash"]}
    finally:
        con.close()


def _persist_snapshots(run_id: int, snapshots: list[BookSnapshot]) -> None:
    for s in snapshots:
        storage.insert_market_snapshot(run_id, {
            "market_id": s.market_id,
            "market_name": s.market_name,
            "event_id": s.event_id,
            "event_name": s.event_name,
            "event_start_ts": s.event_start_ts,
            "selection_id": s.selection_id,
            "selection_name": s.selection_name,
            "best_back_odds": s.best_back_odds,
            "best_back_size": s.best_back_size,
            "best_lay_odds": s.best_lay_odds,
            "best_lay_size": s.best_lay_size,
            "total_matched": s.total_matched,
            "tier": 1,
        })


def _persist_opportunities(run_id: int, opps: list[Cat1Opportunity]) -> list[int]:
    ids: list[int] = []
    for o in opps:
        opp_row = o.to_row()
        # Ensure 'event_title' field name compatibility
        opp_row["event_title"] = opp_row.pop("event_title", None) or opp_row.get("event_name")
        opp_id = storage.insert_opportunity(run_id, opp_row)
        ids.append(opp_id)
    return ids


def run_once(source: str = "manual") -> dict[str, Any]:
    global _catalogue_cache, _catalogue_cache_ts, _spread_ms, _cycle_counter

    if killswitch.is_active():
        log.warning("kill switch active — run_once skipped")
        storage.record_job_run(source=source, duration_sec=0.0,
                               status="skipped_killswitch",
                               message="kill switch active")
        return {
            "ok": False, "skipped": True, "reason": "kill_switch",
            "cycle_number": _cycle_counter,
            "events_scanned": 0, "markets_scanned": 0, "opps_found": 0,
        }

    _cycle_counter += 1
    run_id = storage.start_run(
        notes=f"source={source}",
        cycle_number=_cycle_counter,
        tier_plan=f"tier1={config.TIER_1_LIMIT}",
    )
    started = time.time()

    n_markets = 0
    n_opps = 0
    n_tradeable = 0
    n_opened = 0
    error: str | None = None
    snapshots: list[BookSnapshot] = []
    opps: list[Cat1Opportunity] = []

    try:
        now = time.time()
        refresh = (
            not _catalogue_cache
            or (now - _catalogue_cache_ts) > _CATALOGUE_TTL_S
        )
        if refresh:
            entries = client.list_markets(
                event_type_ids=config.EVENT_TYPE_IDS,
                horizon_hours=config.HORIZON_HOURS,
                max_results=max(1, config.TIER_1_LIMIT
                                    + config.TIER_2_LIMIT
                                    + config.TIER_3_LIMIT),
            )
            _catalogue_cache = {
                m["marketId"]: m for m in entries
                if m.get("marketId")
                and float(m.get("totalMatched") or 0.0) >= config.MIN_TOTAL_MATCHED
            }
            _catalogue_cache_ts = now
            log.info("catalogue refreshed: %d markets pass liquidity filter",
                     len(_catalogue_cache))

        # Only Tier-1 on every cycle (MVP); tier-2/3 rotation can be added later.
        market_ids = list(_catalogue_cache.keys())[: config.TIER_1_LIMIT]
        if market_ids:
            books = client.list_books(market_ids)
            n_markets = len(books)
            snapshots = client.snapshots_from_books(books, _catalogue_cache)

        # Track how long each crossed spread has persisted across cycles.
        elapsed_ms_estimate = int(config.CYCLE_SECONDS * 1000)
        from arbitrage import _legs_hash
        new_spread_ms: dict[str, int] = {}
        for s in snapshots:
            if (
                s.best_back_odds is not None
                and s.best_lay_odds is not None
                and s.best_back_odds >= s.best_lay_odds
            ):
                lh = _legs_hash(s.market_id, s.selection_id,
                                float(s.best_back_odds), float(s.best_lay_odds))
                new_spread_ms[lh] = _spread_ms.get(lh, 0) + elapsed_ms_estimate
        _spread_ms = new_spread_ms

        opps = detect_category_1(
            snapshots,
            known_legs_hashes=_known_open_hashes(),
            previous_spread_ms=_spread_ms,
        )
        n_opps = len(opps)
        n_tradeable = sum(1 for o in opps if o.feasibility_class != "ghost")

        # Persist audit trail
        _persist_snapshots(run_id, snapshots)
        opp_ids = _persist_opportunities(run_id, opps)

        # Paper trading: try to open qualifying ones
        for o, oid in zip(opps, opp_ids):
            opp_row = o.to_row()
            opp_row["event_title"] = opp_row.get("event_title") or opp_row.get("event_name")
            pid = paper_trading.maybe_open_position(opp_row, run_id=run_id)
            if pid is not None:
                n_opened += 1

        # MTM and close scans
        snaps_by_key = {
            (s.market_id, s.selection_id): s for s in snapshots
        }
        paper_trading.update_open_positions(snaps_by_key, run_id=run_id)

    except Exception as exc:  # noqa: BLE001
        log.exception("collector.run_once failed: %s", exc)
        error = f"{type(exc).__name__}: {exc}"

    finally:
        rss = _rss_mb()
        storage.finish_run(
            run_id,
            n_events=len({s.event_id for s in snapshots if s.event_id}),
            n_markets=n_markets,
            n_opps=n_opps,
            n_tradeable=n_tradeable,
            error=error,
            memory_mb=rss,
        )
        duration = time.time() - started
        storage.record_job_run(
            source=source, duration_sec=duration,
            status="ok" if error is None else "failed",
            message=error or f"opps={n_opps} opened={n_opened}",
        )

    return {
        "ok": error is None,
        "cycle_number": _cycle_counter,
        "run_id": run_id,
        "events_scanned": len({s.event_id for s in snapshots if s.event_id}),
        "markets_scanned": n_markets,
        "opps_found": n_opps,
        "opps_tradeable": n_tradeable,
        "positions_opened": n_opened,
        "memory_mb": round(rss, 1),
        "duration_sec": round(time.time() - started, 2),
        "error": error,
    }
