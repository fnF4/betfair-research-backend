"use client";

import type { Portfolio } from "@/lib/api";
import { fmtPct, fmtUsd } from "@/lib/format";

/**
 * ExposureWidget: mostra l'esposizione di capitale live vs il cap di sicurezza.
 *
 * Esposizione = sum(entry_cost) di posizioni aperte.
 * Cap = PAPER_TOTAL_CAPITAL_USD + realized_pnl_cumulative.
 *
 * Color coding:
 *  - verde: 0-70% del cap
 *  - giallo: 70-90%
 *  - rosso: >90%
 */
export function ExposureWidget({ p }: { p: Portfolio | null }) {
  if (!p) return null;
  const s = p.summary;

  // Fallback se backend non ha ancora i nuovi campi
  const exposure = s.exposure_usd ?? s.cash_used ?? 0;
  const cap = s.exposure_cap_usd ?? s.total_capital ?? 10000;
  const pct = s.exposure_pct ?? (cap > 0 ? exposure / cap : 0);
  const cashFree = Math.max(0, cap - exposure);

  // Determina colore in base alla soglia
  let barColor = "bg-accent";
  let tone: "ok" | "warn" | "bad" = "ok";
  if (pct >= 0.9) {
    barColor = "bg-bad";
    tone = "bad";
  } else if (pct >= 0.7) {
    barColor = "bg-warn";
    tone = "warn";
  }

  const toneLabel = tone === "bad"
    ? "ALTO — cap vicino"
    : tone === "warn"
    ? "moderato"
    : "sicuro";

  const barWidth = `${Math.min(100, Math.max(0, pct * 100)).toFixed(1)}%`;

  return (
    <div className="bg-panel border border-line rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="text-[11px] uppercase tracking-wide text-muted">
          Esposizione di capitale live
        </div>
        <div
          className={`text-[11px] px-2 py-0.5 rounded-full ${
            tone === "bad"
              ? "bg-bad/15 text-bad"
              : tone === "warn"
              ? "bg-warn/15 text-warn"
              : "bg-accent/15 text-accent"
          }`}
        >
          {toneLabel}
        </div>
      </div>
      <div className="flex items-baseline gap-2 mb-3">
        <div className="text-2xl font-semibold mono">{fmtUsd(exposure)}</div>
        <div className="text-sm text-muted mono">/ {fmtUsd(cap)}</div>
        <div className={`text-sm mono ml-auto ${
          tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : "text-accent"
        }`}>
          {fmtPct(pct, 1)}
        </div>
      </div>
      {/* Progress bar */}
      <div className="w-full h-2 bg-panel-2 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all ${barColor}`}
          style={{ width: barWidth }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted mt-2 mono">
        <span>Libero: {fmtUsd(cashFree)}</span>
        <span>{s.n_open} posizioni aperte</span>
      </div>
      <div className="text-[11px] text-muted mt-1">
        Cap = $10k base + realized cumulativo ({fmtUsd(s.realized)})
      </div>
    </div>
  );
}
