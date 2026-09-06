import type { GraphEdge, GraphNode } from "./types";

export const SENTIMENT_COLOR: Record<string, string> = {
  positive: "#16a34a",
  neutral: "#64748b",
  wary: "#d97706",
  negative: "#dc2626",
};
const ENGAGED = "#3b82f6";
const W = 1000, H = 604;
const LANES: [string, string][] = [["exec", "Exec"], ["director", "Director"], ["team", "Team"]];
const LANE_TOP = 26;
const LANE_H = 186;

interface Pos { x: number; y: number }

export function layout(nodes: GraphNode[]): Map<string, Pos> {
  const pos = new Map<string, Pos>();
  const laneY = (lane: string) => LANE_TOP + LANE_H * (lane === "exec" ? 0 : lane === "director" ? 1 : 2);

  for (const [lane] of LANES) {
    const sellers = nodes.filter((n) => n.side === "seller" && n.lane === lane).sort((a, b) => b.events - a.events);
    sellers.forEach((n, i) => {
      const frac = sellers.length === 1 ? 0.5 : 0.26 + (0.48 * i) / (sellers.length - 1);
      pos.set(n.id, { x: i % 2 ? 205 : 105, y: laneY(lane) + LANE_H * frac });
    });
    const buyers = nodes.filter((n) => n.side === "buyer" && !n.ghost && n.lane === lane).sort((a, b) => a.id.localeCompare(b.id));
    buyers.forEach((n, i) => {
      const x = buyers.length === 1 ? 620 : 500 + (320 * i) / (buyers.length - 1);
      pos.set(n.id, { x, y: laneY(lane) + LANE_H / 2 });
    });
  }
  const ghosts = nodes.filter((n) => n.ghost);
  ghosts.forEach((n, i) => {
    pos.set(n.id, { x: 925, y: 110 + (i * (H - 240)) / Math.max(1, ghosts.length - 1 || 1) });
  });
  const unknownLane = nodes.filter((n) => !n.ghost && n.lane === "unknown");
  unknownLane.forEach((n, i) => pos.set(n.id, { x: 620, y: 60 + i * 50 }));
  return pos;
}

export const EDGE_PALETTE = ["#3b82f6", "#14b8a6", "#8b5cf6", "#f59e0b"];

export function sellerColors(nodes: GraphNode[]): Map<string, string> {
  const sellers = nodes.filter((n) => n.side === "seller").sort((a, b) => a.id.localeCompare(b.id));
  return new Map(sellers.map((n, i) => [n.id, EDGE_PALETTE[i % EDGE_PALETTE.length]]));
}

