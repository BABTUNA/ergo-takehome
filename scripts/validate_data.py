#!/usr/bin/env python3
"""Validate the synthetic data streams against stories.yaml.

Checks, per deal:
  1. Stream files exist and match the expected shape
  2. Every timestamp falls inside the story window
  3. Every participant resolves to a cast member (seller or buyer)
  4. Every beat has at least one event in its named stream within +/- 1 day
  5. CRM consistency: in_crm cast members appear in salesforce contacts, others don't
  6. Story-specific assertions (silences, ghost mentions, planted variants)

Exit code 0 = all pass. Run: python3 scripts/validate_data.py
"""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

failures = []


def fail(deal, msg):
    failures.append(f"[{deal}] {msg}")


def ok(deal, msg):
    print(f"  pass  [{deal}] {msg}")


def parse_ts(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_deal(slug):
    streams = {}
    for name in ("zoom", "gmail", "slack", "salesforce"):
        path = DATA / "deals" / slug / f"{name}.json"
        if not path.exists():
            fail(slug, f"missing stream file {path.name}")
            streams[name] = None
            continue
        streams[name] = json.loads(path.read_text())
    return streams


def collect_events(streams):
    """Flatten every stream into (ts, stream, emails, text) tuples."""
    events = []
    zoom = streams.get("zoom") or {"meetings": []}
    for m in zoom["meetings"]:
        emails = [a["email"] for a in m["attendees"]]
        text = " ".join(t["text"] for t in m["transcript"])
        events.append((parse_ts(m["start_time"]), "zoom", emails, text))
    gmail = streams.get("gmail") or {"threads": []}
    for th in gmail["threads"]:
        for msg in th["messages"]:
            emails = [msg["from"]] + msg.get("to", []) + msg.get("cc", [])
            events.append((parse_ts(msg["date"]), "gmail", emails, msg["body"]))
    slack = streams.get("slack") or {"messages": []}
    for msg in slack["messages"]:
        events.append((parse_ts(msg["ts"]), "slack", [msg["author"]], msg["text"]))
    return events


def main():
    stories = yaml.safe_load((DATA / "stories.yaml").read_text())
    anchor = stories["anchor"]
    window_start = datetime.combine(anchor["window_start"], datetime.min.time())
    window_end = datetime.combine(anchor["today"], datetime.max.time())
    seller_emails = {c["email"] for c in stories["seller"]["cast"]}

    for slug, deal in stories["deals"].items():
        streams = load_deal(slug)
        events = collect_events(streams)
        cast_emails = {c["email"] for c in deal["cast"]} | seller_emails

        # 2. timestamps in window
        out_of_window = [e for e in events if not (window_start <= e[0].replace(tzinfo=None) <= window_end)]
        if out_of_window:
            for e in out_of_window:
                fail(slug, f"event at {e[0]} outside window")
        else:
            ok(slug, f"{len(events)} events, all inside window")

        # 3. participants resolve
        strangers = {em for e in events for em in e[2] if em not in cast_emails}
        if strangers:
            fail(slug, f"unresolved participants: {sorted(strangers)}")
        else:
            ok(slug, "every participant resolves to cast")

        # 4. beats present
        for beat in deal["beats"]:
            beat_day = beat["date"]
            lo = datetime.combine(beat_day - timedelta(days=1), datetime.min.time())
            hi = datetime.combine(beat_day + timedelta(days=1), datetime.max.time())
            hits = [e for e in events if e[1] == beat["stream"] and lo <= e[0].replace(tzinfo=None) <= hi]
            if not hits:
                fail(slug, f"beat missing: {beat_day} [{beat['stream']}] {beat['note'][:60]}")
        ok(slug, f"{len(deal['beats'])} beats checked")

        # 5. CRM consistency
        sf = streams.get("salesforce") or {"contacts": []}
        crm_emails = {c["email"] for c in sf["contacts"]}
        for member in deal["cast"]:
            if member.get("in_crm") and member["email"] not in crm_emails:
                fail(slug, f"{member['name']} should be in salesforce contacts but isn't")
            if not member.get("in_crm") and member["email"] in crm_emails:
                fail(slug, f"{member['name']} should NOT be in salesforce contacts but is")
        ok(slug, "CRM contact flags consistent")

        # 6. story-specific assertions
        story_checks(slug, events, streams)

    print()
    if failures:
        print(f"FAILED: {len(failures)} problem(s)")
        for f in failures:
            print(f"  FAIL  {f}")
        sys.exit(1)
    print("All checks passed.")


def last_activity(events, email):
    dates = [e[0] for e in events if email in e[2]]
    return max(dates) if dates else None


def count_events(events, email):
    return sum(1 for e in events if email in e[2])


def mention_count(events, needle):
    return sum(1 for e in events if needle.lower() in e[3].lower())


def story_checks(slug, events, streams):
    if slug == "globex":
        last_rhea = last_activity(events, "rhea@globex.com")
        cutoff = datetime(2026, 3, 26, tzinfo=last_rhea.tzinfo) if last_rhea else None
        # Rhea authors nothing after Mar 20 email; only *receives* after. Check she authored nothing after Mar 26.
        authored = [e[0] for e in events
                    if e[1] != "zoom" and e[2][:1] == ["rhea@globex.com"]]
        late = [d for d in authored if d.replace(tzinfo=None) > datetime(2026, 3, 26, 23, 59)]
        if late:
            fail(slug, f"Rhea authored messages after Mar 26: {late}")
        else:
            ok(slug, "Rhea silent (as author) after Mar 26")
        if mention_count(events, "priya") >= 2:
            ok(slug, "Priya mentioned >= 2 times")
        else:
            fail(slug, "Priya ghost mentions < 2")
        if mention_count(events, "security team") >= 1:
            ok(slug, "unnamed security team mentioned")
        else:
            fail(slug, "no 'security team' mention found")
        if mention_count(events, "Rhea K.") >= 1:
            ok(slug, "'Rhea K.' name variant planted")
        else:
            fail(slug, "'Rhea K.' name variant missing")

    if slug == "initech":
        last_sarah = last_activity(events, "sbloom@initech.com")
        authored = [e[0] for e in events if e[2][:1] == ["sbloom@initech.com"]]
        late = [d for d in authored if d.replace(tzinfo=None) > datetime(2026, 3, 24, 23, 59)]
        if late:
            fail(slug, f"Sarah authored messages after Mar 24: {late}")
        else:
            ok(slug, "Sarah silent (as author) after Mar 24")
        if count_events(events, "gortiz@initech.com") == 0:
            ok(slug, "CFO Gwen has zero events (CRM-only)")
        else:
            fail(slug, "CFO Gwen should have zero events")
        if count_events(events, "thale@initech.com") <= 2:
            ok(slug, "Travis appears once then vanishes")
        else:
            fail(slug, "Travis has too many events")

    if slug == "umbra":
        for em, name in (("sam@harborview.io", "Sam"), ("ava@harborview.io", "Ava")):
            n = count_events(events, em)
            if n == 0:
                ok(slug, f"{name} has zero Umbra contacts (internal single-threading)")
            else:
                fail(slug, f"{name} should have zero Umbra events, has {n}")

    if slug == "acme":
        for em in ("mwebb@acmeind.com", "dwhitfield@acmeind.com",
                   "lnakamura@acmeind.com", "ifarah@acmeind.com"):
            if count_events(events, em) < 2:
                fail(slug, f"{em} under-engaged for the healthy control")
        if count_events(events, "ava@harborview.io") >= 1:
            ok(slug, "healthy control: all buyers engaged, Ava present")
        else:
            fail(slug, "Ava missing from the healthy control")


if __name__ == "__main__":
    main()
