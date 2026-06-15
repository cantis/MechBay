"""Fetch complete MUL faction list from the official index page."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

INDEX_URL = "https://masterunitlist.azurewebsites.net/Faction/Index"
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "data" / "mul_factions.json"

# MUL renders factions as clickable tiles: data-link + nearby <strong> label.
_FACTION_PATTERN = re.compile(
    r'data-link="(/Faction/Details/(\d+))"[^>]*>.*?<strong[^>]*>([^<]+)</strong>',
    re.S,
)


def main() -> None:
    html = urllib.request.urlopen(INDEX_URL, timeout=30).read().decode("utf-8", errors="replace")
    seen: set[int] = set()
    factions: list[dict] = []

    for _link, raw_id, name in _FACTION_PATTERN.findall(html):
        faction_id = int(raw_id)
        clean_name = name.strip()
        if not clean_name or faction_id in seen:
            continue
        seen.add(faction_id)
        factions.append({"id": faction_id, "name": clean_name})

    factions.sort(key=lambda f: f["name"].lower())
    OUTPUT.write_text(json.dumps(factions, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(factions)} factions to {OUTPUT}")
    merc = next((f for f in factions if f["name"] == "Mercenary"), None)
    print("Mercenary:", merc)


if __name__ == "__main__":
    main()
