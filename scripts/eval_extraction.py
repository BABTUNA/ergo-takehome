#!/usr/bin/env python3
"""Assert extraction found what the stories scripted. Run after any prompt change."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSIGHTS = ROOT / "data" / "insights"

failures = []


def check(deal, label, cond):
    print(f"  {'pass' if cond else 'FAIL'}  [{deal}] {label}")
    if not cond:
        failures.append(f"[{deal}] {label}")


def load(slug):
    return json.loads((INSIGHTS / slug / "insights.json").read_text())


def main():
    g = load("globex")
    rhea = g["people"].get("p_rhea", {})
    check("globex", "Rhea sentiment = wary/negative", rhea.get("sentiment") in ("wary", "negative"))
    check("globex", "Rhea role = economic_buyer", rhea.get("role") == "economic_buyer")
    check("globex", "Rhea seniority = exec (inferred, no title)", rhea.get("seniority") == "exec")
    check("globex", "Rhea momentum = cooling", rhea.get("stats", {}).get("momentum") == "cooling")
    roi = [c for c in g["commitments"] if "roi" in c.get("what", "").lower()]
    check("globex", "ROI commitment found and broken",
          bool(roi) and roi[0]["status"] == "broken")
    named = [x for x in g["ghosts"] if x.get("named")]
    check("globex", "Priya = named ghost with >= 2 mentions",
          any("priya" in (x.get("name") or "").lower() and x["count"] >= 2 for x in named))
    check("globex", "security team = unnamed ghost",
          any(not x.get("named") and "security" in x["label"].lower() for x in g["ghosts"]))

    i = load("initech")
    sarah = i["people"].get("p_sbloom", {})
    check("initech", "Sarah momentum = cooling", sarah.get("stats", {}).get("momentum") == "cooling")
    check("initech", "Gwen (zero events) has no rollup", "p_gortiz" not in i["people"])

    u = load("umbra")
    for pid, name in (("p_evasquez", "Elena"), ("p_mjones", "Malik"), ("p_tsingh", "Tara")):
        check("umbra", f"{name} sentiment positive",
              u["people"].get(pid, {}).get("sentiment") == "positive")

    a = load("acme")
    check("acme", "no broken commitments",
          not any(c["status"] == "broken" for c in a["commitments"]))
    check("acme", "no named ghosts", not any(x.get("named") for x in a["ghosts"]))

    print()
    if failures:
        print(f"FAILED: {len(failures)} assertion(s)")
        sys.exit(1)
    print("All extraction assertions passed.")


if __name__ == "__main__":
    main()
