# Ergo take-home: stakeholder graph

A take-home project for Ergo (YC W25). Builds a multi-stream ingestion pipeline over synthetic
sales data and ships one feature their product doesn't have: a per-deal stakeholder graph with
seniority lanes, sentiment, momentum, ghost contacts, and a click-through contact timeline.

Example first: the demo deal is "Globex, $120k, negotiation." The CRM says it's healthy. The
graph shows every thread runs through one director who went quiet 12 days ago, the CFO is wary
on pricing, and a VP of engineering keeps getting mentioned but has never been in a room.

## Layers

1. Data layer (synthetic streams)
2. Ingestion layer
3. Extraction layer
4. Graph + detection logic
5. UI
6. Polish (README, demo script)

---

## 1. Data layer

Goal: four channel-shaped streams (Zoom, Gmail, Slack, Salesforce) that look like real API
output, telling pre-scripted deal stories so demo moments are guaranteed.

### What is a story

A story = one deal's complete scripted history. Two parts:

1. **A hand-written outline** (one entry in `stories.yaml`): cast, deal metadata, and the
   narrative arc, written backwards from the demo moment - decide what the graph should
   reveal, then define the events that make it true.
2. **The generated evidence**: the four JSON streams containing the conversations that make
   the arc real. If the outline says "rep breaks a promise," the evidence is an email
   saying "I'll send it this week" followed by silence in every channel.

One story = one deal = one folder in `data/deals/`. The extraction layer must discover the
arc from the evidence alone; nothing in the JSON labels it.

### Core schemas

Everything normalizes to three entities downstream, so the generator targets them from day one:

- **Person**: id, name, email, company, title (title only where a real stream would have it)
- **Deal**: id, name, amount, stage, close date (mirrors the Salesforce object)
- **Event**: id, deal id, channel, timestamp, participants, content, direction

### Stream formats (mimic the real APIs)

Each stream is its own JSON file per deal, shaped like the source would ship it:

- `zoom.json` - meetings with topic, start time, duration, attendee list (name + email),
  and a speaker-labeled transcript with timestamps
- `gmail.json` - threads with from/to/cc, subject, date, plain-text body per message
- `slack.json` - one Slack Connect channel per deal: member list, then messages with
  author, timestamp, text
- `salesforce.json` - thin: Opportunity, Contacts, and stage history. Kept because deal
  metadata must come from somewhere, and "this person isn't in the CRM" is itself a signal

Example shapes (abridged, from the Globex flagship story):

```json
// zoom.json
{"meetings": [{
  "id": "zm_88213", "topic": "Globex <> YourCo - Platform demo",
  "start_time": "2026-03-12T17:00:00Z", "duration_min": 42,
  "attendees": [{"name": "Rhea Kim", "email": "rhea@globex.com"},
                {"name": "Jordan Lee", "email": "jordan@yourco.com"}],
  "transcript": [
    {"ts": "00:14:22", "speaker": "Rhea Kim",
     "text": "What does this look like at 500 seats? I need total cost, not list price."},
    {"ts": "00:15:01", "speaker": "Jordan Lee",
     "text": "Happy to put together a full ROI breakdown for you."}]}]}

// gmail.json
{"threads": [{
  "id": "th_4471", "subject": "ROI breakdown",
  "messages": [
    {"from": "rhea@globex.com", "to": ["jordan@yourco.com"], "cc": ["odiaz@globex.com"],
     "date": "2026-03-20T14:02:00Z",
     "body": "Following up on the demo. I need the ROI breakdown before renewal planning."}]}]}

// slack.json
{"channel": "yourco-globex",
 "members": ["jordan@yourco.com", "odiaz@globex.com"],
 "messages": [
   {"author": "odiaz@globex.com", "ts": "2026-03-25T19:12:00Z",
    "text": "sandbox is up. Rhea K. still waiting on that ROI doc btw"}]}

// salesforce.json
{"opportunity": {"id": "opp_009", "name": "Globex", "amount": 120000,
   "stage": "Negotiation", "close_date": "2026-04-30", "owner": "jordan@yourco.com"},
 "contacts": [{"name": "Omar Diaz", "email": "odiaz@globex.com", "title": "Director of IT"}],
 "stage_history": [{"stage": "Discovery", "entered": "2026-02-10"},
                   {"stage": "Negotiation", "entered": "2026-03-15"}]}
```

