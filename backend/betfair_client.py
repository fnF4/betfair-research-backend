"""Thin wrapper around the Betfair Exchange API.

Uses `betfairlightweight` (community-standard Python SDK). Exposes:
- `BookSnapshot` — the minimal (market, selection, best back/lay) view
  needed for Category-1 arb detection.
- `BetfairClient` — session-lifetime wrapper with auto-login, keep-alive,
  and `fetch_books()` that returns a list of BookSnapshots.

No orders, no execution. Read-only.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import betfairlightweight
from betfairlightweight import filters
from betfairlightweight.exceptions import BetfairError as _LwBetfairError

import config


log = logging.getLogger(__name__)


class BetfairError(RuntimeError):
    """Wrapped error so upstream code never imports bflw types directly."""


@dataclass
class BookSnapshot:
    market_id: str
    market_name: Optional[str]
    event_id: Optional[str]
    event_name: Optional[str]
    event_start_ts: Optional[float]
    selection_id: int
    selection_name: Optional[str]
    best_back_odds: Optional[float]
    best_back_size: Optional[float]
    best_lay_odds: Optional[float]
    best_lay_size: Optional[float]
    total_matched: Optional[float]
    snapshot_ts: float


class BetfairClient:
    _SESSION_REFRESH_SECONDS = 15 * 60

    def __init__(self) -> None:
        self._trading: Optional[betfairlightweight.APIClient] = None
        self._last_keepalive_ts: float = 0.0

    # ------------------------------------------------------------------ auth

    # Where we materialize the cert/key from env vars (tempfs, not persisted).
    _CERT_DIR = "/tmp/betfair_certs"
    _CERT_FILE = "/tmp/betfair_certs/client-2048.crt"
    _KEY_FILE = "/tmp/betfair_certs/client-2048.key"

    def _materialize_certs_from_env(self) -> str | None:
        """If BETFAIR_CERT_PEM + BETFAIR_KEY_PEM env vars are set, write them
        to /tmp/betfair_certs/ and return that directory path. Returns None
        if env vars are empty (fall back to BETFAIR_CERT_PATH behaviour).
        """
        import os as _os
        cert_pem = _os.environ.get("BETFAIR_CERT_PEM", "").strip()
        key_pem = _os.environ.get("BETFAIR_KEY_PEM", "").strip()
        if not cert_pem or not key_pem:
            return None
        # Render env vars sometimes deliver newlines as literal '\n'. Normalise.
        cert_pem = cert_pem.replace("\\n", "\n")
        key_pem = key_pem.replace("\\n", "\n")
        _os.makedirs(self._CERT_DIR, exist_ok=True)
        with open(self._CERT_FILE, "w") as fh:
            fh.write(cert_pem if cert_pem.endswith("\n") else cert_pem + "\n")
        _os.chmod(self._CERT_FILE, 0o600)
        with open(self._KEY_FILE, "w") as fh:
            fh.write(key_pem if key_pem.endswith("\n") else key_pem + "\n")
        _os.chmod(self._KEY_FILE, 0o600)
        log.info("Betfair certs materialized in %s", self._CERT_DIR)
        return self._CERT_DIR

    def _build(self) -> betfairlightweight.APIClient:
        if not config.BETFAIR_USERNAME or not config.BETFAIR_PASSWORD:
            raise BetfairError("BETFAIR_USERNAME / BETFAIR_PASSWORD not set")
        if not config.BETFAIR_APP_KEY:
            raise BetfairError("BETFAIR_APP_KEY not set")

        kwargs: dict[str, Any] = dict(
            username=config.BETFAIR_USERNAME,
            password=config.BETFAIR_PASSWORD,
            app_key=config.BETFAIR_APP_KEY,
            locale=(config.BETFAIR_LOCALE or "").lower() or None,
        )
        if config.BETFAIR_USE_CERTS:
            cert_dir = self._materialize_certs_from_env()
            if cert_dir is None:
                if not config.BETFAIR_CERT_PATH or not config.BETFAIR_KEY_PATH:
                    raise BetfairError(
                        "BETFAIR_USE_CERTS=true but neither BETFAIR_CERT_PEM/"
                        "BETFAIR_KEY_PEM env vars nor BETFAIR_CERT_PATH/"
                        "BETFAIR_KEY_PATH file paths are set"
                    )
                cert_dir = config.BETFAIR_CERT_PATH
            kwargs["certs"] = cert_dir
            # Sanity check: betfairlightweight derives the cert/key tuple
            # from this directory and looks for files named EXACTLY
            # client-2048.crt and client-2048.key. Verify they're there.
            import os as _os
            for _name in ("client-2048.crt", "client-2048.key"):
                _path = _os.path.join(cert_dir, _name)
                if not _os.path.isfile(_path):
                    raise BetfairError(
                        f"Expected cert file not found: {_path}"
                    )
            log.info("Cert dir %s contains both .crt and .key", cert_dir)

        return betfairlightweight.APIClient(**kwargs)

    def _ensure(self) -> betfairlightweight.APIClient:
        if self._trading is None:
            self._trading = self._build()
            # DIAGNOSTIC LOGGING
            try:
                log.info(
                    "DEBUG client.certs=%r client.cert=%r locale=%r URL=%r",
                    self._trading.certs,
                    self._trading.cert,
                    self._trading.locale,
                    self._trading.identity_uri,
                )
            except Exception as _e:  # noqa: BLE001
                log.warning("debug log failed: %s", _e)
            try:
                if config.BETFAIR_USE_CERTS:
                    self._trading.login()
                else:
                    self._trading.login_interactive()
            except _LwBetfairError as exc:
                self._trading = None
                raise BetfairError(f"Betfair login failed: {exc}") from exc
            self._last_keepalive_ts = time.time()
            log.info("Betfair session established locale=%s certs=%s",
                     config.BETFAIR_LOCALE, config.BETFAIR_USE_CERTS)
            return self._trading

        if time.time() - self._last_keepalive_ts > self._SESSION_REFRESH_SECONDS:
            try:
                self._trading.keep_alive()
                self._last_keepalive_ts = time.time()
            except _LwBetfairError as exc:
                log.warning("keep_alive failed, re-login: %s", exc)
                self._trading = None
                return self._ensure()
        return self._trading

    def logout(self) -> None:
        if self._trading is not None:
            try:
                self._trading.logout()
            except Exception:  # noqa: BLE001
                pass
            self._trading = None

    # -------------------------------------------------------------- catalog

    def list_markets(
        self,
        event_type_ids: Iterable[int],
        horizon_hours: int,
        max_results: int,
    ) -> list[dict]:
        trading = self._ensure()
        now = datetime.now(timezone.utc)
        soon = now + timedelta(hours=horizon_hours)
        mf = filters.market_filter(
            event_type_ids=[str(x) for x in event_type_ids],
            market_start_time={
                "from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": soon.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            in_play_only=False,
            turn_in_play_enabled=True,
        )
        projection = [
            "COMPETITION", "EVENT", "EVENT_TYPE",
            "MARKET_DESCRIPTION", "RUNNER_DESCRIPTION", "MARKET_START_TIME",
        ]
        try:
            resp = trading.betting.list_market_catalogue(
                filter=mf,
                market_projection=projection,
                max_results=max_results,
                sort="MAXIMUM_TRADED",
            )
        except _LwBetfairError as exc:
            raise BetfairError(f"list_market_catalogue failed: {exc}") from exc
        return [m._data for m in resp]

    # -------------------------------------------------------------- books

    def list_books(self, market_ids: list[str]) -> list[dict]:
        if not market_ids:
            return []
        trading = self._ensure()
        price_proj = filters.price_projection(
            price_data=["EX_BEST_OFFERS"],
            ex_best_offers_overrides=filters.ex_best_offers_overrides(
                best_prices_depth=3,
                rollup_model="STAKE",
                rollup_limit=1,
            ),
            virtualise=True,
        )
        out: list[dict] = []
        CHUNK = 40  # Betfair API enforces <=40 markets per list_market_book
        for i in range(0, len(market_ids), CHUNK):
            batch = market_ids[i:i + CHUNK]
            try:
                resp = trading.betting.list_market_book(
                    market_ids=batch,
                    price_projection=price_proj,
                    order_projection="ALL",
                )
            except _LwBetfairError as exc:
                raise BetfairError(f"list_market_book failed: {exc}") from exc
            out.extend(b._data for b in resp)
        return out

    # -------------------------------------------------- book -> snapshots

    @staticmethod
    def _iso_to_ts(value: Any) -> Optional[float]:
        if not value:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
        return None

    @classmethod
    def snapshots_from_books(
        cls,
        books: list[dict],
        catalogue_by_id: dict[str, dict],
    ) -> list[BookSnapshot]:
        out: list[BookSnapshot] = []
        now = time.time()
        for book in books:
            mid = book.get("marketId")
            if not mid:
                continue
            cat = catalogue_by_id.get(mid, {})
            event = cat.get("event") or {}
            market_name = cat.get("marketName")
            event_id = event.get("id")
            event_name = event.get("name")
            event_start_ts = cls._iso_to_ts(event.get("openDate")) \
                or cls._iso_to_ts(cat.get("marketStartTime"))
            runners_meta = {r.get("selectionId"): r.get("runnerName")
                            for r in (cat.get("runners") or [])}
            total_matched = book.get("totalMatched")
            for runner in book.get("runners", []) or []:
                if runner.get("status") != "ACTIVE":
                    continue
                sel_id = runner.get("selectionId")
                ex = runner.get("ex") or {}
                backs = ex.get("availableToBack") or []
                lays = ex.get("availableToLay") or []
                best_back = backs[0] if backs else {}
                best_lay = lays[0] if lays else {}
                out.append(BookSnapshot(
                    market_id=str(mid),
                    market_name=market_name,
                    event_id=str(event_id) if event_id else None,
                    event_name=event_name,
                    event_start_ts=event_start_ts,
                    selection_id=int(sel_id),
                    selection_name=runners_meta.get(sel_id),
                    best_back_odds=best_back.get("price"),
                    best_back_size=best_back.get("size"),
                    best_lay_odds=best_lay.get("price"),
                    best_lay_size=best_lay.get("size"),
                    total_matched=total_matched,
                    snapshot_ts=now,
                ))
        return out


# Module-level singleton
client = BetfairClient()
