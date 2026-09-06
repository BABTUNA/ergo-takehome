# Extraction layer spec

Input: `data/processed/<slug>/{events.json, people.json}`
Output: `data/insights/<slug>/insights.json` (person attributes, signals, commitments, ghosts - every claim carries evidence event ids)
Run: `python3 -m pipeline.extract` (needs `ANTHROPIC_API_KEY`; cached results run free)

The only LLM stage. Two passes: a cheap model reads every event (volume), a stronger
model judges every person (reasoning). Momentum, engagement, and commitment fulfillment
are computed in plain code, not prompted.

## Call trace

```
main()                                                          [extract.py]
└─ for each slug in data/processed/*:
   extract_deal(slug)                                           [extract.py]
   ├─ events, people = load processed files                     [extract.py]
   ├─ registry = Registry rebuilt from people.json              [identity.py]
   ├─ pass1: for each conversation event:                       [extract.py]
   │   └─ extract_event(event)                                  [extract.py]
   │       └─ complete(HAIKU, EVENT_PROMPT, schema)             [llm.py]      # disk-cached
   ├─ ghosts = resolve_mentions(pass1 mentions)                 [extract.py]
   │   └─ Registry.match_name() per mention                     [identity.py] # no match = ghost
   ├─ commitments = match_fulfillment(pass1 commitments)        [extract.py]  # code, not LLM
   ├─ stats = engagement_stats(events)                          [extract.py]  # momentum arithmetic
   ├─ pass2: for each person with >= 1 event:
   │   └─ rollup_person(person, their signals + stats)          [extract.py]
   │       └─ complete(SONNET, PERSON_PROMPT, schema)           [llm.py]      # disk-cached
   └─ write insights.json                                       [extract.py]
```

## Files

### pipeline/llm.py

The API boundary. One function makes every model call; a disk cache in `data/cache/`
makes reruns free and lets the committed cache serve the demo with no key at all.

| Function | Does |
|---|---|
| `complete(model, prompt, schema)` | calls the Claude API asking for JSON matching `schema`, parses and returns it; retries once on malformed JSON. Cache hit = return cached JSON, no API call; miss = call, write `data/cache/<key>.json` |
| `cache_key(model, prompt)` | sha256 of model + prompt + `PROMPT_VERSION`; a prompt edit invalidates exactly the calls it affects |

### pipeline/prompts.py

Every prompt and output schema in one reviewable place, plus `PROMPT_VERSION` (bump it
to force re-extraction after a prompt edit).

| Item | Does |
|---|---|
| `EVENT_PROMPT` + `EVENT_SCHEMA` | pass 1: one event in -> `signals[]` (tag, who, quote), `commitments[]` (by, to, what, due), `mentions[]` (name, by, context), `tone[]` (who, label). Empty arrays over invented content |
| `PERSON_PROMPT` + `PERSON_SCHEMA` | pass 2: one person's ordered history + stats in -> role, seniority, sentiment, each with a one-line rationale and supporting event ids |

### pipeline/extract.py

The orchestrator. Runs both passes, does the code-side derivations, writes one
insights.json per deal.

| Function | Does |
|---|---|
| `extract_deal(slug)` | full pipeline for one deal (see trace); skips `stage_change` events in pass 1 |
| `extract_event(event, people)` | builds the pass-1 prompt (event content + participant roster) and returns its parsed JSON |
| `resolve_mentions(mentions, registry)` | `match_name` each mention: known person = dropped, named no-match = named ghost (Priya), nameless label = unnamed ghost ("security team"); dedupes with counts + event ids |
| `match_fulfillment(commitments, events, pass1)` | per commitment, HAIKU yes/no over the committer's later events; unfulfilled + past due = `broken`, not yet due = `open` |
| `engagement_stats(events)` | code only: per-person event counts, last touch, trailing 14d vs prior 14d -> momentum `rising/flat/cooling`, `quiet_days` |
| `rollup_person(person, history)` | builds the pass-2 prompt from the person's signals, tones, commitments, stats; returns role/seniority/sentiment with rationales |
| `write_insights(slug, ...)` | merges rollups + signals + commitments + ghosts + stats into insights.json |
| `main()` | runs `extract_deal` for every processed deal, prints per-deal summary |

### scripts/eval_extraction.py

