import { useEffect, useRef } from "react";
import { SENTIMENT_COLOR, sellerColors } from "./StakeholderGraph";
import type { DealBundle, Event, GraphNode } from "./types";

const CHANNEL_LABEL: Record<string, string> = {
  zoom: "CALL", gmail: "MAIL", slack: "SLACK", salesforce: "CRM",
};

function sellerAbsenceNote(title: string): string {
  if (title.includes("Solutions")) return "Zero contacts means every technical question the buyer asks is being answered by sales instead of an engineer.";
  if (title.includes("VP")) return "Zero contacts means no exec-to-exec relationship exists if this deal needs leverage or unblocking.";
  return "Zero contacts on a deal they are rostered for.";
}

function snippet(e: Event): string {
  if (e.type === "meeting") return `${e.content.topic} (${e.content.duration_min} min)`;
  if (e.channel === "gmail") return `${e.content.subject}: ${e.content.body ?? ""}`;
  return e.content.text ?? "";
}

export function ContactPanel({ bundle, node, cutoff, highlightEvent, onClose }: {
  bundle: DealBundle;
  node: GraphNode;
  cutoff: string;
  highlightEvent: string | null;
  onClose: () => void;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  const isGhost = node.ghost;
  const events = bundle.events.events.filter((e) =>
    e.ts.slice(0, 10) <= cutoff &&
    (isGhost ? (node.mention_events ?? []).includes(e.id) : e.participants.includes(node.id)));
  const signalsByEvent = new Map<string, { tag: string; quote: string }[]>();
  for (const s of bundle.insights.signals) {
    if (!isGhost && s.who === node.id) {
      const list = signalsByEvent.get(s.event_id) ?? [];
      list.push(s);
      signalsByEvent.set(s.event_id, list);
    }
  }
  const insight = bundle.insights.people[node.id];
  const lastSnap = bundle.graph.snapshots[bundle.graph.snapshots.length - 1];
  const nameById = new Map(lastSnap.nodes.map((n) => [n.id, n.name.split(" ")[0]]));
  const repColor = sellerColors(lastSnap.nodes);
  const chip = (pid: string) => {
    const color = repColor.get(pid);
    return (
      <span key={pid} style={{
        fontSize: 10.5, fontWeight: 600, padding: "1px 7px", borderRadius: 999,
        background: color ? `${color}18` : "#f1f5f9",
        color: color ?? "#64748b",
        border: `1px solid ${color ? `${color}55` : "#e2e8f0"}`,
      }}>{nameById.get(pid) ?? pid}</span>
    );
  };

  useEffect(() => {
    if (highlightEvent && listRef.current) {
      listRef.current.querySelector(`[data-ev="${highlightEvent}"]`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [highlightEvent, node.id]);

  const color = SENTIMENT_COLOR[node.sentiment] ?? "#77756d";
  return (
    <div className="card panel">
      <div className="who">
        <div className="avatar" style={{ background: `${color}22`, color }}>
          {isGhost ? "?" : node.name.split(" ").map((w) => w[0]).join("").slice(0, 2)}
        </div>
        <div>
          <h2>{node.name}</h2>
          <div className="meta">
            {node.title || (isGhost ? "never engaged" : "title unknown")}
            {insight && <> · {insight.role.replace("_", " ")} · {insight.sentiment}</>}
            {!isGhost && !node.in_crm && node.side === "buyer" && <> · not in CRM</>}
          </div>
        </div>
        <span className="close" onClick={onClose}>×</span>
      </div>
      {insight?.sentiment_rationale && (
        <div className="rationale">{insight.sentiment_rationale}</div>
      )}
      {node.side === "seller" && node.events === 0 && (
        <div className="rationale">
          <div style={{ marginBottom: 6 }}>
            On the map from the Harborview team roster, not from this deal's
            conversations - drawn so their absence is visible.
          </div>
          <div>{sellerAbsenceNote(node.title)}</div>
        </div>
      )}
      {node.side === "seller" && node.events > 0 && (
        <div className="rationale">
          Your team - on the map because they appear in {node.events} conversation
          {node.events > 1 ? "s" : ""} on this deal.
        </div>
      )}
      {isGhost && (
        <div className="rationale">
          <div style={{ marginBottom: 6 }}>
            Never on a call, email, or Slack. This person exists on the map only because
            the conversations below referred to them:
          </div>
          {(node.mention_contexts ?? []).map((ctx, i) => (
            <div key={i} style={{ marginBottom: 4 }}>· "{ctx}"</div>
          ))}
        </div>
      )}
      <div ref={listRef}>
        {events.length === 0 && <div className="empty">No activity before {cutoff}</div>}
        {events.map((e) => (
          <div key={e.id} data-ev={e.id} className={`tev${highlightEvent === e.id ? " hilite" : ""}`}>
            <span className="ico">{CHANNEL_LABEL[e.channel] ?? e.channel}</span>
            <div className="body">
              <div className="when" style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
                <span>
                  {new Date(e.ts).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  {e.channel === "gmail" && e.content.from === node.id && " · sent"}
                  {e.channel === "gmail" && e.content.from !== node.id && !isGhost && " · received"}
                </span>
                {e.participants.map(chip)}
              </div>
              <div className="snippet">{snippet(e).slice(0, 180)}</div>
              <div className="tags">
                {isGhost && <span className="tag" style={{ background: "#fffbeb", color: "#b45309" }}>mentioned here</span>}
                {(signalsByEvent.get(e.id) ?? []).map((s, i) => (
                  <span key={i} className="tag" title={s.quote}>{s.tag.replace(/_/g, " ")}</span>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
