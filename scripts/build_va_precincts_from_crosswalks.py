#!/usr/bin/env python3
"""
Build Virginia precinct polygons from tabblock geometry + VTD block assignment crosswalk.

Inputs:
- Data/tl_2020_51_tabblock20.zip
- Data/BlockAssign_ST51_VA.zip (BlockAssign_ST51_VA_VTD.txt)
- Data/tl_2020_51_county20.geojson
- Data/openelections/**/*.csv (optional, for precinct label enrichment)

Output:
- Data/va_precincts.geojson
"""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

try:
    import geopandas as gpd
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: geopandas. Install it in your active environment first."
    ) from exc


def find_zip_member(zip_path: Path, suffix: str) -> str:
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [m for m in zf.namelist() if m.endswith(suffix)]
    if not members:
        raise FileNotFoundError(f"No member ending with {suffix!r} in {zip_path}")
    return members[0]


def normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip()).upper()


def normalize_precinct_code(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not s:
        return ""
    s = re.sub(r"[^A-Z0-9.\-]", "", s)
    if re.fullmatch(r"\d+", s):
        return str(int(s))
    return s


def extract_precinct_code(precinct_raw: str) -> str:
    p = (precinct_raw or "").strip().upper()
    if not p:
        return ""
    # Prefer "NNN - NAME" style first.
    if " - " in p:
        token = p.split(" - ", 1)[0].strip()
    else:
        token = re.split(r"[_\s]+", p, maxsplit=1)[0].strip()
    return normalize_precinct_code(token)


def parse_precinct_label(precinct_raw: str, code: str) -> str:
    p = normalize_key(precinct_raw)
    if not p:
        return code
    if " - " in p:
        return p
    if code:
        return f"{code} - {p}"
    return p


def load_county_name_map(county_geojson: Path) -> dict[str, str]:
    counties = gpd.read_file(county_geojson)
    out: dict[str, str] = {}
    for _, row in counties.iterrows():
        county_fp = str(row.get("COUNTYFP20", "")).strip()
        county_name = str(row.get("NAME20", "")).strip()
        if county_fp and county_name:
            out[county_fp] = county_name
    return out


def load_csv_precinct_labels(openelections_root: Path) -> dict[tuple[str, str], str]:
    """
    Build most-common OpenElections precinct labels by (county, code).
    """
    counts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    if not openelections_root.exists():
        return {}

    for csv_path in sorted(openelections_root.rglob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                county = normalize_key(row.get("county", ""))
                precinct = normalize_key(row.get("precinct", ""))
                if not county or not precinct:
                    continue
                code = extract_precinct_code(precinct)
                if not code:
                    continue
                label = parse_precinct_label(precinct, code)
                counts[(county, code)][label] += 1

    best: dict[tuple[str, str], str] = {}
    for key, counter in counts.items():
        best[key] = counter.most_common(1)[0][0]
    return best


def load_vtd_block_crosswalk(crosswalk_zip: Path) -> pd.DataFrame:
    member = find_zip_member(crosswalk_zip, "BlockAssign_ST51_VA_VTD.txt")
    with zipfile.ZipFile(crosswalk_zip, "r") as zf:
        with zf.open(member) as f:
            df = pd.read_csv(
                f,
                sep="|",
                dtype={"BLOCKID": str, "COUNTYFP": str, "DISTRICT": str},
            )
    for col in ("BLOCKID", "COUNTYFP", "DISTRICT"):
        if col not in df.columns:
            raise ValueError(f"Expected {col} in {member}")
    df["BLOCKID"] = df["BLOCKID"].astype(str).str.strip()
    df["COUNTYFP"] = df["COUNTYFP"].astype(str).str.zfill(3).str.strip()
    df["DISTRICT"] = df["DISTRICT"].astype(str).str.strip()
    return df[["BLOCKID", "COUNTYFP", "DISTRICT"]]


def load_tabblocks(tabblock_zip: Path) -> gpd.GeoDataFrame:
    shp_member = find_zip_member(tabblock_zip, ".shp")
    uri = f"zip://{tabblock_zip.resolve().as_posix()}!{shp_member}"
    blocks = gpd.read_file(uri)
    required = {"GEOID20", "COUNTYFP20", "geometry"}
    missing = required - set(blocks.columns)
    if missing:
        raise ValueError(f"Missing expected tabblock columns: {sorted(missing)}")
    blocks["GEOID20"] = blocks["GEOID20"].astype(str).str.strip()
    blocks["COUNTYFP20"] = blocks["COUNTYFP20"].astype(str).str.zfill(3).str.strip()
    if blocks.crs is None:
        blocks = blocks.set_crs(epsg=4269, allow_override=True)
    return blocks[["GEOID20", "COUNTYFP20", "geometry"]]


def build_precincts(
    blocks: gpd.GeoDataFrame,
    vtd_xwalk: pd.DataFrame,
    county_names: dict[str, str],
    precinct_labels: dict[tuple[str, str], str],
) -> gpd.GeoDataFrame:
    merged = blocks.merge(vtd_xwalk, left_on="GEOID20", right_on="BLOCKID", how="inner")
    if merged.empty:
        raise ValueError("No block rows matched between tabblocks and VTD crosswalk")

    gdf = gpd.GeoDataFrame(merged, geometry="geometry", crs=blocks.crs)
    dissolved = gdf.dissolve(by=["COUNTYFP", "DISTRICT"], as_index=False, aggfunc="first")

    rows = []
    for _, row in dissolved.iterrows():
        county_fp = str(row.get("COUNTYFP", "")).zfill(3)
        district_raw = str(row.get("DISTRICT", "")).strip()
        county_name = county_names.get(county_fp, county_fp)
        prec_id = normalize_precinct_code(district_raw)
        county_up = normalize_key(county_name)

        label = precinct_labels.get((county_up, prec_id))
        if not label:
            label = f"{prec_id} - VTD {district_raw}" if prec_id else f"VTD {district_raw}"

        precinct_norm = normalize_key(f"{county_name} - {prec_id}")
        county_norm = normalize_key(county_name)

        rows.append(
            {
                "countyfp20": county_fp,
                "district_raw": district_raw,
                "county_nam": county_name,
                "county_norm": county_norm,
                "prec_id": prec_id,
                "precinct_name": label,
                "precinct_norm": precinct_norm,
                "geometry": row.geometry,
            }
        )

    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=blocks.crs)
    out = out.sort_values(["countyfp20", "prec_id"], kind="stable").reset_index(drop=True)
    out["id"] = out.index + 1

    if out.crs.to_epsg() != 4326:
        out = out.to_crs(epsg=4326)

    # Reorder columns for map readability.
    out = out[
        [
            "id",
            "countyfp20",
            "district_raw",
            "county_nam",
            "county_norm",
            "prec_id",
            "precinct_name",
            "precinct_norm",
            "geometry",
        ]
    ]
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build VA precinct polygons from tabblocks + crosswalks."
    )
    parser.add_argument(
        "--tabblock-zip",
        default="Data/tl_2020_51_tabblock20.zip",
        help="Path to tabblock ZIP (default: Data/tl_2020_51_tabblock20.zip)",
    )
    parser.add_argument(
        "--crosswalk-zip",
        default="Data/BlockAssign_ST51_VA.zip",
        help="Path to BlockAssign ZIP (default: Data/BlockAssign_ST51_VA.zip)",
    )
    parser.add_argument(
        "--county-geojson",
        default="Data/tl_2020_51_county20.geojson",
        help="Path to county GeoJSON (default: Data/tl_2020_51_county20.geojson)",
    )
    parser.add_argument(
        "--openelections-dir",
        default="Data/openelections",
        help="Path to OpenElections CSV root (default: Data/openelections)",
    )
    parser.add_argument(
        "--output",
        default="Data/va_precincts.geojson",
        help="Output precinct GeoJSON (default: Data/va_precincts.geojson)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tabblock_zip = Path(args.tabblock_zip)
    crosswalk_zip = Path(args.crosswalk_zip)
    county_geojson = Path(args.county_geojson)
    openelections_dir = Path(args.openelections_dir)
    output_path = Path(args.output)

    for path in (tabblock_zip, crosswalk_zip, county_geojson):
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    county_names = load_county_name_map(county_geojson)
    precinct_labels = load_csv_precinct_labels(openelections_dir)
    vtd_xwalk = load_vtd_block_crosswalk(crosswalk_zip)
    blocks = load_tabblocks(tabblock_zip)

    precincts = build_precincts(blocks, vtd_xwalk, county_names, precinct_labels)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    precincts.to_file(output_path, driver="GeoJSON")

    print(f"Wrote {len(precincts)} precinct features to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
