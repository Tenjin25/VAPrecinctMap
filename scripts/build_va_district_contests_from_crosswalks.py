#!/usr/bin/env python3
"""
Build district-contest layers for VA from OpenElections precinct CSVs + Census block crosswalks.

Outputs:
- Data/district_contests/<scope>_<contest_type>_<year>.json
- Data/district_contests/manifest.json
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

try:
    import geopandas as gpd
except ImportError as exc:
    raise SystemExit("Missing dependency: geopandas. Install it in your active environment first.") from exc


SCOPES = ("congressional", "state_house", "state_senate")
STATEWIDE_CONTESTS = ("president", "us_senate", "governor", "lieutenant_governor", "attorney_general")
DISTRICT_CONTESTS = ("state_house", "state_senate")
ALL_CONTESTS = set(STATEWIDE_CONTESTS) | set(DISTRICT_CONTESTS)


def find_member(zip_path: Path, suffix: str) -> str:
    with zipfile.ZipFile(zip_path, "r") as zf:
        matches = [m for m in zf.namelist() if m.endswith(suffix)]
    if not matches:
        raise FileNotFoundError(f"No zip member ending with {suffix!r} in {zip_path}")
    return matches[0]


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
    if " - " in p:
        token = p.split(" - ", 1)[0].strip()
    else:
        token = re.split(r"[_\s]+", p, maxsplit=1)[0].strip()
    return normalize_precinct_code(token)


def normalize_district_id(raw: str) -> str:
    s = (raw or "").strip().upper()
    if not s:
        return ""
    s = re.sub(r"[^A-Z0-9\-]", "", s)
    if re.fullmatch(r"\d+", s):
        return str(int(s))
    return s


def normalize_party_bucket(party: str) -> str:
    p = (party or "").strip().upper()
    if p.startswith("DEM"):
        return "dem"
    if p.startswith("REP"):
        return "rep"
    return "other"


def normalize_office_text(office: str) -> str:
    return re.sub(r"[^A-Z0-9 ]+", "", (office or "").upper()).strip()


def classify_office(office: str, year: int) -> tuple[str, str, str | None] | None:
    norm = normalize_office_text(office)
    raw_u = (office or "").upper()
    if norm == "PRESIDENT":
        return ("statewide", "president", None)
    if norm in {"US SENATE", "U S SENATE"}:
        return ("statewide", "us_senate", None)
    if norm == "GOVERNOR":
        return ("statewide", "governor", None)
    if norm == "LIEUTENANT GOVERNOR":
        return ("statewide", "lieutenant_governor", None)
    if norm == "ATTORNEY GENERAL":
        return ("statewide", "attorney_general", None)

    m_house = re.search(r"MEMBER,\s*HOUSE OF DELEGATES\s*\((\d+)(?:ST|ND|RD|TH)\s+DISTRICT\)", raw_u)
    if m_house and year in {2023, 2025}:
        return ("district", "state_house", str(int(m_house.group(1))))

    m_sen = re.search(r"MEMBER,\s*SENATE OF VIRGINIA\s*\((\d+)(?:ST|ND|RD|TH)\s+DISTRICT\)", raw_u)
    if m_sen and year in {2023, 2025}:
        return ("district", "state_senate", str(int(m_sen.group(1))))

    return None


def is_non_geographic_precinct(precinct_raw: str) -> bool:
    p = (precinct_raw or "").upper()
    tokens = (
        "ABSENTEE",
        "PROVISIONAL",
        "EARLY",
        "MAIL",
        "CURBSIDE",
        "ONE STOP",
        "OS ",
        "OS-",
    )
    return any(t in p for t in tokens)


def normalize_locality_key(raw: str) -> str:
    s = re.sub(r"\s+", " ", (raw or "").strip()).upper()
    if not s:
        return ""
    m_city_of = re.match(r"^CITY OF\s+(.+)$", s)
    if m_city_of:
        return f"{m_city_of.group(1).strip()} CITY"
    return s


def canonical_locality_from_census(name20: str, namelsad20: str) -> str:
    value = normalize_locality_key(namelsad20) or normalize_locality_key(name20)
    if not value:
        return ""
    m = re.match(r"^(.+?)\s+(COUNTY|CITY|TOWN)$", value)
    if m:
        return f"{m.group(1).strip()} {m.group(2)}"
    return value


def locality_aliases(canonical: str) -> set[str]:
    aliases = {normalize_locality_key(canonical)}
    m = re.match(r"^(.+?)\s+(COUNTY|CITY|TOWN)$", normalize_locality_key(canonical))
    if m:
        base = m.group(1).strip()
        suffix = m.group(2)
        aliases.add(base)
        aliases.add(f"{base} {suffix}")
        if suffix == "CITY":
            aliases.add(f"CITY OF {base}")
    return {a for a in aliases if a}


def build_locality_alias_map(county_geojson: Path) -> dict[str, str]:
    counties = gpd.read_file(county_geojson)
    alias_to_targets: dict[str, set[str]] = {}
    for _, row in counties.iterrows():
        canonical = canonical_locality_from_census(
            str(row.get("NAME20", "")),
            str(row.get("NAMELSAD20", "")),
        )
        if not canonical:
            continue
        for alias in locality_aliases(canonical):
            alias_to_targets.setdefault(alias, set()).add(canonical)
    return {
        alias: next(iter(targets))
        for alias, targets in alias_to_targets.items()
        if len(targets) == 1
    }


def canonicalize_locality(raw: str, locality_alias_map: dict[str, str]) -> str:
    key = normalize_locality_key(raw)
    if not key:
        return ""
    return locality_alias_map.get(key, key)


def load_county_name_map(county_geojson: Path) -> dict[str, str]:
    counties = gpd.read_file(county_geojson)
    out: dict[str, str] = {}
    for _, row in counties.iterrows():
        county_fp = str(row.get("COUNTYFP20", "")).strip().zfill(3)
        county_name = canonical_locality_from_census(
            str(row.get("NAME20", "")),
            str(row.get("NAMELSAD20", "")),
        )
        if county_fp and county_name:
            out[county_fp] = county_name
    return out


def load_block_weights(tabblock_zip: Path) -> pd.DataFrame:
    shp = find_member(tabblock_zip, ".shp")
    uri = f"zip://{tabblock_zip.resolve().as_posix()}!{shp}"
    blocks = gpd.read_file(uri, ignore_geometry=True)
    cols = set(blocks.columns)
    if {"GEOID20", "ALAND20", "AWATER20"}.issubset(cols):
        geoid_col, aland_col, awater_col = "GEOID20", "ALAND20", "AWATER20"
    elif {"GEOID10", "ALAND10", "AWATER10"}.issubset(cols):
        geoid_col, aland_col, awater_col = "GEOID10", "ALAND10", "AWATER10"
    elif {"GEOID", "ALAND", "AWATER"}.issubset(cols):
        geoid_col, aland_col, awater_col = "GEOID", "ALAND", "AWATER"
    else:
        raise ValueError(
            "Expected tabblock columns for either 2020 (GEOID20/ALAND20/AWATER20) "
            "or 2010-era (GEOID10/ALAND10/AWATER10 or GEOID/ALAND/AWATER)."
        )

    w = blocks[[geoid_col, aland_col, awater_col]].copy()
    w["BLOCKID"] = w[geoid_col].astype(str).str.strip()
    w["weight"] = pd.to_numeric(w[aland_col], errors="coerce").fillna(0) + pd.to_numeric(w[awater_col], errors="coerce").fillna(0)
    w["weight"] = w["weight"].where(w["weight"] > 0, 1.0)
    return w[["BLOCKID", "weight"]]


def load_assign_df(assign_zip: Path, member_name: str, keep_county: bool) -> pd.DataFrame:
    with zipfile.ZipFile(assign_zip, "r") as zf:
        with zf.open(member_name) as f:
            df = pd.read_csv(f, sep="|", dtype=str)
    if "BLOCKID" not in df.columns or "DISTRICT" not in df.columns:
        raise ValueError(f"Expected BLOCKID and DISTRICT in {member_name}")
    df["BLOCKID"] = df["BLOCKID"].astype(str).str.strip()
    df["DISTRICT"] = df["DISTRICT"].astype(str).str.strip()
    if keep_county:
        if "COUNTYFP" not in df.columns:
            raise ValueError(f"Expected COUNTYFP in {member_name}")
        df["COUNTYFP"] = df["COUNTYFP"].astype(str).str.strip().str.zfill(3)
        return df[["BLOCKID", "COUNTYFP", "DISTRICT"]]
    return df[["BLOCKID", "DISTRICT"]]


def build_scope_mapping(
    weights: pd.DataFrame,
    vtd_df: pd.DataFrame,
    target_df: pd.DataFrame,
    county_name_by_fp: dict[str, str],
) -> dict[str, dict]:
    # Join block -> VTD and block -> target district, then weight by block area.
    merged = vtd_df.merge(target_df, on="BLOCKID", suffixes=("_VTD", "_DST"))
    merged = merged.merge(weights, on="BLOCKID", how="left")
    merged["weight"] = merged["weight"].fillna(1.0)

    grouped = (
        merged.groupby(["COUNTYFP", "DISTRICT_VTD", "DISTRICT_DST"], as_index=False)["weight"]
        .sum()
    )
    grouped["total_weight"] = grouped.groupby(["COUNTYFP", "DISTRICT_VTD"])["weight"].transform("sum")
    grouped["share"] = grouped["weight"] / grouped["total_weight"]

    mapping: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    county_weights: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for _, row in grouped.iterrows():
        county_fp = str(row["COUNTYFP"]).zfill(3)
        county_name = county_name_by_fp.get(county_fp, county_fp).upper()
        prec_code = normalize_precinct_code(str(row["DISTRICT_VTD"]))
        district_id = normalize_district_id(str(row["DISTRICT_DST"]))
        share = float(row["share"])
        if not county_name or not prec_code or not district_id or share <= 0:
            continue
        mapping[(county_name, prec_code)].append((district_id, share))

    # Normalize any floating drift so each precinct sums to exactly 1.
    for key, vals in list(mapping.items()):
        s = sum(v for _, v in vals)
        if s <= 0:
            del mapping[key]
            continue
        mapping[key] = [(d, v / s) for d, v in vals]

    county_grouped = (
        merged.groupby(["COUNTYFP", "DISTRICT_DST"], as_index=False)["weight"]
        .sum()
    )
    county_grouped["county_total_weight"] = county_grouped.groupby(["COUNTYFP"])["weight"].transform("sum")
    county_grouped["share"] = county_grouped["weight"] / county_grouped["county_total_weight"]

    for _, row in county_grouped.iterrows():
        county_fp = str(row["COUNTYFP"]).zfill(3)
        county_name = county_name_by_fp.get(county_fp, county_fp).upper()
        district_id = normalize_district_id(str(row["DISTRICT_DST"]))
        share = float(row["share"])
        if not county_name or not district_id or share <= 0:
            continue
        county_weights[county_name].append((district_id, share))

    for county, vals in list(county_weights.items()):
        s = sum(v for _, v in vals)
        if s <= 0:
            del county_weights[county]
            continue
        county_weights[county] = [(d, v / s) for d, v in vals]

    return {
        "precinct_map": mapping,
        "county_weights": county_weights,
    }


def build_all_scope_mappings(
    assign_zip: Path,
    tabblock_zip: Path,
    county_geojson: Path,
) -> dict[str, dict]:
    county_names = load_county_name_map(county_geojson)
    weights = load_block_weights(tabblock_zip)

    vtd = load_assign_df(assign_zip, "BlockAssign_ST51_VA_VTD.txt", keep_county=True)
    cd = load_assign_df(assign_zip, "BlockAssign_ST51_VA_CD.txt", keep_county=False)
    sldl = load_assign_df(assign_zip, "BlockAssign_ST51_VA_SLDL.txt", keep_county=False)
    sldu = load_assign_df(assign_zip, "BlockAssign_ST51_VA_SLDU.txt", keep_county=False)

    return {
        "congressional": build_scope_mapping(weights, vtd, cd, county_names),
        "state_house": build_scope_mapping(weights, vtd, sldl, county_names),
        "state_senate": build_scope_mapping(weights, vtd, sldu, county_names),
    }


def category_color_for_margin(margin_pct_abs: float, winner: str) -> str:
    if margin_pct_abs >= 40:
        return "#67000d" if winner == "R" else "#08306b"
    if margin_pct_abs >= 30:
        return "#a50f15" if winner == "R" else "#08519c"
    if margin_pct_abs >= 20:
        return "#cb181d" if winner == "R" else "#3182bd"
    if margin_pct_abs >= 10:
        return "#ef3b2c" if winner == "R" else "#6baed6"
    if margin_pct_abs >= 5.5:
        return "#fb6a4a" if winner == "R" else "#9ecae1"
    if margin_pct_abs >= 1.0:
        return "#fcae91" if winner == "R" else "#c6dbef"
    if margin_pct_abs >= 0.5:
        return "#fee8c8" if winner == "R" else "#e1f5fe"
    return "#f7f7f7"


def parse_year_from_filename(path: Path) -> int:
    m = re.match(r"(\d{4})\d{4}__", path.name)
    if m:
        return int(m.group(1))
    m2 = re.match(r"(\d{4})", path.name)
    if m2:
        return int(m2.group(1))
    raise ValueError(f"Could not parse year from filename: {path.name}")


def build_district_contests(
    openelections_root: Path,
    scope_mappings: dict[str, dict],
    locality_alias_map: dict[str, str],
) -> tuple[dict[tuple[str, str, int, str], dict], dict[tuple[str, str, int], dict], dict[tuple[str, str, int], dict]]:
    # district_key -> accum
    district_acc = defaultdict(
        lambda: {
            "dem": 0.0,
            "rep": 0.0,
            "other": 0.0,
            "dem_cands": Counter(),
            "rep_cands": Counter(),
        }
    )
    totals = defaultdict(lambda: {"dem": 0.0, "rep": 0.0, "other": 0.0})
    coverage = defaultdict(
        lambda: {
            "input_votes": 0.0,
            "direct_matched_votes": 0.0,
            "allocated_votes": 0.0,
            "matched_votes": 0.0,
        }
    )
    unmatched_by_county = defaultdict(
        lambda: {
            "dem": 0.0,
            "rep": 0.0,
            "other": 0.0,
            "dem_cands": Counter(),
            "rep_cands": Counter(),
        }
    )
    matched_county_district = defaultdict(lambda: defaultdict(float))

    for csv_path in sorted(openelections_root.rglob("*.csv")):
        year = parse_year_from_filename(csv_path)
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                office = row.get("office", "")
                classified = classify_office(office, year)
                if not classified:
                    continue

                kind, contest_type, office_district = classified
                if contest_type not in ALL_CONTESTS:
                    continue

                county = canonicalize_locality(row.get("county", ""), locality_alias_map)
                precinct = row.get("precinct", "")
                party_bucket = normalize_party_bucket(row.get("party", ""))
                candidate = (row.get("candidate") or "").strip()
                votes = float(row.get("votes") or 0)
                if not county or votes <= 0:
                    continue

                if kind == "statewide":
                    for scope in SCOPES:
                        cov_key = (scope, contest_type, year)
                        coverage[cov_key]["input_votes"] += votes
                        splits = None
                        if not is_non_geographic_precinct(precinct):
                            prec_code = extract_precinct_code(precinct)
                            if prec_code:
                                splits = scope_mappings[scope]["precinct_map"].get((county, prec_code))

                        if splits:
                            coverage[cov_key]["direct_matched_votes"] += votes
                            coverage[cov_key]["matched_votes"] += votes
                            county_scope_key = (scope, contest_type, year, county)
                            for district_id, share in splits:
                                amount = votes * share
                                k = (scope, contest_type, year, district_id)
                                district_acc[k][party_bucket] += amount
                                totals[(scope, contest_type, year)][party_bucket] += amount
                                matched_county_district[county_scope_key][district_id] += amount
                                if party_bucket == "dem" and candidate:
                                    district_acc[k]["dem_cands"][candidate] += amount
                                elif party_bucket == "rep" and candidate:
                                    district_acc[k]["rep_cands"][candidate] += amount
                        else:
                            u_key = (scope, contest_type, year, county)
                            unmatched_by_county[u_key][party_bucket] += votes
                            if party_bucket == "dem" and candidate:
                                unmatched_by_county[u_key]["dem_cands"][candidate] += votes
                            elif party_bucket == "rep" and candidate:
                                unmatched_by_county[u_key]["rep_cands"][candidate] += votes
                else:
                    if not office_district:
                        continue
                    scope = contest_type
                    district_id = normalize_district_id(office_district)
                    if not district_id:
                        continue
                    k = (scope, contest_type, year, district_id)
                    district_acc[k][party_bucket] += votes
                    totals[(scope, contest_type, year)][party_bucket] += votes
                    cov_key = (scope, contest_type, year)
                    coverage[cov_key]["input_votes"] += votes
                    coverage[cov_key]["direct_matched_votes"] += votes
                    coverage[cov_key]["matched_votes"] += votes
                    if party_bucket == "dem" and candidate:
                        district_acc[k]["dem_cands"][candidate] += votes
                    elif party_bucket == "rep" and candidate:
                        district_acc[k]["rep_cands"][candidate] += votes

    # Reallocate unmatched county votes by district share.
    for (scope, contest_type, year, county), node in unmatched_by_county.items():
        cov_key = (scope, contest_type, year)
        county_scope_key = (scope, contest_type, year, county)

        matched_dist = matched_county_district.get(county_scope_key, {})
        matched_sum = float(sum(matched_dist.values()))
        if matched_sum > 0:
            alloc_weights = [(d, v / matched_sum) for d, v in matched_dist.items() if v > 0]
        else:
            alloc_weights = scope_mappings[scope]["county_weights"].get(county, [])

        if not alloc_weights:
            continue

        to_allocate = float(node["dem"] + node["rep"] + node["other"])
        if to_allocate <= 0:
            continue

        coverage[cov_key]["allocated_votes"] += to_allocate
        coverage[cov_key]["matched_votes"] += to_allocate

        for bucket in ("dem", "rep", "other"):
            base_votes = float(node[bucket])
            if base_votes <= 0:
                continue
            for district_id, share in alloc_weights:
                amount = base_votes * share
                k = (scope, contest_type, year, district_id)
                district_acc[k][bucket] += amount
                totals[(scope, contest_type, year)][bucket] += amount

        for cand, cand_votes in node["dem_cands"].items():
            if cand_votes <= 0:
                continue
            for district_id, share in alloc_weights:
                k = (scope, contest_type, year, district_id)
                district_acc[k]["dem_cands"][cand] += cand_votes * share

        for cand, cand_votes in node["rep_cands"].items():
            if cand_votes <= 0:
                continue
            for district_id, share in alloc_weights:
                k = (scope, contest_type, year, district_id)
                district_acc[k]["rep_cands"][cand] += cand_votes * share

    return district_acc, totals, coverage


def district_sort_key(d: str) -> tuple[int, str]:
    if re.fullmatch(r"\d+", d or ""):
        return (0, str(int(d)))
    return (1, d or "")


def render_payload_for_group(
    scope: str,
    contest_type: str,
    year: int,
    district_acc: dict[tuple[str, str, int, str], dict],
    coverage_stats: dict[tuple[str, str, int], dict],
) -> tuple[dict, int]:
    keys = [k for k in district_acc.keys() if k[0] == scope and k[1] == contest_type and k[2] == year]
    keys = sorted(keys, key=lambda k: district_sort_key(k[3]))

    results = {}
    for _, _, _, district in keys:
        node = district_acc[(scope, contest_type, year, district)]
        dem = int(round(node["dem"]))
        rep = int(round(node["rep"]))
        other = int(round(node["other"]))
        total = dem + rep + other
        if total <= 0:
            continue
        signed_margin_pct = ((rep - dem) / total) * 100.0
        margin_pct_abs = abs(signed_margin_pct)
        if rep > dem:
            winner = "Republican"
            winner_short = "R"
        elif dem > rep:
            winner = "Democratic"
            winner_short = "D"
        else:
            winner = "Tie"
            winner_short = "T"

        dem_cand = node["dem_cands"].most_common(1)[0][0] if node["dem_cands"] else ""
        rep_cand = node["rep_cands"].most_common(1)[0][0] if node["rep_cands"] else ""
        color = category_color_for_margin(margin_pct_abs, "R" if winner_short in {"R", "T"} else "D")

        results[str(district)] = {
            "dem_votes": dem,
            "rep_votes": rep,
            "other_votes": other,
            "total_votes": total,
            "dem_candidate": dem_cand,
            "rep_candidate": rep_cand,
            "winner": winner,
            "margin": abs(rep - dem),
            "margin_pct": signed_margin_pct,
            "color": color,
        }

    cov = coverage_stats.get(
        (scope, contest_type, year),
        {"input_votes": 0.0, "matched_votes": 0.0, "direct_matched_votes": 0.0, "allocated_votes": 0.0},
    )
    input_votes = float(cov["input_votes"] or 0.0)
    matched_votes = float(cov["matched_votes"] or 0.0)
    direct_matched_votes = float(cov.get("direct_matched_votes", 0.0) or 0.0)
    allocated_votes = float(cov.get("allocated_votes", 0.0) or 0.0)
    match_pct = (matched_votes / input_votes * 100.0) if input_votes > 0 else 0.0
    direct_match_pct = (direct_matched_votes / input_votes * 100.0) if input_votes > 0 else 0.0

    payload = {
        "meta": {
            "scope": scope,
            "contest_type": contest_type,
            "year": year,
            "district_count": len(results),
            "input_votes": int(round(input_votes)),
            "matched_votes": int(round(matched_votes)),
            "direct_matched_votes": int(round(direct_matched_votes)),
            "allocated_votes": int(round(allocated_votes)),
            "match_coverage_pct": match_pct,
            "direct_match_coverage_pct": direct_match_pct,
        },
        "general": {
            "results": results,
        },
    }
    return payload, len(results)


def write_outputs(
    output_dir: Path,
    district_acc: dict[tuple[str, str, int, str], dict],
    totals: dict[tuple[str, str, int], dict],
    coverage: dict[tuple[str, str, int], dict],
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Remove previously generated json slices to avoid stale files lingering.
    for old in output_dir.glob("*.json"):
        if old.name == "manifest.json":
            continue
        old.unlink()

    groups = sorted({(k[0], k[1], k[2]) for k in district_acc.keys()}, key=lambda t: (SCOPES.index(t[0]), t[1], t[2]))
    manifest_entries = []

    for scope, contest_type, year in groups:
        payload, row_count = render_payload_for_group(scope, contest_type, year, district_acc, coverage)
        if row_count <= 0:
            continue

        filename = f"{scope}_{contest_type}_{year}.json"
        out_path = output_dir / filename
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        t = totals[(scope, contest_type, year)]
        dem_total = int(round(t["dem"]))
        rep_total = int(round(t["rep"]))
        manifest_entries.append(
            {
                "scope": scope,
                "contest_type": contest_type,
                "year": year,
                "file": filename,
                "rows": row_count,
                "dem_total": dem_total,
                "rep_total": rep_total,
                "major_party_contested": bool(dem_total > 0 and rep_total > 0),
            }
        )

    manifest = {"files": manifest_entries}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build VA district contest layers from CSVs + crosswalks.")
    parser.add_argument("--openelections-dir", default="Data/openelections")
    parser.add_argument("--assign-zip", default="Data/BlockAssign_ST51_VA.zip")
    parser.add_argument(
        "--tabblock-zip",
        default="Data/tl_2020_51_tabblock20.zip",
        help="Tabblock ZIP for weights (supports 2020 GEOID20 schema or 2010 GEOID10 schema).",
    )
    parser.add_argument("--county-geojson", default="Data/tl_2020_51_county20.geojson")
    parser.add_argument("--output-dir", default="Data/district_contests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    openelections_dir = Path(args.openelections_dir)
    assign_zip = Path(args.assign_zip)
    tabblock_zip = Path(args.tabblock_zip)
    county_geojson = Path(args.county_geojson)
    output_dir = Path(args.output_dir)

    for p in (openelections_dir, assign_zip, tabblock_zip, county_geojson):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    scope_maps = build_all_scope_mappings(assign_zip, tabblock_zip, county_geojson)
    locality_alias_map = build_locality_alias_map(county_geojson)
    district_acc, totals, coverage = build_district_contests(openelections_dir, scope_maps, locality_alias_map)
    manifest = write_outputs(output_dir, district_acc, totals, coverage)

    print(f"Wrote {len(manifest.get('files', []))} district contest slices to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
