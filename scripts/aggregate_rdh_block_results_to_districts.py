#!/usr/bin/env python3
"""Aggregate RDH 2020-block election disaggregations to Virginia districts."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"congressional": "cd", "state_house": "state_house", "state_senate": "state_senate"}
ELECTIONS = {
    ("president", 2016): {
        "dem": "G16PREDCLI",
        "rep": "G16PRERTRU",
        "other": ["G16PRELJOH", "G16PREIMCM", "G16PREGSTE", "G16PREOWRI"],
    },
    ("us_senate", 2018): {
        "dem": "G18USSDKAI",
        "rep": "G18USSRSTE",
        "other": ["G18USSLWAT", "G18USSOWRI"],
    },
}


def largest_remainder(weights: dict[str, float], target: int) -> dict[str, int]:
    keys = sorted(weights, key=lambda value: int(value))
    total = sum(max(0.0, weights[key]) for key in keys)
    raw = {key: (target * max(0.0, weights[key]) / total if total else target / len(keys)) for key in keys}
    result = {key: math.floor(raw[key]) for key in keys}
    order = sorted(keys, key=lambda key: (-(raw[key] - result[key]), int(key)))
    for key in order[: target - sum(result.values())]:
        result[key] += 1
    return result


def color_for_margin(margin: float, winner: str) -> str:
    cutoffs = [
        (40, "#67000d", "#08306b"), (30, "#a50f15", "#08519c"),
        (20, "#cb181d", "#3182bd"), (10, "#ef3b2c", "#6baed6"),
        (5.5, "#fb6a4a", "#9ecae1"), (1, "#fcae91", "#c6dbef"),
        (0.5, "#fee5d9", "#deebf7"), (0, "#f7f7f7", "#f7f7f7"),
    ]
    for cutoff, rep, dem in cutoffs:
        if abs(margin) >= cutoff:
            return rep if winner == "Republican" else dem
    return "#f7f7f7"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--president-2016-zip", type=Path, required=True)
    parser.add_argument("--senate-2018-zip", type=Path, required=True)
    parser.add_argument("--assignments", type=Path, default=ROOT / "Data/scv_2021_block_assignments.csv")
    parser.add_argument("--official-dir", type=Path, default=ROOT / "Data/contests")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "Data/district_contests")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def aggregate(archive: Path, contest: str, year: int, args: argparse.Namespace) -> list[str]:
    fields = ELECTIONS[(contest, year)]
    vote_columns = [fields["dem"], fields["rep"], *fields["other"]]
    blocks = gpd.read_file(archive.resolve(), ignore_geometry=True)[["GEOID20", *vote_columns]]
    blocks["GEOID20"] = blocks["GEOID20"].astype(str).str.strip().str.zfill(15)
    for column in vote_columns:
        blocks[column] = pd.to_numeric(blocks[column], errors="coerce").fillna(0.0)
    blocks["dem"] = blocks[fields["dem"]]
    blocks["rep"] = blocks[fields["rep"]]
    blocks["other"] = blocks[fields["other"]].sum(axis=1)

    assignments = pd.read_csv(args.assignments, dtype=str).fillna("")
    assignments["block_geoid20"] = assignments["block_geoid20"].str.strip().str.zfill(15)
    merged = assignments.merge(
        blocks[["GEOID20", "dem", "rep", "other"]],
        left_on="block_geoid20", right_on="GEOID20", how="left", validate="one_to_one",
    )
    if merged[["dem", "rep", "other"]].isna().any(axis=None):
        missing = int(merged["dem"].isna().sum())
        raise ValueError(f"{archive}: {missing} assigned blocks lack RDH rows")

    official = json.loads((args.official_dir / f"{contest}_{year}.json").read_text(encoding="utf-8"))
    targets = {party: int(official["meta"][f"{party}_total"]) for party in ("dem", "rep", "other")}
    candidates = official["rows"][0]
    changed: list[str] = []
    for scope, district_column in SCOPES.items():
        grouped = merged.groupby(district_column, as_index=True)[["dem", "rep", "other"]].sum()
        grouped.index = grouped.index.map(lambda value: str(int(float(value))))
        allocated = {
            party: largest_remainder(grouped[party].to_dict(), targets[party])
            for party in ("dem", "rep", "other")
        }
        path = args.output_dir / f"{scope}_{contest}_{year}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        results = {}
        for district in sorted(grouped.index, key=int):
            dem, rep, other = (allocated[p][district] for p in ("dem", "rep", "other"))
            total = dem + rep + other
            signed_margin = ((rep - dem) / total * 100.0) if total else 0.0
            winner = "Republican" if rep > dem else ("Democratic" if dem > rep else "Tie")
            results[district] = {
                "dem_votes": dem, "rep_votes": rep, "other_votes": other, "total_votes": total,
                "dem_candidate": candidates["dem_candidate"], "rep_candidate": candidates["rep_candidate"],
                "winner": winner, "margin": abs(rep - dem), "margin_pct": signed_margin,
                "color": color_for_margin(signed_margin, winner),
            }
        payload["general"]["results"] = results
        for stale_key in (
            "whole_locality_threshold", "whole_locality_exact_districts",
            "exact_locality_cluster_districts", "protected_benchmark_districts",
            "locality_cluster_constraints",
        ):
            payload["meta"].pop(stale_key, None)
        payload["meta"].update({
            "district_count": len(results),
            "input_votes": sum(targets.values()), "matched_votes": sum(targets.values()),
            "direct_matched_votes": sum(targets.values()), "allocated_votes": 0,
            "match_coverage_pct": 100.0, "direct_match_coverage_pct": 100.0,
            "statewide_vote_reconciled": True,
            "statewide_vote_reconciliation_method": (
                "RDH election results disaggregated to 2020 Census blocks, joined directly to "
                "official SCV Final 2021 block district assignments; party buckets rounded by "
                "largest remainder to official statewide totals."
            ),
            "block_result_source": archive.name,
            "block_assignment_source": args.assignments.name,
        })
        if args.write:
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        changed.append(path.name)
    return changed


def main() -> int:
    args = parse_args()
    changed = []
    changed += aggregate(args.president_2016_zip, "president", 2016, args)
    changed += aggregate(args.senate_2018_zip, "us_senate", 2018, args)
    print(("Wrote" if args.write else "Validated") + f" {len(changed)} district slices")
    for path in changed:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
