#!/usr/bin/env python3
"""
Diagnose district assignment/allocation error drivers for benchmark targets.

Outputs:
- benchmark_raw_error_report.csv
- benchmark_county_contributions.csv
- benchmark_county_coverage.csv
- benchmark_diagnostics_summary.json
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import build_va_district_contests_from_crosswalks as builder


def parse_year_from_filename(path: Path) -> int:
    return builder.parse_year_from_filename(path)


def filter_targets(
    targets: dict[tuple[str, str, int, str], float],
    scope_filters: set[str] | None,
    contest_filters: set[str] | None,
    year_filters: set[int] | None,
) -> dict[tuple[str, str, int, str], float]:
    out: dict[tuple[str, str, int, str], float] = {}
    for (scope, contest_type, year, district), val in targets.items():
        if scope_filters and scope not in scope_filters:
            continue
        if contest_filters and contest_type not in contest_filters:
            continue
        if year_filters and year not in year_filters:
            continue
        out[(scope, contest_type, year, district)] = float(val)
    return out


def build_code_index(source: dict[str, dict]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for scope, scope_node in source.items():
        idx: dict[str, set[str]] = defaultdict(set)
        for county_name, code in scope_node.get("precinct_map", {}).keys():
            idx[county_name].add(code)
        out[scope] = {k: sorted(v) for k, v in idx.items()}
    return out


def normalize_pairs(pairs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    return builder.normalize_weight_pairs(pairs)


def collect_diagnostics(
    openelections_root: Path,
    scope_mappings: dict[str, dict],
    locality_alias_map: dict[str, str],
    target_filter: set[tuple[str, str, int]],
) -> tuple[dict[tuple[str, str, int, str], dict], dict[tuple[str, str, int, str, str], dict], dict[tuple[str, str, int, str], dict]]:
    district_acc = defaultdict(lambda: {"dem": 0.0, "rep": 0.0, "other": 0.0})
    unmatched_by_county = defaultdict(lambda: {"dem": 0.0, "rep": 0.0, "other": 0.0})
    matched_county_district = defaultdict(lambda: defaultdict(float))
    matched_county_district_by_party = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

    county_coverage = defaultdict(lambda: {"input_votes": 0.0, "direct_votes": 0.0, "allocated_votes": 0.0, "unallocated_votes": 0.0})
    district_county = defaultdict(
        lambda: {
            "dem_direct": 0.0,
            "rep_direct": 0.0,
            "other_direct": 0.0,
            "dem_allocated": 0.0,
            "rep_allocated": 0.0,
            "other_allocated": 0.0,
        }
    )

    allowed_scope_by_contest_year: dict[tuple[str, int], set[str]] = defaultdict(set)
    needed_years: set[int] = set()
    for scope, contest_type, year in target_filter:
        allowed_scope_by_contest_year[(contest_type, year)].add(scope)
        needed_years.add(year)

    explicit_overrides = builder.build_explicit_precinct_district_overrides(openelections_root)
    scope_code_index = build_code_index(scope_mappings)
    explicit_code_index = build_code_index(explicit_overrides)

    for csv_path in sorted(openelections_root.rglob("*.csv")):
        year = parse_year_from_filename(csv_path)
        if needed_years and year not in needed_years:
            continue

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                office = row.get("office", "")
                classified = builder.classify_office(office, year)
                if not classified:
                    continue

                kind, contest_type, office_district = classified
                allowed_scopes = allowed_scope_by_contest_year.get((contest_type, year), set())
                if not allowed_scopes:
                    continue

                county = builder.canonicalize_locality(row.get("county", ""), locality_alias_map)
                precinct = row.get("precinct", "")
                party_bucket = builder.normalize_party_bucket(row.get("party", ""))
                try:
                    votes = float(row.get("votes") or 0.0)
                except ValueError:
                    votes = 0.0
                if not county or votes <= 0:
                    continue

                if kind == "statewide":
                    scope_iter = [s for s in builder.SCOPES if s in allowed_scopes]
                    for scope in scope_iter:
                        county_key = (scope, contest_type, year, county)
                        county_coverage[county_key]["input_votes"] += votes

                        splits = None
                        prec_code = builder.extract_precinct_code(precinct)
                        if prec_code and not builder.is_non_geographic_precinct(precinct):
                            splits = builder.resolve_precinct_splits(
                                county,
                                prec_code,
                                scope_mappings[scope],
                                scope_code_index.get(scope, {}),
                            )
                            if not splits and scope in {"state_house", "state_senate"}:
                                splits = builder.resolve_precinct_splits(
                                    county,
                                    prec_code,
                                    explicit_overrides.get(scope, {}),
                                    explicit_code_index.get(scope, {}),
                                )

                        if splits:
                            county_coverage[county_key]["direct_votes"] += votes
                            for district_id, share in splits:
                                amount = votes * share
                                dkey = (scope, contest_type, year, district_id)
                                district_acc[dkey][party_bucket] += amount
                                matched_county_district[county_key][district_id] += amount
                                matched_county_district_by_party[county_key][party_bucket][district_id] += amount

                                dckey = (scope, contest_type, year, district_id, county)
                                district_county[dckey][f"{party_bucket}_direct"] += amount
                        else:
                            unmatched_by_county[county_key][party_bucket] += votes
                else:
                    scope = contest_type
                    if scope not in allowed_scopes:
                        continue
                    if not office_district:
                        continue
                    district_id = builder.normalize_district_id(office_district)
                    if not district_id:
                        continue
                    county_key = (scope, contest_type, year, county)
                    county_coverage[county_key]["input_votes"] += votes
                    county_coverage[county_key]["direct_votes"] += votes
                    dkey = (scope, contest_type, year, district_id)
                    district_acc[dkey][party_bucket] += votes
                    dckey = (scope, contest_type, year, district_id, county)
                    district_county[dckey][f"{party_bucket}_direct"] += votes

    for (scope, contest_type, year, county), node in unmatched_by_county.items():
        county_key = (scope, contest_type, year, county)
        to_allocate = float(node["dem"] + node["rep"] + node["other"])
        if to_allocate <= 0:
            continue

        matched_weights = normalize_pairs(list(matched_county_district.get(county_key, {}).items()))
        county_weights = normalize_pairs(scope_mappings[scope]["county_weights"].get(county, []))

        if scope == "congressional":
            alloc_weights_total = builder.blend_weight_pairs(matched_weights, county_weights, 1.0)
        else:
            alloc_weights_total = matched_weights if matched_weights else county_weights

        if not alloc_weights_total:
            county_coverage[county_key]["unallocated_votes"] += to_allocate
            continue

        county_coverage[county_key]["allocated_votes"] += to_allocate
        total_weight_map = {d: float(v) for d, v in alloc_weights_total}

        def get_bucket_alloc_weights(bucket: str) -> list[tuple[str, float]]:
            party_dist = matched_county_district_by_party.get(county_key, {}).get(bucket, {})
            party_sum = float(sum(party_dist.values()))
            if party_sum > 0:
                party_weight_map = {d: float(v / party_sum) for d, v in party_dist.items() if v > 0}
                if scope == "congressional":
                    party_blend = builder.CONGRESSIONAL_PARTY_BLEND_BY_COUNTY.get(
                        county,
                        builder.PARTY_FALLBACK_BLEND_CONGRESSIONAL,
                    )
                elif scope == "state_house":
                    party_blend = builder.STATE_HOUSE_PARTY_BLEND_BY_COUNTY.get(county, builder.PARTY_FALLBACK_BLEND)
                elif scope == "state_senate":
                    party_blend = builder.STATE_SENATE_PARTY_BLEND_BY_COUNTY.get(county, builder.PARTY_FALLBACK_BLEND)
                else:
                    party_blend = builder.PARTY_FALLBACK_BLEND
                if total_weight_map and party_blend > 0:
                    districts = set(total_weight_map) | set(party_weight_map)
                    blended = {}
                    for district_id in districts:
                        total_share = total_weight_map.get(district_id, 0.0)
                        party_share = party_weight_map.get(district_id, 0.0)
                        blended[district_id] = ((1.0 - party_blend) * total_share) + (party_blend * party_share)
                    s = float(sum(v for v in blended.values() if v > 0))
                    if s > 0:
                        return [(d, v / s) for d, v in blended.items() if v > 0]
                return list(party_weight_map.items())
            return alloc_weights_total

        for bucket in ("dem", "rep", "other"):
            base_votes = float(node[bucket])
            if base_votes <= 0:
                continue
            bucket_weights = get_bucket_alloc_weights(bucket)
            for district_id, share in bucket_weights:
                amount = base_votes * share
                dkey = (scope, contest_type, year, district_id)
                district_acc[dkey][bucket] += amount
                dckey = (scope, contest_type, year, district_id, county)
                district_county[dckey][f"{bucket}_allocated"] += amount

    return district_acc, district_county, county_coverage


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose benchmark district assignment/allocation errors.")
    parser.add_argument("--openelections-dir", default="Data/openelections")
    parser.add_argument("--assign-zip", default="Data/BlockAssign_ST51_VA.zip")
    parser.add_argument("--tabblock-zip", default="Data/tl_2020_51_tabblock20.zip")
    parser.add_argument("--county-geojson", default="Data/tl_2020_51_county20.geojson")
    parser.add_argument("--vtd-zip", default="Data/tl_2020_51_vtd20.zip")
    parser.add_argument("--precinct-geojson", default="Data/va_precincts.geojson")
    parser.add_argument("--congressional-geojson", default="Data/tl_2024_51_cd119.geojson")
    parser.add_argument("--state-house-geojson", default="Data/tl_2022_51_sldl.geojson")
    parser.add_argument("--state-senate-geojson", default="Data/tl_2022_51_sldu.geojson")
    parser.add_argument(
        "--mapping-source",
        choices=("overlay", "blockassign", "auto"),
        default="overlay",
        help=(
            "How to build precinct->district splits. "
            "'overlay' uses displayed district lines (current map vintages), "
            "'blockassign' uses BlockAssign_* tables, "
            "'auto' tries blockassign then falls back to overlay."
        ),
    )
    parser.add_argument("--margin-targets-csv", default=builder.DEFAULT_MARGIN_TARGETS_CSV)
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--contest-type", action="append", default=[])
    parser.add_argument("--year", action="append", type=int, default=[])
    parser.add_argument("--top-counties", type=int, default=6)
    parser.add_argument("--output-dir", default="Data/benchmarks/diagnostics")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    openelections_dir = Path(args.openelections_dir)
    assign_zip = Path(args.assign_zip)
    tabblock_zip = Path(args.tabblock_zip)
    county_geojson = Path(args.county_geojson)
    vtd_zip = Path(args.vtd_zip)
    precinct_geojson = Path(args.precinct_geojson)
    congressional_geojson = Path(args.congressional_geojson)
    state_house_geojson = Path(args.state_house_geojson)
    state_senate_geojson = Path(args.state_senate_geojson)
    margin_targets_csv = Path(args.margin_targets_csv)
    output_dir = Path(args.output_dir)

    for p in (
        openelections_dir,
        assign_zip,
        tabblock_zip,
        county_geojson,
        vtd_zip,
        precinct_geojson,
        congressional_geojson,
        state_house_geojson,
        state_senate_geojson,
        margin_targets_csv,
    ):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    targets_all = builder.load_district_margin_targets(margin_targets_csv)
    scope_filters = {s.strip().lower() for s in args.scope if s.strip()}
    contest_filters = {c.strip().lower() for c in args.contest_type if c.strip()}
    year_filters = set(args.year) if args.year else None
    targets = filter_targets(targets_all, scope_filters or None, contest_filters or None, year_filters)
    if not targets:
        raise ValueError("No benchmark targets after filters")

    scope_maps = builder.build_all_scope_mappings(
        assign_zip,
        tabblock_zip,
        county_geojson,
        vtd_zip,
        precinct_geojson,
        congressional_geojson,
        state_house_geojson,
        state_senate_geojson,
        args.mapping_source,
    )
    locality_alias_map = builder.build_locality_alias_map(county_geojson)
    target_filter = {(scope, contest_type, year) for scope, contest_type, year, _ in targets.keys()}

    district_acc, district_county, county_coverage = collect_diagnostics(
        openelections_dir,
        scope_maps,
        locality_alias_map,
        target_filter,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_report_rows = []
    county_contrib_rows = []
    coverage_rows = []

    per_target_summary: list[dict[str, Any]] = []
    for (scope, contest_type, year, district), target_margin in sorted(
        targets.items(),
        key=lambda kv: (builder.SCOPES.index(kv[0][0]), kv[0][1], kv[0][2], builder.district_sort_key(kv[0][3])),
    ):
        key = (scope, contest_type, year, district)
        node = district_acc.get(key, {"dem": 0.0, "rep": 0.0, "other": 0.0})
        dem = float(node["dem"])
        rep = float(node["rep"])
        other = float(node["other"])
        total = dem + rep + other
        raw_margin = builder.compute_signed_margin_pct(node) if total > 0 else None
        raw_error = (float(raw_margin - target_margin) if raw_margin is not None else None)
        raw_abs_error = (abs(raw_error) if raw_error is not None else None)

        county_rows = []
        for (s, c, y, d, county), contrib in district_county.items():
            if (s, c, y, d) != key:
                continue
            dem_direct = float(contrib["dem_direct"])
            rep_direct = float(contrib["rep_direct"])
            other_direct = float(contrib["other_direct"])
            dem_alloc = float(contrib["dem_allocated"])
            rep_alloc = float(contrib["rep_allocated"])
            other_alloc = float(contrib["other_allocated"])
            direct_total = dem_direct + rep_direct + other_direct
            alloc_total = dem_alloc + rep_alloc + other_alloc
            county_total = direct_total + alloc_total
            if county_total <= 0:
                continue

            ckey = (scope, contest_type, year, county)
            cstats = county_coverage.get(ckey, {"input_votes": 0.0, "direct_votes": 0.0, "allocated_votes": 0.0, "unallocated_votes": 0.0})
            county_input = float(cstats["input_votes"])
            county_allocated = float(cstats["allocated_votes"])
            county_direct = float(cstats["direct_votes"])

            county_rows.append(
                {
                    "scope": scope,
                    "contest_type": contest_type,
                    "year": year,
                    "district": district,
                    "county": county,
                    "district_county_total_votes": round(county_total, 3),
                    "district_county_dem_votes": round(dem_direct + dem_alloc, 3),
                    "district_county_rep_votes": round(rep_direct + rep_alloc, 3),
                    "district_county_other_votes": round(other_direct + other_alloc, 3),
                    "district_county_direct_votes": round(direct_total, 3),
                    "district_county_allocated_votes": round(alloc_total, 3),
                    "district_county_allocated_share": round((alloc_total / county_total) if county_total > 0 else 0.0, 6),
                    "district_share_of_total": round((county_total / total) if total > 0 else 0.0, 6),
                    "county_scope_input_votes": round(county_input, 3),
                    "county_scope_direct_votes": round(county_direct, 3),
                    "county_scope_allocated_votes": round(county_allocated, 3),
                    "county_scope_allocated_share": round((county_allocated / county_input) if county_input > 0 else 0.0, 6),
                }
            )

        county_rows.sort(key=lambda r: float(r["district_county_total_votes"]), reverse=True)
        county_contrib_rows.extend(county_rows)

        top_n = max(1, int(args.top_counties))
        top_summary_parts = []
        for r in county_rows[:top_n]:
            pct = float(r["district_share_of_total"]) * 100.0
            alloc_pct = float(r["district_county_allocated_share"]) * 100.0
            top_summary_parts.append(f"{r['county']}:{pct:.1f}% (alloc {alloc_pct:.1f}%)")
        top_summary = " | ".join(top_summary_parts)

        raw_report_rows.append(
            {
                "scope": scope,
                "contest_type": contest_type,
                "year": year,
                "district": district,
                "target_margin_pct": round(float(target_margin), 3),
                "raw_margin_pct": round(float(raw_margin), 3) if raw_margin is not None else "",
                "raw_error_pct": round(float(raw_error), 3) if raw_error is not None else "",
                "raw_abs_error_pct": round(float(raw_abs_error), 3) if raw_abs_error is not None else "",
                "dem_votes": round(dem, 3),
                "rep_votes": round(rep, 3),
                "other_votes": round(other, 3),
                "total_votes": round(total, 3),
                "top_counties": top_summary,
            }
        )

        per_target_summary.append(
            {
                "scope": scope,
                "contest_type": contest_type,
                "year": year,
                "district": district,
                "target_margin_pct": float(target_margin),
                "raw_margin_pct": float(raw_margin) if raw_margin is not None else None,
                "raw_abs_error_pct": float(raw_abs_error) if raw_abs_error is not None else None,
                "top_counties": top_summary_parts,
            }
        )

    raw_report_rows.sort(key=lambda r: float(r["raw_abs_error_pct"] or 0.0), reverse=True)

    for (scope, contest_type, year, county), stats in sorted(
        county_coverage.items(),
        key=lambda kv: (builder.SCOPES.index(kv[0][0]), kv[0][1], kv[0][2], kv[0][3]),
    ):
        input_votes = float(stats["input_votes"])
        direct_votes = float(stats["direct_votes"])
        allocated_votes = float(stats["allocated_votes"])
        unallocated_votes = float(stats["unallocated_votes"])
        coverage_rows.append(
            {
                "scope": scope,
                "contest_type": contest_type,
                "year": year,
                "county": county,
                "input_votes": round(input_votes, 3),
                "direct_votes": round(direct_votes, 3),
                "allocated_votes": round(allocated_votes, 3),
                "unallocated_votes": round(unallocated_votes, 3),
                "direct_match_pct": round((direct_votes / input_votes * 100.0) if input_votes > 0 else 0.0, 3),
                "allocated_pct": round((allocated_votes / input_votes * 100.0) if input_votes > 0 else 0.0, 3),
                "unallocated_pct": round((unallocated_votes / input_votes * 100.0) if input_votes > 0 else 0.0, 3),
            }
        )

    raw_report_path = output_dir / "benchmark_raw_error_report.csv"
    county_contrib_path = output_dir / "benchmark_county_contributions.csv"
    county_coverage_path = output_dir / "benchmark_county_coverage.csv"
    summary_path = output_dir / "benchmark_diagnostics_summary.json"

    write_csv(
        raw_report_path,
        [
            "scope",
            "contest_type",
            "year",
            "district",
            "target_margin_pct",
            "raw_margin_pct",
            "raw_error_pct",
            "raw_abs_error_pct",
            "dem_votes",
            "rep_votes",
            "other_votes",
            "total_votes",
            "top_counties",
        ],
        raw_report_rows,
    )
    write_csv(
        county_contrib_path,
        [
            "scope",
            "contest_type",
            "year",
            "district",
            "county",
            "district_county_total_votes",
            "district_county_dem_votes",
            "district_county_rep_votes",
            "district_county_other_votes",
            "district_county_direct_votes",
            "district_county_allocated_votes",
            "district_county_allocated_share",
            "district_share_of_total",
            "county_scope_input_votes",
            "county_scope_direct_votes",
            "county_scope_allocated_votes",
            "county_scope_allocated_share",
        ],
        county_contrib_rows,
    )
    write_csv(
        county_coverage_path,
        [
            "scope",
            "contest_type",
            "year",
            "county",
            "input_votes",
            "direct_votes",
            "allocated_votes",
            "unallocated_votes",
            "direct_match_pct",
            "allocated_pct",
            "unallocated_pct",
        ],
        coverage_rows,
    )

    summary = {
        "targets_file": str(margin_targets_csv),
        "targets_used": len(targets),
        "scope_filters": sorted(scope_filters),
        "contest_filters": sorted(contest_filters),
        "year_filters": sorted(year_filters) if year_filters else [],
        "outputs": {
            "raw_error_report_csv": str(raw_report_path),
            "county_contributions_csv": str(county_contrib_path),
            "county_coverage_csv": str(county_coverage_path),
            "summary_json": str(summary_path),
        },
        "worst_targets": per_target_summary[: min(12, len(per_target_summary))],
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Targets used: {len(targets)}")
    print(f"Wrote: {raw_report_path}")
    print(f"Wrote: {county_contrib_path}")
    print(f"Wrote: {county_coverage_path}")
    print(f"Wrote: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
