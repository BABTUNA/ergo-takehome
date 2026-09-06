# UI layer spec

Input: `data/graph/<slug>/graph.json`, `data/processed/<slug>/events.json`,
`data/insights/<slug>/insights.json` (copied into `web/public/data/` by a sync script)
Output: the dashboard - pipeline list, deal graph, contact timeline
Run: `cd web && npm install && npm run dev` (static build: `npm run build`)

React + Vite + TypeScript, no backend: the app fetches precomputed JSON and renders it.
The graph is plain SVG in React (fixed lane layout needs no physics library).

## Component tree

<pre>
<a href="../web/src/App.tsx">App (router)</a>                                          [App.tsx]
├─ / .................. <a href="../web/src/PipelineList.tsx">PipelineList</a>                  [PipelineList.tsx]
│   └─ one row per deal from last-snapshot rollup, sorted by severity
└─ /deal/:slug ........ <a href="../web/src/DealView.tsx">DealView</a>                      [DealView.tsx]
    ├─ loads graph.json + events.json + insights.json via <a href="../web/src/data.ts">data.ts</a>
    ├─ TimelineSlider (picks snapshot index, inline in DealView)
    ├─ <a href="../web/src/StakeholderGraph.tsx">StakeholderGraph</a> (SVG)                         [StakeholderGraph.tsx]
    │   ├─ lane bands (exec / director / team)
    │   ├─ node per person (click -> ContactPanel)
    │   └─ edges with weight + staleness styling
    ├─ layer toggles (sentiment, momentum)
    ├─ flag cards per flag in the current snapshot (inline in DealView)
    └─ <a href="../web/src/ContactPanel.tsx">ContactPanel</a> (slide-in on node click)          [ContactPanel.tsx]
        └─ timeline rows per event involving that
           person (events.json joined with signal
           tags from insights.json)
</pre>

## Data flow example

Slider at snapshot 6 (Mar 23), user clicks Rhea's node:

```
graph.json.snapshots[6]  -> StakeholderGraph props: nodes, edges, flags
                            Rhea's node: lane exec, sentiment wary, momentum flat
click "p_rhea"           -> ContactPanel opens
events.json              -> filter: events where p_rhea in participants, ts <= Mar 23
insights.json.signals    -> join: tags + quotes per event_id
                         -> rendered as the channel-icon timeline, newest last
```

## Files

All under `web/src/`.

| File | Does |
|---|---|
| `App.tsx` | router (`/` and `/deal/:slug`), theme shell |
| `types.ts` | TypeScript mirrors of graph.json / events.json / insights.json shapes |
| `data.ts` | `loadDeal(slug)` fetches + caches the three JSON files; `loadAllRollups()` for the list page |
| `PipelineList.tsx` | deal rows: name, amount, stage, thread score, flag badges from the final rollup; sorted by top severity; row click navigates |
| `DealView.tsx` | page state: current snapshot index, selected person, layer toggles; composes everything below |
| `StakeholderGraph.tsx` | the SVG: three lane bands, seller column left / buyer columns right, deterministic node positions (sorted by id within lane), edges under nodes with width = weight and opacity fading by days_stale |
| (in `DealView.tsx`) | slider, flag cards (summary, suggested move, clickable evidence ids), and legend ended up inline - they are small and share DealView state |
| `ContactPanel.tsx` | slide-in: person header (role, sentiment, rationale from insights), assembled timeline |
| `scripts/sync_data.sh` | copies the pipeline outputs into `web/public/data/` (run before dev/build) |

## Decisions

- Plain SVG, no force layout: node positions are a pure function of (lane, sorted index),
  so the replay slider reads as fade/appear, never reshuffle.
- Node x-positions: sellers at 15%, engaged buyers spread across 50-85% of their lane,
  ghosts pinned at 92% - missing people literally sit at the edge of the org.
- The contact timeline is assembled client-side from events.json + insights.json rather
  than adding a new pipeline output - the pipeline's contract stays three files.
- Sentiment toggle off = all engaged nodes render one neutral "engaged" color;
  momentum toggle off = arrows hidden. Defaults: both on.
- Slider filters the ContactPanel timeline too (events after the snapshot date hidden),
  so the whole page always agrees about "now".
- Light styling, no component library: one CSS file, system font stack - the design
  language from the mockups (lanes, badges, severity tints).