Note what's latent in the example: the broken promise spans gmail and slack, "Rhea Kim" /
"rhea@globex.com" / "Rhea K." are the same person across streams, and Rhea is absent from
Salesforce contacts despite being the economic buyer.

Rule: no stream contains derived insight. Sentiment, roles, momentum, and ghosts must be
*earned* by the extraction layer, never planted in the data.

### Scripted stories (4 deals)

Each deal gets a one-paragraph outline written by hand, then an LLM expands it into
transcripts and threads. Four deals, each demoing distinct graph features, with the
overlapping insights merged so nothing is lost:

1. **Healthy control** ("Acme") - 4+ engaged contacts, exec involved, multi-threaded on
   both sides, positive sentiment, rising momentum. The baseline every other deal is
   compared against.
2. **Flagship: cooling CFO + ghosts** ("Globex") - CFO asks for an ROI breakdown, the rep
   promises it and never sends it, she goes quiet (broken commitment found in the timeline).
   VP eng is mentioned twice but never engaged; unnamed "security team" lurks in an email.
   Demos: sentiment, momentum, ghost nodes, timeline receipts.
3. **Single-threaded + altitude** ("Initech") - one director-level champion holds every
   thread and starts going quiet; nobody above director has ever engaged.
   Demos: single-threading flag, seniority lanes, empty exec band.
4. **Internal single-threading** ("Umbra") - buyer side looks healthy, but the AE holds
   every relationship; SE and VP sales have zero contacts, and there is no exec-to-exec
   pairing. Demos: the seller side of the graph, manager persona value.

### Synthetic generation plan

Step by step:

1. **Write `stories.yaml` by hand.** Four entries: cast (names, titles, emails, side),
   deal metadata, arc paragraph, and a `beats` list - the must-exist events with rough
   dates ("Mar 20: Rhea emails asking for ROI breakdown", "Mar 26 onward: Rhea silent").
   Beats are the contract between the outline and the generator.
2. **Generate per channel, per deal.** One LLM pass per stream: prompt = arc + cast +
   beats + the channel's JSON schema. Beats pin the required events; the LLM freely
   invents filler around them (scheduling chatter, small talk, benign threads).
3. **Inject imperfections deterministically in code, not by prompt.** Name variants
   ("Rhea K."), the missing-from-CRM contact, the external lawyer. Post-process so they
   are guaranteed, since LLMs follow "be messy" instructions unreliably.
4. **Validate with a checklist script.** Asserts per deal: every beat appears in the right
   stream and date range, all timestamps inside the 8-week window, every speaker/author
   resolves to a cast member (except planted strangers), JSON matches schema. Regenerate
   any stream that fails.
5. **Anchor and commit.** All dates relative to one shared "today", then written out as
   absolutes. Generated JSON is checked into the repo; generation never runs during the
   demo.

Knobs:

- Transcript realism: 10-15 exchange excerpts per call, plus one full-length showcase
  call in the Globex flagship
- Density: ~25-50 events per deal (3-5 calls, 4-8 email threads, 15-30 Slack messages)
- Cast: 3-6 buyer-side people plus 2-3 seller-side per deal

### Layout

```
data/
  stories.yaml            # hand-written outlines + cast
  deals/<deal-slug>/
    zoom.json
    gmail.json
    slack.json
    salesforce.json       # thin: Opportunity + Contacts + stage history
```

### Deliberate imperfections

Real streams are messy; plant a little of it so identity resolution has something to do:

- Same person as "Rhea Kim" on Zoom, "rhea@globex.com" on email, "Rhea K." on Slack
- A contact missing from Salesforce entirely (only exists in conversations)
- One email participant who is an external lawyer, not part of either org

---

## 2. Ingestion layer

Goal: turn four channel-shaped streams into one normalized event log per deal, with every
participant resolved to a canonical Person. This is the boundary that maps to OAuth +
webhooks in production, so it should look like connectors, not like file loading.

### Connector pattern

One adapter per channel, all implementing the same interface:

```
Connector
  fetch(deal) -> raw payload     (here: reads the JSON file)
  normalize(raw) -> Event[]      (channel-specific mapping)
```

