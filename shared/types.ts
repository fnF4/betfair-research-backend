/**
 * Tipi condivisi tra frontend e backend (Betfair variant — documentativi).
 *
 * Il backend è in Python quindi questi tipi non sono importati direttamente,
 * ma servono come contratto API. I tipi runtime del frontend sono in
 * frontend/src/lib/api.ts.
 */

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
  selection_id: number;
  selection_name: string | null;
  back_odds: number;
  lay_odds: number;
  edge_gross: number;
  edge_net: number;
  max_back_stake: number | null;
  expected_profit: number | null;
  expected_payout: number | null;
  commission_rate: number | null;
  feasibility_class: FeasibilityClass;
  legs_hash: string;
  simulated_only: 1;
}
