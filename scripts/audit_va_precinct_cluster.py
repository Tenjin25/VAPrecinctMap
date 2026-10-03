#!/usr/bin/env python3
"""Reconstruct a Virginia district cluster from precinct returns and geometry.

Geographic precinct votes follow precinct/district polygon intersections.
Unmatched non-geographic votes are distributed within their locality using the
party-specific geographic precinct distribution. Final integer rounding
conserves each party's official input total across the requested cluster.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd

from reconcile_va_district_contests import district_sort_key, largest_remainder, normalize_district


ROOT = Path(__file__).resolve().parents[1]
PARTY_BUCKETS = {"DEM": "dem", "REP": "rep"}


def precinct_code(raw: object) -> str:
    text = str(raw or "").strip().upper()
    match = re.match(r"^0*([0-9]+)(?:\s*-|$)", text)
    return str(int(match.group(1))) if match else ""


def normalize_locality(raw: object) -> str:
    value = re.sub(r"\s+", " ", str(raw or "").strip().upper())
    return {"KING & QUEEN COUNTY": "KING AND QUEEN COUNTY"}.get(value, value)


def normalize_pairs(weights: dict[str, float]) -> dict[str, float]:
    positive = {key: max(0.0, float(value)) for key, value in weights.items() if float(value) > 0}
    total = sum(positive.values())
    return {key: value / total for key, value in positive.items()} if total else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-csv", default="Data/openelections/2024/20241105__va__general__precinct__u_s_senate.csv")
    parser.add_argument("--precinct-geojson", default="Data/va_precincts_current.geojson")
    parser.add_argument("--district-geojson", default="Data/tl_2022_51_sldl.geojson")
    parser.add_argument("--district-field", default="SLDLST")
    parser.add_argument(
        "--locality",
        action="append",
        default=[],
        help="Locality to audit. If omitted, derive localities intersecting the requested seed districts.",
    )
    parser.add_argument("--district", action="append", required=True)
    parser.add_argument(
        "--include-touching-districts",
        action="store_true",
        help="Include every district touching the selected/derived localities so their votes are conserved.",
    )
    parser.add_argument(
        "--minimum-share",
        type=float,
        default=0.001,
        help="Drop sub-0.1%% polygon slivers and renormalize, matching NCPrecinctMap.",
    )
    parser.add_argument("--output", default="Data/benchmarks/precinct_cluster_reconstruction.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    localities = {normalize_locality(value) for value in args.locality}
    districts = {normalize_district(value) for value in args.district}

    precincts = gpd.read_file(ROOT / args.precinct_geojson)
    precincts["locality"] = precincts["county_norm"].map(normalize_locality)
    precincts["code"] = precincts["prec_id"].map(precinct_code)
    district_shapes = gpd.read_file(ROOT / args.district_geojson)
    district_shapes["district"] = district_shapes[args.district_field].map(normalize_district)
    if precincts.empty or district_shapes.empty:
        raise ValueError("Requested precinct or district geometry is empty")

    precincts = precincts.to_crs(5070)
    district_shapes = district_shapes.to_crs(5070)
    if not localities:
        seeds = district_shapes[district_shapes["district"].isin(districts)].copy()
        if seeds.empty:
            raise ValueError("Requested seed district geometry is empty")
        locality_hits = gpd.overlay(
            precincts[["locality", "geometry"]],
            seeds[["district", "geometry"]],
            how="intersection",
            keep_geom_type=False,
        )
        locality_hits = locality_hits[locality_hits.geometry.area > 0]
        localities = set(locality_hits["locality"].astype(str))
    precincts = precincts[precincts["locality"].isin(localities)].copy()
    if args.include_touching_districts:
        district_hits = gpd.overlay(
            precincts[["locality", "geometry"]],
            district_shapes[["district", "geometry"]],
            how="intersection",
            keep_geom_type=False,
        )
        district_hits = district_hits[district_hits.geometry.area > 0]
        districts = set(district_hits["district"].astype(str))
    district_shapes = district_shapes[district_shapes["district"].isin(districts)].copy()
    precincts["precinct_area"] = precincts.geometry.area
    intersections = gpd.overlay(
        precincts[["locality", "code", "precinct_area", "geometry"]],
        district_shapes[["district", "geometry"]],
        how="intersection",
        keep_geom_type=False,
    )
    intersections["intersection_area"] = intersections.geometry.area
    intersections["share"] = intersections["intersection_area"] / intersections["precinct_area"]

    precinct_weights: dict[tuple[str, str], dict[str, float]] = {}
    for (locality, code), rows in intersections.groupby(["locality", "code"]):
        raw = {
            str(row.district): float(row.share)
            for row in rows.itertuples(index=False)
            if float(row.share) >= float(args.minimum_share)
        }
        if not raw and not rows.empty:
            best = rows.sort_values("share", ascending=False).iloc[0]
            raw = {str(best["district"]): float(best["share"])}
        precinct_weights[(str(locality), str(code))] = normalize_pairs(raw)

    returns = pd.read_csv(ROOT / args.results_csv, dtype=str).fillna("")
    returns["locality"] = returns["county"].map(normalize_locality)
    returns = returns[returns["locality"].isin(localities)].copy()
    returns["code"] = returns["precinct"].map(precinct_code)
    returns["votes"] = pd.to_numeric(returns["votes"], errors="coerce").fillna(0.0)
    returns["bucket"] = returns["party"].map(PARTY_BUCKETS).fillna("other")

    district_votes: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    locality_district_votes: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    unmatched: dict[tuple[str, str], float] = defaultdict(float)
    direct_votes = 0.0
    input_votes = float(returns["votes"].sum())
    for row in returns.itertuples(index=False):
        key = (str(row.locality), str(row.code))
        weights = precinct_weights.get(key) if row.code else None
        if not weights:
            unmatched[(str(row.locality), str(row.bucket))] += float(row.votes)
            continue
        direct_votes += float(row.votes)
        for district, share in weights.items():
            amount = float(row.votes) * share
            district_votes[district][str(row.bucket)] += amount
            locality_district_votes[(str(row.locality), district)][str(row.bucket)] += amount

    for (locality, bucket), votes in unmatched.items():
        weights = normalize_pairs({
            district: node.get(bucket, 0.0)
            for (row_locality, district), node in locality_district_votes.items()
            if row_locality == locality
        })
        if not weights:
            weights = normalize_pairs({
                district: sum(node.values())
                for (row_locality, district), node in locality_district_votes.items()
                if row_locality == locality
            })
        if not weights:
            raise ValueError(f"Cannot allocate unmatched votes for {locality} {bucket}")
        for district, share in weights.items():
            amount = votes * share
            district_votes[district][bucket] += amount
            locality_district_votes[(locality, district)][bucket] += amount

    official = {
        bucket: int(round(float(returns.loc[returns["bucket"] == bucket, "votes"].sum())))
        for bucket in ("dem", "rep", "other")
    }
    rounded: dict[str, dict[str, int]] = {district: {} for district in sorted(districts, key=district_sort_key)}
    for bucket, target in official.items():
        allocation = largest_remainder(
            {district: district_votes[district].get(bucket, 0.0) for district in rounded},
            target,
        )
        for district in rounded:
            rounded[district][bucket] = allocation[district]

    for district, node in rounded.items():
        total = sum(node.values())
        node["total"] = total
        node["margin_pct"] = ((node["rep"] - node["dem"]) / total * 100.0) if total else 0.0

    payload = {
        "method": "Precinct returns through the selected precinct and district geometry; sub-0.1% polygon slivers dropped and remaining shares renormalized per the NCPrecinctMap rule; party-specific within-locality allocation for non-geographic rows",
        "inputs": {
            "results_csv": args.results_csv,
            "precinct_geojson": args.precinct_geojson,
            "district_geojson": args.district_geojson,
            "minimum_share": float(args.minimum_share),
        },
        "localities": sorted(localities),
        "districts": sorted(districts, key=district_sort_key),
        "coverage": {
            "input_votes": input_votes,
            "direct_geographic_votes": direct_votes,
            "direct_coverage_pct": (direct_votes / input_votes * 100.0) if input_votes else 0.0,
            "unmatched_allocated_votes": sum(unmatched.values()),
        },
        "official_cluster_totals": official,
        "district_results": rounded,
        "unmatched_by_locality_party": [
            {"locality": locality, "bucket": bucket, "votes": votes}
            for (locality, bucket), votes in sorted(unmatched.items())
        ],
        "precinct_weights": [
            {"locality": locality, "precinct": code, "districts": weights}
            for (locality, code), weights in sorted(precinct_weights.items())
        ],
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "coverage": payload["coverage"],
        "district_results": rounded,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
