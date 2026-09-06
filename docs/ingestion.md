# Ingestion layer spec

Input: `data/deals/<slug>/{zoom,gmail,slack,salesforce}.json`
Output: `data/processed/<slug>/events.json` (sorted Event list) + `people.json` (person registry)
Run: `python3 -m pipeline.ingest`

## Call trace

<pre>
<a href="../pipeline/ingest.py#L43">main()</a>                                                          [ingest.py]
└─ for each slug in data/deals/*:
   <a href="../pipeline/ingest.py#L18">ingest_deal(slug)</a>                                            [ingest.py]
   ├─ sf_raw = <a href="../pipeline/connectors.py#L20">SalesforceConnector.fetch(slug)</a>                  [connectors.py]
   ├─ <a href="../pipeline/identity.py#L22">Registry.seed_from_crm</a>(<a href="../pipeline/connectors.py#L93">contacts(sf_raw)</a>)                  [identity.py]   # CRM first: in_crm flags
   ├─ events  = <a href="../pipeline/connectors.py#L99">SalesforceConnector.normalize(sf_raw, ...)</a>      [connectors.py] # stage changes
   ├─ events += <a href="../pipeline/connectors.py#L20">ZoomConnector.fetch</a> + <a href="../pipeline/connectors.py#L31">normalize</a>                 [connectors.py]
   │            └─ <a href="../pipeline/identity.py#L36">Registry.resolve()</a> per attendee              [identity.py]
   ├─ events += <a href="../pipeline/connectors.py#L20">GmailConnector.fetch</a> + <a href="../pipeline/connectors.py#L50">normalize</a>                [connectors.py]
   │            └─ <a href="../pipeline/identity.py#L36">Registry.resolve()</a> per from/to/cc            [identity.py]
   ├─ events += <a href="../pipeline/connectors.py#L20">SlackConnector.fetch</a> + <a href="../pipeline/connectors.py#L73">normalize</a>                [connectors.py]
   │            └─ <a href="../pipeline/identity.py#L36">Registry.resolve()</a> per author                [identity.py]
   └─ <a href="../pipeline/ingest.py#L32">write_outputs(slug, events, registry,</a>                     [ingest.py]
                    <a href="../pipeline/connectors.py#L96">SalesforceConnector.opportunity(sf_raw)</a>)
</pre>

Order matters once: CRM seeding runs before conversation streams so a person first seen
in a conversation is provably not-in-CRM, not just not-yet-seen.

Ingestion never reads `stories.yaml`. It only sees what a real system would see: CRM
records and observed conversations. Titles exist only where the CRM has them; the CFO
title of a person missing from CRM (Rhea) is *unknown* here and inferred by extraction.

## Files

### pipeline/models.py

The shared data shapes. Every stage downstream (extraction, graph, UI) speaks in these
two records and nothing else.

| Function | Does |
|---|---|
| `Event` (dataclass) | id, deal_id, channel, type, ts, participants (person ids), direction, thread_key, content |
| `Person` (dataclass) | id, name, email, title, side, in_crm, provisional, aliases (per-channel names seen) |

### pipeline/identity.py

Who is who. One registry per deal maps every observed email and name variant to a single
canonical Person, and records where each alias was seen.

| Function | Does |
|---|---|
| `Registry.seed_from_crm(contacts)` | creates Persons from salesforce contacts with `in_crm=True`, title from CRM |
| `Registry.resolve(email, name=None)` | returns Person for email; creates provisional Person (`in_crm=False`) if unseen; records `name` as an alias; sets side by domain (harborview.io = seller) |
| `Registry.match_name(name)` | finds a Person by name/alias/initials ("Rhea K." -> Rhea Kim); used by extraction for mention resolution, unused during ingestion |
| `Registry.to_json()` | serializes the registry to people.json shape |

### pipeline/connectors.py

The channel boundary. One connector per source; `fetch()` is the production swap point
(reads a committed JSON file here, would be an OAuth'd API pull or webhook feed in a real
deployment), `normalize()` is identical either way.

Each `normalize` converts its channel's raw JSON into the common Event record. Example,
one Gmail message in:

```json
{"from": "rhea@globex.com", "to": ["jordan@harborview.io"], "date": "2026-03-20T14:02:00Z",
 "body": "I need the ROI breakdown..."}
```

one Event out:

```json
{"id": "ev_012", "channel": "gmail", "type": "message", "ts": "2026-03-20T14:02:00Z",
 "participants": ["p_rhea", "p_jordan"], "direction": "inbound",
 "thread_key": "th_4471", "content": {"subject": "ROI breakdown", "from": "p_rhea", "body": "..."}}
```

The conversion is always the same three moves: pick the timestamp field, swap raw
emails/names for canonical person ids (via `Registry.resolve`), and keep the channel's
payload under `content`. Per connector:

| Function | Raw in -> Events out |
|---|---|
| `ZoomConnector.normalize` | each meeting in `meetings[]` -> one `meeting` Event. `ts` = start_time, participants = attendee emails resolved to ids, `thread_key` = meeting id, content keeps topic/duration/full transcript |
| `GmailConnector.normalize` | each message inside each thread -> one `message` Event (a 3-message thread = 3 Events sharing `thread_key` = thread id). Participants = from + to + cc resolved; `direction` = outbound if the sender's domain is ours, else inbound |
| `SlackConnector.normalize` | each message in `messages[]` -> one `message` Event. Participant = author only (channel members are resolved into the registry but not attached per message), `thread_key` = channel name |
| `SalesforceConnector.normalize` | each `stage_history` entry -> one `stage_change` Event with empty participants, content = the stage name. Gives the timeline "moved to Negotiation on Mar 15" markers |
| `SalesforceConnector.contacts(raw)` | not events: hands the raw CRM contact list to `Registry.seed_from_crm` before any conversation stream runs |
| `SalesforceConnector.opportunity(raw)` | not events: hands deal metadata (amount, stage, close date) straight through to the events.json header |

### pipeline/ingest.py

The orchestrator. Wires connectors and registry together per deal and writes the two
output files.

| Function | Does |
|---|---|
| `ingest_deal(slug)` | full pipeline for one deal (see trace above); returns event/person counts |
| `write_outputs(slug, events, registry, opportunity)` | sorts events by ts, assigns `ev_NNN` ids, writes both JSON files |
| `main()` | discovers deal slugs from `data/deals/*`, runs `ingest_deal` on each, prints summary |
