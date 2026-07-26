#!/usr/bin/env python3
"""Build block-weighted VTD20-to-current Virginia precinct result crosswalks."""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import pandas as pd


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


def key_text(key: tuple[str, str]) -> str:
    return f"{key[0]} - {key[1]}"


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


def shapefile_uri(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".shp")]
    if len(members) != 1:
        raise RuntimeError(f"Expected one shapefile in {zip_path}; found {members}")
    return f"zip://{zip_path.resolve().as_posix()}!{members[0]}"


def read_vtd20(vtd_zip: Path, legacy_reference: Path) -> gpd.GeoDataFrame:
    reference = gpd.read_file(
        legacy_reference,
        columns=["countyfp20", "county_norm", "geometry"],
    )
    county_names = (
        reference[["countyfp20", "county_norm"]]
        .drop_duplicates("countyfp20")
        .set_index("countyfp20")["county_norm"]
        .map(locality)
        .to_dict()
    )
    vtds = gpd.read_file(
        shapefile_uri(vtd_zip),
        columns=["COUNTYFP20", "VTDST20", "NAME20", "geometry"],
    )
    vtds["countyfp20"] = vtds["COUNTYFP20"].astype(str).str.zfill(3)
    vtds["county_norm"] = vtds["countyfp20"].map(county_names)
    vtds["prec_id"] = vtds["VTDST20"].map(precinct_code)
    vtds["precinct_name"] = vtds["NAME20"].astype(str)
    missing = int(vtds["county_norm"].isna().sum())
    if missing:
        raise RuntimeError(f"{missing} VTD20 features lack a locality-name mapping")
    return vtds[
        ["countyfp20", "county_norm", "prec_id", "precinct_name", "geometry"]
    ].copy()


