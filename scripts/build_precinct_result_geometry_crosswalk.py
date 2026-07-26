#!/usr/bin/env python3
"""Build year-specific election-key to current-precinct geometry crosswalks."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import geopandas as gpd


DEFAULT_ELECTIONS = {
    2023: (
        "Data/openelections/2023/"
        "20231107__va__general__precinct__multi_office__a6f500ae_6aed_4237_b29a_8a94a22dfbbb.csv",
        None,
    ),
    2024: (
        "Data/openelections/2024/20241105__va__general__precinct__president.csv",
        "PRESIDENT",
    ),
    2025: (
        "Data/openelections/2025/"
        "20251104__va__general__precinct__multi_office__9b503992_5765_47e2_989d_5ed01f31621e.csv",
        "GOVERNOR",
    ),
}


def locality(value: object) -> str:
    text = str(value or "").strip().upper().replace("&", " AND ")
    text = re.sub(r"\s+", " ", text)
    if text.startswith("CITY OF "):
        text = f"{text[8:].strip()} CITY"
    return text


def precinct_code(value: object) -> str:
    text = str(value or "").strip().upper()
    first = re.split(r"[_\s]+", text, maxsplit=1)[0].strip()
    token = re.sub(r"[^A-Z0-9.\-]", "", first).rstrip("-")
    code_name = re.match(r"^([A-Z]{0,3}\d{1,4}[A-Z]{0,2})-[A-Z].*$", token)
    token = code_name.group(1) if code_name else token
    return str(int(token)) if token.isdigit() else token


def result_keys(path: Path, office: str | None) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if office and str(row.get("office", "")).upper() != office:
                continue
            precinct = str(row.get("precinct", "")).upper()
            if any(
                token in precinct
                for token in ("ABSENTEE", "PROVISIONAL", "ONE STOP", "CURBSIDE")
            ):
                continue
            key = (locality(row.get("county")), precinct_code(precinct))
            if all(key):
                keys.add(key)
    return keys


def geometry_key(row: object) -> tuple[str, str]:
    return locality(row.county_norm), precinct_code(row.prec_id)


def key_text(key: tuple[str, str]) -> str:
    return f"{key[0]} - {key[1]}"


def target_weights(
    source: object,
    current_locality: gpd.GeoDataFrame,
    minimum_weight: float,
) -> list[list[object]]:
    targets = current_locality.copy()
    targets["_intersection_area"] = targets.geometry.map(
        lambda geometry: geometry.intersection(source.geometry).area
    )
    targets = targets[targets["_intersection_area"] > 0].copy()
    if targets.empty:
        return []
    targets["_weight"] = (
        targets["_intersection_area"] / targets["_intersection_area"].sum()
    )
    targets = targets[targets["_weight"] >= minimum_weight].copy()
    if targets.empty:
        return []
    targets["_weight"] = targets["_weight"] / targets["_weight"].sum()
    targets = targets.sort_values("_weight", ascending=False, kind="stable")
    return [
        [key_text(geometry_key(row)), round(float(row["_weight"]), 6)]
        for _, row in targets.iterrows()
    ]


def build_year(
    year: int,
    keys: set[tuple[str, str]],
    legacy: gpd.GeoDataFrame,
    current: gpd.GeoDataFrame,
    minimum_parent_coverage: float,
    minimum_target_weight: float,
) -> dict[str, object]:
    current_keys = {geometry_key(row) for _, row in current.iterrows()}
    current_without_result = current_keys - keys
    result_without_current = keys - current_keys
    selected_sources: set[tuple[str, str]] = set()

    # Always carry result rows whose identifiers disappeared from current geometry.
    legacy_keys = {geometry_key(row) for _, row in legacy.iterrows()}
    selected_sources.update(result_without_current & legacy_keys)

    # For every new current polygon, find reported legacy parents covering a
    # material share of its area.
    for _, target in current.iterrows():
        target_key = geometry_key(target)
        if target_key not in current_without_result or target.geometry.area <= 0:
            continue
        candidates = legacy[legacy["county_norm"] == target.county_norm]
        for _, source in candidates.iterrows():
            source_key = geometry_key(source)
            if source_key not in keys:
                continue
            overlap = source.geometry.intersection(target.geometry).area
            if overlap / target.geometry.area >= minimum_parent_coverage:
                selected_sources.add(source_key)

    splits = []
    for source_key in sorted(selected_sources):
        source_rows = legacy[
            (legacy["county_norm"].map(locality) == source_key[0])
            & (legacy["prec_id"].map(precinct_code) == source_key[1])
        ]
        if source_rows.empty:
            continue
        source = source_rows.iloc[0]
        targets = target_weights(
            source,
            current[current["county_norm"] == source.county_norm],
            minimum_target_weight,
        )
        if not targets:
            continue
        splits.append(
            {
                "source": key_text(source_key),
                "targets": targets,
                "method": "legacy_to_current_land_overlap",
            }
        )

    covered_targets = {
        target[0]
        for split in splits
        for target in split["targets"]
        if target[1] > 0
    }
    unresolved = []
    for key in sorted(current_without_result):
        text = key_text(key)
        if text in covered_targets:
            continue
        current_row = current[
            (current["county_norm"].map(locality) == key[0])
            & (current["prec_id"].map(precinct_code) == key[1])
        ].iloc[0]
        polling_location = str(current_row.get("polling_location", "") or "").strip()
        reason = (
            "no_registered_voters"
            if "NO REGISTERED VOTERS" in polling_location.upper()
            else "created_after_election_or_no_reported_parent"
        )
        unresolved.append(
            {
                "precinct": text,
                "name": str(current_row.get("precinct_name", "") or ""),
                "reason": reason,
            }
        )

    return {
        "splits": splits,
        "unresolved_current": unresolved,
        "counts": {
            "result_keys": len(keys),
            "current_geometry_keys": len(current_keys),
            "direct_keys": len(keys & current_keys),
            "split_sources": len(splits),
            "unresolved_current": len(unresolved),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy", default="Data/va_precincts.geojson")
    parser.add_argument("--current", default="Data/va_precincts_current.geojson")
    parser.add_argument(
        "--output", default="Data/precinct_result_geometry_crosswalk.json"
    )
    parser.add_argument("--minimum-parent-coverage", type=float, default=0.05)
    parser.add_argument("--minimum-target-weight", type=float, default=0.005)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    legacy = gpd.read_file(args.legacy).to_crs(5070)
    current = gpd.read_file(args.current).to_crs(5070)
    payload = {
        "meta": {
            "description": "Election-year precinct result keys allocated to current ELECT polygons",
            "method": "legacy polygon to current polygon land-area overlap",
            "weights_conserve_each_source": True,
            "minimum_parent_coverage": args.minimum_parent_coverage,
            "minimum_target_weight": args.minimum_target_weight,
        },
        "years": {},
    }
    for year, (path, office) in DEFAULT_ELECTIONS.items():
        payload["years"][str(year)] = build_year(
            year,
            result_keys(Path(path), office),
            legacy,
            current,
            args.minimum_parent_coverage,
            args.minimum_target_weight,
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({year: data["counts"] for year, data in payload["years"].items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
