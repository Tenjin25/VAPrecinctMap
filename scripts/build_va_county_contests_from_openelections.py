#!/usr/bin/env python3
"""
Build county-level contest slices from VA OpenElections-style precinct CSVs.

Outputs:
- Data/contests/<contest_type>_<year>.json
- Data/contests/manifest.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


CONTEST_ORDER = ["president", "us_senate", "governor", "lieutenant_governor", "attorney_general"]


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).upper()


def canonical_locality_from_census(name20: str, namelsad20: str) -> str:
    value = normalize_key(namelsad20) or normalize_key(name20)
    if not value:
        return ""
    m = re.match(r"^(.+?)\s+(COUNTY|CITY|TOWN)$", value)
    if m:
        return f"{m.group(1).strip()} {m.group(2)}"
    return value


def locality_aliases(canonical: str) -> set[str]:
    aliases = {normalize_key(canonical)}
    m = re.match(r"^(.+?)\s+(COUNTY|CITY|TOWN)$", normalize_key(canonical))
    if m:
        base = m.group(1).strip()
        suffix = m.group(2)
        aliases.add(base)
        aliases.add(f"{base} {suffix}")
        if suffix == "CITY":
            aliases.add(f"CITY OF {base}")
    return {a for a in aliases if a}


def build_locality_alias_map(county_geojson: Path) -> dict[str, str]:
    raw = json.loads(county_geojson.read_text(encoding="utf-8"))
    alias_to_targets: dict[str, set[str]] = {}
    for feature in raw.get("features", []):
        props = feature.get("properties", {}) or {}
        canonical = canonical_locality_from_census(
            str(props.get("NAME20", "")),
            str(props.get("NAMELSAD20", "")),
        )
        if not canonical:
            continue
        for alias in locality_aliases(canonical):
            alias_to_targets.setdefault(alias, set()).add(canonical)
    return {
        alias: next(iter(targets))
        for alias, targets in alias_to_targets.items()
        if len(targets) == 1
    }


def normalize_locality(raw: str, locality_alias_map: dict[str, str]) -> str:
    u = normalize_key(raw)
    if not u:
        return ""
    m_city_of = re.match(r"^CITY OF\s+(.+)$", u)
    if m_city_of:
        u = f"{m_city_of.group(1).strip()} CITY"
    return locality_alias_map.get(u, u)


def parse_year_from_filename(path: Path) -> int:
    m = re.match(r"(\d{4})\d{4}__", path.name)
    if m:
        return int(m.group(1))
    m2 = re.match(r"(\d{4})", path.name)
    if m2:
        return int(m2.group(1))
    raise ValueError(f"Unable to parse year from {path.name}")


def normalize_office(office: str) -> str:
    return re.sub(r"[^A-Z0-9 ]+", "", (office or "").upper()).strip()


def classify_contest(office: str) -> str | None:
    norm = normalize_office(office)
    if norm == "PRESIDENT":
        return "president"
    if norm in {"US SENATE", "U S SENATE"}:
        return "us_senate"
    if norm == "GOVERNOR":
        return "governor"
    if norm == "LIEUTENANT GOVERNOR":
        return "lieutenant_governor"
    if norm == "ATTORNEY GENERAL":
        return "attorney_general"
    return None


def normalize_party_bucket(party: str) -> str:
    p = (party or "").strip().upper()
    if p.startswith("DEM"):
        return "dem"
    if p.startswith("REP"):
        return "rep"
    return "other"


def color_for_margin(margin_pct_abs: float, winner: str) -> str:
    # Mirrors map color ramp logic.
    if margin_pct_abs >= 40:
        return "#67000d" if winner == "R" else "#08306b"
    if margin_pct_abs >= 30:
        return "#a50f15" if winner == "R" else "#08519c"
    if margin_pct_abs >= 20:
        return "#cb181d" if winner == "R" else "#3182bd"
    if margin_pct_abs >= 10:
        return "#ef3b2c" if winner == "R" else "#6baed6"
    if margin_pct_abs >= 5.5:
        return "#fb6a4a" if winner == "R" else "#9ecae1"
    if margin_pct_abs >= 1.0:
        return "#fcae91" if winner == "R" else "#c6dbef"
    if margin_pct_abs >= 0.5:
        return "#fee8c8" if winner == "R" else "#e1f5fe"
    return "#f7f7f7"


def build_slices(openelections_dir: Path, locality_alias_map: dict[str, str]) -> tuple[dict[tuple[str, int], dict], list[dict]]:
    # contest/year -> county -> aggregate
    by_contest_year = defaultdict(
        lambda: defaultdict(
            lambda: {
                "dem": 0,
                "rep": 0,
                "other": 0,
                "dem_cands": Counter(),
                "rep_cands": Counter(),
            }
        )
    )

    for csv_path in sorted(openelections_dir.rglob("*.csv")):
        year = parse_year_from_filename(csv_path)
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                contest_type = classify_contest(row.get("office", ""))
                if not contest_type:
                    continue
                county = normalize_locality(row.get("county", ""), locality_alias_map)
                if not county:
                    continue
                try:
                    votes = int(float(row.get("votes") or 0))
                except ValueError:
                    votes = 0
                if votes <= 0:
                    continue

                bucket = normalize_party_bucket(row.get("party", ""))
                cand = (row.get("candidate") or "").strip()

                node = by_contest_year[(contest_type, year)][county]
                node[bucket] += votes
                if bucket == "dem" and cand:
                    node["dem_cands"][cand] += votes
                elif bucket == "rep" and cand:
                    node["rep_cands"][cand] += votes

    manifest_entries: list[dict] = []
    payloads: dict[tuple[str, int], dict] = {}

    for contest_type, year in sorted(by_contest_year.keys(), key=lambda k: (CONTEST_ORDER.index(k[0]), k[1]) if k[0] in CONTEST_ORDER else (999, k[1])):
        county_map = by_contest_year[(contest_type, year)]
        rows = []
        dem_total = rep_total = other_total = 0

        for county in sorted(county_map.keys()):
            node = county_map[county]
            dem = int(node["dem"])
            rep = int(node["rep"])
            other = int(node["other"])
            total = dem + rep + other
            if total <= 0:
                continue

            dem_total += dem
            rep_total += rep
            other_total += other

            dem_cand = node["dem_cands"].most_common(1)[0][0] if node["dem_cands"] else ""
            rep_cand = node["rep_cands"].most_common(1)[0][0] if node["rep_cands"] else ""

            if rep > dem:
                winner = "Republican"
                winner_short = "R"
            elif dem > rep:
                winner = "Democratic"
                winner_short = "D"
            else:
                winner = "Tie"
                winner_short = "T"

            margin = abs(rep - dem)
            margin_pct = ((rep - dem) / total) * 100.0
            color = color_for_margin(abs(margin_pct), "R" if winner_short in {"R", "T"} else "D")

            rows.append(
                {
                    "county": county,
                    "dem_votes": dem,
                    "rep_votes": rep,
                    "other_votes": other,
                    "total_votes": total,
                    "dem_candidate": dem_cand,
                    "rep_candidate": rep_cand,
                    "winner": winner,
                    "margin": margin,
                    "margin_pct": margin_pct,
                    "color": color,
                }
            )

        payload = {
            "meta": {
                "contest_type": contest_type,
                "year": int(year),
                "rows": len(rows),
                "dem_total": dem_total,
                "rep_total": rep_total,
                "other_total": other_total,
                "total_votes": dem_total + rep_total + other_total,
            },
            "rows": rows,
        }
        payloads[(contest_type, year)] = payload

        filename = f"{contest_type}_{year}.json"
        manifest_entries.append(
            {
                "contest_type": contest_type,
                "year": int(year),
                "file": filename,
                "rows": len(rows),
                "dem_total": dem_total,
                "rep_total": rep_total,
                "major_party_contested": bool(dem_total > 0 and rep_total > 0),
            }
        )

    return payloads, manifest_entries


def write_outputs(output_dir: Path, payloads: dict[tuple[str, int], dict], manifest_entries: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale generated contest slices.
    for old in output_dir.glob("*.json"):
        if old.name == "manifest.json":
            continue
        old.unlink()

    for (contest_type, year), payload in payloads.items():
        out_path = output_dir / f"{contest_type}_{year}.json"
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    manifest = {"files": manifest_entries}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build VA county contest slices from OpenElections CSVs.")
    parser.add_argument("--openelections-dir", default="Data/openelections")
    parser.add_argument("--output-dir", default="Data/contests")
    parser.add_argument("--county-geojson", default="Data/tl_2020_51_county20.geojson")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    openelections_dir = Path(args.openelections_dir)
    output_dir = Path(args.output_dir)
    county_geojson = Path(args.county_geojson)
    if not openelections_dir.exists():
        raise FileNotFoundError(f"OpenElections directory not found: {openelections_dir}")
    if not county_geojson.exists():
        raise FileNotFoundError(f"County GeoJSON not found: {county_geojson}")

    locality_alias_map = build_locality_alias_map(county_geojson)
    payloads, manifest_entries = build_slices(openelections_dir, locality_alias_map)
    write_outputs(output_dir, payloads, manifest_entries)
    print(f"Wrote {len(payloads)} county contest slices to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