def pl_member(archive: zipfile.ZipFile, pattern: str) -> str:
    matches = [
        name
        for name in archive.namelist()
        if re.search(pattern, Path(name).name, flags=re.IGNORECASE)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one PL 94-171 member matching {pattern}; found {matches}")
    return matches[0]


def build_block_population_cache(pl_zip: Path, output: Path) -> pd.DataFrame:
    with zipfile.ZipFile(pl_zip) as archive:
        geo_name = pl_member(archive, r"geo2020\.pl$")
        seq1_name = pl_member(archive, r"000012020\.pl$")
        seq2_name = pl_member(archive, r"000022020\.pl$")

        logrec_to_geoid: dict[str, str] = {}
        with archive.open(geo_name) as handle:
            rows = csv.reader(
                (line.decode("utf-8") for line in handle),
                delimiter="|",
            )
            for row in rows:
                if len(row) > 9 and row[2] == "750":
                    logrec_to_geoid[row[7]] = row[9]

        populations: dict[str, list[int]] = {
            logrecno: [0, 0] for logrecno in logrec_to_geoid
        }
        for member, value_index in ((seq1_name, 0), (seq2_name, 1)):
            with archive.open(member) as handle:
                rows = csv.reader(
                    (line.decode("utf-8") for line in handle),
                    delimiter="|",
                )
                for row in rows:
                    if len(row) <= 5 or row[4] not in populations:
                        continue
                    populations[row[4]][value_index] = int(row[5] or 0)

    frame = pd.DataFrame(
        (
            geoid,
            populations[logrecno][0],
            populations[logrecno][1],
        )
        for logrecno, geoid in logrec_to_geoid.items()
    )
    frame.columns = ["block_geoid20", "total_population_2020", "voting_age_population_2020"]
    frame = frame.sort_values("block_geoid20", kind="stable")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    return frame


def read_block_population(pl_zip: Path, cache: Path) -> pd.DataFrame:
    if cache.exists():
        return pd.read_csv(
            cache,
            dtype={"block_geoid20": str},
        )
    return build_block_population_cache(pl_zip, cache)


def read_vtd20_assignments(zip_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.endswith("_VTD.txt")]
        if len(members) != 1:
            raise RuntimeError(f"Expected one VTD assignment table; found {members}")
        frame = pd.read_csv(
            archive.open(members[0]),
            sep="|",
            usecols=["BLOCKID", "COUNTYFP", "DISTRICT"],
            dtype=str,
        )
    frame = frame.rename(
        columns={
            "BLOCKID": "block_geoid20",
            "COUNTYFP": "countyfp20",
            "DISTRICT": "vtd20_code",
        }
    )
    frame["block_geoid20"] = frame["block_geoid20"].str.strip()
    frame["countyfp20"] = frame["countyfp20"].str.zfill(3)
    frame["vtd20_code"] = frame["vtd20_code"].map(precinct_code)
    return frame


def build_block_transition_weights(
    tabblock_zip: Path,
    block_assignments_zip: Path,
    population: pd.DataFrame,
    legacy: gpd.GeoDataFrame,
    current: gpd.GeoDataFrame,
) -> tuple[dict[str, list[dict[str, object]]], dict[str, int]]:
    source_names = (
        legacy[["countyfp20", "county_norm"]]
        .drop_duplicates("countyfp20")
        .set_index("countyfp20")["county_norm"]
        .map(locality)
        .to_dict()
    )
    assignments = read_vtd20_assignments(block_assignments_zip)
    assignments["source"] = assignments.apply(
        lambda row: key_text(
            (source_names.get(row["countyfp20"], ""), row["vtd20_code"])
        ),
        axis=1,
    )

    blocks = gpd.read_file(
        shapefile_uri(tabblock_zip),
        columns=["GEOID20", "ALAND20", "geometry"],
    )
    blocks = blocks.rename(
        columns={"GEOID20": "block_geoid20", "ALAND20": "block_land_area_m2"}
    )
    blocks["block_geoid20"] = blocks["block_geoid20"].astype(str)
    blocks_equal_area = blocks.to_crs(5070)
    block_points = gpd.GeoDataFrame(
        blocks_equal_area[
            ["block_geoid20", "block_land_area_m2"]
        ].copy(),
        geometry=blocks_equal_area.geometry.representative_point(),
        crs=5070,
    )

    targets = current[["county_norm", "prec_id", "geometry"]].copy()
    targets["target"] = targets.apply(lambda row: key_text(geometry_key(row)), axis=1)
    joined = gpd.sjoin(
        block_points,
        targets[["target", "geometry"]],
        how="left",
        predicate="within",
    )
    joined = joined.sort_values(
        ["block_geoid20", "index_right"],
        kind="stable",
    ).drop_duplicates("block_geoid20", keep="first")
    joined = joined.drop(columns=["index_right"])
    joined = joined.merge(assignments[["block_geoid20", "source"]], on="block_geoid20", how="left")
    joined = joined.merge(population, on="block_geoid20", how="left")
    joined["_population_matched"] = joined["total_population_2020"].notna()
    for column in (
        "block_land_area_m2",
        "total_population_2020",
        "voting_age_population_2020",
    ):
        joined[column] = pd.to_numeric(joined[column], errors="coerce").fillna(0.0)

    valid = joined.dropna(subset=["source", "target"]).copy()
    grouped = (
        valid.groupby(["source", "target"], as_index=False)
        .agg(
            block_land_area_m2=("block_land_area_m2", "sum"),
            total_population_2020=("total_population_2020", "sum"),
            voting_age_population_2020=("voting_age_population_2020", "sum"),
            blocks=("block_geoid20", "nunique"),
        )
    )
    by_source: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in grouped.to_dict("records"):
        by_source[str(row["source"])].append(row)
    stats = {
        "blocks_total": len(joined),
        "blocks_with_population": int(joined["_population_matched"].sum()),
        "blocks_assigned_to_current": int(joined["target"].notna().sum()),
        "blocks_unassigned_to_current": int(joined["target"].isna().sum()),
        "total_population_unassigned_to_current": int(
            joined.loc[joined["target"].isna(), "total_population_2020"].sum()
        ),
        "voting_age_population_unassigned_to_current": int(
            joined.loc[
                joined["target"].isna(),
                "voting_age_population_2020",
            ].sum()
        ),
        "blocks_with_complete_transition": len(valid),
    }
    return dict(by_source), stats


def geometry_target_weights(
    source: object,
    current_locality: gpd.GeoDataFrame,
    minimum_weight: float,
) -> tuple[list[list[object]], str]:
    targets = current_locality.copy()
    targets["_intersection_area"] = targets.geometry.map(
        lambda geometry: geometry.intersection(source.geometry).area
    )
    targets = targets[targets["_intersection_area"] > 0].copy()
    if targets.empty:
        return [], "unresolved"
    targets["_weight"] = targets["_intersection_area"] / targets["_intersection_area"].sum()
    targets = targets[targets["_weight"] >= minimum_weight].copy()
    if targets.empty:
        return [], "unresolved"
    targets["_weight"] = targets["_weight"] / targets["_weight"].sum()
    targets = targets.sort_values("_weight", ascending=False, kind="stable")
    return (
        [
            [key_text(geometry_key(row)), round(float(row["_weight"]), 6)]
            for _, row in targets.iterrows()
        ],
        "vtd20_to_current_land_overlap_fallback",
    )


def block_target_weights(
    source_key: tuple[str, str],
    block_transitions: dict[str, list[dict[str, object]]],
    minimum_weight: float,
) -> tuple[list[list[object]], str]:
    rows = block_transitions.get(key_text(source_key), [])
    if not rows:
        return [], "unresolved"
    totals = {
        column: sum(float(row[column]) for row in rows)
        for column in (
            "voting_age_population_2020",
            "total_population_2020",
            "block_land_area_m2",
        )
    }
    if totals["voting_age_population_2020"] > 0:
        weight_column = "voting_age_population_2020"
        method = "vtd20_to_current_2020_block_voting_age_population"
    elif totals["total_population_2020"] > 0:
        weight_column = "total_population_2020"
        method = "vtd20_to_current_2020_block_total_population"
    else:
        weight_column = "block_land_area_m2"
        method = "vtd20_to_current_2020_block_land_area"

    denominator = totals[weight_column]
    weighted = [
        [str(row["target"]), float(row[weight_column]) / denominator]
        for row in rows
        if float(row[weight_column]) / denominator >= minimum_weight
    ]
    if not weighted:
        return [], "unresolved"
    retained_total = sum(weight for _, weight in weighted)
    weighted = [[target, weight / retained_total] for target, weight in weighted]
    weighted.sort(key=lambda item: (-item[1], item[0]))
    rounded = [[target, round(weight, 6)] for target, weight in weighted]
    rounded[0][1] = round(
        float(rounded[0][1]) + (1.0 - sum(float(weight) for _, weight in rounded)),
        6,
    )
    return rounded, method


def resolve_reported_source_key(
    raw_key: tuple[str, str],
    reported_keys: set[tuple[str, str]],
) -> tuple[str, str] | None:
    if raw_key in reported_keys:
        return raw_key
    locality_name, code = raw_key
    candidates: list[str] = []
    if code.isdigit() and len(code) >= 2:
        candidates.append(code[:-1])
    if re.fullmatch(r"5\d{2,}", code):
        candidates.append(code[1:])
    matches = {
        (locality_name, candidate)
        for candidate in candidates
        if candidate and (locality_name, candidate) in reported_keys
    }
    return next(iter(matches)) if len(matches) == 1 else None


def align_vtd20_to_reported_sources(
    legacy: gpd.GeoDataFrame,
    block_transitions: dict[str, list[dict[str, object]]],
    reported_keys: set[tuple[str, str]],
) -> tuple[gpd.GeoDataFrame, dict[str, list[dict[str, object]]], int]:
    aligned = legacy.copy()
    aligned["_raw_key"] = aligned.apply(geometry_key, axis=1)
    aligned["_reported_key"] = aligned["_raw_key"].map(
        lambda key: resolve_reported_source_key(key, reported_keys)
    )
    collapsed_pieces = int(
        sum(
            raw_key != reported_key
            for raw_key, reported_key in zip(
                aligned["_raw_key"],
                aligned["_reported_key"],
            )
            if reported_key is not None
        )
    )
    aligned = aligned.dropna(subset=["_reported_key"]).copy()
    aligned["county_norm"] = aligned["_reported_key"].map(lambda key: key[0])
    aligned["prec_id"] = aligned["_reported_key"].map(lambda key: key[1])
    aligned = aligned.dissolve(
        by=["county_norm", "prec_id"],
        as_index=False,
        aggfunc="first",
    )

    grouped: dict[tuple[str, str], dict[str, float | int]] = defaultdict(
        lambda: {
            "block_land_area_m2": 0.0,
            "total_population_2020": 0.0,
            "voting_age_population_2020": 0.0,
            "blocks": 0,
        }
    )
    for raw_source, rows in block_transitions.items():
        raw_locality, raw_code = raw_source.rsplit(" - ", 1)
        reported_key = resolve_reported_source_key(
            (raw_locality, raw_code),
            reported_keys,
        )
        if reported_key is None:
            continue
        reported_source = key_text(reported_key)
        for row in rows:
            key = (reported_source, str(row["target"]))
            for column in (
                "block_land_area_m2",
                "total_population_2020",
                "voting_age_population_2020",
                "blocks",
            ):
                grouped[key][column] += float(row[column])

    remapped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (source, target), metrics in grouped.items():
        remapped[source].append(
            {
                "source": source,
                "target": target,
                **metrics,
            }
        )
    return aligned, dict(remapped), collapsed_pieces


def build_year(
    keys: set[tuple[str, str]],
    legacy: gpd.GeoDataFrame,
    current: gpd.GeoDataFrame,
    block_transitions: dict[str, list[dict[str, object]]],
    minimum_parent_coverage: float,
    minimum_target_weight: float,
) -> dict[str, object]:
    legacy, block_transitions, collapsed_vtd20_pieces = align_vtd20_to_reported_sources(
        legacy,
        block_transitions,
        keys,
    )
    current_keys = {geometry_key(row) for _, row in current.iterrows()}
    current_without_result = current_keys - keys
    result_without_current = keys - current_keys
    selected_sources: set[tuple[str, str]] = set()

    legacy_keys = {geometry_key(row) for _, row in legacy.iterrows()}
    selected_sources.update(result_without_current & legacy_keys)

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
    method_counts: dict[str, int] = defaultdict(int)
    for source_key in sorted(selected_sources):
        source_rows = legacy[
            (legacy["county_norm"].map(locality) == source_key[0])
            & (legacy["prec_id"].map(precinct_code) == source_key[1])
        ]
        if source_rows.empty:
            continue
        targets, method = block_target_weights(
            source_key,
            block_transitions,
            minimum_target_weight,
        )
        if not targets:
            source = source_rows.iloc[0]
            targets, method = geometry_target_weights(
                source,
                current[current["county_norm"] == source.county_norm],
                minimum_target_weight,
            )
        if not targets:
            continue
        method_counts[method] += 1
        splits.append(
            {
                "source": key_text(source_key),
                "targets": targets,
                "method": method,
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
            "collapsed_vtd20_pieces": collapsed_vtd20_pieces,
            "methods": dict(sorted(method_counts.items())),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vtd20", default="Data/tl_2020_51_vtd20.zip")
    parser.add_argument("--legacy-reference", default="Data/va_precincts.geojson")
    parser.add_argument("--current", default="Data/va_precincts_current.geojson")
    parser.add_argument("--tabblock20", default="Data/tl_2020_51_tabblock20.zip")
    parser.add_argument("--block-assignments", default="Data/BlockAssign_ST51_VA.zip")
    parser.add_argument("--pl94", default="Data/va2020.pl.zip")
    parser.add_argument(
        "--block-population-cache",
        default="Data/va_2020_block_population.csv",
    )
    parser.add_argument(
        "--output",
        default="Data/precinct_result_geometry_crosswalk.json",
    )
    parser.add_argument("--minimum-parent-coverage", type=float, default=0.05)
    parser.add_argument("--minimum-target-weight", type=float, default=0.005)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    legacy = read_vtd20(Path(args.vtd20), Path(args.legacy_reference)).to_crs(5070)
    current = gpd.read_file(args.current).to_crs(5070)
    population = read_block_population(
        Path(args.pl94),
        Path(args.block_population_cache),
    )
    block_transitions, block_stats = build_block_transition_weights(
        Path(args.tabblock20),
        Path(args.block_assignments),
        population,
        legacy,
        current,
    )
    payload = {
        "meta": {
            "description": "Election-year VTD20 result keys allocated to current ELECT precincts",
            "preferred_method": "2020 Census block voting-age population",
            "fallback_method": "2020 Census block total population, then block or polygon land area",
            "weights_conserve_each_source": True,
            "minimum_parent_coverage": args.minimum_parent_coverage,
            "minimum_target_weight": args.minimum_target_weight,
            "sources": {
                "vtd20": str(args.vtd20),
                "current_precincts": str(args.current),
                "tabulation_blocks": str(args.tabblock20),
                "block_assignments": str(args.block_assignments),
                "pl94_redistricting_data": str(args.pl94),
            },
            "block_stats": block_stats,
        },
        "years": {},
    }
    for year, (path, office) in DEFAULT_ELECTIONS.items():
        payload["years"][str(year)] = build_year(
            result_keys(Path(path), office),
            legacy,
            current,
            block_transitions,
            args.minimum_parent_coverage,
            args.minimum_target_weight,
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "block_stats": block_stats,
                "years": {
                    year: data["counts"]
                    for year, data in payload["years"].items()
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
