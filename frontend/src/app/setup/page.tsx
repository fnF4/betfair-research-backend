"use client";

import { useEffect, useState } from "react";
import { api, type HealthState, type StatusState } from "@/lib/api";

type Check = { label: string; ok: boolean; detail: string };

export default function SetupPage() {
  const [status, setStatus] = useState<StatusState | null>(null);
  const [health, setHealth] = useState<HealthState | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function load() {
    try {
      const [s, h] = await Promise.all([api.status(), api.health()]);
      setStatus(s);
      setHealth(h);
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 15000);
    return () => clearInterval(id);
  }, []);

  const checks: Check[] = [];
  checks.push({
    label: "Backend raggiungibile",
    ok: status != null && err == null,
    detail: err ? err : "FastAPI ha risposto correttamente",
  });
  if (status) {
    checks.push({
      label: "Execution provider in modalità paper",
      ok: status.execution_provider?.name === "paper",
      detail: `provider: ${status.execution_provider?.name} · status: ${status.execution_provider?.status}`,
    });
    checks.push({
      label: "Compliance flags attive",
      ok: !!(
        status.compliance?.paper_only &&
        status.compliance?.no_wallet &&
        status.compliance?.no_order_submission
      ),
      detail: "paper_only + no_wallet + no_order_submission confermati",
    });
    checks.push({
      label: "Kill switch OFF (scan attivo)",
      ok: !status.kill_switch?.active,
      detail: status.kill_switch?.active
        ? `ATTIVO: ${status.kill_switch.reason}`
        : "Scan in esecuzione",
    });
    checks.push({
      label: "Betfair API reachable",
      ok: (status.circuit_breakers as any)?.betfair === "ok",
      detail: `betfair=${(status.circuit_breakers as any)?.betfair ?? "unknown"}`,
    });
    checks.push({
      label: "Betfair app key configured",
      ok: status.config?.betfair_app_key === "***set***",
      detail: `app_key=${status.config?.betfair_app_key ?? "?"} · user=${status.config?.betfair_username ?? "?"} · locale=${status.config?.betfair_locale ?? "?"}`,
    });
  }
  if (health) {
    checks.push({
      label: "Scanner sta girando (cicli recenti)",
      ok: health.status !== "red",
      detail: `status=${health.status} · ultimo ciclo ${health.last_cycle_ago_sec ?? "?"}s fa · cicli/ora=${health.cycles_last_hour}/${health.expected_cycles_hour}`,
    });
    checks.push({
      label: "Uptime 24h sufficiente (>70%)",
      ok: (health.uptime_pct_24h ?? 0) >= 70,
      detail: `uptime 24h=${health.uptime_pct_24h}%`,
    });
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Setup checklist</h1>
      <div className="text-sm text-muted">
        Stato dei componenti necessari al funzionamento del pilota. Tutti verdi = pronto.
      </div>
      <div className="bg-panel border border-line rounded-xl divide-y divide-line">
        {checks.map((c, i) => (
          <div key={i} className="flex items-start gap-3 p-4">
            <span
              className={`inline-block w-3 h-3 rounded-full mt-1.5 ${
                c.ok ? "bg-accent" : "bg-bad"
              }`}
            />
            <div className="flex-1">
              <div className="text-sm">{c.label}</div>
              <div className="text-xs text-muted mt-0.5">{c.detail}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-panel border border-line rounded-xl p-4 text-sm">
        <div className="font-semibold mb-2">Prossimi passi</div>
        <ol className="list-decimal pl-5 space-y-2 text-muted">
          <li>Se qualche check è rosso, guarda la colonna <code className="text-fg">detail</code> per capire cosa manca.</li>
          <li>Il README in <code className="text-fg">docs/DEPLOYMENT.md</code> ha la guida click-per-click per Render + Vercel.</li>
          <li>Per pausare lo scan senza spegnere il deploy, chiama <code className="text-fg">POST /api/admin/kill</code> con l'header <code className="text-fg">X-Admin-Secret</code>.</li>
        </ol>
      </div>
    </div>
  );
}
