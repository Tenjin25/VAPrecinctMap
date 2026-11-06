#!/usr/bin/env python3
"""Build DRA 2020 block-level custom-election CSVs from a precinct export.

The output uses 2020 Census block GEOIDs and DRA's required election fields:
GEOID20, Tot, D, and R. Producing block-level rows prevents DRA from separately
disaggregating Tot, D, and R from VTDs, which can create negative Other votes
through rounding. Current precinct returns are allocated to blocks by voting-age
population, with total-population and land-area fallbacks. Non-geographic returns
are distributed within locality using same-party geographic returns.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import build_precinct_result_geometry_crosswalk as crosswalk
import build_va_district_contests_from_crosswalks as district_builder


CONTESTS = {
    "us_senate": (lambda office: office == "Member, United States Senate", "party"),
    "us_house": (lambda office: office.startswith("Member, House of Representatives"), "party"),
    "constitutional_amendment_1": (lambda office: office == "Proposed Constitutional Amendment Question 1", "choice"),
    "constitutional_amendment_2": (lambda office: office == "Proposed Constitutional Amendment Question 2", "choice"),
    "constitutional_amendment_3": (lambda office: office == "Proposed Constitutional Amendment Question 3", "choice"),
}


def largest_remainder(total: int, weights: list[tuple[str, float]]) -> dict[str, int]:
    positive = [(key, float(weight)) for key, weight in weights if float(weight) > 0]
    denom = sum(weight for _, weight in positive)
    if total <= 0 or denom <= 0:
        return {}
    exact = [(key, total * weight / denom) for key, weight in positive]
    allocated = {key: int(math.floor(value)) for key, value in exact}
    remaining = total - sum(allocated.values())
    order = sorted(exact, key=lambda item: (-(item[1] - math.floor(item[1])), item[0]))
    for key, _ in order[:remaining]:
        allocated[key] += 1
    return allocated


def build_current_to_block_weights(args: argparse.Namespace):
    current = crosswalk.gpd.read_file(args.current_precincts).to_crs(5070)
    population = crosswalk.read_block_population(args.pl94, args.block_population)
    blocks = crosswalk.gpd.read_file(
        crosswalk.shapefile_uri(args.tabblocks),
        columns=["GEOID20", "ALAND20", "geometry"],
    )
    blocks = blocks.rename(columns={"GEOID20": "geoid", "ALAND20": "area"})
    blocks["geoid"] = blocks["geoid"].astype(str).str.zfill(15)
    blocks_equal_area = blocks.to_crs(5070)
    block_points = crosswalk.gpd.GeoDataFrame(
        blocks_equal_area[["geoid", "area"]].copy(),
        geometry=blocks_equal_area.geometry.representative_point(),
        crs=5070,
    )
    targets = current[["county_norm", "prec_id", "geometry"]].copy()
    targets["target"] = targets.apply(lambda row: crosswalk.key_text(crosswalk.geometry_key(row)), axis=1)
    joined = crosswalk.gpd.sjoin(
        block_points,
        targets[["target", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined.sort_values(["geoid", "index_right"], kind="stable").drop_duplicates("geoid", keep="first")
    joined = joined.drop(columns=["index_right"]).merge(
        population.rename(columns={"block_geoid20": "geoid"}),
        on="geoid",
        how="left",
    )
    for column in ("area", "total_population_2020", "voting_age_population_2020"):
        joined[column] = crosswalk.pd.to_numeric(joined[column], errors="coerce").fillna(0.0)

    by_target_records = defaultdict(list)
    county_records = defaultdict(list)
    for row in joined.itertuples():
        if crosswalk.pd.isna(row.target):
            continue
        target = str(row.target)
        county = target.rsplit(" - ", 1)[0]
        item = {
            "geoid": str(row.geoid),
            "vap": float(row.voting_age_population_2020 or 0),
            "pop": float(row.total_population_2020 or 0),
            "area": float(row.area or 0),
        }
        by_target_records[target].append(item)
        county_records[county].append(item)

    def normalized(records: list[dict]) -> list[tuple[str, float]]:
        combined = defaultdict(lambda: {"vap": 0.0, "pop": 0.0, "area": 0.0})
        for record in records:
            for metric in ("vap", "pop", "area"):
                combined[record["geoid"]][metric] += record[metric]
        metric = next(
            (candidate for candidate in ("vap", "pop", "area") if sum(v[candidate] for v in combined.values()) > 0),
            "area",
        )
        return sorted((geoid, values[metric]) for geoid, values in combined.items() if values[metric] > 0)

    by_target = {target: normalized(records) for target, records in by_target_records.items()}
    by_county = {county: normalized(records) for county, records in county_records.items()}
    return by_target, by_county


def party_bucket(party: str) -> str:
    value = (party or "").strip().upper()
    if value.startswith("DEM"):
        return "D"
    if value.startswith("REP"):
        return "R"
    return "O"


def build_contest(rows: list[dict], predicate, bucket_mode, by_target, by_county):
    totals = defaultdict(lambda: {"D": 0, "R": 0, "O": 0})
    direct_by_county = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    unmatched = defaultdict(lambda: defaultdict(int))

    for row in rows:
        office = (row.get("office") or "").strip()
        if not predicate(office):
            continue
        votes = int(float(row.get("votes") or 0))
        if votes <= 0:
            continue
        county = crosswalk.locality(row.get("county"))
        precinct = row.get("precinct") or ""
        if bucket_mode == "choice":
            choice = (row.get("candidate") or "").strip().upper()
            bucket = "D" if choice == "YES" else ("R" if choice == "NO" else "O")
        else:
            bucket = party_bucket(row.get("party") or "")
        target = crosswalk.key_text((county, crosswalk.precinct_code(precinct)))
        weights = None if district_builder.is_non_geographic_precinct(precinct) else by_target.get(target)
        if not weights:
            unmatched[county][bucket] += votes
            continue
        for geoid, amount in largest_remainder(votes, weights).items():
            totals[geoid][bucket] += amount
            direct_by_county[county][bucket][geoid] += amount

    for county, buckets in unmatched.items():
        for bucket, votes in buckets.items():
            matched = direct_by_county[county][bucket]
            weights = list(matched.items()) if sum(matched.values()) > 0 else by_county.get(county, [])
            if not weights:
                raise RuntimeError(f"No VTD20 allocation weights for {county}")
            for geoid, amount in largest_remainder(votes, weights).items():
                totals[geoid][bucket] += amount

    return [
        {
            "GEOID20": geoid,
            "Tot": totals[geoid]["D"] + totals[geoid]["R"] + totals[geoid]["O"],
            "D": totals[geoid]["D"],
            "R": totals[geoid]["R"],
        }
        for geoid in sorted(totals, key=int)
        if totals[geoid]["D"] + totals[geoid]["R"] + totals[geoid]["O"] > 0
    ]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="OpenElections-style precinct CSV")
    parser.add_argument("--output-dir", type=Path, default=root / "Data/dra/2026")
    parser.add_argument("--current-precincts", type=Path, default=root / "Data/va_precincts_current.geojson")
    parser.add_argument("--tabblocks", type=Path, default=root / "Data/tl_2020_51_tabblock20.zip")
    parser.add_argument("--pl94", type=Path, default=root / "Data/va2020.pl.zip")
    parser.add_argument("--block-population", type=Path, default=root / "Data/va_2020_block_population.csv")
    args = parser.parse_args()

    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_target, by_county = build_current_to_block_weights(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for contest, (predicate, bucket_mode) in CONTESTS.items():
        output_rows = build_contest(rows, predicate, bucket_mode, by_target, by_county)
        output = args.output_dir / f"2026_va_{contest}_dra.csv"
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["GEOID20", "Tot", "D", "R"])
            writer.writeheader()
            writer.writerows(output_rows)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
