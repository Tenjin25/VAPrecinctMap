#!/usr/bin/env python3
"""Build current Virginia precinct display points from ELECT polygons."""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--precinct-geojson",
        default="Data/va_precincts_current.geojson",
        help="Current ELECT precinct polygon GeoJSON.",
    )
    parser.add_argument(
        "--output",
        default="Data/va_precinct_centroids.geojson",
        help="Output point GeoJSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_path = Path(args.precinct_geojson)
    output_path = Path(args.output)
    if not source_path.exists():
        raise FileNotFoundError(f"Current precinct GeoJSON not found: {source_path}")

    precincts = gpd.read_file(source_path)
    if precincts.crs is None:
        precincts = precincts.set_crs(4326, allow_override=True)

    # Calculate in an equal-area projection and use representative points so
    # every display point remains inside its ELECT precinct, including concave
    # and multipart polygons.
    projected = precincts.to_crs(5070)
    points = projected.geometry.representative_point()
    keep_columns = [
        column
        for column in (
            "id",
            "countyfp20",
            "county_norm",
            "county_nam",
            "prec_id",
            "district_raw",
            "precinct_name",
            "precinct_label",
            "precinct_norm",
            "source_geoid",
            "source_last_edited",
            "source_package",
            "source",
        )
        if column in precincts.columns
    ]
    centroids = precincts[keep_columns].copy()
    centroids = gpd.GeoDataFrame(centroids, geometry=points, crs=5070).to_crs(4326)
    centroids["centroid_source"] = "Virginia Department of Elections current precinct geometry"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    centroids.to_file(output_path, driver="GeoJSON")
    print(
        f"Wrote {len(centroids)} ELECT-derived precinct display points "
        f"to {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
