import type { GraphEdge, GraphNode } from "./types";

export const SENTIMENT_COLOR: Record<string, string> = {
  positive: "#1d7a52",
  neutral: "#77756d",
  wary: "#b07b16",
  negative: "#b3382f",
};
const ENGAGED = "#2f6fb3";
const W = 1000, H = 560;
const LANES: [string, string][] = [["exec", "Exec"], ["director", "Director"], ["team", "Team"]];
const LANE_H = H / 3;

interface Pos { x: number; y: number }

export function layout(nodes: GraphNode[]): Map<string, Pos> {
  const pos = new Map<string, Pos>();
  const laneY = (lane: string) => LANE_H * (lane === "exec" ? 0 : lane === "director" ? 1 : 2);

  for (const [lane] of LANES) {
    const sellers = nodes.filter((n) => n.side === "seller" && n.lane === lane).sort((a, b) => b.events - a.events);
    sellers.forEach((n, i) => {
      pos.set(n.id, { x: 130, y: laneY(lane) + (LANE_H * (i + 1)) / (sellers.length + 1) });
    });
    const buyers = nodes.filter((n) => n.side === "buyer" && !n.ghost && n.lane === lane).sort((a, b) => a.id.localeCompare(b.id));
    buyers.forEach((n, i) => {
      const x = buyers.length === 1 ? 620 : 500 + (320 * i) / (buyers.length - 1);
      pos.set(n.id, { x, y: laneY(lane) + LANE_H / 2 });
    });
  }
  const ghosts = nodes.filter((n) => n.ghost);
  ghosts.forEach((n, i) => {
    pos.set(n.id, { x: 925, y: 90 + (i * (H - 180)) / Math.max(1, ghosts.length - 1 || 1) });
  });
  const unknownLane = nodes.filter((n) => !n.ghost && n.lane === "unknown");
  unknownLane.forEach((n, i) => pos.set(n.id, { x: 620, y: 60 + i * 50 }));
  return pos;
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

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block" }}>
      {LANES.map(([lane, label], i) => (
        <g key={lane}>
          <rect x={0} y={i * LANE_H + 2} width={W} height={LANE_H - 4} rx={8}
            fill={i % 2 ? "#f1efe9" : "#f5f3ee"} />
          <text x={12} y={i * LANE_H + 22} fontSize={11.5} fill="#8a887f">{label}</text>
        </g>
      ))}
      <text x={130} y={16} fontSize={11.5} fill="#8a887f" textAnchor="middle">Your team</text>
      {nodes.some((n) => n.ghost) && <text x={925} y={16} fontSize={11.5} fill="#8a887f" textAnchor="middle">Never engaged</text>}

      {edges.map((e) => {
        const a = pos.get(e.a), b = pos.get(e.b);
        if (!a || !b) return null;
        return (
          <line key={`${e.a}-${e.b}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke="#96938a"
            strokeWidth={Math.min(1 + e.weight / 3, 6)}
            strokeOpacity={Math.max(0.18, 1 - e.days_stale / 30)} />
        );
      })}

      {nodes.map((n) => {
        const p = pos.get(n.id);
        if (!p) return null;
        const engaged = n.events > 0;
        const fill = n.ghost ? "transparent"
          : !engaged ? "transparent"
          : n.side === "seller" ? "#5a6b7d"
          : showSentiment ? SENTIMENT_COLOR[n.sentiment] : ENGAGED;
        const stroke = n.ghost ? "#b07b16" : engaged ? "none" : "#b07b16";
        const r = n.ghost ? 15 : Math.min(16 + n.events, 26);
        return (
          <g key={n.id} style={{ cursor: "pointer" }} onClick={() => onSelect(n.id === selected ? null : n.id)}>
            {selected === n.id && <circle cx={p.x} cy={p.y} r={r + 5} fill="none" stroke="#2f6fb3" strokeWidth={2} />}
            <circle cx={p.x} cy={p.y} r={r} fill={fill}
              stroke={stroke} strokeWidth={1.4}
              strokeDasharray={n.ghost || !engaged ? "4 3" : undefined} />
            {n.ghost && <text x={p.x} y={p.y + 4} fontSize={12} fill="#b07b16" textAnchor="middle">?</text>}
            {!n.ghost && engaged && (
              <text x={p.x} y={p.y + 4} fontSize={10.5} fill="#fff" textAnchor="middle">
                {n.name.split(" ").map((w) => w[0]).join("").slice(0, 2)}
              </text>
            )}
            <text x={p.x} y={p.y + r + 14} fontSize={11.5} fill="#3c3a34" textAnchor="middle" fontWeight={500}>
              {n.name.split(" ")[0]}{n.title ? ` · ${shortTitle(n.title)}` : ""}
            </text>
            {(n.ghost || !engaged) && (
              <text x={p.x} y={p.y + r + 27} fontSize={10.5} fill="#b07b16" textAnchor="middle">
                {n.ghost ? `mentioned ${n.mentions ?? 1}x` : "0 contacts"}
              </text>
            )}
            {!n.ghost && engaged && n.side === "buyer" && n.momentum === "cooling" && (n.quiet_days ?? 0) > 7 && (
              <text x={p.x} y={p.y + r + 27} fontSize={10.5} fill="#b3382f" textAnchor="middle">
                quiet {n.quiet_days}d
              </text>
            )}
            {showMomentum && engaged && !n.ghost && n.momentum !== "flat" && (
              <path
                d={n.momentum === "rising"
                  ? `M ${p.x + r + 6} ${p.y + 4} l 5 -9 l 5 9 z`
                  : `M ${p.x + r + 6} ${p.y - 5} l 5 9 l 5 -9 z`}
                fill={n.momentum === "rising" ? "#1d7a52" : "#b3382f"} />
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
