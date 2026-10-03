#!/usr/bin/env python3
"""Benchmark district projections against RDH block-disaggregated results."""

from __future__ import annotations

import argparse
import json
import zipfile
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyogrio

from build_va_district_contests_from_crosswalks import category_color_for_margin
from reconcile_va_district_contests import district_sort_key, largest_remainder


ROOT = Path(__file__).resolve().parents[1]
SCOPES = {"congressional": "cd", "state_house": "state_house", "state_senate": "state_senate"}
ELECTION_COLUMNS = {
    2020: {
        "president": {"dem": ["G20PREDBID"], "rep": ["G20PRERTRU"], "other": ["G20PRELJOR", "G20PREOWRI"]},
        "us_senate": {"dem": ["G20USSDWAR"], "rep": ["G20USSRGAD"], "other": ["G20USSOWRI"]},
    },
    2024: {
        "president": {
            "dem": ["G24PREDHAR"],
            "rep": ["G24PRERTRU"],
            "other": ["G24PREGSTE", "G24PREICRU", "G24PREIWES", "G24PRELOLI", "G24PREOOTH"],
        },
        "us_senate": {"dem": ["G24USSDKAI"], "rep": ["G24USSRCAO"], "other": ["G24USSOOTH"]},
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, choices=sorted(ELECTION_COLUMNS), required=True)
    parser.add_argument("--input-zip", required=True)
    parser.add_argument("--assignments-csv", default="Data/scv_2021_block_assignments.csv")
    parser.add_argument("--district-contests-dir", default="Data/district_contests")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--write-candidate-dir",
        help="Optionally write production-shaped district JSON candidates using the block benchmark.",
    )
    return parser.parse_args()


def resolve(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def load_blocks(path: Path, year: int) -> pd.DataFrame:
    columns = ["GEOID20"] + sorted({c for contest in ELECTION_COLUMNS[year].values() for cols in contest.values() for c in cols})
    if year == 2020:
        return pyogrio.read_dataframe(f"zip://{path}", columns=columns, read_geometry=False)
    with zipfile.ZipFile(path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"Expected one CSV in {path}, found {csv_names}")
        with archive.open(csv_names[0]) as source:
            return pd.read_csv(source, usecols=columns, dtype={"GEOID20": str})


def rounded_district_votes(frame: pd.DataFrame, district_col: str, columns: dict[str, list[str]]) -> dict[str, dict[str, int]]:
    work = frame.copy()
    districts = sorted(work[district_col].dropna().astype(str).str.lstrip("0").unique(), key=district_sort_key)
    work["district"] = work[district_col].astype(str).str.lstrip("0")
    raw: dict[str, dict[str, float]] = defaultdict(dict)
    for bucket, source_columns in columns.items():
        work[bucket] = work[source_columns].sum(axis=1)
        grouped = work.groupby("district")[bucket].sum()
        allocation = largest_remainder(grouped.to_dict(), int(round(float(grouped.sum()))))
        for district in districts:
            raw[district][bucket] = int(allocation.get(district, 0))
    out: dict[str, dict[str, int]] = {}
    for district in districts:
        row = raw[district]
        total = sum(row.values())
        out[district] = {
            **row,
            "total": total,
            "margin_pct": ((row["rep"] - row["dem"]) / total * 100.0) if total else 0.0,
        }
    return out


def main() -> int:
    args = parse_args()
    input_path = resolve(args.input_zip)
    assignments_path = resolve(args.assignments_csv)
    production_dir = resolve(args.district_contests_dir)
    blocks = load_blocks(input_path, args.year)
    blocks["GEOID20"] = blocks["GEOID20"].astype(str).str.zfill(15)
    assignments = pd.read_csv(assignments_path, dtype=str).rename(columns={"block_geoid20": "GEOID20"})
    assignments["GEOID20"] = assignments["GEOID20"].astype(str).str.zfill(15)
    merged = blocks.merge(assignments, on="GEOID20", how="left", validate="one_to_one")
    missing = int(merged[list(SCOPES.values())].isna().all(axis=1).sum())

    files = []
    candidate_dir = resolve(args.write_candidate_dir) if args.write_candidate_dir else None
    if candidate_dir:
        candidate_dir.mkdir(parents=True, exist_ok=True)
    for scope, assignment_column in SCOPES.items():
        for contest, columns in ELECTION_COLUMNS[args.year].items():
            benchmark = rounded_district_votes(merged, assignment_column, columns)
            filename = f"{scope}_{contest}_{args.year}.json"
            production_path = production_dir / filename
            production = json.loads(production_path.read_text(encoding="utf-8"))
            production_rows = production.get("general", {}).get("results", {})
            comparisons = []
            for district, row in benchmark.items():
                old = production_rows.get(district, {})
                production_margin = float(old.get("margin_pct", 0) or 0)
                comparisons.append({
                    "district": district,
                    "production_margin_pct": production_margin,
                    "block_benchmark_margin_pct": row["margin_pct"],
                    "abs_change_pct": abs(row["margin_pct"] - production_margin),
                    "block_votes": {key: row[key] for key in ("dem", "rep", "other", "total")},
                })
            comparisons.sort(key=lambda row: row["abs_change_pct"], reverse=True)
            files.append({
                "file": filename,
                "district_count": len(benchmark),
                "block_totals": {
                    bucket: sum(row[bucket] for row in benchmark.values())
                    for bucket in ("dem", "rep", "other")
                },
                "max_abs_margin_change_pct": comparisons[0]["abs_change_pct"] if comparisons else 0.0,
                "largest_margin_changes": comparisons[:10],
            })
            if candidate_dir:
                candidate = json.loads(json.dumps(production))
                candidate["meta"].update({
                    "block_disaggregated_source": input_path.name,
                    "block_disaggregated_method": (
                        "RDH modified-VAP precinct-to-2020-block disaggregation joined to official SCV assignments"
                    ),
                    "block_rows": len(blocks),
                })
                candidate_rows = candidate["general"]["results"]
                for district, row in benchmark.items():
                    target = candidate_rows[district]
                    dem, rep, other, total = row["dem"], row["rep"], row["other"], row["total"]
                    signed = float(row["margin_pct"])
                    if rep > dem:
                        winner, party = "Republican", "R"
                    elif dem > rep:
                        winner, party = "Democratic", "D"
                    else:
                        winner, party = "Tie", "R"
                    target.update({
                        "dem_votes": dem,
                        "rep_votes": rep,
                        "other_votes": other,
                        "total_votes": total,
                        "winner": winner,
                        "margin": abs(rep - dem),
                        "margin_pct": signed,
                        "color": category_color_for_margin(abs(signed), party),
                    })
                (candidate_dir / filename).write_text(
                    json.dumps(candidate, indent=2) + "\n", encoding="utf-8"
                )

    payload = {
        "year": args.year,
        "input": input_path.name,
        "method": "RDH precinct results disaggregated to 2020 Census blocks by modified VAP, joined by GEOID20 to official SCV 2021 district assignments, with largest-remainder integer conservation by party.",
        "block_rows": len(blocks),
        "unique_blocks": int(blocks["GEOID20"].nunique()),
        "blocks_missing_all_assignments": missing,
        "files": files,
    }
    output = resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "block_rows": payload["block_rows"],
        "blocks_missing_all_assignments": missing,
        "max_drift_by_file": {row["file"]: row["max_abs_margin_change_pct"] for row in files},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
