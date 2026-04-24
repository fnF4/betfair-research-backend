"use client";

import { useEffect, useState } from "react";
import { api, type Opportunity } from "@/lib/api";
import { OpportunitiesTable } from "@/components/OpportunitiesTable";

export default function OpportunitiesPage() {
  const [opps, setOpps] = useState<Opportunity[]>([]);

  async function refresh() {
    const o = await api.opportunities({ limit: 500, hours: 72 });
    setOpps(o);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Opportunità rilevate (ultime 72h)</h1>
      <div className="bg-panel border border-line rounded-xl p-4 text-sm text-muted">
        <div className="text-[11px] uppercase tracking-wide mb-2">Come leggere le classi di feasibility</div>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong className="text-bad">ghost</strong> — spread crossed osservato per meno del soglia minima ({"<"} GHOST_MS). Non apribile dal retail: i market maker HFT la chiudono entro decine di ms.</li>
          <li><strong className="text-accent">catchable</strong> — spread persiste abbastanza a lungo da essere teoricamente eseguibile (5× soglia).</li>
          <li><strong className="text-warn">live</strong> — spread stabilmente crossed: o è un'inefficienza strutturale rara oppure errore del venditore.</li>
        </ul>
      </div>
      <OpportunitiesTable opps={opps} />
    </div>
  );
}
