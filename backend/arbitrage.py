"""Category-1 arbitrage detection for Betfair Exchange.

Category 1 = "crossed book": on the same selection, same market, best_back
>= best_lay. You can simultaneously back and lay the same outcome for
guaranteed profit.

HEDGE MATH
----------
Back stake X at odds B:
    win if selection wins:  X * (B - 1)
    lose if selection loses: X
Lay stake Y at odds L (liability Y * (L - 1)):
    lose if selection wins: Y * (L - 1)
    win  if selection loses: Y

Perfectly hedged: Y = X * B / L
    PnL both branches = X * (B - L) / L   (risk-free)

Commission `c` applied on net winnings:
    edge_net = (B - L) / L * (1 - c)

The maximum matchable back stake is constrained by:
    - best_back_size (the liquidity at the crossed quote on the back side)
    - best_lay_size * L / B (the lay side expressed in back stake units)
    - the per-trade cap from config

Structure of `Cat1Opportunity` closely mirrors the Polymarket Opportunity
dataclass (kind / edge_gross / edge_net / feasibility_class / legs_hash)
so the frontend types can stay nearly identical.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass
from typing import Optional

import config
from betfair_client import BookSnapshot


log = logging.getLogger(__name__)


@dataclass
class Cat1Opportunity:
    kind: str                     # always 'cat1_crossed'
    market_id: str
    market_name: Optional[str]
    event_id: Optional[str]
    event_title: Optional[str]
    event_start_ts: Optional[float]
    selection_id: int
    selection_name: Optional[str]

    back_odds: float
    back_size: float
    lay_odds: float
    lay_size: float

    edge_gross: float
    edge_net: float
    commission_rate: float

    max_back_stake: float
    expected_profit: float
    expected_payout: float

    feasibility_class: str        # 'ghost' | 'catchable' | 'live'
    observed_ms: int

    legs_hash: str
    detected_ts: float

    def to_row(self) -> dict:
        return asdict(self)


def _legs_hash(market_id: str, selection_id: int, back_odds: float, lay_odds: float) -> str:
    key = f"{market_id}|{selection_id}|{round(back_odds, 4)}|{round(lay_odds, 4)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _max_stake(
    best_back_size: float,
    best_lay_size: float,
    back_odds: float,
    lay_odds: float,
    cap: float,
) -> float:
    if back_odds <= 0 or lay_odds <= 0:
        return 0.0
    lay_in_back_units = best_lay_size * lay_odds / back_odds
    return max(0.0, min(cap, best_back_size, lay_in_back_units))


def detect_category_1(
    snapshots: list[BookSnapshot],
    known_legs_hashes: Optional[set[str]] = None,
    previous_spread_ms: Optional[dict[str, int]] = None,
) -> list[Cat1Opportunity]:
    """Scan snapshots and emit Category-1 opportunities sorted by edge_net."""
    known = known_legs_hashes or set()
    prev_ms = previous_spread_ms or {}
    c = config.BETFAIR_COMMISSION
    min_edge = config.MIN_EDGE_NET
    safety = config.SAFETY_MARGIN
    ghost_ms = config.GHOST_THRESHOLD_MS
    per_trade_cap = config.PAPER_PER_TRADE_USD

    out: list[Cat1Opportunity] = []
    for s in snapshots:
        if s.best_back_odds is None or s.best_lay_odds is None:
            continue
        if s.best_back_size is None or s.best_lay_size is None:
            continue
        if s.best_back_odds < s.best_lay_odds:
            continue   # normal non-crossed book

        B = float(s.best_back_odds)
        L = float(s.best_lay_odds)
        if B <= 1.0 or L <= 1.0:
            continue

        edge_gross = (B - L) / L
        edge_net = edge_gross * (1.0 - c)
        if edge_net < min_edge:
            continue

        stake = _max_stake(float(s.best_back_size), float(s.best_lay_size),
                           B, L, per_trade_cap)
        if stake <= 0.0:
            continue

        expected_profit = stake * edge_net
        min_profit = max(1.0, safety * c * stake)
        if expected_profit < min_profit:
            continue

        expected_payout = stake + expected_profit

        lh = _legs_hash(s.market_id, s.selection_id, B, L)
        if lh in known:
            continue

        observed = prev_ms.get(lh, 0)
        if observed < ghost_ms:
            fclass = "ghost"
        elif observed < ghost_ms * 5:
            fclass = "catchable"
        else:
            fclass = "live"

        out.append(Cat1Opportunity(
            kind="cat1_crossed",
            market_id=s.market_id,
            market_name=s.market_name,
            event_id=s.event_id,
            event_title=s.event_name,
            event_start_ts=s.event_start_ts,
            selection_id=s.selection_id,
            selection_name=s.selection_name,
            back_odds=B,
            back_size=float(s.best_back_size),
            lay_odds=L,
            lay_size=float(s.best_lay_size),
            edge_gross=edge_gross,
            edge_net=edge_net,
            commission_rate=c,
            max_back_stake=stake,
            expected_profit=expected_profit,
            expected_payout=expected_payout,
            feasibility_class=fclass,
            observed_ms=observed,
            legs_hash=lh,
            detected_ts=s.snapshot_ts,
        ))

    out.sort(key=lambda o: o.edge_net, reverse=True)
    if out:
        log.info("detected %d Category-1 opps top edge=%.4f cls=%s",
                 len(out), out[0].edge_net, out[0].feasibility_class)
    return out
