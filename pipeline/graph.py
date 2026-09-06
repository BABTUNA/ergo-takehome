"""Build the render-ready graph for one deal at one date. Pure code, no LLM."""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

LANE_WEIGHT = {"exec": 1.5, "director": 1.0, "team": 0.5}


def _ts(event):
    return datetime.fromisoformat(event["ts"].replace("Z", ""))


def seller_roster():
    """All seller-side people across every deal, with titles from your own org's
    directory (data/seller_directory.json) since a buyer's CRM never has them."""
    directory = {d["email"]: d for d in
                 json.loads((ROOT / "data" / "seller_directory.json").read_text())}
    roster = {}
    for path in PROCESSED.glob("*/people.json"):
        for p in json.loads(path.read_text()):
            if p["side"] == "seller":
                entry = roster.setdefault(p["email"], dict(p))
                info = directory.get(p["email"], {})
                entry["title"] = info.get("title", entry.get("title", ""))
                entry["name"] = entry["name"] or info.get("name", "")
    return list(roster.values())


def _seller_lane(person):
    title = (person.get("title") or "").lower()
    if "vp" in title or title.startswith("chief") or " c" in f" {title[:3]}":
        return "exec"
    return "team"


def momentum_at(events, pid, t):
    """Trailing 14d vs prior 14d of authored/attended activity, as of t."""
    dates = []
    for e in events:
        active = e["participants"] if e["type"] == "meeting" else e["participants"][:1]
        if pid in active and _ts(e) <= t:
            dates.append(_ts(e))
    if not dates:
        return "flat", None
    recent = sum(1 for d in dates if d > t - timedelta(days=14))
    prior = sum(1 for d in dates if t - timedelta(days=28) < d <= t - timedelta(days=14))
    if recent > prior:
        momentum = "rising"
    elif recent == 0 and prior > 0 or recent < prior / 2:
        momentum = "cooling"
    else:
        momentum = "flat"
    return momentum, max(dates)


def build_graph(events, insights, people, roster, t):
    conv = [e for e in events if e["type"] != "stage_change" and _ts(e) <= t]
    people_by_id = {p["id"]: p for p in people}
    rollups = insights["people"]

    seen = defaultdict(int)
    for e in conv:
        for pid in e["participants"]:
            seen[pid] += 1

    roster_by_email = {p["email"]: p for p in roster}
    nodes = []
    node_ids = set()
    for pid, count in seen.items():
        person = people_by_id[pid]
        if person["side"] == "seller" and person["email"] in roster_by_email:
            person = {**person, "title": roster_by_email[person["email"]]["title"]}
        rollup = rollups.get(pid, {})
        momentum, last = momentum_at(events, pid, t)
        lane = _seller_lane(person) if person["side"] == "seller" \
            else rollup.get("seniority") or "team"
        nodes.append({
            "id": pid, "name": person["name"] or person["email"],
            "title": person["title"], "side": person["side"], "lane": lane,
            "role": rollup.get("role", "seller" if person["side"] == "seller" else "neutral"),
            "sentiment": rollup.get("sentiment", "neutral"),
            "momentum": momentum, "events": count,
            "quiet_days": (t - last).days if last else None,
            "in_crm": person["in_crm"], "ghost": False})
        node_ids.add(pid)

    for person in roster:
        if person["id"] not in node_ids:
            nodes.append({
                "id": person["id"], "name": person["name"], "title": person["title"],
                "side": "seller", "lane": _seller_lane(person), "role": "seller",
                "sentiment": "neutral", "momentum": "flat", "events": 0,
                "quiet_days": None, "in_crm": person["in_crm"], "ghost": False})
            node_ids.add(person["id"])

    events_by_id = {e["id"]: e for e in events}
    for i, ghost in enumerate(insights.get("ghosts", [])):
        mention_times = [_ts(events_by_id[eid]) for eid in ghost["events"] if eid in events_by_id]
        if not mention_times or min(mention_times) > t:
            continue
        seen_mentions = sum(1 for mt in mention_times if mt <= t)
        nodes.append({
            "id": f"ghost_{i}", "name": ghost.get("name") or ghost["label"],
            "title": "", "side": "buyer", "lane": "unknown", "role": "ghost",
            "sentiment": "neutral", "momentum": "flat", "events": 0,
            "quiet_days": None, "in_crm": False, "ghost": True,
            "named": ghost.get("named", False), "mentions": seen_mentions,
            "mention_events": ghost["events"]})

    edges = _build_edges(conv, t)
    return {"t": t.date().isoformat(), "nodes": nodes, "edges": edges}


def _build_edges(conv, t):
    pair_times = defaultdict(list)
    slack_activity = defaultdict(lambda: defaultdict(list))

    for e in conv:
        when = _ts(e)
        if e["type"] == "meeting":
            ids = e["participants"]
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    pair_times[tuple(sorted((a, b)))].append(when)
        elif e["channel"] == "gmail":
            sender, others = e["participants"][0], e["participants"][1:]
            for b in others:
                pair_times[tuple(sorted((sender, b)))].append(when)
        elif e["channel"] == "slack":
            slack_activity[e["thread_key"]][e["participants"][0]].append(when)

    for channel_authors in slack_activity.values():
        authors = list(channel_authors)
        for i, a in enumerate(authors):
            for b in authors[i + 1:]:
                weight = min(len(channel_authors[a]), len(channel_authors[b]))
                last = min(max(channel_authors[a]), max(channel_authors[b]))
                pair_times[tuple(sorted((a, b)))].extend([last] * weight)

    edges = []
    for (a, b), times in pair_times.items():
        edges.append({"a": a, "b": b, "weight": len(times),
                      "days_stale": (t - max(times)).days})
    return sorted(edges, key=lambda e: -e["weight"])


def deal_rollup(graph, flags):
    engaged = [n for n in graph["nodes"]
               if n["side"] == "buyer" and not n["ghost"] and n["events"] > 0]
    thread_score = round(sum(LANE_WEIGHT.get(n["lane"], 0.5) for n in engaged), 1)
    lanes = [n["lane"] for n in engaged]
    highest = "exec" if "exec" in lanes else "director" if "director" in lanes else \
              "team" if lanes else "none"
    severities = [f["severity"] for f in flags]
    return {"thread_score": thread_score, "engaged_buyers": len(engaged),
            "highest_lane": highest, "open_flags": len(flags),
            "top_severity": "high" if "high" in severities else
                            "med" if "med" in severities else
                            "low" if severities else "none"}
