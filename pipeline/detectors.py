"""Seven risk detectors: rule functions over one graph snapshot.

Each returns a flag dict or None. Moves are filled from templates with names and
dates from the evidence - never LLM-generated, so the demo can't improvise.
"""

SINGLE_THREAD_SHARE = 0.80
INTERNAL_THREAD_SHARE = 0.90
QUIET_DAYS_LIMIT = 10
ALTITUDE_STAGES = {"Proposal", "Negotiation"}


def _buyer_edge_share(graph, side_of_interest):
    """Per-person share of cross-side edge weight, for one side."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    totals = {}
    for e in graph["edges"]:
        a, b = nodes.get(e["a"]), nodes.get(e["b"])
        if not a or not b or a["side"] == b["side"]:
            continue
        person = a if a["side"] == side_of_interest else b
        totals[person["id"]] = totals.get(person["id"], 0) + e["weight"]
    total = sum(totals.values())
    return totals, total


def single_threaded(graph, insights, deal, t):
    totals, total = _buyer_edge_share(graph, "buyer")
    if not total:
        return None
    top_id, top = max(totals.items(), key=lambda kv: kv[1])
    if top / total < SINGLE_THREAD_SHARE:
        return None
    nodes = {n["id"]: n for n in graph["nodes"]}
    name = nodes[top_id]["name"]
    return {"id": "single_threaded", "severity": "high",
            "summary": f"{int(100 * top / total)}% of buyer contact runs through {name}",
            "evidence": [],
            "suggested_move": f"Ask {name} to introduce a second stakeholder before the next call"}


def altitude_gap(graph, insights, deal, t):
    if deal["stage"] not in ALTITUDE_STAGES:
        return None
    engaged = [n for n in graph["nodes"]
               if n["side"] == "buyer" and not n["ghost"] and n["events"] > 0]
    if not engaged or any(n["lane"] == "exec" for n in engaged):
        return None
    return {"id": "altitude_gap", "severity": "med",
            "summary": f"Deal in {deal['stage']} with no one above director level ever engaged",
            "evidence": [],
            "suggested_move": "Get an exec sponsor into the next meeting before advancing the stage"}


def cooling_key_contact(graph, insights, deal, t):
    for n in graph["nodes"]:
        if (n["role"] in ("economic_buyer", "champion") and n["momentum"] == "cooling"
                and (n["quiet_days"] or 0) > QUIET_DAYS_LIMIT):
            rollup = insights["people"].get(n["id"], {})
            return {"id": "cooling_key_contact", "severity": "high",
                    "summary": f"{n['name']} ({n['role'].replace('_', ' ')}) quiet for {n['quiet_days']} days",
                    "evidence": rollup.get("evidence", []),
                    "suggested_move": f"Re-engage {n['name']} with something of value, not a check-in"}
    return None


def broken_commitment(graph, insights, deal, t):
    broken = [c for c in insights.get("commitments", []) if c["status"] == "broken"]
    for c in sorted(broken, key=lambda c: c["origin_event"], reverse=True):
            return {"id": "broken_commitment", "severity": "high",
                    "summary": f'Promise not kept: "{c["what"]}" (due {c.get("due") or "unspecified"})',
                    "evidence": [c["origin_event"]],
                    "suggested_move": f'Deliver "{c["what"]}" today and acknowledge the delay'}
    return None


def ghost_stakeholder(graph, insights, deal, t):
    ghosts = [n for n in graph["nodes"] if n["ghost"]]
    named = [g for g in ghosts if g.get("named") and g.get("mentions", 0) >= 2]
    blocking = [g for g in ghosts if not g.get("named")
                and any(w in g["name"].lower() for w in ("security", "review", "approval"))]
    target = (named + blocking)
    if not target:
        return None
    g = target[0]
    return {"id": "ghost_stakeholder", "severity": "med",
            "summary": f"{g['name']} mentioned {g.get('mentions', 1)}x but never engaged",
            "evidence": g.get("mention_events", []),
            "suggested_move": f"Ask your champion to bring {g['name']} into the next session"}


def internal_single_thread(graph, insights, deal, t):
    engaged_buyers = [n for n in graph["nodes"]
                      if n["side"] == "buyer" and not n["ghost"] and n["events"] >= 2]
    sellers = [n for n in graph["nodes"] if n["side"] == "seller"]
    if len(engaged_buyers) < 2 or len(sellers) < 2:
        return None
    totals, total = _buyer_edge_share(graph, "seller")
    if not total:
        return None
    top_id, top = max(totals.items(), key=lambda kv: kv[1])
    if top / total < INTERNAL_THREAD_SHARE:
        return None
    nodes = {n["id"]: n for n in graph["nodes"]}
    idle = [n["name"] for n in sellers if totals.get(n["id"], 0) == 0]
    return {"id": "internal_single_thread", "severity": "med",
            "summary": f"{nodes[top_id]['name']} holds every buyer relationship; {', '.join(idle) or 'teammates'} have none",
            "evidence": [],
            "suggested_move": f"Pair {idle[0] if idle else 'a teammate'} with a buyer counterpart before the next milestone"}


def no_exec_pairing(graph, insights, deal, t):
    nodes = {n["id"]: n for n in graph["nodes"]}
    buyer_execs = [n for n in graph["nodes"]
                   if n["side"] == "buyer" and n["lane"] == "exec"
                   and not n["ghost"] and n["events"] > 0]
    seller_execs = {n["id"] for n in graph["nodes"]
                    if n["side"] == "seller" and n["lane"] == "exec"}
    for exec_buyer in buyer_execs:
        paired = any({e["a"], e["b"]} & seller_execs and exec_buyer["id"] in (e["a"], e["b"])
                     for e in graph["edges"])
        if not paired:
            seller_name = next((nodes[s]["name"] for s in seller_execs), "your exec")
            return {"id": "no_exec_pairing", "severity": "low",
                    "summary": f"{exec_buyer['name']} ({exec_buyer['title'] or 'exec'}) has no seller-exec relationship",
                    "evidence": [],
                    "suggested_move": f"Introduce {seller_name} to {exec_buyer['name']} before commercial talks"}
    return None


ALL = (single_threaded, altitude_gap, cooling_key_contact, broken_commitment,
       ghost_stakeholder, internal_single_thread, no_exec_pairing)


def run_detectors(graph, insights, deal, t):
    flags = [f for f in (d(graph, insights, deal, t) for d in ALL) if f]
    ids = {f["id"] for f in flags}
    if "single_threaded" in ids:
        # one buyer contact implies one seller contact; the internal flag adds nothing
        flags = [f for f in flags if f["id"] != "internal_single_thread"]
    order = {"high": 0, "med": 1, "low": 2}
    return sorted(flags, key=lambda f: order[f["severity"]])
