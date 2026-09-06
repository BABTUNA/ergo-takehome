"""Ingestion entry point: raw channel streams -> events.json + people.json per deal.

Run: python3 -m pipeline.ingest
"""

import json
from pathlib import Path

from .connectors import (GmailConnector, SalesforceConnector, SlackConnector,
                         ZoomConnector)
from .identity import Registry

ROOT = Path(__file__).resolve().parent.parent
DEALS = ROOT / "data" / "deals"
OUT = ROOT / "data" / "processed"


def ingest_deal(slug):
    registry = Registry()
    sf = SalesforceConnector()
    sf_raw = sf.fetch(slug)
    registry.seed_from_crm(sf.contacts(sf_raw))

    events = sf.normalize(sf_raw, slug, registry)
    for connector in (ZoomConnector(), GmailConnector(), SlackConnector()):
        events += connector.normalize(connector.fetch(slug), slug, registry)

    write_outputs(slug, events, registry, sf.opportunity(sf_raw))
    return len(events), len(registry.people())


def write_outputs(slug, events, registry, opportunity):
    events.sort(key=lambda e: e.ts)
    for i, event in enumerate(events, 1):
        event.id = f"ev_{i:03d}"
    out_dir = OUT / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "events.json").write_text(json.dumps(
        {"deal": opportunity, "events": [e.to_dict() for e in events]}, indent=2))
    (out_dir / "people.json").write_text(json.dumps(registry.to_json(), indent=2))


def main():
    for slug in sorted(p.name for p in DEALS.iterdir() if p.is_dir()):
        n_events, n_people = ingest_deal(slug)
        print(f"{slug}: {n_events} events, {n_people} people")


if __name__ == "__main__":
    main()
