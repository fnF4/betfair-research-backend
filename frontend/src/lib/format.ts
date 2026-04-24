export const fmtPct = (v: number | null | undefined, dp = 2) => {
  if (v == null || isNaN(v)) return "—";
  return (v * 100).toFixed(dp) + "%";
};

export const fmtUsd = (v: number | null | undefined, dp = 2) => {
  if (v == null || isNaN(v)) return "—";
  return "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: dp });
};

export const fmtUsdSigned = (v: number | null | undefined) => {
  if (v == null || isNaN(v)) return "—";
  const sign = v >= 0 ? "+" : "−";
  return sign + "$" + Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
};

export const fmtAgo = (tsSec: number | null | undefined) => {
  if (!tsSec) return "—";
  const d = Date.now() / 1000 - tsSec;
  if (d < 60) return Math.floor(d) + "s fa";
  if (d < 3600) return Math.floor(d / 60) + "min fa";
  if (d < 86400) return Math.floor(d / 3600) + "h fa";
  return Math.floor(d / 86400) + "g fa";
};

export const fmtSec = (s: number | null | undefined) => {
  if (s == null) return "—";
  if (s < 60) return s + "s";
  if (s < 3600) return Math.floor(s / 60) + "min";
  if (s < 86400) return Math.floor(s / 3600) + "h";
  return Math.floor(s / 86400) + "g";
};
