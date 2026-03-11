#!/usr/bin/env python3
"""
Targeted fix for VA CD-01 and CD-02 2024 presidential district totals.

What this script does:
1) Repairs known newline corruption in Data/benchmarks/district_result_overrides.csv.
2) Upserts exact override rows for congressional/president/2024 (districts 1 and 2).
3) Patches Data/district_contests/congressional_president_2024.json for districts 1 and 2.
4) Recomputes the corresponding manifest dem/rep totals for that file.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path

CSV_FIELDS = [
    "scope",
    "contest_type",
    "year",
    "district",
    "dem_votes",
    "rep_votes",
    "other_votes",
    "dem_candidate",
    "rep_candidate",
    "notes",
]

TARGET_SCOPE = "congressional"
TARGET_CONTEST = "president"
TARGET_YEAR = "2024"
TARGET_DEM_CANDIDATE = "Kamala D. Harris"
TARGET_REP_CANDIDATE = "Donald J. Trump"
TARGET_DISTRICT_FIXES: dict[str, dict[str, int | str]] = {
    "1": {
        "dem_votes": 227074,
        "rep_votes": 250992,
        "other_votes": 8529,
        "notes": "User-supplied actual CD-01 presidential totals",
    },
    "2": {
        "dem_votes": 203182,
        "rep_votes": 204265,
        "other_votes": 6695,
        "notes": "User-supplied actual CD-02 presidential totals",
    },
}


def build_target_row(district: str, fix: dict[str, int | str]) -> dict[str, str]:
    return {
        "scope": TARGET_SCOPE,
        "contest_type": TARGET_CONTEST,
        "year": TARGET_YEAR,
        "district": str(district),
        "dem_votes": str(int(fix.get("dem_votes", 0) or 0)),
        "rep_votes": str(int(fix.get("rep_votes", 0) or 0)),
        "other_votes": str(int(fix.get("other_votes", 0) or 0)),
        "dem_candidate": TARGET_DEM_CANDIDATE,
        "rep_candidate": TARGET_REP_CANDIDATE,
        "notes": str(fix.get("notes", "") or ""),
    }


def normalize_int_token(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    try:
        return str(int(float(s)))
    except ValueError:
        return s


def repair_known_csv_corruption(raw: str) -> str:
    fixed = raw
    fixed = fixed.replace(
        "rep_candidate,notescongressional,",
        "rep_candidate,notes\ncongressional,",
        1,
    )
    fixed = fixed.replace(
        "CD-01 presidential totalsstate_house,president,2024,41,",
        "CD-01 presidential totals\nstate_house,president,2024,41,",
        1,
    )
    return fixed


def load_override_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    raw = path.read_text(encoding="utf-8")
    repaired = repair_known_csv_corruption(raw)
    reader = csv.DictReader(io.StringIO(repaired))

    rows: list[dict[str, str]] = []
    for row in reader:
        normalized = {field: (row.get(field) or "").strip() for field in CSV_FIELDS}
        if not any(normalized.values()):
            continue
        if not normalized["scope"] or not normalized["contest_type"] or not normalized["year"] or not normalized["district"]:
            continue
        normalized["scope"] = normalized["scope"].lower()
        normalized["contest_type"] = normalized["contest_type"].lower()
        normalized["year"] = normalize_int_token(normalized["year"])
        normalized["district"] = normalize_int_token(normalized["district"])
        rows.append(normalized)
    return rows


def upsert_target_overrides(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], int, int]:
    row_by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            (row.get("scope") or "").lower(),
            (row.get("contest_type") or "").lower(),
            normalize_int_token(row.get("year", "")),
            normalize_int_token(row.get("district", "")),
        )
        row_by_key[key] = row

    updated = 0
    inserted = 0
    for district, fix in TARGET_DISTRICT_FIXES.items():
        target_row = build_target_row(district, fix)
        target_key = (
            target_row["scope"],
            target_row["contest_type"],
            target_row["year"],
            target_row["district"],
        )
        existing = row_by_key.get(target_key)
        if existing is not None:
            existing.update(target_row)
            updated += 1
        else:
            rows.append(target_row)
            row_by_key[target_key] = target_row
            inserted += 1
    return rows, updated, inserted


def row_sort_key(row: dict[str, str]) -> tuple[int, str, int, tuple[int, str]]:
    scope_rank = {"congressional": 0, "state_house": 1, "state_senate": 2}.get(
        (row.get("scope") or "").lower(),
        99,
    )
    contest_type = (row.get("contest_type") or "").lower()
    try:
        year = int(normalize_int_token(row.get("year", "")))
    except ValueError:
        year = 9999
    district_raw = normalize_int_token(row.get("district", ""))
    if district_raw.isdigit():
        district_key = (0, str(int(district_raw)))
    else:
        district_key = (1, district_raw)
    return scope_rank, contest_type, year, district_key


def write_override_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=row_sort_key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def category_color_for_margin(margin_pct_abs: float, winner_short: str) -> str:
    if margin_pct_abs >= 40:
        return "#67000d" if winner_short == "R" else "#08306b"
    if margin_pct_abs >= 30:
        return "#a50f15" if winner_short == "R" else "#08519c"
    if margin_pct_abs >= 20:
        return "#cb181d" if winner_short == "R" else "#3182bd"
    if margin_pct_abs >= 10:
        return "#ef3b2c" if winner_short == "R" else "#6baed6"
    if margin_pct_abs >= 5.5:
        return "#fb6a4a" if winner_short == "R" else "#9ecae1"
    if margin_pct_abs >= 1.0:
        return "#fcae91" if winner_short == "R" else "#c6dbef"
    if margin_pct_abs >= 0.5:
        return "#fee8c8" if winner_short == "R" else "#e1f5fe"
    return "#f7f7f7"


def patch_congressional_results_json(path: Path) -> bool:
    if not path.exists():
        return False

    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload.setdefault("general", {}).setdefault("results", {})
    for district, fix in TARGET_DISTRICT_FIXES.items():
        node = results.setdefault(str(district), {})
        dem = int(fix.get("dem_votes", 0) or 0)
        rep = int(fix.get("rep_votes", 0) or 0)
        other = int(fix.get("other_votes", 0) or 0)
        total = dem + rep + other
        signed_margin_pct = ((rep - dem) / total * 100.0) if total > 0 else 0.0
        signed_margin_pct = round(signed_margin_pct, 2)

        if rep > dem:
            winner = "Republican"
            winner_short = "R"
        elif dem > rep:
            winner = "Democratic"
            winner_short = "D"
        else:
            winner = "Tie"
            winner_short = "T"

        color = category_color_for_margin(abs(signed_margin_pct), "R" if winner_short in {"R", "T"} else "D")

        node.update(
            {
                "dem_votes": dem,
                "rep_votes": rep,
                "other_votes": other,
                "total_votes": total,
                "dem_candidate": TARGET_DEM_CANDIDATE,
                "rep_candidate": TARGET_REP_CANDIDATE,
                "winner": winner,
                "margin": abs(rep - dem),
                "margin_pct": signed_margin_pct,
                "color": color,
            }
        )

    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def update_manifest_totals(manifest_path: Path, contest_json_path: Path) -> bool:
    if not manifest_path.exists() or not contest_json_path.exists():
        return False

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = json.loads(contest_json_path.read_text(encoding="utf-8"))
    results = payload.get("general", {}).get("results", {})

    dem_total = 0
    rep_total = 0
    for node in results.values():
        dem_total += int(node.get("dem_votes", 0) or 0)
        rep_total += int(node.get("rep_votes", 0) or 0)

    changed = False
    for entry in manifest.get("files", []):
        scope = (entry.get("scope") or "").lower()
        contest = (entry.get("contest_type") or "").lower()
        year = normalize_int_token(str(entry.get("year", "")))
        if scope == TARGET_SCOPE and contest == TARGET_CONTEST and year == TARGET_YEAR:
            entry["dem_total"] = dem_total
            entry["rep_total"] = rep_total
            entry["rows"] = len(results)
            entry["major_party_contested"] = bool(dem_total > 0 and rep_total > 0)
            changed = True
            break

    if changed:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fix CD-01/CD-02 2024 presidential totals in overrides + district output.")
    parser.add_argument("--overrides-csv", default="Data/benchmarks/district_result_overrides.csv")
    parser.add_argument("--contest-json", default="Data/district_contests/congressional_president_2024.json")
    parser.add_argument("--manifest-json", default="Data/district_contests/manifest.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    overrides_csv = Path(args.overrides_csv)
    contest_json = Path(args.contest_json)
    manifest_json = Path(args.manifest_json)

    rows = load_override_rows(overrides_csv)
    rows, updated_count, inserted_count = upsert_target_overrides(rows)
    write_override_rows(overrides_csv, rows)

    contest_patched = patch_congressional_results_json(contest_json)
    manifest_patched = update_manifest_totals(manifest_json, contest_json)

    print(f"Override rows updated={updated_count}, inserted={inserted_count}: {overrides_csv}")
    if contest_patched:
        print(f"Patched district results file: {contest_json}")
    else:
        print(f"Skipped patch (file not found): {contest_json}")
    if manifest_patched:
        print(f"Updated manifest totals: {manifest_json}")
    else:
        print(f"Skipped manifest update (file/entry not found): {manifest_json}")


if __name__ == "__main__":
    main()
