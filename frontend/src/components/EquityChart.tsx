"use client";

import type { EquityPoint } from "@/lib/api";
import { fmtUsd, fmtUsdSigned } from "@/lib/format";

export function EquityChart({ curve, baseCapital }: { curve: EquityPoint[]; baseCapital: number }) {
  if (!curve || curve.length === 0) {
    return (
      <div className="bg-panel border border-line rounded-xl p-4">
        <div className="text-[11px] uppercase tracking-wide text-muted mb-2">Equity curve</div>
        <div className="h-[180px] flex items-center justify-center text-muted text-sm">in attesa di dati…</div>
      </div>
    );
  }

  const W = 1000, H = 180, PAD = 4;
  const values = curve.map((p) => p.total_equity);
  const minV = Math.min(...values, baseCapital);
  const maxV = Math.max(...values, baseCapital);
  const range = Math.max(maxV - minV, baseCapital * 0.002);
  const scaleX = (i: number) => PAD + (i / Math.max(1, curve.length - 1)) * (W - 2 * PAD);
  const scaleY = (v: number) => H - PAD - ((v - minV) / range) * (H - 2 * PAD);

  let d = "";
  curve.forEach((p, i) => {
    d += (i ? "L" : "M") + scaleX(i).toFixed(1) + "," + scaleY(p.total_equity).toFixed(1) + " ";
  });
  const fillD = "M" + scaleX(0).toFixed(1) + "," + H + " " + d.substring(1) + " L" + scaleX(curve.length - 1).toFixed(1) + "," + H + " Z";

  const first = curve[0].total_equity;
  const last = curve[curve.length - 1].total_equity;
  const delta = last - first;

  return (
    <div className="bg-panel border border-line rounded-xl p-4">
      <div className="text-[11px] uppercase tracking-wide text-muted mb-2">Equity curve (paper trading)</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-[180px]" preserveAspectRatio="none">
        <defs>
          <linearGradient id="gradPos" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#3ad29f" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#3ad29f" stopOpacity={0} />
          </linearGradient>
        </defs>
        <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="#232a31" strokeDasharray="3 3" />
        <path d={fillD} fill="url(#gradPos)" opacity={0.3} />
        <path d={d} fill="none" stroke="#3ad29f" strokeWidth={2} />
      </svg>
      <div className="text-xs text-muted mt-2">
        {curve.length} punti · da {fmtUsd(first)} a {fmtUsd(last)} ({fmtUsdSigned(delta)})
      </div>
    </div>
  );
}