The point of the split: swapping `fetch` from "read file" to "Zoom OAuth + webhook
subscription" is the production story, and `normalize` stays identical. Say this in the
README; it is the whole argument that the mock is honest.

### Event granularity

One event = one atomic communication:

- Zoom: one event per meeting (transcript kept whole as content; utterances are not
  separate events)
- Gmail: one event per message (not per thread; thread id kept as a grouping key)
- Slack: one event per message
- Salesforce: one event per stage change (from stage history); the Opportunity record
  itself is deal metadata, not an event

Normalized Event:

```json
{"id": "ev_0042", "deal_id": "globex", "channel": "zoom",
 "ts": "2026-03-12T17:00:00Z", "type": "meeting",
 "participants": ["p_rhea", "p_omar", "p_jordan"],
 "thread_key": "zm_88213", "direction": "n/a",
 "content": {...channel-specific payload...}}
```

Direction (inbound/outbound) is set for email and Slack from the author's side; meetings
are bidirectional.

### Identity resolution

A person registry built incrementally as events are ingested:

1. **Email exact match** - the primary key when present (email, Slack members, Zoom
   attendees all carry emails)
2. **Name match against known cast** - exact name, then normalized (case, initials:
   "Rhea K." matches "Rhea Kim" when first name + initial align and company context
   agrees)
3. **No match** - create a provisional Person with whatever fields exist; provisional
   people surface in the UI as "unrecognized participant" rather than being dropped

Resolution scope: ingestion resolves *participants* (people actually on the event).
People merely *mentioned* in content are extraction's job; extraction emits mention
candidates and resolves them against this same registry, so ghost nodes come from one
shared identity store.

Output per deal: `events.json` (sorted by ts) + `people.json` (registry with per-person
channel aliases). These two files are the only input the extraction layer sees.

### Decisions

- **Stated simplification: deal attribution is given.** Ingestion is pure code, no LLM.
  This works because data arrives pre-grouped per deal (one folder per deal), so no
  parser ever has to decide which deal a message belongs to. Partly realistic (Slack
  Connect channels map to one account; meetings link via calendar invites), but real
  attribution of a loose email to a deal needs participant-domain and CRM heuristics.
  Named in the README as the layer's main simplification.
- Batch, not streaming: ingest everything at startup. The replay slider filters by
  timestamp downstream, so incremental ingestion buys nothing here. The connector
  interface is already webhook-shaped if asked about production.
- No cross-deal identity: each deal's registry is independent. Real product would
  dedupe globally; noted as future work.
- Salesforce contacts seed the registry before conversation streams run, so "in CRM"
  vs "not in CRM" is a queryable flag per person from day one.

## 3. Extraction layer

Goal: turn `events.json` + `people.json` into the fields the graph renders. The only LLM
layer. Everything it claims must carry evidence (event id + quote), or the UI won't show it.

### Two passes

**Pass 1, per event.** Each event goes to the LLM with its content and participant list.
Output per event:

```json
{"event_id": "ev_012",
 "signals": [{"tag": "pricing_concern", "who": "p_rhea",
              "quote": "I need total cost, not list price"}],
 "commitments": [{"by": "p_jordan", "to": "p_rhea",
                  "what": "send ROI breakdown", "due": "week of Mar 20"}],
 "mentions": [{"name": "Priya", "context": "VP eng wants a technical review",
               "by": "p_omar"}],
 "tone": [{"who": "p_rhea", "label": "wary"}]}
```

**Pass 2, per person.** Each person's full signal history goes to the LLM for a rollup:
role (champion / economic buyer / evaluator / blocker), seniority tier (exec / director /
team, from title when present, inferred when not), overall sentiment label, each with a
one-line rationale and supporting event ids.

### Computed, not prompted

Momentum and engagement are arithmetic, not LLM calls: event counts and recency over
trailing windows (e.g. last 14 days vs prior 14). Commitment fulfillment is code too:
a commitment closes if a later event from the same person matches it (small LLM check
per candidate pair). Ghost nodes = mentions whose name resolves to no registry person
(named ghost) or to no name at all ("our security team", unnamed ghost).

### Mechanics

- Strict JSON schemas, temperature 0, one deal processed at a time
- Disk cache keyed on hash(event content + prompt version), so dev iteration is free
  and the demo needs zero live LLM calls
