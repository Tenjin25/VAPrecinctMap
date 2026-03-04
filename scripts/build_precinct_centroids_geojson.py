#!/usr/bin/env python3
"""
Build VA precinct centroid GeoJSON from TIGER/Line VTD polygons.
"""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

try:
    import geopandas as gpd
    from shapely.geometry import Point
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: geopandas/shapely. Install them in your active environment first."
    ) from exc


def find_shp_name(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "r") as zf:
        shp_names = [n for n in zf.namelist() if n.lower().endswith(".shp")]
    if not shp_names:
        raise FileNotFoundError(f"No .shp found in {zip_path}")
    return shp_names[0]


def normalize_precinct_id(vtdst: str) -> str:
    s = (vtdst or "").strip()
    if not s:
        return ""
    digits = re.sub(r"[^0-9]", "", s)
    if digits:
        return str(int(digits))
    return s


def normalize_key(text: str) -> str:
    return (
        (text or "")
        .strip()
        .replace("\t", " ")
        .replace("\n", " ")
        .upper()
    )


def canonical_locality_name(name20: str, namelsad20: str) -> str:
    base = (namelsad20 or name20 or "").strip()
    if not base:
        return ""
    return normalize_key(base)


def safe_float(value: object) -> float | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build VA precinct centroid GeoJSON.")
    parser.add_argument(
        "--vtd-zip",
        default="Data/tl_2020_51_vtd20.zip",
        help="Path to TIGER VTD ZIP (default: Data/tl_2020_51_vtd20.zip).",
    )
    parser.add_argument(
        "--county-geojson",
        default="Data/tl_2020_51_county20.geojson",
        help="Path to county GeoJSON for county name join (default: Data/tl_2020_51_county20.geojson).",
    )
    parser.add_argument(
        "--output",
        default="Data/va_precinct_centroids.geojson",
        help="Output centroid GeoJSON path (default: Data/va_precinct_centroids.geojson).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vtd_zip = Path(args.vtd_zip)
    county_geojson = Path(args.county_geojson)
    output_path = Path(args.output)

    if not vtd_zip.exists():
        raise FileNotFoundError(f"VTD ZIP not found: {vtd_zip}")
    if not county_geojson.exists():
        raise FileNotFoundError(f"County GeoJSON not found: {county_geojson}")

    shp_name = find_shp_name(vtd_zip)
    vtd_uri = f"zip://{vtd_zip.resolve().as_posix()}!{shp_name}"

    vtd = gpd.read_file(vtd_uri)
    counties = gpd.read_file(county_geojson)

    if vtd.crs is None:
        vtd = vtd.set_crs(epsg=4269, allow_override=True)
    if vtd.crs.to_epsg() != 4326:
        vtd = vtd.to_crs(epsg=4326)

    county_name_map = {}
    for _, row in counties.iterrows():
        county_fp = str(row.get("COUNTYFP20", "")).strip()
        county_name = canonical_locality_name(
            str(row.get("NAME20", "")),
            str(row.get("NAMELSAD20", "")),
        )
        if county_fp:
            county_name_map[county_fp] = county_name

    rows = []
    for _, row in vtd.iterrows():
        county_fp = str(row.get("COUNTYFP20", "")).strip()
        county_name = county_name_map.get(county_fp, county_fp)
        prec_id = normalize_precinct_id(str(row.get("VTDST20", "")))
        precinct_name_raw = str(row.get("NAME20", "")).strip()
        precinct_name = f"{prec_id} - {precinct_name_raw}" if prec_id and precinct_name_raw else precinct_name_raw
        precinct_norm = normalize_key(f"{county_name} - {prec_id}")

        lon = safe_float(row.get("INTPTLON20"))
        lat = safe_float(row.get("INTPTLAT20"))
        if lon is not None and lat is not None:
            geometry = Point(lon, lat)
        else:
            geometry = row.geometry.representative_point()

        rows.append(
            {
                "statefp20": str(row.get("STATEFP20", "")).strip(),
                "countyfp20": county_fp,
                "geoid20": str(row.get("GEOID20", "")).strip(),
                "vtdst20": str(row.get("VTDST20", "")).strip(),
                "county_nam": county_name,
                "prec_id": prec_id,
                "precinct_name": precinct_name,
                "precinct_norm": precinct_norm,
                "geometry": geometry,
            }
        )

    centroids = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    centroids.to_file(output_path, driver="GeoJSON")

    print(f"Wrote {len(centroids)} centroid features to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
