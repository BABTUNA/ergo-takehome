"""Every prompt and output shape in one reviewable place.

Bump PROMPT_VERSION after editing any prompt to invalidate the whole cache on purpose.
"""

PROMPT_VERSION = "1"

EVENT_KEYS = ("signals", "commitments", "mentions", "tone")

EVENT_PROMPT = """You are analyzing ONE communication event from a B2B sales deal.

Participants (use these ids in your answer, never names):
{roster}

Channel: {channel}
Content:
{content}

Extract, from THIS EVENT ONLY:
1. signals: notable sales signals. tag is a short snake_case label such as
   pricing_concern, buying_signal, info_request, objection, risk, next_step_set.
   Include the exact quote and the person id who expressed it.
2. commitments: explicit promises one person made to another. Include what was
   promised and any stated deadline, verbatim where possible.
3. mentions: people referred to by name or role who are NOT in the participant list
   above. Give the name exactly as written (or a label like "security team" if
   unnamed), the id of who said it, and brief context.
4. tone: one lowercase word per participant who actually spoke or wrote, describing
   their tone (e.g. positive, neutral, wary, enthusiastic, urgent, frustrated).

Do NOT invent content. A routine scheduling message legitimately has all arrays empty.

Answer with ONLY this JSON, no prose:
{{"signals": [{{"tag": "...", "who": "p_...", "quote": "..."}}],
  "commitments": [{{"by": "p_...", "to": "p_...", "what": "...", "due": "..."}}],
  "mentions": [{{"name": "...", "by": "p_...", "context": "..."}}],
  "tone": [{{"who": "p_...", "label": "..."}}]}}"""

PERSON_KEYS = ("role", "seniority", "sentiment")

PERSON_PROMPT = """You are judging ONE person's position in a B2B sales deal, using
their complete extracted history below.

Person: {person_line}
Deal: {deal_line}
Computed stats: {stats_line}

History, oldest first:
{history}

Judge this person across the WHOLE deal:
- role: one of champion, economic_buyer, evaluator, blocker, neutral
  (seller-side people are always "seller")
- seniority: one of exec, director, team. Use their title if given; if the title is
  unknown, infer from behavior (who controls budget, who defers to whom).
- sentiment: one of positive, neutral, wary, negative - their disposition toward
  buying, considering the trend over time, not just the average.

Answer with ONLY this JSON, no prose:
{{"role": "...", "role_rationale": "one line",
  "seniority": "...", "seniority_rationale": "one line",
  "sentiment": "...", "sentiment_rationale": "one line",
  "evidence": ["ev_...", "ev_..."]}}"""

FULFILL_PROMPT = """A person in a sales deal made this promise:
  "{what}" (promised {due})

Later, the same person did this ({channel}, {ts}):
{content}

Does that later event FULFILL the promise? A related-but-lesser action does not count
(e.g. sending a pricing one-pager does not fulfill a promised ROI breakdown).

Answer with ONLY this JSON: {{"fulfills": true or false, "why": "one line"}}"""
