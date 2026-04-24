"use client";

import type { PaperPosition } from "@/lib/api";
import { fmtAgo, fmtUsd, fmtUsdSigned } from "@/lib/format";
import { KindBadge } from "./FeasibilityBadge";

export function OpenPositionsTable({ rows }: { rows: PaperPosition[] }) {
  return (
    <div className="bg-panel border border-line rounded-xl overflow-hidden">
      <div className="px-3 py-2 text-[11px] uppercase tracking-wide text-muted border-b border-line">
        Posizioni aperte ({rows.length})
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted">
            <th className="text-left py-2 px-3">Tipo</th>
            <th className="text-left">Evento</th>
            <th className="text-right">Size</th>
            <th className="text-right">Entry cost</th>
            <th className="text-right">MtM</th>
            <th className="text-right" title="Mark-to-bid corrente (spesso negativo per lo spread)">
              Unrealized
            </th>
            <th className="text-right" title="Profit GARANTITO a resolution se arb valida">
              Profit atteso
            </th>
            <th className="text-right pr-3">Aperto</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={8} className="text-center text-muted py-8">
                Nessuna posizione aperta.
              </td>
            </tr>
          )}
          {rows.map((p) => {
            const unr = p.unrealized ?? 0;
            const expProfit = p.expected_profit ?? 0;
            return (
              <tr key={p.id} className="border-t border-line hover:bg-white/[0.02]">
                <td className="py-2 px-3">
                  <KindBadge kind={p.kind} />
                </td>
                <td>
                  <div>{(p.event_title || p.market_name || "—").slice(0, 60)}</div>
                  <div className="text-xs text-muted">
                    {p.selection_name || "?"} · B {p.back_odds?.toFixed(2)} / L {p.lay_odds?.toFixed(2)}
                  </div>
                </td>
                <td className="text-right mono">{fmtUsd(p.back_stake)}</td>
                <td className="text-right mono">{fmtUsd(p.entry_cost)}</td>
                <td className="text-right mono">{p.mtm_value != null ? fmtUsd(p.mtm_value) : "—"}</td>
                <td className={`text-right mono ${unr >= 0 ? "text-accent" : "text-bad"}`}>
                  {fmtUsdSigned(unr)}
                </td>
                <td className={`text-right mono ${expProfit >= 0 ? "text-accent" : "text-bad"}`}>
                  {fmtUsdSigned(expProfit)}
                </td>
                <td className="text-right pr-3 text-muted text-xs">{fmtAgo(p.opened_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ClosedPositionsTable({ rows }: { rows: PaperPosition[] }) {
  return (
    <div className="bg-panel border border-line rounded-xl overflow-hidden">
      <div className="px-3 py-2 text-[11px] uppercase tracking-wide text-muted border-b border-line">
        Trade chiusi ({rows.length})
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted">
            <th className="text-left py-2 px-3">Tipo</th>
            <th className="text-left">Evento</th>
            <th className="text-right">Size</th>
            <th className="text-right">P&L</th>
            <th className="text-left pl-4">Motivo</th>
            <th className="text-right">Hold</th>
            <th className="text-right pr-3">Chiuso</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} className="text-center text-muted py-8">
                Nessun trade chiuso ancora.
              </td>
            </tr>
          )}
          {rows.map((p) => {
            const pnl = p.realized_pnl ?? 0;
            const hold =
              p.opened_at && p.closed_at ? ((p.closed_at - p.opened_at) / 3600).toFixed(1) + "h" : "—";
            return (
              <tr key={p.id} className="border-t border-line hover:bg-white/[0.02]">
                <td className="py-2 px-3">
                  <KindBadge kind={p.kind} />
                </td>
                <td>
                  <div>{(p.event_title || p.market_name || "—").slice(0, 60)}</div>
                  <div className="text-xs text-muted">{p.selection_name || "?"}</div>
                </td>
                <td className="text-right mono">{fmtUsd(p.back_stake)}</td>
                <td className={`text-right mono ${pnl >= 0 ? "text-accent" : "text-bad"}`}>
                  {fmtUsdSigned(pnl)}
                </td>
                <td className="text-muted pl-4">{p.close_reason || "—"}</td>
                <td className="text-right mono text-muted">{hold}</td>
                <td className="text-right pr-3 text-muted text-xs">{fmtAgo(p.closed_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
