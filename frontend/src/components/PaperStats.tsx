"use client";

import type { Portfolio } from "@/lib/api";
import { fmtPct, fmtUsd, fmtUsdSigned } from "@/lib/format";

export function PaperStats({ p }: { p: Portfolio | null }) {
  if (!p) return null;
  const s = p.summary;
  const pnl = s.total_pnl ?? 0;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      <Card title="Equity totale simulata" value={fmtUsd(s.total_equity)} sub={`capitale base ${fmtUsd(s.total_capital)}`} />
      <Card
        title="P&L totale"
        value={fmtUsdSigned(pnl)}
        sub={`${fmtPct(s.total_pnl_pct)} vs capitale`}
        tone={pnl >= 0 ? "pos" : "neg"}
      />
      <Card
        title="P&L realizzato"
        value={fmtUsdSigned(s.realized)}
        sub={`${s.n_closed} trade chiusi`}
        tone={s.realized >= 0 ? "pos" : "neg"}
      />
      <Card title="Posizioni aperte" value={String(s.n_open)} sub={`unrealized ${fmtUsdSigned(s.unrealized)}`} />
    </div>
  );
}

function Card({ title, value, sub, tone }: { title: string; value: string; sub?: string; tone?: "pos" | "neg" }) {
  const cls = tone === "pos" ? "text-accent" : tone === "neg" ? "text-bad" : "";
  return (
    <div className="bg-panel border border-line rounded-xl p-4">
      <div className="text-[11px] uppercase tracking-wide text-muted mb-2">{title}</div>
      <div className={`text-2xl font-semibold mono ${cls}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}
