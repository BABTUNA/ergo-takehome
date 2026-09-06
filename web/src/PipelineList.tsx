import { useEffect, useState } from "react";
import { loadAllGraphs } from "./data";
import type { GraphFile } from "./types";

const FLAG_LABELS: Record<string, string> = {
  single_threaded: "single-threaded",
  altitude_gap: "no exec engaged",
  cooling_key_contact: "key buyer cooling",
  broken_commitment: "broken promise",
  ghost_stakeholder: "ghost stakeholder",
  internal_single_thread: "one rep holds all",
  no_exec_pairing: "no exec pairing",
};

const SEV_ORDER = { high: 0, med: 1, low: 2, none: 3 };

export function PipelineList() {
  const [deals, setDeals] = useState<{ slug: string; graph: GraphFile }[] | null>(null);
  useEffect(() => { loadAllGraphs().then(setDeals); }, []);
  if (!deals) return <div className="loading">Loading pipeline...</div>;

  const rows = deals
    .map(({ slug, graph }) => {
      const last = graph.snapshots[graph.snapshots.length - 1];
      return { slug, deal: graph.deal, rollup: last.rollup, flags: last.flags };
    })
    .sort((a, b) =>
      SEV_ORDER[a.rollup.top_severity] - SEV_ORDER[b.rollup.top_severity] ||
      a.rollup.thread_score - b.rollup.thread_score);

  return (
    <>
      <div className="topbar">
        <h1>Pipeline</h1>
        <span className="sub">{rows.length} open deals · as of Apr 7, 2026</span>
      </div>
      <div className="card rows">
        <div className="header">
          <span>Deal</span><span>Amount</span><span>Stage</span><span>Threads</span><span>Flags</span>
        </div>
        {rows.map((r) => (
          <a key={r.slug} className={`row risk-${r.rollup.top_severity}`} href={`#/deal/${r.slug}`}>
            <span className="name">{r.deal.name}</span>
            <span>${Math.round(r.deal.amount / 1000)}k</span>
            <span>{r.deal.stage}</span>
            <span className={r.rollup.thread_score >= 3 ? "score-good" : "score-bad"}>
              {r.rollup.thread_score.toFixed(1)}
            </span>
            <span className="badges">
              {r.flags.length === 0 && <span className="badge ok">healthy</span>}
              {r.flags.map((f) => (
                <span key={f.id} className={`badge ${f.severity}`}>{FLAG_LABELS[f.id] ?? f.id}</span>
              ))}
            </span>
          </a>
        ))}
      </div>
    </>
  );
}
