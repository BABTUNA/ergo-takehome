"""Core data shapes shared by every pipeline stage."""

from dataclasses import dataclass, field, asdict


@dataclass
class Event:
    id: str
    deal_id: str
    channel: str          # zoom | gmail | slack | salesforce
    type: str             # meeting | message | stage_change
    ts: str               # ISO 8601
    participants: list    # person ids, empty for stage_change
    direction: str        # inbound | outbound | n/a
    thread_key: str       # meeting id / thread id / channel name / ""
    content: dict         # channel-specific payload

    def to_dict(self):
        return asdict(self)


@dataclass
class Person:
    id: str
    name: str             # best known display name ("" if only an email was ever seen)
    email: str
    title: str            # from CRM only; "" when unknown
    side: str             # seller | buyer
    in_crm: bool
    provisional: bool     # True when first seen in a conversation, not the CRM
    aliases: dict = field(default_factory=dict)   # channel -> names seen there

    def to_dict(self):
        return asdict(self)
