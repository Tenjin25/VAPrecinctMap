#!/usr/bin/env python3
"""Download and merge Virginia's Census 2000 VTD TIGER/Line shapefiles."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

try:
    import geopandas as gpd
    import pandas as pd
    from shapely import set_precision
except ImportError as exc:
    raise SystemExit("Missing dependency: geopandas (including pandas and shapely).") from exc


BASE_URL = "https://www2.census.gov/geo/tiger/TIGER2008/51_VIRGINIA/"
LOCALITY_DIR_RE = re.compile(r"""href=["'](51\d{3}_[^"'/?#]+/)["']""", re.IGNORECASE)


def fetch_bytes(url: str, attempts: int = 4) -> bytes:
    error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "VAPrecinctMap/1.0"}
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except Exception as exc:  # retry Census archive timeouts and resets
            error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Failed to download {url}: {error}")


def locality_packages(index_file: Path | None = None) -> list[tuple[str, str, str]]:
    html = (
        index_file.read_text(encoding="utf-8", errors="replace")
        if index_file
        else fetch_bytes(BASE_URL).decode("utf-8", errors="replace")
    )
    directories = sorted(set(LOCALITY_DIR_RE.findall(html)))
    if len(directories) < 133:
        raise RuntimeError(
            f"Expected at least 133 Virginia locality directories; found {len(directories)}"
        )
    packages: list[tuple[str, str, str]] = []
    for directory in directories:
        fips = directory[:5]
        filename = f"tl_2008_{fips}_vtd00.zip"
        locality = directory.rstrip("/").split("_", 1)[1].replace("_", " ").upper()
        packages.append(
            (urllib.parse.urljoin(BASE_URL, directory + filename), filename, locality)
        )
    return packages


def download_package(url: str, destination: Path) -> Path:
    if destination.exists():
        try:
            with zipfile.ZipFile(destination) as archive:
                if archive.testzip() is None:
                    return destination
        except zipfile.BadZipFile:
            pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".zip.part")
    curl = shutil.which("curl") or shutil.which("curl.exe")
    fips_match = re.search(r"tl_2008_(51\d{3})_vtd00\.zip$", destination.name)
    candidates = [url]
    if fips_match:
        fips = fips_match.group(1)
        candidates.append(
            "https://www2.census.gov/geo/tiger/TIGER2010/VTD/2000/"
            f"tl_2010_{fips}_vtd00.zip"
        )

    errors: list[str] = []
    for candidate in candidates:
        try:
            if curl:
                subprocess.run(
                    [
                        curl,
                        "--fail",
                        "--location",
                        "--silent",
                        "--show-error",
                        "--retry",
                        "2",
                        "--retry-all-errors",
                        "--retry-delay",
                        "2",
                        "--connect-timeout",
                        "15",
                        "--max-time",
                        "60",
                        "--output",
                        str(temporary),
                        candidate,
                    ],
                    check=True,
                )
            else:
                temporary.write_bytes(fetch_bytes(candidate))
            with zipfile.ZipFile(temporary) as archive:
                bad_member = archive.testzip()
                if bad_member:
                    raise RuntimeError(f"Corrupt member {bad_member}")
            temporary.replace(destination)
            return destination
        except (OSError, RuntimeError, subprocess.CalledProcessError, zipfile.BadZipFile) as exc:
            errors.append(f"{candidate}: {exc}")
    raise RuntimeError("All Census download sources failed:\n" + "\n".join(errors))


def shapefile_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".shp")]
    if len(members) != 1:
        raise RuntimeError(f"Expected one shapefile in {zip_path}; found {members}")
    return members[0]


def text(frame: gpd.GeoDataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series("", index=frame.index, dtype="string")
    return frame[column].fillna("").astype(str).str.strip()


def normalize_code(value: object) -> str:
    value_text = str(value or "").strip().upper()
    return str(int(value_text)) if value_text.isdigit() else value_text


def load_package(zip_path: Path, locality_name: str) -> gpd.GeoDataFrame:
    member = shapefile_member(zip_path)
    frame = gpd.read_file(f"zip://{zip_path.resolve().as_posix()}!{member}")
    if frame.crs is None:
        frame = frame.set_crs(4269, allow_override=True)
    frame = frame.to_crs(4326)
    county = text(frame, "COUNTYFP00").str.zfill(3)
    vtd = text(frame, "VTDST00")
    code = vtd.map(normalize_code)
    name = text(frame, "NAME00")
    return gpd.GeoDataFrame(
        {
            "statefp00": text(frame, "STATEFP00").str.zfill(2),
            "countyfp00": county,
            "county_nam": locality_name,
            "county_norm": locality_name,
            "vtdst00": vtd,
            "vtdidfp00": text(frame, "VTDIDFP00"),
            "vtdi00": text(frame, "VTDI00"),
            "name00": name,
            "namelsad00": text(frame, "NAMELSAD00"),
            "prec_id": code,
            "precinct_name": code + " - " + name.str.upper(),
            "precinct_norm": locality_name + " - " + code,
            "source_package": zip_path.name,
        },
        geometry=frame.geometry,
        crs=4326,
    )


def build_layer(
    cache_dir: Path, workers: int, index_file: Path | None = None
) -> gpd.GeoDataFrame:
    packages = locality_packages(index_file)
    cache_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_package, url, cache_dir / filename): filename
            for url, filename, _ in packages
        }
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            future.result()
            completed += 1
            print(f"Downloaded {completed}/{len(packages)}: {futures[future]}", flush=True)

    frames = []
    for number, (_, filename, locality_name) in enumerate(packages, start=1):
        frame = load_package(cache_dir / filename, locality_name)
        frames.append(frame)
        print(f"Loaded {number}/{len(packages)}: {filename} ({len(frame)} VTDs)", flush=True)

    merged = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=4326)
    merged.geometry = merged.geometry.make_valid()
    if merged.duplicated(["countyfp00", "vtdst00"]).any():
        merged = merged.dissolve(
            by=["countyfp00", "vtdst00"], as_index=False, aggfunc="first"
        )
    merged.geometry = merged.geometry.make_valid()
    merged = merged.sort_values(["countyfp00", "vtdst00"], kind="stable").reset_index(
        drop=True
    )
    merged.insert(0, "id", range(1, len(merged) + 1))
    merged["source"] = "U.S. Census Bureau TIGER/Line 2008 Census 2000 VTD archive"
    return merged


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default="Data/vtd00_zips")
    parser.add_argument("--output", default="Data/tl_2008_51_vtd00.geojson")
    parser.add_argument("--summary-output", default="Data/tl_2008_51_vtd00_summary.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--simplify", type=float, default=0.00001)
    parser.add_argument(
        "--index-file",
        help="Optional saved HTML copy of the Census Virginia TIGER2008 directory index.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    layer = build_layer(
        Path(args.cache_dir),
        max(1, args.workers),
        Path(args.index_file) if args.index_file else None,
    )
    duplicate_count = int(layer.duplicated(["countyfp00", "vtdst00"]).sum())
    invalid_count = int((~layer.geometry.is_valid).sum())
    empty_count = int((layer.geometry.is_empty | layer.geometry.isna()).sum())
    summary = {
        "features": len(layer),
        "localities": int(layer["countyfp00"].nunique()),
        "duplicate_keys": duplicate_count,
        "invalid_geometries": invalid_count,
        "empty_geometries": empty_count,
        "bounds": [round(float(value), 6) for value in layer.total_bounds],
        "source": BASE_URL,
    }
    if summary["localities"] < 133 or duplicate_count or invalid_count or empty_count:
        raise RuntimeError(f"VTD00 layer failed validation: {summary}")

    web_layer = layer.copy()
    if args.simplify > 0:
        web_layer.geometry = web_layer.geometry.simplify(
            args.simplify, preserve_topology=True
        )
    web_layer.geometry = web_layer.geometry.map(
        lambda geometry: set_precision(geometry, 0.000001)
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    web_layer.to_file(output, driver="GeoJSON")
    Path(args.summary_output).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
