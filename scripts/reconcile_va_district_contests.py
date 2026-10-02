#!/usr/bin/env python3
"""Reconcile VA district slices to statewide totals and exact locality components.

This is the Virginia counterpart to NCPrecinctMap's whole/mixed-county rules.
Virginia counties and independent cities are both treated as localities:

* a locality is whole in a district when at least 99.9% of its 2020 Census VAP
  is assigned to that district;
* its official locality vote is held exact, including when the district also
  contains portions of other localities;
* only split-locality components are reweighted to make every statewide
  Democratic, Republican, and other total exact;
* exact district-result overrides and explicit margin targets remain locked.

The command audits by default. Pass --write to update the district JSON files
and manifest. A JSON report is always written to the output directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCOPES = {
    "congressional": "cd",
    "state_house": "state_house",
    "state_senate": "state_senate",
}
STATEWIDE_CONTESTS = {"president", "us_senate", "governor", "lieutenant_governor", "attorney_general"}
BUCKET_FIELDS = {"dem": "dem_votes", "rep": "rep_votes", "other": "other_votes"}


def normalize_district(raw: object) -> str:
    value = str(raw or "").strip()
    try:
        return str(int(float(value)))
    except ValueError:
        return value


def district_sort_key(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except ValueError:
        return 10**9, value


def largest_remainder(weights: dict[str, float], target: int) -> dict[str, int]:
    if target < 0:
        raise ValueError(f"Cannot allocate a negative target: {target}")
    keys = sorted(weights, key=district_sort_key)
    if not keys:
        if target:
            raise ValueError(f"No adjustable districts available for {target} votes")
        return {}
    positive = {key: max(0.0, float(weights[key])) for key in keys}
    weight_sum = sum(positive.values())
    if weight_sum <= 0:
        positive = {key: 1.0 for key in keys}
        weight_sum = float(len(keys))
    raw = {key: target * positive[key] / weight_sum for key in keys}
    out = {key: math.floor(raw[key]) for key in keys}
    remainder = target - sum(out.values())
    order = sorted(keys, key=lambda key: (-(raw[key] - out[key]), district_sort_key(key)))
    for key in order[:remainder]:
        out[key] += 1
    return out


def build_locality_components(
    official_assignments_csv: Path,
    assignment_column: str,
    block_vap_path: Path,
    county_geojson: Path,
    threshold: float,
) -> dict[str, Any]:
    counties = gpd.read_file(county_geojson, ignore_geometry=True)
    county_names = {
        str(row.get("COUNTYFP20", "")).strip().zfill(3): str(row.get("NAMELSAD20", "")).strip().upper()
        for row in counties.to_dict(orient="records")
        if str(row.get("COUNTYFP20", "")).strip()
    }
    vap = pd.read_csv(block_vap_path, dtype={"block_geoid20": str})[
        ["block_geoid20", "voting_age_population_2020"]
    ].rename(columns={"block_geoid20": "GEOID20", "voting_age_population_2020": "vap"})
    vap["GEOID20"] = vap["GEOID20"].astype(str).str.strip().str.zfill(15)
    assignments = pd.read_csv(
        official_assignments_csv,
        dtype={"block_geoid20": str, assignment_column: str},
        usecols=["block_geoid20", assignment_column],
    ).rename(columns={"block_geoid20": "GEOID20", assignment_column: "district"})
    assignments["GEOID20"] = assignments["GEOID20"].astype(str).str.strip().str.zfill(15)
    assignments["district"] = assignments["district"].map(normalize_district)
    assignments["COUNTYFP20"] = assignments["GEOID20"].str.slice(2, 5)
    merged = assignments.merge(vap, on="GEOID20", how="left")
    merged["vap"] = pd.to_numeric(merged["vap"], errors="coerce").fillna(0.0)
    merged = merged[merged["vap"] > 0].copy()
    merged["locality"] = merged["COUNTYFP20"].map(county_names)

    grouped = merged.groupby(["locality", "district"], as_index=False)["vap"].sum()
    locality_total = grouped.groupby("locality")["vap"].sum().to_dict()
    district_total = grouped.groupby("district")["vap"].sum().to_dict()

    whole_by_district: dict[str, list[str]] = defaultdict(list)
    whole_area_by_district: dict[str, float] = defaultdict(float)
    partial_by_district: dict[str, list[str]] = defaultdict(list)
    for row in grouped.itertuples(index=False):
        share = float(row.vap) / float(locality_total[row.locality])
        if share >= threshold:
            whole_by_district[row.district].append(row.locality)
            whole_area_by_district[row.district] += float(row.vap)
        elif share > (1.0 - threshold):
            partial_by_district[row.district].append(row.locality)

    exact_clusters = []
    for district, localities in whole_by_district.items():
        coverage = whole_area_by_district[district] / float(district_total[district])
        if coverage >= threshold:
            exact_clusters.append(district)

    return {
        "whole_by_district": {
            key: sorted(set(whole_by_district[key]))
            for key in sorted(whole_by_district, key=district_sort_key)
        },
        "partial_by_district": {
            key: sorted(set(partial_by_district[key]))
            for key in sorted(partial_by_district, key=district_sort_key)
        },
        "exact_clusters": sorted(set(exact_clusters), key=district_sort_key),
    }


def load_protected_districts(margin_csv: Path, override_csv: Path) -> dict[tuple[str, str, int, str], dict[str, Any]]:
    protected: dict[tuple[str, str, int, str], dict[str, Any]] = {}
    for kind, path in (("margin", margin_csv), ("override", override_csv)):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                try:
                    key = (
                        str(row.get("scope", "")).strip().lower(),
                        str(row.get("contest_type", "")).strip().lower(),
                        int(str(row.get("year", "")).strip()),
                        normalize_district(row.get("district", "")),
                    )
                except ValueError:
                    continue
                if all((key[0], key[1], key[3])):
                    spec: dict[str, Any] = {"kind": kind}
                    if kind == "margin":
                        spec["target_margin_pct"] = float(row.get("target_margin_pct", 0) or 0)
                    else:
                        spec["votes"] = {
                            bucket: int(float(row.get(field, 0) or 0))
                            for bucket, field in BUCKET_FIELDS.items()
                        }
                    protected[key] = spec
    return protected


def load_official(path: Path) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    statewide = {
        "dem": int(meta.get("dem_total", 0) or 0),
        "rep": int(meta.get("rep_total", 0) or 0),
        "other": int(meta.get("other_total", 0) or 0),
    }
    localities: dict[str, dict[str, int]] = {}
    for row in payload.get("rows", []):
        locality = str(row.get("county", "")).strip().upper()
        if not locality:
            continue
        localities[locality] = {
            bucket: int(row.get(field, 0) or 0) for bucket, field in BUCKET_FIELDS.items()
        }
    return statewide, localities


def finalize_row(row: dict[str, Any]) -> None:
    dem = int(row.get("dem_votes", 0) or 0)
    rep = int(row.get("rep_votes", 0) or 0)
    other = int(row.get("other_votes", 0) or 0)
    total = dem + rep + other
    row["total_votes"] = total
    row["margin"] = abs(rep - dem)
    row["margin_pct"] = ((rep - dem) / total * 100.0) if total else 0.0
    row["winner"] = "Republican" if rep > dem else ("Democratic" if dem > rep else "Tie")


def reconcile_file(
    path: Path,
    official_path: Path,
    components: dict[str, Any],
    protected_keys: dict[tuple[str, str, int, str], dict[str, Any]],
    write: bool,
    max_margin_drift: float,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    scope = str(meta.get("scope", ""))
    contest = str(meta.get("contest_type", ""))
    year = int(meta.get("year", 0) or 0)
    results = payload.get("general", {}).get("results", {})
    statewide, locality_totals = load_official(official_path)
    before = {bucket: sum(int(row.get(field, 0) or 0) for row in results.values()) for bucket, field in BUCKET_FIELDS.items()}
    before_margins = {
        normalize_district(district): ((int(row.get("rep_votes", 0) or 0) - int(row.get("dem_votes", 0) or 0)) / int(row.get("total_votes", 0) or 1) * 100.0)
        for district, row in results.items()
    }

    locked: set[str] = set()
    for district, row in results.items():
        district = normalize_district(district)
        spec = protected_keys.get((scope, contest, year, district))
        if not spec:
            continue
        if spec["kind"] == "override":
            if all(int(row.get(field, 0) or 0) == spec["votes"][bucket] for bucket, field in BUCKET_FIELDS.items()):
                locked.add(district)
        else:
            total = sum(int(row.get(field, 0) or 0) for field in BUCKET_FIELDS.values())
            margin = ((int(row.get("rep_votes", 0) or 0) - int(row.get("dem_votes", 0) or 0)) / total * 100.0) if total else 0.0
            if abs(margin - float(spec["target_margin_pct"])) <= 0.011:
                locked.add(district)
    whole_by_district = components["whole_by_district"]
    shortfalls: list[dict[str, Any]] = []

    for bucket, field in BUCKET_FIELDS.items():
        fixed: dict[str, int] = {}
        adjustable_weights: dict[str, float] = {}
        for district, row in results.items():
            district = normalize_district(district)
            current = int(row.get(field, 0) or 0)
            if district in locked:
                fixed[district] = current
                continue
            whole_vote = sum(
                locality_totals.get(locality, {}).get(bucket, 0)
                for locality in whole_by_district.get(district, [])
            )
            fixed[district] = whole_vote
            adjustable_weights[district] = max(0, current - whole_vote)
            if current < whole_vote:
                shortfalls.append({
                    "district": district,
                    "bucket": bucket,
                    "current": current,
                    "whole_locality_floor": whole_vote,
                })

        remaining = statewide[bucket] - sum(fixed.values())
        allocated = largest_remainder(adjustable_weights, remaining)
        for district, row in results.items():
            district = normalize_district(district)
            if district in locked:
                continue
            row[field] = fixed[district] + allocated[district]

    for row in results.values():
        finalize_row(row)
    margin_drifts = {
        normalize_district(district): abs(float(row.get("margin_pct", 0) or 0) - before_margins[normalize_district(district)])
        for district, row in results.items()
    }
    worst_margin_drift = max(margin_drifts.values(), default=0.0)
    if write and worst_margin_drift > max_margin_drift:
        raise ValueError(
            f"Refusing to write {path.name}: maximum district margin drift "
            f"{worst_margin_drift:.3f} exceeds guard {max_margin_drift:.3f}"
        )
    after = {bucket: sum(int(row.get(field, 0) or 0) for row in results.values()) for bucket, field in BUCKET_FIELDS.items()}
    differences = {bucket: after[bucket] - statewide[bucket] for bucket in BUCKET_FIELDS}
    if any(differences.values()):
        raise AssertionError(f"Reconciliation failed for {path}: {differences}")

    meta["statewide_vote_reconciled"] = True
    meta["statewide_vote_reconciliation_method"] = (
        "Exact whole-locality components (county or independent city) at >=99.9% coverage; "
        "largest-remainder allocation across split-locality components."
    )
    meta["whole_locality_threshold"] = 0.999
    meta["whole_locality_exact_districts"] = sorted(whole_by_district, key=district_sort_key)
    meta["exact_locality_cluster_districts"] = components["exact_clusters"]
    meta["protected_benchmark_districts"] = sorted(locked, key=district_sort_key)
    if write:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    return {
        "file": path.name,
        "scope": scope,
        "contest_type": contest,
        "year": year,
        "before": before,
        "official": statewide,
        "after": after,
        "before_difference": {bucket: before[bucket] - statewide[bucket] for bucket in BUCKET_FIELDS},
        "protected_districts": sorted(locked, key=district_sort_key),
        "whole_component_shortfalls": shortfalls,
        "maximum_margin_drift_pct": worst_margin_drift,
    }


def update_manifest(output_dir: Path) -> None:
    path = output_dir / "manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for entry in payload.get("files", []):
        contest_path = output_dir / str(entry.get("file", ""))
        if not contest_path.exists():
            continue
        contest = json.loads(contest_path.read_text(encoding="utf-8"))
        rows = contest.get("general", {}).get("results", {}).values()
        entry["dem_total"] = sum(int(row.get("dem_votes", 0) or 0) for row in rows)
        rows = contest.get("general", {}).get("results", {}).values()
        entry["rep_total"] = sum(int(row.get("rep_votes", 0) or 0) for row in rows)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.999)
    parser.add_argument(
        "--official-assignments-csv",
        default="Data/scv_2021_block_assignments.csv",
        help="Tracked compact table derived from the official SCV Final 2021 block assignments.",
    )
    parser.add_argument("--block-vap-csv", default="Data/va_2020_block_population.csv")
    parser.add_argument("--county-geojson", default="Data/tl_2020_51_county20.geojson")
    parser.add_argument("--max-margin-drift", type=float, default=5.0)
    parser.add_argument("--district-contests-dir", default="Data/district_contests")
    parser.add_argument("--statewide-contests-dir", default="Data/contests")
    parser.add_argument("--margin-targets-csv", default="Data/benchmarks/district_margin_targets.csv")
    parser.add_argument("--result-overrides-csv", default="Data/benchmarks/district_result_overrides.csv")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = ROOT / args.district_contests_dir
    official_dir = ROOT / args.statewide_contests_dir
    protected = load_protected_districts(ROOT / args.margin_targets_csv, ROOT / args.result_overrides_csv)

    component_catalog: dict[str, Any] = {}
    for scope, assignment_column in SCOPES.items():
        component_catalog[scope] = build_locality_components(
            ROOT / args.official_assignments_csv,
            assignment_column,
            ROOT / args.block_vap_csv,
            ROOT / args.county_geojson,
            float(args.threshold),
        )

    reports = []
    for path in sorted(output_dir.glob("*.json")):
        if path.name == "manifest.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {})
        scope = str(meta.get("scope", ""))
        contest = str(meta.get("contest_type", ""))
        year = int(meta.get("year", 0) or 0)
        if scope not in component_catalog or contest not in STATEWIDE_CONTESTS:
            continue
        official_path = official_dir / f"{contest}_{year}.json"
        if not official_path.exists():
            continue
        reports.append(reconcile_file(
            path, official_path, component_catalog[scope], protected, args.write, float(args.max_margin_drift)
        ))

    if args.write:
        update_manifest(output_dir)
    report_payload = {
        "mode": "write" if args.write else "audit",
        "threshold": float(args.threshold),
        "locality_definition": "Virginia county or independent city, keyed by Census county-equivalent FIPS",
        "component_weight": "2020 Census voting-age population by block, assigned by the official SCV Final 2021 block-assignment files",
        "components": component_catalog,
        "files": reports,
    }
    report_path = output_dir / "locality_component_reconciliation_report.json"
    report_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
    changed = sum(1 for row in reports if any(row["before_difference"].values()))
    print(f"Audited {len(reports)} statewide district slices; {changed} required reconciliation.")
    print(f"Mode: {'write' if args.write else 'audit'}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
