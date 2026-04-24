/**
 * Backend API client — Betfair variant.
 * Read-only. No method ever sends bets to Betfair.
 */

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    ...init,
    cache: "no-store",
    headers: { Accept: "application/json", ...(init?.headers || {}) },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status} on ${path}`);
  return r.json() as Promise<T>;
}

export const api = {
  health: () => getJson<HealthState>(`/api/health`),
  status: () => getJson<StatusState>(`/api/status`),
  metrics: (hours = 24) => getJson<Metrics>(`/api/metrics?hours=${hours}`),
  opportunities: (params: OppParams = {}) => {
    const qs = new URLSearchParams();
    if (params.limit) qs.set("limit", String(params.limit));
    if (params.only_tradeable) qs.set("only_tradeable", "true");
    if (params.feasibility_class) qs.set("feasibility_class", params.feasibility_class);
    if (params.kind) qs.set("kind", params.kind);
    if (params.hours) qs.set("hours", String(params.hours));
    return getJson<Opportunity[]>(`/api/opportunities?${qs.toString()}`);
  },
  opportunity: (id: number) => getJson<Opportunity>(`/api/opportunity/${id}`),
  markets: (limit = 100) => getJson<Market[]>(`/api/markets?limit=${limit}`),
  portfolio: () => getJson<Portfolio>(`/api/portfolio`),
  timeline: (hours = 24) => getJson<TimelineBucket[]>(`/api/timeline?hours=${hours}`),
  executionProvider: () => getJson<StatusState>(`/api/status`).then(s => s.execution_provider),
};

// --- Types ---------------------------------------------------------------

export type HealthStatus = "green" | "yellow" | "red";

export interface HealthState {
  status: HealthStatus;
  label: string;
  last_cycle_ago_sec: number | null;
  cycles_last_hour: number;
  cycles_last_24h: number;
  expected_cycles_hour: number;
  expected_cycles_24h: number;
  last_run_markets: number;
  last_run_opps: number;
  uptime_pct_24h: number;
  last_run_at?: number;
}

export interface StatusState {
  config: Record<string, any>;
  kill_switch: { active: boolean; source: string | null; reason: string | null };
  execution_provider: ProviderInfo;
  circuit_breakers: Record<string, any>;
  compliance: Record<string, boolean>;
}

export interface Metrics {
  hours: number;
  total_signals: number;
  unique_opportunities: number;
  tradeable_signals: number;
  by_kind: { kind: string; c: number; avg_edge: number; max_edge: number }[];
  by_feasibility: { cls: string; c: number }[];
  runs: { c: number; avg_markets: number; total_opps: number };
}

export interface OppParams {
  limit?: number;
  only_tradeable?: boolean;
  feasibility_class?: "ghost" | "catchable" | "live";
  kind?: "cat1_crossed";
  hours?: number;
}

export type FeasibilityClass = "ghost" | "catchable" | "live";

export interface Opportunity {
  id: number;
  ts: number;
  kind: "cat1_crossed";
  market_id: string;
  market_name: string | null;
  event_id: string | null;
  event_title: string | null;
  event_start_ts: number | null;
  selection_id: number;
  selection_name: string | null;

  back_odds: number;
  back_size: number | null;
  lay_odds: number;
  lay_size: number | null;

  edge_gross: number;
  edge_net: number;
  max_back_stake: number | null;
  expected_profit: number | null;
  expected_payout: number | null;
  commission_rate: number | null;

  feasibility_class: FeasibilityClass;
  observed_ms: number | null;
  legs_hash: string;
  opened: 0 | 1;
  simulated_only: 1;
}

export interface Market {
  market_id: string;
  market_name: string | null;
  event_name: string | null;
  last_ts: number;
  total_matched: number | null;
  tier: number | null;
}

export interface PaperPosition {
  id: number;
  kind: string;
  market_name: string | null;
  event_title: string | null;
  selection_name: string | null;
  back_odds: number;
  back_stake: number;
  lay_odds: number;
  lay_stake?: number;
  size_usd: number;
  entry_cost: number;
  mtm_value: number | null;
  unrealized?: number;
  realized_pnl?: number;
  exit_value?: number;
  close_reason?: string;
  opened_at: number;
  closed_at?: number;
  feasibility_at_open: string | null;
  expected_payout?: number;
  expected_profit?: number;
  entry_edge_net?: number;
}

export interface EquityPoint {
  ts: number;
  total_equity: number;
  realized_pnl_cumulative: number;
  unrealized_pnl: number;
  open_positions: number;
}

export interface Portfolio {
  summary: {
    total_capital: number;
    total_equity: number;
    total_pnl: number;
    total_pnl_pct: number;
    realized: number;
    unrealized: number;
    cash_used: number;
    cash_free: number;
    exposure_usd?: number;
    exposure_cap_usd?: number;
    exposure_pct?: number;
    n_open: number;
    n_closed: number;
    days_active?: number;
    daily_rate_usd?: number;
    annualized_usd?: number;
    annualized_pct?: number;
    annualized_confidence?: "high" | "medium" | "low" | "insufficient_data";
  };
  open_positions: PaperPosition[];
  closed_positions: PaperPosition[];
  equity_curve: EquityPoint[];
}

export interface TimelineBucket {
  bucket: number;
  c: number;
  avg_edge: number;
  n_tradeable: number;
}

export interface ProviderInfo {
  name: string;
  supports_live: boolean;
  status: string;
  description: string;
  limitations?: string[];
  reason?: string;
}
