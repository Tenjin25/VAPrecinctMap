#!/usr/bin/env python3
"""
Download and merge Virginia ELECT's locality-maintained precinct GIS packages.

The current layer is deliberately written alongside, rather than over, the
Census-2020-derived production layer.  A spatial bridge CSV records how each
legacy precinct relates to the current geometry so historical election
crosswalks can remain versioned and unchanged.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

try:
    import geopandas as gpd
    import pandas as pd
    from shapely import set_precision
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: geopandas (and its pandas dependency). "
        "Install geopandas in the active Python environment."
    ) from exc


GIS_PAGE = "https://www.elections.virginia.gov/casting-a-ballot/redistricting/gis/"
ZIP_LINK_RE = re.compile(
    r"""href=["']([^"']*/media/redistricting/gis/-zip-files/[^"']+\.zip)["']""",
    re.IGNORECASE,
)


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "VAPrecinctMap/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def official_zip_urls() -> list[str]:
    request = urllib.request.Request(GIS_PAGE, headers={"User-Agent": "VAPrecinctMap/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        html = response.read().decode("utf-8", errors="replace")
    urls = sorted({urllib.parse.urljoin(GIS_PAGE, href) for href in ZIP_LINK_RE.findall(html)})
    if len(urls) != 133:
        raise RuntimeError(f"Expected 133 official locality ZIP links; found {len(urls)}")
    return urls


def shapefile_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".shp")]
    if len(members) != 1:
        raise RuntimeError(f"Expected one shapefile in {zip_path}; found {members}")
    return members[0]


def text_series(frame: gpd.GeoDataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="string")
    return frame[column].fillna("").astype(str).str.strip()


def normalize_code(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+", text):
        return str(int(text))
    return text.upper()


def precinct_code(frame: gpd.GeoDataFrame) -> pd.Series:
    # PrecinctFI is the statewide locality+precinct identifier.  Its final
    # three digits are stable even when Precinct_1 is descriptive text such as
    # Fredericksburg's "PRECINCT 1 - DISTRICT THREE".
    return text_series(frame, "PrecinctFI").str[-3:].map(normalize_code)


def load_locality(zip_path: Path) -> gpd.GeoDataFrame:
    member = shapefile_member(zip_path)
    frame = gpd.read_file(f"zip://{zip_path.resolve().as_posix()}!{member}")
    if frame.crs is None:
        raise RuntimeError(f"Missing CRS in {zip_path}")
    frame = frame.to_crs(4326)

    locality = text_series(frame, "LocalityNa").str.upper()
    locality_fips = text_series(frame, "LocalityFI").str.zfill(3)
    code = precinct_code(frame)
    name = text_series(frame, "PrecinctNa").str.upper()
    display = text_series(frame, "Precinct_1").str.upper()
    display = display.where(display.ne(""), code + " - " + name)

    output = gpd.GeoDataFrame(
        {
            "countyfp20": locality_fips,
            "district_raw": text_series(frame, "PrecinctFI"),
            "county_nam": locality,
            "county_norm": locality,
            "prec_id": code,
            "precinct_name": display,
            "precinct_norm": locality + " - " + code,
            "precinct_label": name,
            "polling_location": text_series(frame, "PollingLoc"),
            "source_geoid": text_series(frame, "GEOID"),
            "source_last_edited": text_series(frame, "last_edi_3"),
            "source_package": zip_path.name,
        },
        geometry=frame.geometry,
        crs=frame.crs,
    )
    return output


def build_current_layer(cache_dir: Path) -> gpd.GeoDataFrame:
    frames: list[gpd.GeoDataFrame] = []
    cached_paths = sorted(cache_dir.glob("*.zip"))
    urls = [] if len(cached_paths) == 133 else official_zip_urls()
    packages = (
        [(None, path) for path in cached_paths]
        if len(cached_paths) == 133
        else [
            (url, cache_dir / Path(urllib.parse.urlparse(url).path).name)
            for url in urls
        ]
    )
    for number, (url, zip_path) in enumerate(packages, start=1):
        if not zip_path.exists() and url:
            download(url, zip_path)
        try:
            frame = load_locality(zip_path)
        except (zipfile.BadZipFile, RuntimeError, ValueError):
            if not url:
                raise
            download(url, zip_path)
            frame = load_locality(zip_path)
        frames.append(frame)
        print(f"[{number:3d}/133] {zip_path.name}: {len(frame)} precincts")

    current = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)
    current.geometry = current.geometry.make_valid()

    # A few localities publish multipart voting precincts as separate records
    # with the same PrecinctFI.  Dissolve those records into one map feature.
    duplicate_mask = current.duplicated(["county_norm", "prec_id"], keep=False)
    if duplicate_mask.any():
        duplicate_labels = (
            current.loc[duplicate_mask]
            .groupby(["county_norm", "prec_id"])["precinct_label"]
            .agg(lambda values: " / ".join(dict.fromkeys(value for value in values if value)))
        )
        current = current.dissolve(
            by=["county_norm", "prec_id"], as_index=False, aggfunc="first"
        )
        for key, label in duplicate_labels.items():
            mask = (current["county_norm"] == key[0]) & (current["prec_id"] == key[1])
            current.loc[mask, "precinct_label"] = label
            current.loc[mask, "precinct_name"] = f"{key[1]} - {label}"
    current.geometry = current.geometry.make_valid()
    current.insert(0, "id", range(1, len(current) + 1))
    current["source"] = "Virginia Department of Elections locality GIS ZIP packages"
    return current


