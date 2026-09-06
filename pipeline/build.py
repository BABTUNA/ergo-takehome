"""Graph layer entry point: insights + events -> weekly graph snapshots per deal.

Run: python3 -m pipeline.build
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from .detectors import run_detectors
from .graph import build_graph, deal_rollup, seller_roster

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"
INSIGHTS = ROOT / "data" / "insights"
OUT = ROOT / "data" / "graph"

TODAY = datetime(2026, 4, 7)
FIRST_SNAPSHOT = datetime(2026, 2, 16)


def snapshot_dates():
    dates, t = [], FIRST_SNAPSHOT
    while t < TODAY:
        dates.append(t)
        t += timedelta(days=7)
    dates.append(TODAY)
    return dates


def build_deal(slug):
    events = json.loads((PROCESSED / slug / "events.json").read_text())
    people = json.loads((PROCESSED / slug / "people.json").read_text())
    insights = json.loads((INSIGHTS / slug / "insights.json").read_text())
    deal = events["deal"]
    roster = seller_roster()

    snapshots = []
    for t in snapshot_dates():
        graph = build_graph(events["events"], insights, people, roster, t)
        flags = run_detectors(graph, insights, deal, t)
        graph["flags"] = flags
        graph["rollup"] = deal_rollup(graph, flags)
        snapshots.append(graph)

    OUT.joinpath(slug).mkdir(parents=True, exist_ok=True)
    (OUT / slug / "graph.json").write_text(json.dumps(
        {"deal": deal, "snapshots": snapshots}, indent=2))
    return snapshots[-1]


def main():
    for slug in sorted(p.name for p in INSIGHTS.iterdir() if p.is_dir()):
        final = build_deal(slug)
        flag_ids = [f["id"] for f in final["flags"]]
        r = final["rollup"]
        print(f"{slug}: score {r['thread_score']}, {r['engaged_buyers']} buyers, "
              f"flags: {flag_ids or 'none'}")


if __name__ == "__main__":
    main()
