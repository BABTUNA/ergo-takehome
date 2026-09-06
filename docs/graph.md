# Graph + detection layer spec

Input: `data/insights/<slug>/insights.json` + `data/processed/<slug>/{events,people}.json`
Output: `data/graph/<slug>/graph.json` - weekly snapshots of nodes, edges, flags, rollup
Run: `python3 -m pipeline.build`

Pure code, no LLM. Everything is a deterministic function of the inputs and a date `t`,
so every claim is explainable ("rule, threshold, evidence") and the replay slider is
just picking a snapshot.

## Call trace

<pre>
<a href="../pipeline/build.py#L52">main()</a>                                                          [build.py]
└─ for each slug in data/insights/*:
   <a href="../pipeline/build.py#L31">build_deal(slug)</a>                                             [build.py]
   ├─ load insights + events + people                           [build.py]
   ├─ roster = <a href="../pipeline/graph.py#L18">seller_roster()</a>                                  [graph.py]    # all seller people + org directory titles
   ├─ for each t in weekly snapshots (Feb 16 .. Apr 7):
   │   ├─ graph = <a href="../pipeline/graph.py#L61">build_graph(events, insights, roster, t)</a>      [graph.py]
   │   │   ├─ nodes: people seen before t + ghosts + roster
   │   │   ├─ <a href="../pipeline/graph.py#L41">momentum_at(events, pid, t)</a> per node              [graph.py]
   │   │   └─ edges: person-pair interactions before t
   │   ├─ flags = <a href="../pipeline/detectors.py#L135">run_detectors(graph, insights, deal, t)</a>       [detectors.py] # 7 rule functions
   │   └─ rollup = <a href="../pipeline/graph.py#L152">deal_rollup(graph, flags)</a>                    [graph.py]
   └─ write graph.json (all snapshots, "today" last)            [build.py]
</pre>

## Snapshot format (graph.json)

```json
{"deal": {...}, "snapshots": [
  {"t": "2026-03-16",
   "nodes": [{"id": "p_rhea", "name": "Rhea Kim", "side": "buyer", "lane": "exec",
              "sentiment": "wary", "momentum": "flat", "events": 4, "in_crm": false,
              "ghost": false}],
   "edges": [{"a": "p_jordan", "b": "p_rhea", "weight": 4, "days_stale": 3}],
   "flags": [{"id": "broken_commitment", "severity": "high",
              "summary": "ROI breakdown promised Mar 20, never sent",
              "evidence": ["ev_012", "ev_021"],
              "suggested_move": "Send Rhea the ROI breakdown she asked for on Mar 20"}],
   "rollup": {"thread_score": 1.5, "highest_lane": "exec", "open_flags": 3}}
]}
```

## Files

### pipeline/graph.py

Builds the render-ready graph for one deal at one date.

| Function | Does |
|---|---|
| `seller_roster()` | all seller-side people across every deal's people.json - your own org is always known, so unengaged teammates (Sam, Ava at Umbra) still get nodes |
| `build_graph(events, insights, roster, t)` | nodes = every person with >= 1 event before `t`, plus roster sellers (0-contact allowed), plus ghosts mentioned before `t`; each node carries side, lane (exec/director/team from seniority), sentiment, momentum-as-of-t, engagement count, in_crm. Edges = person pairs weighted by shared meetings + direct emails + slack exchanges before `t`, with days-stale |
| `momentum_at(events, pid, t)` | recomputes the trailing-14d-vs-prior-14d arithmetic at `t` (insights.json only has it for "today") |
| `deal_rollup(graph, flags)` | thread score (engaged buyers weighted by lane), highest lane engaged, flags sorted by severity - feeds the pipeline list view |

### pipeline/detectors.py

Seven rule functions, each `detect_x(graph, deal, t) -> flag | None` where a flag is
`{id, severity (high/med/low), summary, evidence: [event ids], suggested_move}`.
Moves are filled from templates with names and dates from the evidence - never generated.

| Detector | Fires when (constants tunable at top of file) |
|---|---|
| `single_threaded` | >= 80% of buyer-side edge weight runs through one buyer contact |
| `altitude_gap` | stage is Negotiation+ and no engaged buyer above director lane |
| `cooling_key_contact` | an economic_buyer or champion has momentum cooling and quiet_days > 10 |
| `broken_commitment` | any commitment with status broken (straight from insights.json) |
| `ghost_stakeholder` | a named ghost mentioned >= 2 times, or any unnamed blocking group |
| `internal_single_thread` | one seller holds >= 90% of buyer-facing edge weight |
| `no_exec_pairing` | a buyer exec is engaged but no seller exec shares an edge with them |

### pipeline/build.py

Entry point and writer.

| Function | Does |
|---|---|
| `build_deal(slug)` | loads inputs, loops the weekly dates + "today" (2026-04-07), assembles snapshots |
| `main()` | runs every deal, prints per-deal flag summary |

## Decisions

- Weekly snapshots (8 per deal + "today"), not arbitrary-date computation: keeps all
  logic in Python, the UI just picks a snapshot, and the slider snaps to weeks.
- Roster sellers get nodes even with zero events - absence is the insight at Umbra.
- Ghost nodes only appear in snapshots after their first mention event.
- Sentiment and role come from insights.json (judged over the whole deal) and are held
  constant across snapshots; momentum and edges are recomputed per `t`. Noted in the
  README as a simplification (per-snapshot re-judgment would need per-t extraction).
