"use client";

import type { HealthState } from "@/lib/api";
import { fmtSec } from "@/lib/format";

export function HealthWidget({ h }: { h: HealthState | null }) {
  if (!h) return null;
  const color =
    h.status === "green"
      ? "bg-accent"
      : h.status === "yellow"
      ? "bg-warn"
      : "bg-bad";
  return (
    <div className="bg-panel border border-line rounded-xl p-4">
      <div className="flex flex-wrap gap-6 items-center justify-between">
        <div className="flex items-center gap-4">
          <span className={`inline-block w-3 h-3 rounded-full ${color}`} />
          <div>
            <div className="text-sm">
              Scanner <strong>{h.status.toUpperCase()}</strong>
            </div>
            <div className="text-xs text-muted">{h.label}</div>
          </div>
        </div>
        <div className="text-xs text-muted flex gap-6">
          <div>
            Ultimo ciclo: <span className="mono">{h.last_cycle_ago_sec != null ? fmtSec(h.last_cycle_ago_sec) + " fa" : "—"}</span>
          </div>
          <div>
            Cicli ultima ora: <span className="mono">{h.cycles_last_hour}</span> / {h.expected_cycles_hour}
          </div>
          <div>
            Uptime 24h: <span className="mono">{h.uptime_pct_24h}%</span>
          </div>
        </div>
        <div className="text-xs text-muted">
          Mercati ultimo: <strong className="mono">{h.last_run_markets}</strong> · Signal: <strong className="mono">{h.last_run_opps}</strong>
        </div>
      </div>
    </div>
  );
}
