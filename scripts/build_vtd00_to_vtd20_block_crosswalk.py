#!/usr/bin/env python3
"""Build a block-chained, area-weighted Virginia VTD00-to-VTD20 crosswalk."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd


def csv_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if len(members) != 1:
        raise RuntimeError(f"Expected one CSV in {zip_path}; found {members}")
    return members[0]


def read_nhgis(zip_path: Path, columns: list[str]) -> pd.DataFrame:
    member = csv_member(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        frame = pd.read_csv(
            archive.open(member),
            usecols=columns,
            dtype={column: str for column in columns if column not in {"parea", "weight"}},
        )
    for numeric in ("parea", "weight"):
        if numeric in frame:
            frame[numeric] = pd.to_numeric(frame[numeric], errors="coerce").fillna(0.0)
    return frame


def shapefile_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".shp")]
    if len(members) != 1:
        raise RuntimeError(f"Expected one shapefile in {zip_path}; found {members}")
    return members[0]


def assign_2000_blocks_to_vtds(
    block_zip: Path, vtd_path: Path
) -> tuple[pd.DataFrame, dict[str, int]]:
    blocks = gpd.read_file(
        f"zip://{block_zip.resolve().as_posix()}",
        columns=["BLKIDFP", "geometry"],
    )
    # TIGER2008 splits many original Census 2000 blocks into A/B/C pieces.
    # NHGIS uses the original 15-digit GEOID, so dissolve those suffix pieces
    # back to the source block before assigning VTD00 and chaining decades.
    blocks["blk2000ge"] = blocks["BLKIDFP"].astype(str).str.strip().str[:15]
    blocks = blocks[blocks["blk2000ge"].str.startswith("51")].copy()
    if blocks.crs is None:
        blocks = blocks.set_crs(4269, allow_override=True)
    blocks = blocks.dissolve(by="blk2000ge", as_index=False)

    blocks_equal_area = blocks.to_crs(5070)
    block_points = gpd.GeoDataFrame(
        {
            "blk2000ge": blocks_equal_area["blk2000ge"],
            "block_area_m2": blocks_equal_area.geometry.area,
        },
        geometry=blocks_equal_area.geometry.representative_point(),
        crs=5070,
    )
    vtds = gpd.read_file(vtd_path).to_crs(5070)
    vtds = vtds[
        ["countyfp00", "vtdst00", "name00", "county_nam", "geometry"]
    ].copy()

    joined = gpd.sjoin(block_points, vtds, how="left", predicate="within")
    joined = joined.sort_values(["blk2000ge", "index_right"], kind="stable")
    joined = joined.drop_duplicates("blk2000ge", keep="first")
    unmatched = int(joined["vtdst00"].isna().sum())
    assigned = joined.dropna(subset=["vtdst00"]).copy()
    assigned["countyfp00"] = assigned["countyfp00"].astype(str).str.zfill(3)
    assigned["vtdst00"] = assigned["vtdst00"].astype(str).str.strip()
    stats = {
        "blocks_total": len(block_points),
        "blocks_assigned_to_vtd00": len(assigned),
        "blocks_unassigned_to_vtd00": unmatched,
    }
    return assigned[
        [
            "blk2000ge",
            "block_area_m2",
            "countyfp00",
            "vtdst00",
            "name00",
            "county_nam",
        ]
    ], stats


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
            "BLOCKID": "blk2020ge",
            "COUNTYFP": "vtd20_countyfp",
            "DISTRICT": "vtd20_code",
        }
    )
    frame["blk2020ge"] = frame["blk2020ge"].str.strip()
    frame["vtd20_countyfp"] = frame["vtd20_countyfp"].str.zfill(3)
    frame["vtd20_code"] = frame["vtd20_code"].str.strip()
    return frame


def build_crosswalk(
    block_assignments: pd.DataFrame,
    crosswalk_00_10: Path,
    crosswalk_10_20: Path,
    vtd20_assignments: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int | float]]:
    x00_10 = read_nhgis(
        crosswalk_00_10,
        ["blk2000ge", "blk2010ge", "parea", "weight"],
    ).rename(columns={"parea": "parea_00_10", "weight": "pop_weight_00_10"})
    x10_20 = read_nhgis(
        crosswalk_10_20,
        ["blk2010ge", "blk2020ge", "parea", "weight"],
    ).rename(columns={"parea": "parea_10_20", "weight": "pop_weight_10_20"})

    paths = block_assignments.merge(x00_10, on="blk2000ge", how="inner")
    paths = paths.merge(x10_20, on="blk2010ge", how="inner")
    paths = paths.merge(vtd20_assignments, on="blk2020ge", how="inner")
    paths["area_weight_m2"] = (
        paths["block_area_m2"]
        * paths["parea_00_10"]
        * paths["parea_10_20"]
    )
    # This is useful as a diagnostic but is not a population total: without a
    # 2000 block population table, it treats every source block equally.
    paths["equal_block_population_weight"] = (
        paths["pop_weight_00_10"] * paths["pop_weight_10_20"]
    )

    group_columns = [
        "countyfp00",
        "county_nam",
        "vtdst00",
        "name00",
        "vtd20_countyfp",
        "vtd20_code",
    ]
    grouped = (
        paths.groupby(group_columns, as_index=False)
        .agg(
            area_weight_m2=("area_weight_m2", "sum"),
            equal_block_population_weight=("equal_block_population_weight", "sum"),
            source_blocks=("blk2000ge", "nunique"),
            block_paths=("blk2020ge", "size"),
        )
    )
    old_key = ["countyfp00", "vtdst00"]
    grouped["old_vtd_area_weight_m2"] = grouped.groupby(old_key)[
        "area_weight_m2"
    ].transform("sum")
    grouped["area_share"] = (
        grouped["area_weight_m2"] / grouped["old_vtd_area_weight_m2"]
    )
    grouped["old_vtd_equal_block_population_weight"] = grouped.groupby(old_key)[
        "equal_block_population_weight"
    ].transform("sum")
    grouped["equal_block_population_share"] = (
        grouped["equal_block_population_weight"]
        / grouped["old_vtd_equal_block_population_weight"].replace(0, pd.NA)
    ).fillna(0.0)
    grouped = grouped.sort_values(
        ["countyfp00", "vtdst00", "area_share"],
        ascending=[True, True, False],
        kind="stable",
    )

    area_sums = grouped.groupby(old_key)["area_share"].sum()
    summary = {
        "block_paths": len(paths),
        "old_vtds_with_successors": int(grouped.groupby(old_key).ngroups),
        "weighted_links": len(grouped),
        "split_old_vtds": int((grouped.groupby(old_key).size() > 1).sum()),
        "max_area_share_sum_error": float((area_sums - 1.0).abs().max()),
    }
    return grouped, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vtd00", default="Data/tl_2008_51_vtd00.geojson")
    parser.add_argument("--tabblock00", default="Data/tl_2008_51_tabblock00.zip")
    parser.add_argument(
        "--crosswalk-00-10", default="Data/nhgis_blk2000_blk2010_51.zip"
    )
    parser.add_argument(
        "--crosswalk-10-20", default="Data/nhgis_blk2010_blk2020_51.zip"
    )
    parser.add_argument("--vtd20-assignments", default="Data/BlockAssign_ST51_VA.zip")
    parser.add_argument(
        "--output", default="Data/vtd00_to_vtd20_block_crosswalk.csv"
    )
    parser.add_argument(
        "--summary-output", default="Data/vtd00_to_vtd20_block_crosswalk_summary.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    assignments, assignment_stats = assign_2000_blocks_to_vtds(
        Path(args.tabblock00), Path(args.vtd00)
    )
    crosswalk, summary = build_crosswalk(
        assignments,
        Path(args.crosswalk_00_10),
        Path(args.crosswalk_10_20),
        read_vtd20_assignments(Path(args.vtd20_assignments)),
    )
    summary = {**assignment_stats, **summary}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    crosswalk.to_csv(output, index=False)
    Path(args.summary_output).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