The free-ground-truth check: asserts the flagship claims against what the stories
scripted. Run after any prompt change; exit 1 on failure = extraction regression.

| Deal | Asserted |
|---|---|
| globex | Rhea = wary / economic_buyer / exec; ROI commitment `broken`; Priya = named ghost (2 mentions); security team = unnamed ghost |
| initech | Sarah momentum = cooling; Gwen (zero events) has no rollup |
| umbra | Elena, Malik, Tara all sentiment positive |
| acme | no broken commitments, no ghosts |

## Examples

### `complete(HAIKU, EVENT_PROMPT, schema)` - pass 1, one call per event

In (the rendered prompt, abridged):

```
Participants: p_rhea = Rhea Kim (buyer), p_jordan = Jordan Lee (seller), ...
Channel: gmail
Content:
Subject: ROI breakdown
Following up from the demo. I still need the ROI breakdown... this week?
```

Out:

```json
{"signals": [{"tag": "info_request", "who": "p_rhea",
              "quote": "I still need the ROI breakdown"}],
 "commitments": [{"by": "p_jordan", "to": "p_rhea",
                  "what": "send ROI breakdown", "due": "week of Mar 20"}],
 "mentions": [],
 "tone": [{"who": "p_rhea", "label": "urgent"}]}
```

A routine scheduling email correctly returns all four arrays empty.

### `complete(SONNET, PERSON_PROMPT, schema)` - pass 2, one call per person

In (the rendered prompt, abridged):

```
Person: p_rhea (Rhea Kim), buyer side, title: unknown, NOT in CRM
Deal: Globex, $120000, stage Negotiation
Computed stats: {"events": 6, "last_touch": "2026-03-26", "quiet_days": 12, "momentum": "cooling"}
History, oldest first:
2026-03-12 ev_007: signal pricing_concern ("I need total cost, not list price")
2026-03-12 ev_007: tone wary
2026-03-20 ev_012: signal info_request ("I still need the ROI breakdown")
received commitment: "send ROI breakdown" (status: broken)
```

Out:

```json
{"role": "economic_buyer", "role_rationale": "Controls budget framing, ties purchase to renewal planning",
 "seniority": "exec", "seniority_rationale": "Owns vendor renewal cycle; no title on file",
 "sentiment": "wary", "sentiment_rationale": "Price-focused throughout, silent after an unmet request",
 "evidence": ["ev_007", "ev_012"]}
```

### `insights.json` - the layer's output, one per deal

```json
{"deal": {"name": "Globex", "amount": 120000, "stage": "Negotiation"},
 "people": {
   "p_rhea": {"role": "economic_buyer", "seniority": "exec", "sentiment": "wary",
              "sentiment_rationale": "...", "evidence": ["ev_007", "ev_012"],
              "stats": {"events": 6, "last_touch": "2026-03-26",
                        "quiet_days": 12, "momentum": "cooling"}}},
 "signals": [{"event_id": "ev_012", "tag": "info_request", "who": "p_rhea",
              "quote": "I still need the ROI breakdown"}],
 "commitments": [{"by": "p_jordan", "to": "p_rhea", "what": "send ROI breakdown",
                  "due": "week of Mar 20", "status": "broken", "origin_event": "ev_012"}],
 "ghosts": [{"name": "Priya", "named": true, "count": 2, "events": ["ev_007", "ev_030"]},
            {"label": "security team", "named": false, "count": 1, "events": ["ev_025"]}]}
```

Four sections: judged people (with stats), raw signals (the receipts), commitment
verdicts, ghosts. The graph layer reads nothing else.

## Decisions

- Models: `claude-haiku-4-5-20251001` for pass 1 and fulfillment checks, `claude-sonnet-5`
  for pass 2. Roughly 100 haiku calls + 15 sonnet calls total across all deals.
- `data/cache/` is committed: the repo demos with zero API key; a fresh clone re-extracts
  only if someone edits prompts or data.
- Seniority comes from CRM title when present; the LLM infers it otherwise (Rhea has no
  title at this stage - inferring exec from "renewal planning" and budget language is the
  showcase).
- Ghost mentions of known people are dropped, not ghosted: "Rhea K." in Slack resolves to
  p_rhea via `match_name`, so she never becomes a false ghost.
