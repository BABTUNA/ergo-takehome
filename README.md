# Deal Graph

A stakeholder graph for B2B deals: who actually holds the relationships, how senior they
are, who's cooling off, and who keeps getting mentioned but has never been in a room.
Built as a take-home exploration of a feature idea for Ergo, on top of a four-channel
ingestion pipeline (Zoom, Gmail, Slack, Salesforce) over synthetic sales data.

Example first: the flagship deal is Globex, $120k, stage Negotiation. The CRM says it's
healthy. The graph shows the economic buyer went silent 17 days ago, right after the rep
promised her an ROI breakdown and quietly never sent it, a VP of engineering has been
mentioned twice but never engaged, and an unnamed security team is waiting at the end of
the deal. Every one of those claims is clickable down to the exact quote it came from.

<!-- TODO: demo GIF here -->

## Run it

```
cd web && npm install && npm run dev
```

Open http://localhost:5173. Everything is precomputed and committed, so there is no
backend, no API key, and no setup. Start on the pipeline list, open Globex, drag the
replay slider, and click Rhea's node.

To rerun the pipeline itself (also keyless, every LLM call is disk-cached):

```
python3 -m pipeline.ingest && python3 -m pipeline.extract && python3 -m pipeline.build
```

## Architecture

Five layers, each with a spec doc, each layer's output committed:

| Layer | What it does | Doc |
|---|---|---|
| 1. Data | 4 hand-scripted deal stories expanded into realistic Zoom/Gmail/Slack/Salesforce JSON (~105 events); a validator proves every story beat survived | [DESIGN.md](DESIGN.md) |
| 2. Ingestion | connectors normalize the streams into one event log + person registry per deal, with identity resolution and CRM-seeded flags | [docs/ingestion.md](docs/ingestion.md) |
| 3. Extraction | the only LLM stage: Haiku reads every event (signals, promises, mentions, tone), Sonnet judges every person (role, seniority, sentiment), code computes momentum and promise fulfillment | [docs/extraction.md](docs/extraction.md) |
| 4. Graph + detection | pure code: weekly graph snapshots plus seven rule-based risk detectors with templated suggested moves | [docs/graph.md](docs/graph.md) |
| 5. UI | React + Vite, no backend: pipeline list, lane graph with focus mode and replay slider, evidence-linked contact timelines | [docs/ui.md](docs/ui.md) |

## What keeps it honest

- **No planted insights.** The synthetic streams contain only raw conversation. Sentiment,
  roles, ghosts, and broken promises must be discovered by extraction; `scripts/validate_data.py`
  proves the stories are in the data, and `scripts/eval_extraction.py` proves extraction
  found them (15/15 assertions against the scripted ground truth).
- **Ingestion never reads the story files.** It sees only what a real system would: CRM
  records and observed conversations. The CFO with no CRM record has no title anywhere in
  the pipeline; extraction infers "exec" from her behavior.
- **Nothing renders without evidence.** Every flag, sentiment label, and ghost node carries
  event ids, and the UI resolves them to the underlying quote.

## Mock to production

The `fetch()` method of each connector is the only fake part of ingestion: it reads a
committed JSON file where production would hold an OAuth grant and a webhook subscription
(Zoom recordings, Gmail push, Slack Events API, Salesforce REST). `normalize()` and
everything downstream is unchanged. Two stated simplifications, both marked in the docs:
deal attribution is given (files arrive pre-grouped per deal; real attribution needs
participant-domain and CRM heuristics), and the seller roster is the whole 3-person org
where production would use the CRM's Opportunity Team.

## Not built, on purpose

Real OAuth, streaming ingestion, cross-deal identity resolution, CRM write-back, and an
MCP server exposing deal context to AI agents (the natural extension, but it would not
make a 5-minute demo better).

## What I'd build next

Per-snapshot sentiment (today's labels are judged once over the whole deal), commitment
tracking as a first-class UI surface, stage-based role expectations ("this deal is in
technical evaluation and no SE is engaged"), and the accuracy harness generalized from
4 scripted deals to a labeled evaluation set.
