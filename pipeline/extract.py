"""Extraction orchestrator: processed events -> insights.json per deal.

Run: python3 -m pipeline.extract
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from . import llm, prompts
from .identity import Registry
from .models import Person

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "data" / "insights"

TODAY = datetime(2026, 4, 7)  # the demo anchor from stories.yaml


def _rebuild_registry(people):
    registry = Registry()
    for p in people:
        registry._by_email[p["email"]] = Person(**p)
    return registry


def _event_text(event):
    c = event["content"]
    if event["type"] == "meeting":
        lines = [f'{t["speaker"]}: {t["text"]}' for t in c["transcript"]]
        return f'Meeting "{c["topic"]}" ({c["duration_min"]} min)\n' + "\n".join(lines)
    if event["channel"] == "gmail":
        return f'Subject: {c["subject"]}\n{c["body"]}'
    return c["text"]


def extract_event(event, people_by_id):
    roster = "\n".join(
        f'{pid} = {people_by_id[pid]["name"] or people_by_id[pid]["email"]} ({people_by_id[pid]["side"]})'
        for pid in event["participants"])
    prompt = prompts.EVENT_PROMPT.format(
        roster=roster, channel=event["channel"], content=_event_text(event))
    result = llm.complete(llm.HAIKU, prompt, prompts.EVENT_KEYS)
    result["event_id"] = event["id"]
    return result


def resolve_mentions(all_mentions, registry):
    ghosts = {}
    for event_id, mention in all_mentions:
        name = (mention.get("name") or "").strip()
        if name and registry.match_name(name):
            continue
        key = name.lower() or mention.get("context", "")[:30].lower()
        ghost = ghosts.setdefault(key, {
            "name": name or None,
            "label": name or mention.get("name") or "unnamed group",
            "named": bool(name and name[0].isupper()),
            "count": 0, "events": [], "contexts": []})
        ghost["count"] += 1
        if event_id not in ghost["events"]:
            ghost["events"].append(event_id)
        ghost["contexts"].append(mention.get("context", ""))
    return list(ghosts.values())


def match_fulfillment(commitments, events):
    events_by_id = {e["id"]: e for e in events}
    results = []
    for event_id, c in commitments:
        origin_ts = events_by_id[event_id]["ts"]
        later = [e for e in events
                 if e["ts"] > origin_ts and c.get("by") in e.get("participants", [])[:1]]
        fulfilled = False
        for e in later:
            prompt = prompts.FULFILL_PROMPT.format(
                what=c.get("what", ""), due=c.get("due", "unspecified"),
                channel=e["channel"], ts=e["ts"], content=_event_text(e)[:1500])
            verdict = llm.complete(llm.HAIKU, prompt)
            if verdict.get("fulfills"):
                fulfilled = True
                break
        status = "kept" if fulfilled else "broken"
        results.append({**c, "origin_event": event_id, "status": status})
    return results


def engagement_stats(events):
    by_person = defaultdict(list)
    for e in events:
        for pid in e.get("participants", []):
            by_person[pid].append(datetime.fromisoformat(e["ts"].replace("Z", "")))
    stats = {}
    for pid, dates in by_person.items():
        recent = sum(1 for d in dates if d > TODAY - timedelta(days=14))
        prior = sum(1 for d in dates if TODAY - timedelta(days=28) < d <= TODAY - timedelta(days=14))
        if recent > prior:
            momentum = "rising"
        elif recent == 0 and prior > 0 or recent < prior / 2:
            momentum = "cooling"
        else:
            momentum = "flat"
        last = max(dates)
        stats[pid] = {"events": len(dates), "last_touch": last.date().isoformat(),
                      "quiet_days": (TODAY - last).days, "momentum": momentum}
    return stats


def rollup_person(person, deal, history_lines, stats):
    person_line = (f'{person["id"]} ({person["name"] or person["email"]}), '
                   f'{person["side"]} side, title: {person["title"] or "unknown"}, '
                   f'{"in CRM" if person["in_crm"] else "NOT in CRM"}')
    stats_line = json.dumps(stats)
    prompt = prompts.PERSON_PROMPT.format(
        person_line=person_line,
        deal_line=f'{deal["name"]}, ${deal["amount"]}, stage {deal["stage"]}',
        stats_line=stats_line, history="\n".join(history_lines) or "(no extracted signals)")
    return llm.complete(llm.SONNET, prompt, prompts.PERSON_KEYS)


def extract_deal(slug):
    data = json.loads((PROCESSED / slug / "events.json").read_text())
    deal, events = data["deal"], data["events"]
    people = json.loads((PROCESSED / slug / "people.json").read_text())
    people_by_id = {p["id"]: p for p in people}
    registry = _rebuild_registry(people)

    conversation = [e for e in events if e["type"] != "stage_change"]
    pass1 = [extract_event(e, people_by_id) for e in conversation]

    all_mentions = [(r["event_id"], m) for r in pass1 for m in r["mentions"]]
    all_commitments = [(r["event_id"], c) for r in pass1 for c in r["commitments"]]
    ghosts = resolve_mentions(all_mentions, registry)
    commitments = match_fulfillment(all_commitments, events)
    stats = engagement_stats(conversation)

    signals = [{**s, "event_id": r["event_id"]} for r in pass1 for s in r["signals"]]
    tones = [(r["event_id"], t) for r in pass1 for t in r["tone"]]
    events_by_id = {e["id"]: e for e in events}

    rollups = {}
    for pid, pstats in stats.items():
        person = people_by_id[pid]
        history = []
        for s in signals:
            if s["who"] == pid:
                history.append(f'{events_by_id[s["event_id"]]["ts"][:10]} {s["event_id"]}: signal {s["tag"]} ("{s["quote"]}")')
        for eid, t in tones:
            if t["who"] == pid:
                history.append(f'{events_by_id[eid]["ts"][:10]} {eid}: tone {t["label"]}')
        for c in commitments:
            if pid in (c.get("by"), c.get("to")):
                who = "made" if c.get("by") == pid else "received"
                history.append(f'{who} commitment: "{c["what"]}" (status: {c["status"]})')
        history.sort()
        rollups[pid] = {**rollup_person(person, deal, history, pstats), "stats": pstats}

    OUT.joinpath(slug).mkdir(parents=True, exist_ok=True)
    (OUT / slug / "insights.json").write_text(json.dumps({
        "deal": deal, "people": rollups, "signals": signals,
        "commitments": commitments, "ghosts": ghosts}, indent=2))
    return len(conversation), len(rollups), len(ghosts)


def main():
    for slug in sorted(p.name for p in PROCESSED.iterdir() if p.is_dir()):
        n_events, n_people, n_ghosts = extract_deal(slug)
        print(f"{slug}: {n_events} events -> {n_people} people, {n_ghosts} ghosts")


if __name__ == "__main__":
    main()