def validate_current(current: gpd.GeoDataFrame) -> dict[str, object]:
    duplicate_mask = current.duplicated(["county_norm", "prec_id"], keep=False)
    invalid_mask = ~current.geometry.is_valid
    empty_mask = current.geometry.is_empty | current.geometry.isna()
    localities = current["county_norm"].nunique()
    summary = {
        "features": len(current),
        "localities": int(localities),
        "duplicate_keys": int(duplicate_mask.sum()),
        "invalid_geometries": int(invalid_mask.sum()),
        "empty_geometries": int(empty_mask.sum()),
        "bounds": [round(float(value), 6) for value in current.total_bounds],
        "source_page": GIS_PAGE,
    }
    if localities != 133 or empty_mask.any():
        raise RuntimeError(f"Current layer failed validation: {summary}")
    return summary


def build_spatial_bridge(
    legacy_path: Path, current: gpd.GeoDataFrame, output_path: Path
) -> dict[str, int]:
    legacy = gpd.read_file(legacy_path).to_crs(4326)
    legacy = legacy.reset_index(drop=True)
    current = current.reset_index(drop=True)

    current_keys = {
        (row.county_norm, str(row.prec_id)): index
        for index, row in current[["county_norm", "prec_id"]].iterrows()
    }
    current_by_locality = {
        locality: group for locality, group in current.groupby("county_norm", sort=False)
    }
    rows: list[dict[str, object]] = []

    for legacy_index, old in legacy.iterrows():
        locality = str(old.get("county_norm", "")).upper()
        old_code = normalize_code(old.get("prec_id", ""))
        exact_index = current_keys.get((locality, old_code))
        method = "exact_key"
        overlap = 1.0

        if exact_index is None:
            candidates = current_by_locality.get(locality)
            if candidates is None or candidates.empty or old.geometry is None or old.geometry.is_empty:
                exact_index = None
                method = "unmatched"
                overlap = 0.0
            else:
                old_equal_area = gpd.GeoSeries([old.geometry], crs=4326).to_crs(5070).iloc[0]
                candidates_equal_area = candidates.to_crs(5070)
                intersections = candidates_equal_area.geometry.intersection(old_equal_area).area
                best_position = int(intersections.to_numpy().argmax())
                best_area = float(intersections.iloc[best_position])
                old_area = float(old_equal_area.area)
                if best_area <= 0 or old_area <= 0:
                    exact_index = None
                    method = "unmatched"
                    overlap = 0.0
                else:
                    exact_index = candidates.index[best_position]
                    method = "largest_overlap"
                    overlap = best_area / old_area

        new = current.loc[exact_index] if exact_index is not None else None
        rows.append(
            {
                "legacy_id": old.get("id", legacy_index + 1),
                "locality": locality,
                "legacy_prec_id": old_code,
                "legacy_precinct_name": old.get("precinct_name", ""),
                "current_prec_id": "" if new is None else new["prec_id"],
                "current_precinct_name": "" if new is None else new["precinct_name"],
                "match_method": method,
                "legacy_area_overlap": round(overlap, 6),
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {
        str(method): int(count)
        for method, count in pd.Series(
            [row["match_method"] for row in rows]
        ).value_counts().items()
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default="Data/elect_precinct_zips")
    parser.add_argument("--output", default="Data/va_precincts_current.geojson")
    parser.add_argument("--legacy", default="Data/va_precincts.geojson")
    parser.add_argument(
        "--bridge-output", default="Data/precinct_geometry_version_crosswalk.csv"
    )
    parser.add_argument(
        "--summary-output", default="Data/va_precincts_current_summary.json"
    )
    parser.add_argument(
        "--simplify",
        type=float,
        default=0.00001,
        help="Output simplification tolerance in degrees (default: 0.00001, about 1 m).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    current = build_current_layer(Path(args.cache_dir))
    summary = validate_current(current)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    web_current = current.copy()
    if args.simplify > 0:
        web_current.geometry = web_current.geometry.simplify(
            args.simplify, preserve_topology=True
        )
    web_current.geometry = web_current.geometry.map(
        lambda geometry: set_precision(geometry, 0.000001)
    )
    web_current.to_file(output_path, driver="GeoJSON")

    bridge_counts = build_spatial_bridge(
        Path(args.legacy), current, Path(args.bridge_output)
    )
    summary["legacy_bridge_methods"] = bridge_counts
    Path(args.summary_output).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
