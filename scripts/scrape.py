#!/usr/bin/env python3
"""Scrape Newcastle Mayor first-preference totals into results.json."""
import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone

URL = "https://results.elections.nsw.gov.au/LB2606/Newcastle/Mayor/FirstPreferencesReport.html"
OUT = pathlib.Path(__file__).resolve().parent.parent / "results.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# Map the surname printed in the header to the candidate key used in the webpage.
SURNAME_TO_KEY = {
    "OBRIEN":  "obrien",
    "MORRIS":  "morris",
    "McCABE":  "mccabe",
    "BARRIE":  "barrie",
    "CLAUSEN": "clausen",
    "CAINE":   "caine",
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def parse(html):
    # Column order comes from the generalHeader row
    header_m = re.search(r'<tr class="generalHeader">(.*?)</tr>', html, re.S)
    if not header_m:
        raise RuntimeError("header row not found")
    col_headers = [re.sub(r"<[^>]+>", "", s).strip()
                   for s in re.findall(r"<th[^>]*>(.*?)</th>", header_m.group(1), re.S)]

    # Candidate columns are those between "Venue and Vote Types" and "Total Formal"
    candidates = []
    for h in col_headers[1:]:
        if h.startswith("Total ") or h in ("Informal", "Count_Status"):
            break
        surname = h.split()[0]
        candidates.append(surname)

    # Find summary row labeled "Total Votes / Ballot Papers"
    summary = None
    for sr in re.findall(r'<tr class="summaryRow">(.*?)</tr>', html, re.S):
        label_m = re.search(r"<td>\s*(.*?)\s*</td>", sr, re.S)
        label = re.sub(r"<[^>]+>", "", label_m.group(1)).strip() if label_m else ""
        if label.startswith("Total Votes"):
            summary = sr
            break
    if summary is None:
        raise RuntimeError("totals summary row not found")

    values = re.findall(r"<span>\s*([^<]*?)\s*</span>", summary)
    # Values align with col_headers[1:]; we expect candidate cols then Total Formal, Informal, Total V/BP
    parsed_values = []
    for v in values:
        v = v.replace(",", "").strip()
        parsed_values.append(int(v) if v.isdigit() else None)

    totals = {}
    for surname, val in zip(candidates, parsed_values):
        key = SURNAME_TO_KEY.get(surname)
        if key is None:
            raise RuntimeError(f"unknown surname {surname!r} — update SURNAME_TO_KEY")
        totals[key] = val if val is not None else 0

    # Formal / informal / ballot papers come after the candidate columns
    tail = parsed_values[len(candidates):]
    formal      = tail[0] if len(tail) > 0 else None
    informal    = tail[1] if len(tail) > 1 else None
    ballot_papers = tail[2] if len(tail) > 2 else None

    return {
        "source": URL,
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": totals,
        "formal": formal,
        "informal": informal,
        "ballot_papers": ballot_papers,
    }

def main():
    html = fetch(URL)
    data = parse(html)
    OUT.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"scrape failed: {e}", file=sys.stderr)
        sys.exit(1)
