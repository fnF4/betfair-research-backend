"use client";

import type { Portfolio } from "@/lib/api";
import { fmtPct, fmtUsd, fmtUsdSigned } from "@/lib/format";

/**
 * AnnualizedWidget: mostra il ritorno annualizzato estrapolato dal ritmo
 * corrente di profit realizzato.
 *
 * Formula: (realized / days_active) * 365 / total_capital
 *
 * Confidence level:
 *  - high: >= 7 giorni attivi + 10 trade chiusi
 *  - medium: >= 1 giorno + 3 trade chiusi
 *  - low: ha dati ma sample piccolo
 *  - insufficient_data: nessun trade chiuso
 */
export function AnnualizedWidget({ p }: { p: Portfolio | null }) {
  if (!p) return null;
  const s = p.summary;

  const daysActive = s.days_active ?? 0;
  const dailyRate = s.daily_rate_usd ?? 0;
  const annualizedPct = s.annualized_pct ?? 0;
  const annualizedUsd = s.annualized_usd ?? 0;
  const confidence = s.annualized_confidence ?? "insufficient_data";
  const nClosed = s.n_closed ?? 0;

  const hasData = confidence !== "insufficient_data" && nClosed > 0;

  // Color by sign + confidence
  let toneColor = "text-muted";
  let badgeClass = "bg-panel-2 text-muted";
  let badgeLabel = "—";
  if (confidence === "high") {
    toneColor = annualizedPct >= 0 ? "text-accent" : "text-bad";
    badgeClass = "bg-accent/15 text-accent";
    badgeLabel = "high confidence";
  } else if (confidence === "medium") {
    toneColor = annualizedPct >= 0 ? "text-accent" : "text-bad";
    badgeClass = "bg-warn/15 text-warn";
    badgeLabel = "medium confidence";
  } else if (confidence === "low") {
    toneColor = annualizedPct >= 0 ? "text-accent" : "text-bad";
    badgeClass = "bg-warn/15 text-warn";
    badgeLabel = "low confidence — sample piccolo";
  } else {
    badgeClass = "bg-panel-2 text-muted";
    badgeLabel = "dati insufficienti";
  }

  return (
    <div className="bg-panel border border-line rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] uppercase tracking-wide text-muted">
          Ritorno annualizzato (se il ritmo continua)
        </div>
        <div className={`text-[11px] px-2 py-0.5 rounded-full ${badgeClass}`}>
          {badgeLabel}
        </div>
      </div>
      {hasData ? (
        <>
          <div className="flex items-baseline gap-3 mb-2">
            <div className={`text-3xl font-semibold mono ${toneColor}`}>
              {fmtPct(annualizedPct, 2)}
            </div>
            <div className="text-sm text-muted mono">
              ({fmtUsdSigned(annualizedUsd)} / anno)
            </div>
          </div>
          <div className="flex justify-between text-xs text-muted mt-2">
            <span>Pace corrente: <span className="mono">{fmtUsdSigned(dailyRate)}/giorno</span></span>
            <span className="mono">{daysActive.toFixed(1)}g attivi · {nClosed} trade chiusi</span>
          </div>
        </>
      ) : (
        <>
          <div className="text-2xl font-semibold mono text-muted">—</div>
          <div className="text-xs text-muted mt-2">
            Servono almeno 1 giorno di attività e 3 trade chiusi per calcolare
            una stima affidabile del ritorno annualizzato.
          </div>
        </>
      )}
      <div className="text-[11px] text-muted mt-2">
        Estrapolazione lineare del realized P&L: assume ritmo costante, senza compounding.
        Stima indicativa per valutare se la strategia è profittevole long-term.
      </div>
    </div>
  );
}
