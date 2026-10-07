#!/usr/bin/env python3
"""Build reusable Yes/No county and district results from a VA OpenElections CSV.

The district allocation reuses the atlas's precinct-to-district overlay mappings.
Precincts that cannot be matched directly are allocated within their locality using
the matched vote distribution, falling back to the locality's geographic weights.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_va_district_contests_from_crosswalks as district_builder
import convert_va_csvs_to_openelections as oe_converter
from build_precinct_result_geometry_crosswalk import locality, precinct_code, read_block_population, shapefile_uri


SCOPES = ("congressional", "state_house", "state_senate")
YES_COLOR = "#16a34a"
NO_COLOR = "#dc2626"
TIE_COLOR = "#94a3b8"

ASSIGNMENT_MEMBERS = {
    "congressional": "BlockAssign_ST51_VA_CD.txt",
    "state_house": "BlockAssign_ST51_VA_SLDL.txt",
    "state_senate": "BlockAssign_ST51_VA_SLDU.txt",
}


def largest_remainder(total: int, weights: list[tuple[str, float]]) -> dict[str, int]:
    weights = district_builder.normalize_weight_pairs(weights)
    if total <= 0 or not weights:
        return {}
    exact = [(district, total * share) for district, share in weights]
    allocated = {district: int(math.floor(value)) for district, value in exact}
    remaining = total - sum(allocated.values())
    order = sorted(exact, key=lambda item: (-(item[1] - math.floor(item[1])), item[0]))
    for district, _ in order[:remaining]:
        allocated[district] += 1
    return allocated


def build_block_vap_scope_mappings(
    current_geojson: Path,
    tabblock_zip: Path,
    assignments_zip: Path,
    pl94_zip: Path,
    population_cache: Path,
) -> dict[str, dict]:
    """Map current precincts directly to districts using block-level VAP weights."""
    current = gpd.read_file(current_geojson).to_crs(5070)
    current["county_norm"] = current["county_norm"].map(locality)
    current["prec_id"] = current["prec_id"].map(precinct_code)
    current = current[["county_norm", "prec_id", "geometry"]]

    blocks = gpd.read_file(
        shapefile_uri(tabblock_zip),
        columns=["GEOID20", "ALAND20", "geometry"],
    ).to_crs(5070)
    blocks = blocks.rename(columns={"GEOID20": "block_geoid20", "ALAND20": "block_land_area_m2"})
    blocks["block_geoid20"] = blocks["block_geoid20"].astype(str)
    points = gpd.GeoDataFrame(
        blocks[["block_geoid20", "block_land_area_m2"]].copy(),
        geometry=blocks.geometry.representative_point(),
        crs=5070,
    )
    joined = gpd.sjoin(points, current, how="left", predicate="within")
    joined = joined.sort_values(["block_geoid20", "index_right"], kind="stable").drop_duplicates("block_geoid20", keep="first")
    joined = joined.drop(columns=["index_right", "geometry"])
    population = read_block_population(pl94_zip, population_cache)
    joined = joined.merge(population, on="block_geoid20", how="left")
    for column in ("voting_age_population_2020", "total_population_2020", "block_land_area_m2"):
        joined[column] = pd.to_numeric(joined[column], errors="coerce").fillna(0.0)
    joined = joined.dropna(subset=["county_norm", "prec_id"])

    mappings = {}
    with zipfile.ZipFile(assignments_zip) as archive:
        for scope, member in ASSIGNMENT_MEMBERS.items():
            assignment = pd.read_csv(
                archive.open(member),
                sep="|",
                usecols=["BLOCKID", "DISTRICT"],
                dtype=str,
            ).rename(columns={"BLOCKID": "block_geoid20", "DISTRICT": "district"})
            assignment["block_geoid20"] = assignment["block_geoid20"].str.strip()
            assignment["district"] = assignment["district"].map(district_builder.normalize_district_id)
            frame = joined.merge(assignment, on="block_geoid20", how="inner")
            grouped = frame.groupby(["county_norm", "prec_id", "district"], as_index=False).agg(
                voting_age_population_2020=("voting_age_population_2020", "sum"),
                total_population_2020=("total_population_2020", "sum"),
                block_land_area_m2=("block_land_area_m2", "sum"),
                blocks=("block_geoid20", "nunique"),
            )

            precinct_map = {}
            code_weights = {}
            method_counts = defaultdict(int)
            for (county, code), rows in grouped.groupby(["county_norm", "prec_id"], sort=False):
                totals = {column: float(rows[column].sum()) for column in ("voting_age_population_2020", "total_population_2020", "block_land_area_m2")}
                if totals["voting_age_population_2020"] > 0:
                    weight_col = "voting_age_population_2020"
                elif totals["total_population_2020"] > 0:
                    weight_col = "total_population_2020"
                else:
                    weight_col = "block_land_area_m2"
                method_counts[weight_col] += 1
                denom = totals[weight_col]
                key = (str(county), str(code))
                precinct_map[key] = [(str(row.district), float(getattr(row, weight_col)) / denom) for row in rows.itertuples() if float(getattr(row, weight_col)) > 0]
                code_weights[key] = denom

            county_weights = {}
            county_grouped = frame.groupby(["county_norm", "district"], as_index=False).agg(
                voting_age_population_2020=("voting_age_population_2020", "sum"),
                total_population_2020=("total_population_2020", "sum"),
                block_land_area_m2=("block_land_area_m2", "sum"),
            )
            for county, rows in county_grouped.groupby("county_norm", sort=False):
                totals = {column: float(rows[column].sum()) for column in ("voting_age_population_2020", "total_population_2020", "block_land_area_m2")}
                weight_col = "voting_age_population_2020" if totals["voting_age_population_2020"] > 0 else ("total_population_2020" if totals["total_population_2020"] > 0 else "block_land_area_m2")
                denom = totals[weight_col]
                county_weights[str(county)] = [(str(row.district), float(getattr(row, weight_col)) / denom) for row in rows.itertuples() if float(getattr(row, weight_col)) > 0]

            mappings[scope] = {
                "precinct_map": precinct_map,
                "county_weights": county_weights,
                "code_weights": code_weights,
                "weighting": {
                    "method": "2020 Census block assignment weighted by voting-age population",
                    "fallback_order": ["voting_age_population_2020", "total_population_2020", "block_land_area_m2"],
                    "precinct_weight_method_counts": dict(method_counts),
                    "blocks_assigned_to_current_precincts": int(len(joined)),
                },
            }
    return mappings


def result_row(yes_votes: int, no_votes: int) -> dict:
    total = yes_votes + no_votes
    margin = yes_votes - no_votes
    winner = "Yes" if margin > 0 else ("No" if margin < 0 else "Tie")
    return {
        "dem_votes": yes_votes,
        "rep_votes": no_votes,
        "other_votes": 0,
        "total_votes": total,
        "dem_candidate": "Yes",
        "rep_candidate": "No",
        "winner": winner,
        "margin": abs(margin),
        "margin_pct": ((no_votes - yes_votes) / total * 100.0) if total else 0.0,
        "color": YES_COLOR if margin > 0 else (NO_COLOR if margin < 0 else TIE_COLOR),
    }


def load_measure_rows(path: Path, office: str) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if (row.get("office") or "").strip() == office]
    out = []
    for row in rows:
        choice = (row.get("candidate") or "").strip().lower()
        if choice not in {"yes", "no"}:
            continue
        votes = int(float((row.get("votes") or "0").replace(",", "")))
        if votes <= 0:
            continue
        out.append({**row, "choice": choice, "votes_int": votes})
    if not out:
        raise ValueError(f"No Yes/No rows found for office {office!r} in {path}")
    return out


def aggregate_counties(rows: list[dict]) -> dict[str, dict[str, int]]:
    totals = defaultdict(lambda: {"yes": 0, "no": 0})
    for row in rows:
        totals[row["county"]][row["choice"]] += row["votes_int"]
    return totals


def aggregate_scope(rows: list[dict], scope: str, mapping: dict, aliases: dict[str, str]):
    direct = defaultdict(lambda: {"yes": 0, "no": 0})
    unmatched = defaultdict(lambda: {"yes": 0, "no": 0})
    matched_locality = defaultdict(lambda: defaultdict(int))
    code_index = defaultdict(set)
    for locality, code in mapping.get("precinct_map", {}).keys():
        code_index[locality].add(code)
    code_index = {locality: sorted(codes) for locality, codes in code_index.items()}

    input_votes = direct_votes = 0
    for row in rows:
        # The current precinct geometry spells this locality with "AND" while
        # VADOE exports use "&"; apply the same normalization used for 2025 data.
        locality_raw = row["county"].replace("&", " AND ")
        locality = district_builder.canonicalize_locality(locality_raw, aliases, year=2026)
        precinct = row["precinct"]
        choice = row["choice"]
        votes = row["votes_int"]
        input_votes += votes
        splits = None
        code = district_builder.extract_precinct_code(precinct)
        if code and not district_builder.is_non_geographic_precinct(precinct):
            splits = district_builder.resolve_precinct_splits(locality, code, mapping, code_index)
        if splits:
            direct_votes += votes
            allocation = largest_remainder(votes, splits)
            for district, amount in allocation.items():
                direct[district][choice] += amount
                matched_locality[locality][district] += amount
        else:
            unmatched[locality][choice] += votes

    allocated_votes = 0
    for locality, choices in unmatched.items():
        matched = list(matched_locality.get(locality, {}).items())
        fallback = mapping.get("county_weights", {}).get(locality, [])
        weights = matched if matched else fallback
        for choice in ("yes", "no"):
            votes = choices[choice]
            if votes <= 0:
                continue
            allocation = largest_remainder(votes, weights)
            for district, amount in allocation.items():
                direct[district][choice] += amount
                allocated_votes += amount

    matched_votes = sum(v["yes"] + v["no"] for v in direct.values())
    return direct, {
        "input_votes": input_votes,
        "matched_votes": matched_votes,
        "direct_matched_votes": direct_votes,
        "allocated_votes": allocated_votes,
        "match_coverage_pct": (matched_votes / input_votes * 100.0) if input_votes else 0.0,
        "direct_match_coverage_pct": (direct_votes / input_votes * 100.0) if input_votes else 0.0,
    }


def write_county_json(path: Path, county_totals: dict[str, dict[str, int]]) -> None:
    rows = []
    for county in sorted(county_totals):
        totals = county_totals[county]
        rows.append({"locality": county, "county": county, **result_row(totals["yes"], totals["no"])})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"year": 2026, "contest_type": "constitutional_amendment", "rows": rows}, indent=2), encoding="utf-8")


def write_district_output(output_dir: Path, scope: str, totals: dict, coverage: dict) -> Path:
    def numeric_district_key(item):
        district = str(item[0])
        return (0, int(district)) if district.isdigit() else (1, district)

    results = {
        str(district): result_row(values["yes"], values["no"])
        for district, values in sorted(totals.items(), key=numeric_district_key)
    }
    payload = {
        "meta": {"scope": scope, "contest_type": "constitutional_amendment", "year": 2026, "district_count": len(results), **coverage},
        "general": {"results": results},
    }
    json_path = output_dir / f"{scope}_constitutional_amendment_2026.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return json_path


def upsert_manifest(path: Path, entries: list[dict]) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"files": []}
    new_keys = {(entry.get("scope"), entry.get("contest_type"), int(entry.get("year", 0))) for entry in entries}
    kept = [entry for entry in manifest.get("files", []) if (entry.get("scope"), entry.get("contest_type"), int(entry.get("year", 0))) not in new_keys]
    manifest["files"] = kept + entries
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate a Virginia Yes/No ballot measure by current districts.")
    parser.add_argument("--input", type=Path, required=True, help="VADOE export or OpenElections-style precinct CSV")
    parser.add_argument("--office", default="Proposed Constitutional Amendment")
    parser.add_argument("--openelections-output-dir", type=Path, default=ROOT / "Data/openelections")
    parser.add_argument("--county-output", type=Path, default=ROOT / "Data/contests/constitutional_amendment_2026.json")
    parser.add_argument("--district-output-dir", type=Path, default=ROOT / "Data/district_contests")
    parser.add_argument("--current-precincts", type=Path, default=ROOT / "Data/va_precincts_current.geojson")
    parser.add_argument("--tabblocks", type=Path, default=ROOT / "Data/tl_2020_51_tabblock20.zip")
    parser.add_argument("--assignments", type=Path, default=ROOT / "Data/BlockAssign_ST51_VA.zip")
    parser.add_argument("--pl94", type=Path, default=ROOT / "Data/va2020.pl.zip")
    parser.add_argument("--block-population", type=Path, default=ROOT / "Data/va_2020_block_population.csv")
    args = parser.parse_args()

    county_geojson = ROOT / "Data/tl_2020_51_county20.geojson"
    with args.input.open("r", encoding="utf-8-sig", newline="") as handle:
        input_fields = next(csv.reader(handle), [])
    oe_input = args.input
    if "CandidateId" in input_fields and "TOTAL_VOTES" in input_fields:
        aliases_for_conversion = oe_converter.build_locality_alias_map(county_geojson)
        converted = oe_converter.convert_long_file(args.input, args.openelections_output_dir, aliases_for_conversion)
        oe_input = Path(converted.output_file)
        oe_manifest = args.openelections_output_dir / "manifest.json"
        manifest = json.loads(oe_manifest.read_text(encoding="utf-8")) if oe_manifest.exists() else {"files": []}
        manifest["files"] = [entry for entry in manifest.get("files", []) if entry.get("input_file") != args.input.name]
        try:
            manifest_output = Path(converted.output_file).resolve().relative_to(ROOT.resolve()).as_posix()
        except ValueError:
            manifest_output = Path(converted.output_file).as_posix()
        manifest["files"].append({"input_file": args.input.name, "output_file": manifest_output, "rows": converted.output_rows})
        oe_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    mappings = build_block_vap_scope_mappings(
        args.current_precincts,
        args.tabblocks,
        args.assignments,
        args.pl94,
        args.block_population,
    )
    aliases = district_builder.build_locality_alias_map(county_geojson)
    rows = load_measure_rows(oe_input, args.office)
    county_totals = aggregate_counties(rows)
    write_county_json(args.county_output, county_totals)

    args.district_output_dir.mkdir(parents=True, exist_ok=True)
    district_entries = []
    outputs = [oe_input, args.county_output]
    for scope in SCOPES:
        totals, coverage = aggregate_scope(rows, scope, mappings[scope], aliases)
        coverage["weighting"] = mappings[scope]["weighting"]
        json_path = write_district_output(args.district_output_dir, scope, totals, coverage)
        outputs.append(json_path)
        yes_total = sum(values["yes"] for values in totals.values())
        no_total = sum(values["no"] for values in totals.values())
        district_entries.append({
            "scope": scope,
            "contest_type": "constitutional_amendment",
            "year": 2026,
            "file": json_path.name,
            "rows": len(totals),
            "dem_total": yes_total,
            "rep_total": no_total,
            "major_party_contested": True,
        })

    upsert_manifest(args.district_output_dir / "manifest.json", district_entries)
    upsert_manifest(ROOT / "Data/contests/manifest.json", [{
        "contest_type": "constitutional_amendment",
        "year": 2026,
        "file": args.county_output.name,
        "rows": len(county_totals),
        "dem_total": sum(v["yes"] for v in county_totals.values()),
        "rep_total": sum(v["no"] for v in county_totals.values()),
        "major_party_contested": True,
    }])

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