- Model: a small fast model for pass 1 (high volume), a stronger one for pass 2 rollups
  (low volume, more judgment)

### Free ground truth

The stories are scripted, so `stories.yaml` beats double as an eval set: after
extraction, assert the flagship claims land ("Rhea sentiment = wary", "commitment
ev_012 unfulfilled", "Priya = ghost"). This is the accuracy story for the README, and
it catches prompt regressions while iterating.

Output per deal: `insights.json` (person attributes, signals, commitments, ghosts, all
with evidence refs). The graph layer consumes only this file.

## 4. Graph + detection logic

Goal: pure functions from `insights.json` + `events.json` to render-ready graph data and
risk flags. No LLM here; everything is deterministic and explainable.

### Graph build

Per deal, as of a given date `t` (the replay slider passes `t`; default = today):

- Nodes: every person with >= 1 event before `t`, plus ghosts (mentions before `t`)
- Node attrs: side, seniority lane, sentiment, momentum, engagement volume, in_crm
- Edges: person-pair interaction counts (shared meetings, direct emails, Slack
  exchanges) before `t`; width = volume, staleness = days since last shared event
- Everything recomputes from scratch for any `t`; no incremental state

### Risk detectors

Each is a small function returning `{flag, severity, evidence, suggested_move}`:

| Detector | Rule (tunable constants) |
|---|---|
| Single-threaded | >= 80% of buyer-side edge volume through one contact |
| Altitude gap | stage >= negotiation and no engaged contact above director |
| Cooling key contact | economic buyer or champion with momentum down and > 10 days quiet |
| Broken commitment | seller commitment past due with no fulfilling event |
| Ghost stakeholder | named ghost mentioned >= 2 times, or any unnamed blocking group |
| Internal single-threading | one seller holds >= 90% of buyer relationships |
| No exec pairing | buyer exec engaged but no seller exec has ever met them |

Suggested moves are templated from evidence, not LLM-generated: "Ask {champion} to
introduce {ghost.name}, mentioned in {event.date} call." Deterministic, so the demo
never improvises.

### Deal-level rollup

Thread score (engaged buyer contacts, weighted by seniority), highest level engaged,
open flags sorted by severity. This feeds the pipeline list view and its risk badges.

## 5. UI

Goal: three views forming one drill-down. Frontend-only: layers 1-4 precompute everything
into JSON, the app just renders it (static site, no backend).

### Views

1. **Pipeline list** - the 4 deals as rows: amount, stage, thread score, risk badges,
   sorted by severity. Demo entry point.
2. **Deal view** - the stakeholder graph plus flag cards with suggested moves below,
   and the replay slider along the bottom. Layer toggles for sentiment and momentum.
3. **Contact panel** - click a node, a panel slides in beside the graph: the person's
   timeline with channel icons, dates, snippets, signal tags, and evidence quotes.

### Graph rendering

- Fixed lane layout, not force-directed: seniority = vertical band, nodes spaced
  horizontally within their lane, seller side left / buyer side right. Deterministic
  and stable while the slider drags; physics layouts jitter and reshuffle.
- Visual encodings: lane = seniority, color = sentiment, small arrow = momentum,
  dashed outline = ghost, edge width = interaction volume, edge fade = staleness.
  One encoding per insight; legend always visible.
- Replay slider re-renders from `buildGraph(deal, t)`; nodes keep their positions
  across `t` so changes read as fading/appearing, not moving.

### Stack

React + Vite, D3 for the graph SVG. All data loaded from the precomputed JSON files.
Runs with one `npm run dev`; deployable as a static site.

## 6. Polish

### README structure

1. What it is + demo GIF
2. Architecture: the five layers, one diagram
3. Mock-to-production mapping: connectors swap to OAuth/webhooks; deal-attribution
   simplification named
4. Honesty rules: no planted insights, nothing renders without evidence
5. Extraction accuracy measured against the scripted beats
6. What I'd build next

### Not built, on purpose

Real OAuth, streaming ingestion, cross-deal identity resolution, CRM write-back, and
an MCP server exposing deal context to agents (a natural extension given Ergo's
"context layer for agents" positioning, but it would not improve a 5-minute demo).
Listed explicitly - naming cuts is the point.
