"use client";

import Link from "next/link";
import { useState } from "react";
import type { Opportunity } from "@/lib/api";
import { fmtAgo, fmtPct, fmtUsd } from "@/lib/format";
import { FeasibilityBadge, KindBadge } from "./FeasibilityBadge";

type Filter = {
  only_tradeable: boolean;
  classFilter: "" | "catchable" | "ghost" | "live";
};

export function OpportunitiesTable({ opps }: { opps: Opportunity[] }) {
  const [f, setF] = useState<Filter>({ only_tradeable: false, classFilter: "" });

  const filtered = opps.filter((o) => {
    if (f.only_tradeable && o.feasibility_class === "ghost") return false;
    if (f.classFilter && o.feasibility_class !== f.classFilter) return false;
    return true;
  });

  return (
    <div className="bg-panel border border-line rounded-xl overflow-hidden">
      <div className="flex flex-wrap gap-3 items-center p-3 border-b border-line">
        <label className="text-xs text-muted flex items-center gap-2">
          <input
            type="checkbox"
            className="accent-accent"
            checked={f.only_tradeable}
            onChange={(e) => setF({ ...f, only_tradeable: e.target.checked })}
          />
          Solo tradeable (no ghost)
        </label>
        <div className="flex gap-1">
          {(["", "catchable", "live", "ghost"] as const).map((c) => (
            <button
              key={c || "all"}
              onClick={() => setF({ ...f, classFilter: c })}
              className={`text-xs px-2 py-1 rounded border ${
                f.classFilter === c ? "border-accent text-accent" : "border-line text-muted"
              }`}
            >
              {c || "tutti"}
            </button>
          ))}
        </div>
        <div className="text-xs text-muted ml-auto">{filtered.length} signal</div>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[11px] uppercase tracking-wide text-muted">
            <th className="text-left py-2 px-3">Tipo</th>
            <th className="text-left">Classe</th>
            <th className="text-left">Evento / Selection</th>
            <th className="text-right">Back</th>
            <th className="text-right">Lay</th>
            <th className="text-right">Edge netto</th>
            <th className="text-right">Size max</th>
            <th className="text-right">Profit atteso</th>
            <th className="text-right pr-3">Quando</th>
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 && (
            <tr>
              <td colSpan={9} className="text-center text-muted py-8">
                Nessun signal nel periodo.
              </td>
            </tr>
          )}
          {filtered.map((o) => (
            <tr key={o.id} className="border-t border-line hover:bg-white/[0.02]">
              <td className="py-2 px-3">
                <KindBadge kind={o.kind} />
              </td>
              <td>
                <FeasibilityBadge cls={o.feasibility_class} />
              </td>
              <td className="max-w-[320px]">
                <Link href={`/opportunities#${o.id}`} className="hover:underline">
                  <strong>{(o.event_title || o.market_name || "—").slice(0, 60)}</strong>
                  <div className="text-xs text-muted">{o.selection_name || `sel ${o.selection_id}`}</div>
                </Link>
              </td>
              <td className="text-right mono">{o.back_odds.toFixed(2)}</td>
              <td className="text-right mono">{o.lay_odds.toFixed(2)}</td>
              <td className="text-right mono text-accent">{fmtPct(o.edge_net)}</td>
              <td className="text-right mono">{fmtUsd(o.max_back_stake || 0)}</td>
              <td className="text-right mono text-good">{fmtUsd(o.expected_profit || 0)}</td>
              <td className="text-right pr-3 text-muted text-xs">{fmtAgo(o.ts)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
