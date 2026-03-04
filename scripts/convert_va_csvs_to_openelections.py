#!/usr/bin/env python3
"""
Convert Virginia election CSVs in ./Data to OpenElections-style precinct CSVs.

Supported input formats:
1) Virginia_Elections_Database__<YEAR>_<OFFICE>_General_Election_including_precincts.csv
2) Election Results_<GUID>.csv (Virginia Department of Elections export)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


WIDE_PATTERN = re.compile(
    r"^Virginia_Elections_Database__(?P<year>\d{4})_(?P<office>.+?)_General_Election_including_precincts\.csv$",
    re.IGNORECASE,
)
LONG_PATTERN = re.compile(r"^Election Results_(?P<id>.+)\.csv$", re.IGNORECASE)

YEAR_TO_GENERAL_DATE = {
    2008: "2008-11-04",
    2009: "2009-11-03",
    2012: "2012-11-06",
    2013: "2013-11-05",
    2014: "2014-11-04",
    2016: "2016-11-08",
    2017: "2017-11-07",
    2018: "2018-11-06",
    2020: "2020-11-03",
    2021: "2021-11-02",
    2024: "2024-11-05",
    2025: "2025-11-04",
}

OFFICE_TOKEN_TO_LABEL = {
    "president": "President",
    "u_s_senate": "U.S. Senate",
    "governor": "Governor",
    "lieutenant_governor": "Lieutenant Governor",
    "attorney_general": "Attorney General",
}

PARTY_MAP = {
    "DEMOCRATIC": "DEM",
    "DEMOCRAT": "DEM",
    "REPUBLICAN": "REP",
    "LIBERTARIAN": "LIB",
    "GREEN": "GRN",
    "INDEPENDENT": "IND",
    "WRITE-IN": "WRI",
    "WRITE IN": "WRI",
    "NONPARTISAN": "",
}


@dataclass
class ConvertedFile:
    input_file: str
    output_file: str
    output_rows: int


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "contest"


def parse_int(value: str) -> int:
    s = (value or "").strip().replace(",", "")
    if not s or s in {"-", "--"}:
        return 0
    try:
        return int(round(float(s)))
    except ValueError:
        return 0


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def normalize_locality(raw: str) -> str:
    s = clean_text(raw)
    if not s:
        return ""
    s = re.sub(r"^City of\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+County$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+City$", "", s, flags=re.IGNORECASE)
    return s.upper()


def normalize_precinct(raw: str) -> str:
    s = clean_text(raw)
    if not s:
        return ""
    # Remove trailing district annotations like "(CD 2)".
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
    return s.upper()


def normalize_party(raw_party: str, candidate: str) -> str:
    party = clean_text(raw_party).upper()
    if not party and clean_text(candidate).upper() == "ALL OTHERS":
        return "OTH"
    if party in PARTY_MAP:
        return PARTY_MAP[party]
    if party == "OTHER":
        return "OTH"
    if len(party) <= 4:
        return party
    return ""


def election_date_for_year(year: int) -> str:
    return YEAR_TO_GENERAL_DATE.get(year, f"{year}-11-01")


def format_date_for_filename(iso_date: str) -> str:
    return iso_date.replace("-", "")


def write_open_elections_csv(path: Path, rows: List[Dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        rows,
        key=lambda r: (
            r["county"],
            r["precinct"],
            r["office"],
            r["district"],
            r["candidate"],
            r["party"],
        ),
    )
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["county", "precinct", "office", "district", "party", "candidate", "votes"],
        )
        writer.writeheader()
        writer.writerows(ordered)
    return len(ordered)


def convert_wide_file(csv_path: Path, output_root: Path) -> ConvertedFile:
    match = WIDE_PATTERN.match(csv_path.name)
    if not match:
        raise ValueError(f"Unsupported wide filename: {csv_path.name}")

    year = int(match.group("year"))
    office_token = slugify(match.group("office"))
    office_label = OFFICE_TOKEN_TO_LABEL.get(office_token, match.group("office").replace("_", " "))
    election_date = election_date_for_year(year)
    date_token = format_date_for_filename(election_date)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = list(csv.reader(f))

    if len(reader) < 3:
        raise ValueError(f"Not enough rows in {csv_path.name}")

    header_row = reader[0]
    party_row = reader[1]
    data_rows = reader[2:]

    rows_out: List[Dict[str, str]] = []
    max_cols = min(len(header_row), max((len(r) for r in data_rows), default=0))

    for row in data_rows:
        if not row:
            continue
        county = normalize_locality(row[0] if len(row) > 0 else "")
        precinct = normalize_precinct(row[2] if len(row) > 2 else "")
        if not county or not precinct:
            continue

        for idx in range(3, max_cols):
            candidate = clean_text(header_row[idx] if idx < len(header_row) else "")
            if not candidate:
                continue
            if candidate.upper() in {"TOTAL VOTES CAST", "TOTAL"}:
                continue

            votes = parse_int(row[idx] if idx < len(row) else "")
            if votes <= 0:
                continue

            party_raw = party_row[idx] if idx < len(party_row) else ""
            party = normalize_party(party_raw, candidate)

            rows_out.append(
                {
                    "county": county,
                    "precinct": precinct,
                    "office": office_label,
                    "district": "",
                    "party": party,
                    "candidate": candidate,
                    "votes": str(votes),
                }
            )

    out_name = f"{date_token}__va__general__precinct__{office_token}.csv"
    out_path = output_root / str(year) / out_name
    row_count = write_open_elections_csv(out_path, rows_out)
    return ConvertedFile(csv_path.name, str(out_path), row_count)


def derive_district(row: Dict[str, str]) -> str:
    district_type = clean_text(row.get("DistrictType", ""))
    district_name = clean_text(row.get("DistrictName", ""))
    if not district_name:
        return ""
    if district_type.lower() == "state":
        return ""
    return district_name


def convert_long_file(csv_path: Path, output_root: Path) -> ConvertedFile:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    rows_out: List[Dict[str, str]] = []
    election_date = ""
    election_type = "general"
    offices: set[str] = set()

    for row in rows:
        county = normalize_locality(row.get("LocalityName", ""))
        precinct = normalize_precinct(row.get("PrecinctName", ""))
        office = clean_text(row.get("OfficeTitle", ""))
        candidate = clean_text(row.get("CandidateName", ""))
        party = normalize_party(row.get("Party", ""), candidate)
        votes = parse_int(row.get("TOTAL_VOTES", ""))
        district = derive_district(row)

        if not election_date:
            election_date = clean_text(row.get("ElectionDate", ""))
        if clean_text(row.get("ElectionType", "")):
            election_type = slugify(row.get("ElectionType", "general"))

        if not county or not precinct or not office or not candidate or votes <= 0:
            continue

        offices.add(office)
        rows_out.append(
            {
                "county": county,
                "precinct": precinct,
                "office": office,
                "district": district,
                "party": party,
                "candidate": candidate,
                "votes": str(votes),
            }
        )

    if not election_date:
        # Fall back to year token from filename if date is missing.
        election_date = f"{Path(csv_path.name).stem[:4]}-11-01"

    year = int(election_date[:4])
    date_token = format_date_for_filename(election_date)
    office_slug = slugify(next(iter(offices))) if len(offices) == 1 else "multi_office"
    source_slug = slugify(Path(csv_path.name).stem.replace("Election Results_", ""))
    out_name = f"{date_token}__va__{election_type}__precinct__{office_slug}__{source_slug}.csv"
    out_path = output_root / str(year) / out_name
    row_count = write_open_elections_csv(out_path, rows_out)
    return ConvertedFile(csv_path.name, str(out_path), row_count)


def convert_all(input_dir: Path, output_root: Path) -> List[ConvertedFile]:
    converted: List[ConvertedFile] = []
    for csv_path in sorted(input_dir.glob("*.csv")):
        name = csv_path.name
        if WIDE_PATTERN.match(name):
            converted.append(convert_wide_file(csv_path, output_root))
            continue
        if LONG_PATTERN.match(name):
            converted.append(convert_long_file(csv_path, output_root))
            continue
    return converted


def save_manifest(output_root: Path, converted_files: Iterable[ConvertedFile]) -> Path:
    manifest = {
        "files": [
            {
                "input_file": item.input_file,
                "output_file": item.output_file.replace("\\", "/"),
                "rows": item.output_rows,
            }
            for item in converted_files
        ]
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert VA election CSVs to OpenElections-style CSVs.")
    parser.add_argument(
        "--input-dir",
        default="Data",
        help="Directory containing source CSV files (default: Data).",
    )
    parser.add_argument(
        "--output-dir",
        default="Data/openelections",
        help="Directory for converted OpenElections-style CSVs (default: Data/openelections).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    converted = convert_all(input_dir, output_dir)
    manifest_path = save_manifest(output_dir, converted)

    print(f"Converted {len(converted)} files into {output_dir}")
    total_rows = 0
    for item in converted:
        total_rows += item.output_rows
        print(f"- {item.input_file} -> {item.output_file} ({item.output_rows} rows)")
    print(f"Total output rows: {total_rows}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
