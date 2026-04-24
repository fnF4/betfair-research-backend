export function FeasibilityBadge({ cls }: { cls?: string | null }) {
  const map: Record<string, { label: string; color: string }> = {
    catchable: { label: "catchable", color: "bg-accent/15 text-accent" },
    live: { label: "live", color: "bg-warn/15 text-warn" },
    ghost: { label: "ghost", color: "bg-bad/15 text-bad" },
  };
  const it = cls ? map[cls] : undefined;
  if (!it) return <span className="inline-block px-2 py-0.5 rounded-full text-[11px] bg-panel-2 text-muted">—</span>;
  return <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] ${it.color}`}>{it.label}</span>;
}

export function KindBadge({ kind }: { kind?: string }) {
  const map: Record<string, { label: string; color: string }> = {
    cat1_crossed: { label: "cat1 · crossed", color: "bg-accent/15 text-accent" },
  };
  const it = kind ? map[kind] : { label: "?", color: "bg-panel-2 text-muted" };
  return (
    <span className="inline-flex gap-1">
      <span className={`inline-block px-2 py-0.5 rounded-full text-[11px] ${it.color}`}>{it.label}</span>
    </span>
  );
}
