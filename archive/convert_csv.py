"""Convert original.csv to MechBay JSON import format."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def convert_csv_to_json(csv_path: str, json_path: str) -> int:
    """Read CSV and convert to MechBay JSON format.

    Returns count of miniatures converted.
    """

    miniatures = []
    csv_file = Path(csv_path)

    # Load existing unique_ids if json_path exists
    existing_ids = set()
    output = Path(json_path)
    if output.exists():
        try:
            with output.open(encoding="utf-8") as jf:
                data = json.load(jf)
                for m in data:
                    if isinstance(m.get("unique_id"), int):
                        existing_ids.add(m["unique_id"])
        except Exception:
            pass

    next_id = max(existing_ids) + 1 if existing_ids else 1

    with csv_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            unit = row.get("Unit", "").strip()
            series = row.get("Series", "").strip()
            id_number = row.get("ID Number", "").strip()
            prefix = row.get("Prefix", "").strip()

            # Skip empty rows (no unit name)
            if not unit:
                continue

            # If ID Number is present and is an integer, use it as unique_id
            unique_id = None
            if id_number.isdigit():
                unique_id = int(id_number)
            else:
                # Assign next available integer unique_id for new miniatures
                unique_id = next_id
                next_id += 1

            # If prefix is missing, leave it blank
            if not prefix:
                prefix = ""

            miniature = {
                "unique_id": unique_id,
                "prefix": prefix,
                "chassis": unit,
                "type": "Mech",  # All appear to be mechs based on the data
                "status": None,
                "tray_id": None,
                "notes": f"Series {series}" if series else None,
            }

            miniatures.append(miniature)

    # Write JSON

    output.write_text(json.dumps(miniatures, indent=2), encoding="utf-8")

    return len(miniatures)


if __name__ == "__main__":
    count = convert_csv_to_json("original.csv", "original_import.json")
    print(f"Converted {count} miniatures to original_import.json")
