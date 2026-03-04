#!/usr/bin/env python3
"""
Build Virginia boundary GeoJSON files from Census TIGER/Line ZIP shapefiles.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

try:
    import geopandas as gpd
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: geopandas. Install it in your active environment first "
        "(for example: pip install geopandas)."
    ) from exc


ZIP_TO_OUTPUT = {
    "tl_2020_51_county20.zip": "tl_2020_51_county20.geojson",
    "tl_2024_51_cd119.zip": "tl_2024_51_cd119.geojson",
    "tl_2022_51_sldl.zip": "tl_2022_51_sldl.geojson",
    "tl_2022_51_sldu.zip": "tl_2022_51_sldu.geojson",
}


def find_shapefile_name(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path, "r") as zf:
        shp_files = [name for name in zf.namelist() if name.lower().endswith(".shp")]
    if not shp_files:
        raise FileNotFoundError(f"No .shp file found in {zip_path}")
    return shp_files[0]


def convert_zip_to_geojson(zip_path: Path, output_path: Path) -> None:
    shp_name = find_shapefile_name(zip_path)
    gdf = gpd.read_file(f"zip://{zip_path.resolve().as_posix()}!{shp_name}")
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4269, allow_override=True)
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert VA TIGER ZIP files to GeoJSON.")
    parser.add_argument(
        "--data-dir",
        default="Data",
        help="Directory containing ZIP inputs and GeoJSON outputs (default: Data).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    converted = 0
    for zip_name, out_name in ZIP_TO_OUTPUT.items():
        zip_path = data_dir / zip_name
        if not zip_path.exists():
            print(f"Skipping missing ZIP: {zip_path}")
            continue
        out_path = data_dir / out_name
        convert_zip_to_geojson(zip_path, out_path)
        converted += 1
        print(f"Built {out_path} from {zip_path.name}")

    print(f"Converted {converted} boundary files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