export function StakeholderGraph({ nodes, edges, showSentiment, showMomentum, selected, onSelect }: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  showSentiment: boolean;
  showMomentum: boolean;
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const pos = layout(nodes);
  const edgeColor = sellerColors(nodes);
  const connected = new Set<string>();
  if (selected) {
    connected.add(selected);
    for (const e of edges) {
      if (e.a === selected) connected.add(e.b);
      if (e.b === selected) connected.add(e.a);
    }
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {LANES.map(([lane, label], i) => (
        <g key={lane}>
          <rect x={0} y={LANE_TOP + i * LANE_H + 2} width={W} height={LANE_H - 4} rx={8}
            fill={i % 2 ? "#eef2f7" : "#f4f7fb"} />
          <text x={12} y={LANE_TOP + i * LANE_H + 22} fontSize={11.5} fill="#94a3b8">{label}</text>
        </g>
      ))}
      <text x={130} y={16} fontSize={11.5} fill="#94a3b8" textAnchor="middle">Your team</text>
      {nodes.some((n) => n.ghost) && <text x={925} y={16} fontSize={11.5} fill="#94a3b8" textAnchor="middle">Never engaged</text>}

      {edges.map((e) => {
        const a = pos.get(e.a), b = pos.get(e.b);
        if (!a || !b) return null;
        const color = edgeColor.get(e.a) ?? edgeColor.get(e.b) ?? "#94a3b8";
        const touching = !selected || e.a === selected || e.b === selected;
        const base = Math.max(0.2, 1 - e.days_stale / 30);
        return (
          <line key={`${e.a}-${e.b}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke={color}
            strokeWidth={Math.min(1 + e.weight / 3, 6)}
            strokeOpacity={touching ? base * 0.75 : 0.05} />
        );
      })}

      {nodes.map((n) => {
        const p = pos.get(n.id);
        if (!p) return null;
        const engaged = n.events > 0;
        const fill = n.ghost ? "transparent"
          : !engaged ? "transparent"
          : n.side === "seller" ? "#16304f"
          : showSentiment ? SENTIMENT_COLOR[n.sentiment] : ENGAGED;
        const stroke = n.ghost ? "#d97706" : engaged ? "none" : "#d97706";
        const r = n.ghost ? 15 : Math.min(16 + n.events, 26);
        const dimmed = selected !== null && !connected.has(n.id);
        return (
          <g key={n.id} style={{ cursor: "pointer" }} opacity={dimmed ? 0.25 : 1}
            onClick={() => onSelect(n.id === selected ? null : n.id)}>
            {selected === n.id && <circle cx={p.x} cy={p.y} r={r + 5} fill="none" stroke="#2f6fb3" strokeWidth={2} />}
            <circle cx={p.x} cy={p.y} r={r} fill={fill}
              stroke={stroke} strokeWidth={1.4}
              strokeDasharray={n.ghost || !engaged ? "4 3" : undefined} />
            {n.ghost && <text x={p.x} y={p.y + 4} fontSize={12} fill="#d97706" textAnchor="middle">?</text>}
            {!n.ghost && engaged && (
              <text x={p.x} y={p.y + 4} fontSize={10.5} fill="#fff" textAnchor="middle">
                {n.name.split(" ").map((w) => w[0]).join("").slice(0, 2)}
              </text>
            )}
            <text x={p.x} y={p.y + r + 14} fontSize={11.5} fill="#334155" textAnchor="middle" fontWeight={500}
              style={{ paintOrder: "stroke" }} stroke="#ffffff" strokeWidth={3.5} strokeLinejoin="round">
              {n.name.split(" ")[0]}{n.title ? ` · ${shortTitle(n.title)}` : ""}
            </text>
            {(n.ghost || !engaged) && (
              <text x={p.x} y={p.y + r + 27} fontSize={10.5} fill="#d97706" textAnchor="middle"
                style={{ paintOrder: "stroke" }} stroke="#ffffff" strokeWidth={3.5} strokeLinejoin="round">
                {n.ghost ? `mentioned ${n.mentions ?? 1}x` : "0 contacts"}
              </text>
            )}
            {!n.ghost && engaged && n.side === "buyer" && n.momentum === "cooling" && (n.quiet_days ?? 0) > 7 && (
              <text x={p.x} y={p.y + r + 27} fontSize={10.5} fill="#dc2626" textAnchor="middle"
                style={{ paintOrder: "stroke" }} stroke="#ffffff" strokeWidth={3.5} strokeLinejoin="round">
                quiet {n.quiet_days}d
              </text>
            )}
            {showMomentum && engaged && !n.ghost && n.momentum !== "flat" && (
              <path
                d={n.momentum === "rising"
                  ? `M ${p.x + r + 6} ${p.y + 4} l 5 -9 l 5 9 z`
                  : `M ${p.x + r + 6} ${p.y - 5} l 5 9 l 5 -9 z`}
                fill={n.momentum === "rising" ? "#16a34a" : "#dc2626"} />
            )}
          </g>
        );
      })}
    </svg>
  );
}

function shortTitle(title: string): string {
  return title
    .replace("Director of Operations", "dir. ops").replace("Director of IT", "dir. IT")
    .replace("Director of Engineering", "dir. eng").replace("Account Executive", "AE")
    .replace("Solutions Engineer", "SE").replace("Business Analyst", "analyst")
    .replace("Engineering Lead", "eng lead").replace("Procurement Manager", "procurement")
    .replace("Operations Manager", "ops mgr").replace("Team Coordinator", "coordinator")
    .replace("VP Sales", "VP sales");
}
