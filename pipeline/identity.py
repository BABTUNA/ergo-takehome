"""Person registry: everything that maps an observed email or name to one Person."""

from .models import Person

SELLER_DOMAIN = "harborview.io"


def _side(email):
    return "seller" if email.endswith("@" + SELLER_DOMAIN) else "buyer"


class Registry:
    def __init__(self):
        self._by_email = {}
        self._counter = 0

    def _new_id(self, email):
        self._counter += 1
        local = email.split("@")[0].replace(".", "_")
        return f"p_{local}"

    def seed_from_crm(self, contacts):
        """CRM contacts enter first so in_crm is a fact, not an ordering accident."""
        for c in contacts:
            email = c["email"].lower()
            self._by_email[email] = Person(
                id=self._new_id(email),
                name=c.get("name", ""),
                email=email,
                title=c.get("title", ""),
                side=_side(email),
                in_crm=True,
                provisional=False,
            )

    def resolve(self, email, name=None, channel=None):
        """Return the Person for an observed email, creating a provisional one if new."""
        email = email.lower()
        person = self._by_email.get(email)
        if person is None:
            person = Person(
                id=self._new_id(email),
                name=name or "",
                email=email,
                title="",
                side=_side(email),
                in_crm=False,
                provisional=True,
            )
            self._by_email[email] = person
        if name:
            if not person.name:
                person.name = name
            if channel:
                seen = person.aliases.setdefault(channel, [])
                if name not in seen:
                    seen.append(name)
        return person

    def match_name(self, name):
        """Best-effort name -> Person for mention resolution (used by extraction).

        Matches full name, any recorded alias, or first name + last initial
        ("Rhea K." -> Rhea Kim). Returns None when nothing matches.
        """
        needle = name.strip().lower().rstrip(".")
        for person in self._by_email.values():
            known = [person.name] + [a for names in person.aliases.values() for a in names]
            for k in known:
                k_low = k.lower()
                if not k_low:
                    continue
                if k_low == needle:
                    return person
                parts = k_low.split()
                n_parts = needle.split()
                if (len(parts) >= 2 and len(n_parts) == 2
                        and parts[0] == n_parts[0]
                        and parts[1].startswith(n_parts[1][0])):
                    return person
                if len(n_parts) == 1 and parts and parts[0] == n_parts[0]:
                    return person
        return None

    def people(self):
        return list(self._by_email.values())

    def to_json(self):
        return [p.to_dict() for p in self._by_email.values()]
