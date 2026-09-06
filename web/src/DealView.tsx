import { useEffect, useState } from "react";
import { ContactPanel } from "./ContactPanel";
import { loadDeal } from "./data";
import { StakeholderGraph } from "./StakeholderGraph";
import type { DealBundle } from "./types";

export function DealView({ slug }: { slug: string }) {
  const [bundle, setBundle] = useState<DealBundle | null>(null);
  const [snapIdx, setSnapIdx] = useState<number | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [highlightEvent, setHighlightEvent] = useState<string | null>(null);
  const [showSentiment, setShowSentiment] = useState(true);
  const [showMomentum, setShowMomentum] = useState(true);

  useEffect(() => {
    setBundle(null);
    setSelected(null);
    loadDeal(slug).then(setBundle);
  }, [slug]);

  if (!bundle) return <div className="loading">Loading {slug}...</div>;

  const snaps = bundle.graph.snapshots;
  const idx = snapIdx ?? snaps.length - 1;
  const snap = snaps[idx];
  const deal = bundle.graph.deal;
  const selectedNode = snap.nodes.find((n) => n.id === selected) ?? null;

  const openEvidence = (eventId: string) => {
    const ev = bundle.events.events.find((e) => e.id === eventId);
    if (!ev) return;
    const buyer = ev.participants.find((p) =>
      snap.nodes.some((n) => n.id === p && n.side === "buyer"));
    setSelected(buyer ?? ev.participants[0] ?? null);
    setHighlightEvent(eventId);
  };

  return (
    <>
      <div className="topbar">
        <a className="back" href="#/">← Pipeline</a>
        <h1>{deal.name}</h1>
        <span className="sub">
          ${Math.round(deal.amount / 1000)}k · {deal.stage} · closes {deal.close_date}
        </span>
      </div>
      <div className="deal-grid">
        <div>
          <div className="card graph-card">
            <div className="graph-head">
              <span className="title">Stakeholder map · {fmtDate(snap.t)}</span>
              <div className="toggles">
                <label>
                  <input type="checkbox" checked={showSentiment}
                    onChange={(e) => setShowSentiment(e.target.checked)} /> sentiment
                </label>
                <label>
                  <input type="checkbox" checked={showMomentum}
                    onChange={(e) => setShowMomentum(e.target.checked)} /> momentum
                </label>
              </div>
            </div>
            <StakeholderGraph nodes={snap.nodes} edges={snap.edges}
              showSentiment={showSentiment} showMomentum={showMomentum}
              selected={selected}
              onSelect={(id) => { setSelected(id); setHighlightEvent(null); }} />
            <div className="legend">
              <span><Line w={3} /> active thread</span>
              <span><Line w={1.5} faded /> going stale</span>
              <span><Dashed /> never engaged / ghost</span>
              {showSentiment && <>
                <span><Dot c="#1d7a52" /> positive</span>
                <span><Dot c="#77756d" /> neutral</span>
                <span><Dot c="#b07b16" /> wary</span>
              </>}
              {showMomentum && <>
                <span><Tri up /> rising</span>
                <span><Tri /> cooling</span>
              </>}
            </div>
          </div>

          <div className="card slider-card">
            <span className="when">{fmtDate(snap.t)}</span>
            <input type="range" min={0} max={snaps.length - 1} value={idx}
              onChange={(e) => { setSnapIdx(Number(e.target.value)); setHighlightEvent(null); }} />
            <span className="hint">drag to replay the deal week by week</span>
          </div>

          <div className="flags">
            {snap.flags.length === 0 && (
              <div className="flag"><div className="summary">No risk flags at this point in the deal.</div></div>
            )}
            {snap.flags.map((f) => (
              <div key={f.id} className={`flag ${f.severity}`}>
                <div className="head">
                  <span className={`badge ${f.severity}`}>{f.severity}</span>
                  <span className="summary">{f.summary}</span>
                </div>
                <div className="move">Suggested move: {f.suggested_move}</div>
                {f.evidence.length > 0 && (
                  <div className="evidence">
                    {f.evidence.map((ev) => (
                      <span key={ev} className="ev" onClick={() => openEvidence(ev)}>{ev}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {selectedNode ? (
          <ContactPanel bundle={bundle} node={selectedNode} cutoff={snap.t}
            highlightEvent={highlightEvent}
            onClose={() => { setSelected(null); setHighlightEvent(null); }} />
        ) : (
          <div className="card panel">
            <div className="empty">Click a person on the map to see every conversation with them.</div>
          </div>
        )}
      </div>
    </>
  );
}

function fmtDate(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US",
    { month: "short", day: "numeric", year: "numeric" });
}

const Line = ({ w, faded }: { w: number; faded?: boolean }) => (
  <svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="#96938a"
    strokeWidth={w} strokeOpacity={faded ? 0.35 : 1} /></svg>
);
const Dashed = () => (
  <svg width="14" height="14"><circle cx="7" cy="7" r="5.5" fill="none" stroke="#b07b16"
    strokeDasharray="3 2" /></svg>
);
const Dot = ({ c }: { c: string }) => (
  <svg width="10" height="10"><circle cx="5" cy="5" r="5" fill={c} /></svg>
);
const Tri = ({ up }: { up?: boolean }) => (
  <svg width="12" height="10">
    <path d={up ? "M 1 9 L 6 1 L 11 9 z" : "M 1 1 L 6 9 L 11 1 z"}
      fill={up ? "#1d7a52" : "#b3382f"} />
  </svg>
);
