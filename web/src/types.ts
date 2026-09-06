export interface Deal {
  name: string;
  account: string;
  amount: number;
  stage: string;
  close_date: string;
}

export interface GraphNode {
  id: string;
  name: string;
  title: string;
  side: "buyer" | "seller";
  lane: "exec" | "director" | "team" | "unknown";
  role: string;
  sentiment: "positive" | "neutral" | "wary" | "negative";
  momentum: "rising" | "flat" | "cooling";
  events: number;
  quiet_days: number | null;
  in_crm: boolean;
  ghost: boolean;
  named?: boolean;
  mentions?: number;
  mention_events?: string[];
  mention_contexts?: string[];
}

export interface GraphEdge {
  a: string;
  b: string;
  weight: number;
  days_stale: number;
}

export interface Flag {
  id: string;
  severity: "high" | "med" | "low";
  summary: string;
  evidence: string[];
  suggested_move: string;
}

export interface Rollup {
  thread_score: number;
  engaged_buyers: number;
  highest_lane: string;
  open_flags: number;
  top_severity: "high" | "med" | "low" | "none";
}

export interface Snapshot {
  t: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  flags: Flag[];
  rollup: Rollup;
}

export interface GraphFile {
  deal: Deal;
  snapshots: Snapshot[];
}

export interface Event {
  id: string;
  deal_id: string;
  channel: string;
  type: string;
  ts: string;
  participants: string[];
  direction: string;
  thread_key: string;
  content: {
    topic?: string;
    duration_min?: number;
    transcript?: { ts: string; speaker: string; text: string }[];
    subject?: string;
    from?: string;
    body?: string;
    text?: string;
    stage?: string;
  };
}

export interface EventsFile {
  deal: Deal;
  events: Event[];
}

export interface PersonInsight {
  role: string;
  role_rationale?: string;
  seniority: string;
  seniority_rationale?: string;
  sentiment: string;
  sentiment_rationale?: string;
  evidence?: string[];
  stats: { events: number; last_touch: string; quiet_days: number; momentum: string };
}

export interface Signal {
  event_id: string;
  tag: string;
  who: string;
  quote: string;
}

export interface InsightsFile {
  deal: Deal;
  people: Record<string, PersonInsight>;
  signals: Signal[];
  commitments: {
    by: string; to?: string; what: string; due?: string;
    status: string; origin_event: string;
  }[];
  ghosts: { name?: string; label: string; named: boolean; count: number; events: string[] }[];
}

export interface DealBundle {
  slug: string;
  graph: GraphFile;
  events: EventsFile;
  insights: InsightsFile;
}
