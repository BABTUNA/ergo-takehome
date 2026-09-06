# 5-minute demo script

Rehearsal target: 4:30, leaving 30s of slack. Have `npm run dev` already running and the
pipeline list open. Don't narrate the code until the feature has landed.

## 0:00 - The pitch (30s)

"Ergo's product knows what was said in every deal conversation. This is a feature that
uses that data to answer a question reps and managers can't see in a CRM: who is actually
holding this deal up, and who's missing from it. It's a stakeholder graph built from four
mocked streams - Zoom, Gmail, Slack, Salesforce - with an LLM extraction pipeline that has
to earn every claim from raw conversation."

## 0:30 - Pipeline list (30s)

- Point at the sort order: riskiest first, badges from rule-based detectors.
- One sentence on the healthy control: "Acme is what good looks like: 4 engaged buyers,
  exec involved, no flags."
- Click Globex.

## 1:00 - The Globex graph (90s)

- Lanes = seniority, colors = sentiment, arrows = momentum, dashed = never engaged.
- Tell the story off the graph, top to bottom: "The CFO is wary and quiet 17 days. The
  champion is strong and rising. And these two dashed nodes are people the conversations
  keep mentioning who have never been in a room - a VP of engineering and an unnamed
  security team."
- **The slider moment**: drag back to late February. "CRM said healthy the whole time.
  Watch when the risk actually appears." Drag forward week by week: Rhea arrives at the
  demo, the promise flag fires, her node cools, the silence flag lands.

## 2:30 - The receipts (60s)

- Click the broken-promise flag's evidence chip: panel opens on Rhea, scrolled to the
  exact email. "She asked for an ROI breakdown, we promised it 'this week', sent a
  pricing one-pager instead, and she's been silent since. The system caught that a
  related-but-lesser action doesn't fulfill a promise."
- Click ghost Priya: "This node exists only because of these two quotes."

## 3:30 - How it's built (60s)

- Five layers, one slide-in-your-head diagram: streams -> connectors -> event log ->
  two-pass LLM extraction -> rule detectors -> React.
- The two things worth saying out loud:
  1. "Ingestion never sees the story scripts, and extraction is evaluated against them:
     15/15 ground-truth assertions. The synthetic data is a test fixture, not a movie set."
  2. "Only the connector fetch() is fake. Swap it for OAuth + webhooks and everything
     downstream runs unchanged."

## 4:30 - Close (30s)

- What I'd build next: Opportunity-Team-based rosters, per-snapshot sentiment, commitment
  tracking as a first-class surface.
- "Happy to go into any layer - the prompts, the detectors, or the data generation."

## Q&A ammo

- Why no MCP server / agent angle? Cut deliberately; it's the natural extension but adds
  nothing to a 5-minute demo. Named in the README.
- How would sentiment not drift per snapshot? Today it's judged once over the whole deal;
  per-snapshot judgment needs per-date extraction runs - cost/latency tradeoff, cache
  makes it feasible.
- Detector false positives? Every rule is a named constant with evidence attached; the
  tuning history (scheduling promises, referrer ghosts) is in the git log.
