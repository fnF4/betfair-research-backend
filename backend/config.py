"""Configurazione centrale del research platform (Betfair variant).

Pattern identico al backend Polymarket: **SOLO valori di configurazione**.
Nessuna credenziale è definita qui come default; tutti i parametri possono
essere overridden via variabile d'ambiente (prefix BETFAIR_).

In produzione (Render) le env var sono impostate nel dashboard del servizio.
In sviluppo locale, copia .env.example in .env.

COMPLIANCE NOTE
---------------
Questo backend accede ESCLUSIVAMENTE all'API ufficiale Betfair Exchange.
Il mandato è ricerca + paper trading: nessun ordine reale viene inviato,
nessun wallet viene toccato, nessuna geografia viene bypassata.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_csv_int(name: str, default: list[int]) -> list[int]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return list(default)
    out: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.append(int(piece))
        except ValueError:
            continue
    return out or list(default)


# --- Betfair endpoint / auth ---------------------------------------------
BETFAIR_LOCALE = os.environ.get("BETFAIR_LOCALE", "IT")
BETFAIR_USERNAME = os.environ.get("BETFAIR_USERNAME", "")
BETFAIR_PASSWORD = os.environ.get("BETFAIR_PASSWORD", "")
BETFAIR_APP_KEY = os.environ.get("BETFAIR_APP_KEY", "")

BETFAIR_USE_CERTS = _env_bool("BETFAIR_USE_CERTS", False)
BETFAIR_CERT_PATH = os.environ.get("BETFAIR_CERT_PATH", "")
BETFAIR_KEY_PATH = os.environ.get("BETFAIR_KEY_PATH", "")

BETFAIR_COMMISSION = _env_float("BETFAIR_COMMISSION", 0.05)

# --- Collector / scanning -------------------------------------------------
EVENT_TYPE_IDS = _env_csv_int("BETFAIR_EVENT_TYPE_IDS", [1, 2])
HORIZON_HOURS = _env_int("BETFAIR_HORIZON_HOURS", 72)

TIER_1_LIMIT = _env_int("BETFAIR_TIER_1_LIMIT", 30)
TIER_2_LIMIT = _env_int("BETFAIR_TIER_2_LIMIT", 0)
TIER_3_LIMIT = _env_int("BETFAIR_TIER_3_LIMIT", 0)

TIER_2_EVERY_N_CYCLES = _env_int("BETFAIR_TIER_2_EVERY", 3)
TIER_3_EVERY_N_CYCLES = _env_int("BETFAIR_TIER_3_EVERY", 12)

MIN_TOTAL_MATCHED = _env_float("BETFAIR_MIN_TOTAL_MATCHED", 1000.0)

# --- Detection thresholds -------------------------------------------------
MIN_EDGE_NET = _env_float("BETFAIR_MIN_EDGE_NET", 0.003)
SAFETY_MARGIN = _env_float("BETFAIR_SAFETY_MARGIN", 1.5)
GHOST_THRESHOLD_MS = _env_int("BETFAIR_GHOST_MS", 2000)

# --- Cycle cadence --------------------------------------------------------
CYCLE_SECONDS = _env_int("BETFAIR_CYCLE_SECONDS", 45)

# --- Paper trading --------------------------------------------------------
PAPER_TOTAL_CAPITAL_USD = _env_float("BETFAIR_CAPITAL", 10_000.0)
PAPER_PER_TRADE_USD = _env_float("BETFAIR_PER_TRADE", 500.0)
PAPER_MIN_EDGE_NET = _env_float("BETFAIR_PAPER_MIN_EDGE", 0.003)
PAPER_MIN_NOTIONAL_USD = _env_float("BETFAIR_PAPER_MIN_NOTIONAL", 25.0)
PAPER_ONLY_CATCHABLE = _env_bool("BETFAIR_ONLY_CATCHABLE", False)
PAPER_MAX_HOLD_HOURS = _env_int("BETFAIR_MAX_HOLD_H", 72)

# --- Storage --------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("BETFAIR_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "monitor.sqlite"
LOG_PATH = DATA_DIR / "monitor.log"

# --- HTTP / misc ----------------------------------------------------------
HTTP_TIMEOUT = _env_int("BETFAIR_HTTP_TIMEOUT", 15)
HTTP_RETRIES = _env_int("BETFAIR_HTTP_RETRIES", 3)
USER_AGENT = os.environ.get(
    "BETFAIR_USER_AGENT",
    "betfair-research-backend/0.1",
)

# --- Kill switch ----------------------------------------------------------
KILL_SWITCH = _env_bool("BETFAIR_KILL_SWITCH", False)

# --- Execution mode -------------------------------------------------------
EXECUTION_MODE = os.environ.get("BETFAIR_EXECUTION_MODE", "paper")
assert EXECUTION_MODE in ("paper", "disabled_live"), (
    f"EXECUTION_MODE must be 'paper' or 'disabled_live', got: {EXECUTION_MODE!r}"
)

# --- CORS -----------------------------------------------------------------
CORS_ORIGINS = [
    o.strip() for o in os.environ.get(
        "BETFAIR_CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if o.strip()
]

# --- Compliance flags (hardcoded) -----------------------------------------
COMPLIANCE_PAPER_ONLY = True
COMPLIANCE_NO_WALLET = True
COMPLIANCE_NO_ORDER_SUBMISSION = True
COMPLIANCE_NO_GEO_BYPASS = True
COMPLIANCE_OFFICIAL_APIS_ONLY = True


def config_snapshot() -> dict:
    """Expose the active configuration for the /api/status endpoint."""
    def mask(v: str) -> str:
        return "***set***" if v else "***empty***"
    return {
        "betfair_locale": BETFAIR_LOCALE,
        "betfair_username": mask(BETFAIR_USERNAME),
        "betfair_app_key": mask(BETFAIR_APP_KEY),
        "betfair_use_certs": BETFAIR_USE_CERTS,
        "betfair_commission": BETFAIR_COMMISSION,
        "event_type_ids": EVENT_TYPE_IDS,
        "horizon_hours": HORIZON_HOURS,
        "tier_1_limit": TIER_1_LIMIT,
        "tier_2_range": f"{TIER_1_LIMIT+1}..{TIER_1_LIMIT+TIER_2_LIMIT}",
        "tier_3_range": f"{TIER_1_LIMIT+TIER_2_LIMIT+1}..{TIER_1_LIMIT+TIER_2_LIMIT+TIER_3_LIMIT}",
        "tier_2_every_n_cycles": TIER_2_EVERY_N_CYCLES,
        "tier_3_every_n_cycles": TIER_3_EVERY_N_CYCLES,
        "min_total_matched": MIN_TOTAL_MATCHED,
        "min_edge_net": MIN_EDGE_NET,
        "safety_margin": SAFETY_MARGIN,
        "ghost_threshold_ms": GHOST_THRESHOLD_MS,
        "cycle_seconds": CYCLE_SECONDS,
        "paper_capital": PAPER_TOTAL_CAPITAL_USD,
        "paper_per_trade": PAPER_PER_TRADE_USD,
        "paper_max_hold_hours": PAPER_MAX_HOLD_HOURS,
        "paper_only_catchable": PAPER_ONLY_CATCHABLE,
        "kill_switch": KILL_SWITCH,
        "execution_mode": EXECUTION_MODE,
        "compliance": {
            "paper_only": COMPLIANCE_PAPER_ONLY,
            "no_wallet": COMPLIANCE_NO_WALLET,
            "no_order_submission": COMPLIANCE_NO_ORDER_SUBMISSION,
            "no_geo_bypass": COMPLIANCE_NO_GEO_BYPASS,
            "official_apis_only": COMPLIANCE_OFFICIAL_APIS_ONLY,
        },
    }
