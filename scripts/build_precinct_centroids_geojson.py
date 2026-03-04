#!/usr/bin/env python3
"""
Build VA precinct centroid GeoJSON from TIGER/Line VTD polygons.
"""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from collections import defaultdict
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
    s = (vtdst or "").strip().upper()
    if not s:
        return ""
    s = re.sub(r"[^A-Z0-9.\-]", "", s)
    if re.fullmatch(r"\d+", s):
        return str(int(s))
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


def extract_precinct_code(precinct_raw: str) -> str:
    p = (precinct_raw or "").strip().upper()
    if not p:
        return ""
    if " - " in p:
        token = p.split(" - ", 1)[0].strip()
    else:
        token = re.split(r"[_\s]+", p, maxsplit=1)[0].strip()
    return normalize_precinct_id(token)


def load_csv_precinct_codes(openelections_root: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    if not openelections_root.exists():
        return out

    for csv_path in sorted(openelections_root.rglob("*.csv")):
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                county = normalize_key(row.get("county", ""))
                precinct = row.get("precinct", "")
                if not county or not precinct:
                    continue
                code = extract_precinct_code(precinct)
                if code:
                    out[county].add(code)
    return out


def canonicalize_precinct_code(county_name: str, prec_id: str, oe_codes_by_county: dict[str, set[str]]) -> str:
    county_up = normalize_key(county_name)
    if not county_up or not prec_id:
        return prec_id

    county_codes = oe_codes_by_county.get(county_up, set())
    if prec_id in county_codes:
        return prec_id

    # Handle legacy VA code variants like 5101 -> 101 (e.g., Alleghany).
    if re.fullmatch(r"5\d{2,}", prec_id):
        candidate = prec_id[1:]
        if candidate in county_codes:
            return candidate

    return prec_id


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
    parser.add_argument(
        "--openelections-dir",
        default="Data/openelections",
        help="Path to OpenElections CSV root for precinct code canonicalization (default: Data/openelections).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vtd_zip = Path(args.vtd_zip)
    county_geojson = Path(args.county_geojson)
    output_path = Path(args.output)
    openelections_dir = Path(args.openelections_dir)

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

    oe_codes_by_county = load_csv_precinct_codes(openelections_dir)

    rows = []
    for _, row in vtd.iterrows():
        county_fp = str(row.get("COUNTYFP20", "")).strip()
        county_name = county_name_map.get(county_fp, county_fp)
        geom_prec_id = normalize_precinct_id(str(row.get("VTDST20", "")))
        prec_id = canonicalize_precinct_code(county_name, geom_prec_id, oe_codes_by_county)
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
