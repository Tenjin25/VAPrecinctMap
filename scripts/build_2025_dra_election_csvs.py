#!/usr/bin/env python3
"""Create DRA election imports from the 2025 Virginia precinct results.

The source results use current precincts, while Dave's Redistricting requires
2020 Census VTD GEOIDs.  The project crosswalk expresses each VTD20's share
among current precincts.  For the reverse conversion used here, incoming
shares are normalized within each current precinct.  This preserves every
contest's statewide vote totals, but allocations for post-2020 precinct
changes are estimates.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import shapefile

from build_precinct_result_geometry_crosswalk import (
    build_block_transition_weights,
    locality,
    precinct_code,
    read_block_population,
    read_vtd20,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "Data/openelections/2025/20251104__va__general__precinct__multi_office__9b503992_5765_47e2_989d_5ed01f31621e.csv"
DEFAULT_VTDS = ROOT / "Data/tl_2020_51_vtd20.zip"
DEFAULT_CURRENT = ROOT / "Data/va_precincts_current.geojson"
DEFAULT_CROSSWALK = ROOT / "Data/precinct_result_geometry_crosswalk.json"
DEFAULT_TABBLOCKS = ROOT / "Data/tl_2020_51_tabblock20.zip"
DEFAULT_ASSIGNMENTS = ROOT / "Data/BlockAssign_ST51_VA.zip"
DEFAULT_PL94 = ROOT / "Data/va2020.pl.zip"
DEFAULT_BLOCK_POPULATION = ROOT / "Data/va_2020_block_population.csv"
DEFAULT_OUTPUT = ROOT / "Data/dra/2025"


CONTESTS = {
    "governor": lambda office: office == "Governor",
    "lieutenant_governor": lambda office: office == "Lieutenant Governor",
    "attorney_general": lambda office: office == "Attorney General",
    "house_of_delegates": lambda office: office.startswith("Member, House of Delegates"),
}


def clean_precinct_id(value: str) -> str:
    value = value.strip().upper()
    match = re.match(r"^(\d+)", value)
    if match:
        return str(int(match.group(1)))
    return re.sub(r"\s+", " ", value)


def result_key(county: str, precinct: str) -> str:
    return f"{locality(county)} - {precinct_code(precinct)}"


def load_vtds(vtd_zip: Path, current_geojson: Path):
    current = json.loads(current_geojson.read_text(encoding="utf-8"))
    county_names = {}
    for feature in current["features"]:
        props = feature["properties"]
        county_names[str(props["countyfp20"])] = props["county_norm"].strip().upper()

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(vtd_zip) as archive:
            archive.extractall(temp_dir)
        shp_path = next(Path(temp_dir).glob("*.shp"))
        reader = shapefile.Reader(str(shp_path))
        fields = [field[0] for field in reader.fields[1:]]
        county_idx = fields.index("COUNTYFP20")
        vtd_idx = fields.index("VTDST20")
        geoid_idx = fields.index("GEOID20")
        vtds = []
        for record in reader.records():
            countyfp = str(record[county_idx])
            locality = county_names[countyfp]
            precinct_id = clean_precinct_id(str(record[vtd_idx]))
            vtds.append((f"{locality} - {precinct_id}", str(record[geoid_idx])))
        reader.close()
    return sorted(vtds, key=lambda item: item[1])


def load_current_to_vtd_by_blocks(
    vtd_zip: Path,
    current_geojson: Path,
    tabblock_zip: Path,
    assignments_zip: Path,
    pl94_zip: Path,
    population_cache: Path,
    vtds,
):
    legacy = read_vtd20(vtd_zip, current_geojson).to_crs(5070)
    current = gpd.read_file(current_geojson).to_crs(5070)
    population = read_block_population(pl94_zip, population_cache)
    transitions, block_stats = build_block_transition_weights(
        tabblock_zip,
        assignments_zip,
        population,
        legacy,
        current,
    )
    key_to_geoid = dict(vtds)
    by_target = defaultdict(list)
    for source, rows in transitions.items():
        geoid = key_to_geoid.get(source)
        if not geoid:
            continue
        for row in rows:
            by_target[str(row["target"])].append((geoid, row))

    weighted = {}
    for target, destinations in by_target.items():
        for column in (
            "voting_age_population_2020",
            "total_population_2020",
            "block_land_area_m2",
        ):
            if sum(float(row[column]) for _, row in destinations) > 0:
                weighted[target] = [
                    (geoid, float(row[column])) for geoid, row in destinations
                ]
                break
    return weighted, block_stats


def load_contest_votes(results_path: Path, predicate):
    votes = defaultdict(lambda: defaultdict(int))
    with results_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not predicate(row["office"]):
                continue
            key = result_key(row["county"], row["precinct"])
            party = row["party"].strip().upper()
            bucket = "D" if party == "DEM" else "R" if party == "REP" else "Other"
            votes[key][bucket] += int(row["votes"] or 0)
    return votes


def allocate_integer(total: int, weighted_geoids):
    if not weighted_geoids:
        return {}
    weight_sum = sum(weight for _, weight in weighted_geoids)
    exact = [(geoid, total * weight / weight_sum) for geoid, weight in weighted_geoids]
    allocated = {geoid: math.floor(value) for geoid, value in exact}
    remainder = total - sum(allocated.values())
    order = sorted(exact, key=lambda item: (-(item[1] - math.floor(item[1])), item[0]))
    for geoid, _ in order[:remainder]:
        allocated[geoid] += 1
    return allocated


def convert_contest(vtds, current_to_vtd, current_votes):
    output = {geoid: {"D": 0, "R": 0, "Other": 0} for _, geoid in vtds}
    unresolved = []
    for current_key, party_votes in current_votes.items():
        destinations = current_to_vtd.get(current_key)
        if not destinations:
            unresolved.append((current_key, sum(party_votes.values())))
            continue
        for bucket in ("D", "R", "Other"):
            for geoid, value in allocate_integer(party_votes[bucket], destinations).items():
                output[geoid][bucket] += value

    return output, sorted(unresolved)


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["GEOID20", "Tot", "D", "R"])
        writer.writeheader()
        for geoid in sorted(rows):
            values = rows[geoid]
            writer.writerow({
                "GEOID20": geoid,
                "Tot": values["D"] + values["R"] + values["Other"],
                "D": values["D"],
                "R": values["R"],
            })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--vtds", type=Path, default=DEFAULT_VTDS)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    parser.add_argument("--tabblocks", type=Path, default=DEFAULT_TABBLOCKS)
    parser.add_argument("--assignments", type=Path, default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--pl94", type=Path, default=DEFAULT_PL94)
    parser.add_argument("--block-population", type=Path, default=DEFAULT_BLOCK_POPULATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    vtds = load_vtds(args.vtds, args.current)
    current_to_vtd, block_stats = load_current_to_vtd_by_blocks(
        args.vtds,
        args.current,
        args.tabblocks,
        args.assignments,
        args.pl94,
        args.block_population,
        vtds,
    )
    report = {
        "method": "Reverse-normalized 2025 current-precinct to 2020 Census VTD allocation",
        "warning": "Post-2020 precinct-change allocations are estimates.",
        "vtd20_rows": len(vtds),
        "block_crosswalk_stats": block_stats,
        "contests": {},
    }

    for slug, predicate in CONTESTS.items():
        current_votes = load_contest_votes(args.results, predicate)
        converted, unresolved = convert_contest(vtds, current_to_vtd, current_votes)
        output_path = args.output / f"2025_va_{slug}_dra_vtd20.csv"
        write_csv(output_path, converted)
        report["contests"][slug] = {
            "output": str(output_path.relative_to(ROOT)),
            "source_precincts": len(current_votes),
            "unresolved_precincts": [
                {"precinct": key, "votes": votes} for key, votes in unresolved
            ],
            "source_totals": {
                bucket: sum(values[bucket] for values in current_votes.values())
                for bucket in ("D", "R", "Other")
            },
            "output_totals": {
                bucket: sum(values[bucket] for values in converted.values())
                for bucket in ("D", "R", "Other")
            },
        }

    report_path = args.output / "2025_va_dra_conversion_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
