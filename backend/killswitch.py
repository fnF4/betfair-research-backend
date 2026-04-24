"""Kill switch identical in shape to the Polymarket backend."""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from config import DB_PATH
from config import KILL_SWITCH as ENV_KILL_SWITCH

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS kill_switch_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    activated_at REAL,
    activated_by TEXT
);
INSERT OR IGNORE INTO kill_switch_state (id, active) VALUES (1, 0);
"""


def _conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_killswitch_schema() -> None:
    con = _conn()
    try:
        con.executescript(SCHEMA)
        con.commit()
    finally:
        con.close()


def is_active() -> bool:
    if ENV_KILL_SWITCH:
        return True
    try:
        con = _conn()
        try:
            row = con.execute(
                "SELECT active FROM kill_switch_state WHERE id=1"
            ).fetchone()
            return bool(row and row["active"])
        finally:
            con.close()
    except sqlite3.OperationalError:
        return False


def get_state() -> dict:
    if ENV_KILL_SWITCH:
        return {
            "active": True, "source": "environment_variable",
            "reason": "BETFAIR_KILL_SWITCH=1",
            "activated_at": None, "activated_by": "env",
        }
    try:
        con = _conn()
        try:
            row = con.execute(
                "SELECT active, reason, activated_at, activated_by FROM kill_switch_state WHERE id=1"
            ).fetchone()
            if row and row["active"]:
                return {
                    "active": True, "source": "database",
                    "reason": row["reason"],
                    "activated_at": row["activated_at"],
                    "activated_by": row["activated_by"],
                }
        finally:
            con.close()
    except sqlite3.OperationalError:
        pass
    return {"active": False, "source": None, "reason": None,
            "activated_at": None, "activated_by": None}


def activate(reason: str = "manual", actor: str = "admin") -> None:
    init_killswitch_schema()
    con = _conn()
    try:
        con.execute(
            """UPDATE kill_switch_state SET active=1, reason=?, activated_at=?, activated_by=?
               WHERE id=1""",
            (reason, time.time(), actor),
        )
        con.commit()
        log.warning("KILL SWITCH ACTIVATED reason=%s actor=%s", reason, actor)
    finally:
        con.close()


def deactivate(actor: str = "admin") -> None:
    init_killswitch_schema()
    con = _conn()
    try:
        con.execute(
            """UPDATE kill_switch_state SET active=0, reason=NULL,
                       activated_at=NULL, activated_by=?
               WHERE id=1""",
            (actor,),
        )
        con.commit()
        log.info("KILL SWITCH DEACTIVATED actor=%s", actor)
    finally:
        con.close()


def assert_not_active(operation: str) -> None:
    if is_active():
        state = get_state()
        raise RuntimeError(
            f"Kill switch attivo, operazione '{operation}' bloccata. "
            f"Reason: {state.get('reason')}"
        )
