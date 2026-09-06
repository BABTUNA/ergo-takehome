"""One connector per channel.

fetch() is the production swap point: here it reads a committed JSON file; in a real
deployment it would be an OAuth'd API pull or webhook feed. normalize() is identical
either way.
"""

import json
from pathlib import Path

from .models import Event

DATA = Path(__file__).resolve().parent.parent / "data" / "deals"


class Connector:
    filename = ""
    channel = ""

    def fetch(self, slug):
        return json.loads((DATA / slug / self.filename).read_text())

    def normalize(self, raw, deal_id, registry):
        raise NotImplementedError


class ZoomConnector(Connector):
    filename = "zoom.json"
    channel = "zoom"

    def normalize(self, raw, deal_id, registry):
        events = []
        for m in raw["meetings"]:
            people = [registry.resolve(a["email"], a.get("name"), "zoom")
                      for a in m["attendees"]]
            events.append(Event(
                id="", deal_id=deal_id, channel="zoom", type="meeting",
                ts=m["start_time"], participants=[p.id for p in people],
                direction="n/a", thread_key=m["id"],
                content={"topic": m["topic"], "duration_min": m["duration_min"],
                         "transcript": m["transcript"]},
            ))
        return events


class GmailConnector(Connector):
    filename = "gmail.json"
    channel = "gmail"

    def normalize(self, raw, deal_id, registry):
        events = []
        for th in raw["threads"]:
            for msg in th["messages"]:
                sender = registry.resolve(msg["from"], None, "gmail")
                others = [registry.resolve(e, None, "gmail")
                          for e in msg.get("to", []) + msg.get("cc", [])]
                events.append(Event(
                    id="", deal_id=deal_id, channel="gmail", type="message",
                    ts=msg["date"],
                    participants=[sender.id] + [p.id for p in others],
                    direction="outbound" if sender.side == "seller" else "inbound",
                    thread_key=th["id"],
                    content={"subject": th["subject"], "from": sender.id,
                             "body": msg["body"]},
                ))
        return events


class SlackConnector(Connector):
    filename = "slack.json"
    channel = "slack"

    def normalize(self, raw, deal_id, registry):
        for member in raw.get("members", []):
            registry.resolve(member, None, "slack")
        events = []
        for msg in raw["messages"]:
            author = registry.resolve(msg["author"], None, "slack")
            events.append(Event(
                id="", deal_id=deal_id, channel="slack", type="message",
                ts=msg["ts"], participants=[author.id],
                direction="outbound" if author.side == "seller" else "inbound",
                thread_key=raw["channel"],
                content={"from": author.id, "text": msg["text"]},
            ))
        return events


class SalesforceConnector(Connector):
    filename = "salesforce.json"
    channel = "salesforce"

    def contacts(self, raw):
        return raw.get("contacts", [])

    def opportunity(self, raw):
        return raw["opportunity"]

    def normalize(self, raw, deal_id, registry):
        events = []
        for entry in raw.get("stage_history", []):
            events.append(Event(
                id="", deal_id=deal_id, channel="salesforce", type="stage_change",
                ts=entry["entered"] + "T00:00:00Z", participants=[],
                direction="n/a", thread_key="",
                content={"stage": entry["stage"]},
            ))
        return events
