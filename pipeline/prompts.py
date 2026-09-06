"""Every prompt and output shape in one reviewable place.

Bump PROMPT_VERSION after editing any prompt to invalidate the whole cache on purpose.
"""

PROMPT_VERSION = "3"

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
2. commitments: explicit promises one person made to another about a FUTURE action.
   Include what was promised and any stated deadline, verbatim where possible.
   Actions stated as already done ("Done, sending them today") and hypothetical
   timelines ("kickoff within a week of signature") are NOT commitments.
3. mentions: PEOPLE (or specific internal teams like "security team") referred to
   but NOT in the participant list above. Give the name exactly as written (or the
   team label), the id of who said it, and brief context. Only people who could be
   involved in or affect THIS deal - not outside references like a referrer or a
   contact at an unrelated company. Never include companies, products, tools,
   places, certifications, documents, or pronoun-only references ("she", "my
   team"). Never include someone who IS a participant.
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
- seniority: one of exec, director, team. Use their title if given (C-suite and VP
  = exec). If the title is unknown, infer from behavior: someone who controls the
  company-wide budget or vendor renewal cycle, or who others defer to for final
  sign-off, is exec.
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
(e.g. sending a pricing one-pager does not fulfill a promised ROI breakdown). But an
event that clearly shows the promised action happened DOES count (a promised meeting
invite followed by that meeting occurring).

Answer with ONLY this JSON: {{"fulfills": true or false, "why": "one line"}}"""

DUE_PROMPT = """A promise was made on {origin_ts} in a sales deal, with the stated
deadline: "{due}"

Convert that deadline to a concrete date. "this week" means the Friday of the week
the promise was made; "mid-April" means April 15; a weekday name means the next such
day after the promise; "this coming week" or "next week" means the Friday of the
FOLLOWING week. If the deadline depends on a future event that may not have
happened ("within a week of signature", "when the review completes"), answer null.

Answer with ONLY this JSON: {{"due_date": "YYYY-MM-DD" or null if no real deadline}}"""

GHOST_PROMPT = """In a sales conversation, someone referred to "{name}".
Context of the mentions: {contexts}

Is "{name}" a PERSON or an internal TEAM of people (like "the security team")?
Places, plants, offices, products, tools, companies, and documents are NOT.

Answer with ONLY this JSON: {{"is_person_or_team": true or false}}"""
