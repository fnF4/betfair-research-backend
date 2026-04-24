"use client";

import { useEffect, useState } from "react";
import { api, type HealthState, type Opportunity, type Portfolio } from "@/lib/api";
import { HealthWidget } from "@/components/HealthWidget";
import { PaperStats } from "@/components/PaperStats";
import { ExposureWidget } from "@/components/ExposureWidget";
import { AnnualizedWidget } from "@/components/AnnualizedWidget";
import { EquityChart } from "@/components/EquityChart";
import { OpportunitiesTable } from "@/components/OpportunitiesTable";
import { OpenPositionsTable, ClosedPositionsTable } from "@/components/PositionsTables";

export default function Dashboard() {
  const [health, setHealth] = useState<HealthState | null>(null);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  async function refresh() {
    try {
      const [h, p, o] = await Promise.all([
        api.health(),
        api.portfolio(),
        api.opportunities({ limit: 100 }),
      ]);
      setHealth(h);
      setPortfolio(p);
      setOpps(o);
      setLastUpdate(new Date());
      setErr(null);
    } catch (e: any) {
      setErr(String(e?.message || e));
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <div className="text-xs text-muted">
          {err ? <span className="text-bad">Errore: {err}</span> : lastUpdate ? `aggiornato ${lastUpdate.toLocaleTimeString()}` : "—"}
        </div>
      </div>

      <HealthWidget h={health} />
      <PaperStats p={portfolio} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ExposureWidget p={portfolio} />
        <AnnualizedWidget p={portfolio} />
      </div>
      <EquityChart curve={portfolio?.equity_curve || []} baseCapital={portfolio?.summary.total_capital || 10000} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <OpenPositionsTable rows={portfolio?.open_positions || []} />
        <ClosedPositionsTable rows={portfolio?.closed_positions || []} />
      </div>

      <OpportunitiesTable opps={opps} />
    </div>
  );
}
