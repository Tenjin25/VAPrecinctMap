#!/usr/bin/env python3
"""
Build cleaned Virginia county/city Census population estimates.

Inputs:
- Data/CO-EST2025-POP-51.csv
- Data/tl_2020_51_county20.geojson

Outputs:
- Data/county_population_estimates_2025.json
- Data/county_population_estimates_2025.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
TABLE_TITLE_PREFIX = "Annual Estimates of the Resident Population for Counties in Virginia:"
FOOTNOTE_PREFIXES = (
    "The Census Bureau has reviewed",
    "The estimates are based on",
    "Suggested Citation:",
    TABLE_TITLE_PREFIX,
    "Source: U.S. Census Bureau",
    "Release Date:",
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_key(value: str) -> str:
    return clean_text(value).replace("&", " AND ").upper()


def parse_int(value: str) -> int:
    s = clean_text(value).replace(",", "")
    if not s or s in {"-", "--"}:
        return 0
    return int(round(float(s)))


def pct_change(start: int, end: int) -> float | None:
    if not start:
        return None
    return round(((end - start) / start) * 100.0, 2)


def infer_locality_type(value: str) -> str:
    norm = normalize_key(value)
    if norm.endswith(" COUNTY"):
        return "county"
    if norm.endswith(" CITY"):
        return "city"
    if norm.endswith(" TOWN"):
        return "town"
    return "other"


def canonical_locality_from_census(name20: str, namelsad20: str) -> str:
    value = normalize_key(namelsad20) or normalize_key(name20)
    if not value:
        return ""
    match = re.match(r"^(.+?)\s+(COUNTY|CITY|TOWN)$", value)
    if match:
        return f"{match.group(1).strip()} {match.group(2)}"
    return value


def build_locality_index(county_geojson: Path) -> dict[str, dict]:
    raw = json.loads(county_geojson.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}

    for feature in raw.get("features", []):
        props = feature.get("properties", {}) or {}
        canonical = canonical_locality_from_census(
            str(props.get("NAME20", "")),
            str(props.get("NAMELSAD20", "")),
        )
        if not canonical:
            continue

        index[canonical] = {
            "name": clean_text(str(props.get("NAME20", ""))),
            "namelsad": clean_text(str(props.get("NAMELSAD20", ""))),
            "countyfp": clean_text(str(props.get("COUNTYFP20", ""))),
            "geoid": clean_text(str(props.get("GEOID20", ""))),
            "locality_type": infer_locality_type(str(props.get("NAMELSAD20", ""))),
        }

    return index


def normalize_csv_locality(raw: str) -> str:
    value = clean_text(raw)
    value = value.lstrip(".")
    value = re.sub(r",\s*VIRGINIA$", "", value, flags=re.IGNORECASE)
    return normalize_key(value)


def extract_table_title(rows: list[list[str]]) -> str:
    for row in rows:
        head = clean_text(row[0] if row else "")
        if head.startswith(TABLE_TITLE_PREFIX):
            return head
    return TABLE_TITLE_PREFIX


def extract_release_date(rows: list[list[str]]) -> str:
    for row in rows:
        head = clean_text(row[0] if row else "")
        if head.startswith("Release Date:"):
            return head.split(":", 1)[1].strip()
    return ""


def build_entry(locality_key: str, locality_name: str, geo: dict | None, estimate_base_2020: int, estimates: dict[int, int]) -> dict:
    estimate_2020 = estimates[2020]
    estimate_2025 = estimates[2025]
    entry = {
        "name": locality_name,
        "normalized_name": locality_key,
        "locality_type": (geo or {}).get("locality_type") or infer_locality_type(locality_name),
        "countyfp": (geo or {}).get("countyfp", ""),
        "geoid": (geo or {}).get("geoid", ""),
        "estimate_base_2020": estimate_base_2020,
        "estimate_2020": estimate_2020,
        "estimate_2021": estimates[2021],
        "estimate_2022": estimates[2022],
        "estimate_2023": estimates[2023],
        "estimate_2024": estimates[2024],
        "estimate_2025": estimate_2025,
        "estimates": {str(year): estimates[year] for year in YEARS},
        "change_base_to_2025": estimate_2025 - estimate_base_2020,
        "pct_change_base_to_2025": pct_change(estimate_base_2020, estimate_2025),
        "change_2020_to_2025": estimate_2025 - estimate_2020,
        "pct_change_2020_to_2025": pct_change(estimate_2020, estimate_2025),
    }
    return entry


def parse_rows(input_csv: Path, locality_index: dict[str, dict]) -> tuple[dict, dict[str, dict]]:
    with input_csv.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    header_idx = None
    for idx, row in enumerate(rows):
        head = clean_text(row[0] if row else "")
        if normalize_key(head) == "GEOGRAPHIC AREA":
            header_idx = idx
            break

    if header_idx is None:
        raise ValueError(f"Could not locate Census header row in {input_csv}")

    table_title = extract_table_title(rows)
    release_date = extract_release_date(rows)

    statewide: dict | None = None
    counties: dict[str, dict] = {}
    unmatched: list[str] = []

    for row in rows[header_idx + 2 :]:
        area_raw = clean_text(row[0] if row else "")
        if not area_raw:
            continue
        if area_raw.startswith(FOOTNOTE_PREFIXES):
            break
        if len(row) < 8:
            continue

        locality_key = normalize_csv_locality(area_raw)
        locality_name = clean_text(re.sub(r",\s*Virginia$", "", area_raw.lstrip("."), flags=re.IGNORECASE))
        estimate_base_2020 = parse_int(row[1])
        estimates = {year: parse_int(row[offset]) for offset, year in enumerate(YEARS, start=2)}
        entry = build_entry(
            locality_key=locality_key,
            locality_name=locality_name,
            geo=locality_index.get(locality_key),
            estimate_base_2020=estimate_base_2020,
            estimates=estimates,
        )

        if locality_key == "VIRGINIA":
            statewide = entry
            continue

        if locality_key not in locality_index:
            unmatched.append(locality_name)
            continue

        counties[locality_key] = entry

    if unmatched:
        raise ValueError(f"Unmatched Census localities: {', '.join(sorted(unmatched))}")

    if statewide is None:
        raise ValueError("Statewide Virginia row was not found in the Census estimates CSV")

    expected_count = len(locality_index)
    actual_count = len(counties)
    if actual_count != expected_count:
        raise ValueError(f"Expected {expected_count} localities, found {actual_count}")

    counties = dict(sorted(counties.items()))
    meta = {
        "source_file": input_csv.name,
        "table_title": table_title,
        "release_date": release_date,
        "estimate_years": YEARS,
        "locality_count": actual_count,
    }
    return meta, {"statewide": statewide, "counties": counties}


def write_json(output_path: Path, meta: dict, payload: dict) -> None:
    output = {
        "meta": meta,
        "statewide": payload["statewide"],
        "counties": payload["counties"],
    }
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")


def write_csv(output_path: Path, counties: dict[str, dict]) -> None:
    fieldnames = [
        "normalized_name",
        "name",
        "locality_type",
        "countyfp",
        "geoid",
        "estimate_base_2020",
        "estimate_2020",
        "estimate_2021",
        "estimate_2022",
        "estimate_2023",
        "estimate_2024",
        "estimate_2025",
        "change_base_to_2025",
        "pct_change_base_to_2025",
        "change_2020_to_2025",
        "pct_change_2020_to_2025",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(counties):
            row = counties[key]
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def build_outputs(input_csv: Path, county_geojson: Path, output_json: Path, output_csv: Path) -> None:
    locality_index = build_locality_index(county_geojson)
    meta, payload = parse_rows(input_csv, locality_index)
    write_json(output_json, meta, payload)
    write_csv(output_csv, payload["counties"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", default="Data/CO-EST2025-POP-51.csv", type=Path)
    parser.add_argument("--county-geojson", default="Data/tl_2020_51_county20.geojson", type=Path)
    parser.add_argument("--output-json", default="Data/county_population_estimates_2025.json", type=Path)
    parser.add_argument("--output-csv", default="Data/county_population_estimates_2025.csv", type=Path)
    args = parser.parse_args()

    build_outputs(args.input_csv, args.county_geojson, args.output_json, args.output_csv)
    print(f"Wrote {args.output_json}")
    print(f"Wrote {args.output_csv}")


if __name__ == "__main__":
    main()
