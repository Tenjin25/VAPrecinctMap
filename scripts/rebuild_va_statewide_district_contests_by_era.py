#!/usr/bin/env python3
"""Stage, audit, and optionally promote every statewide district projection.

The rebuild is deliberately split by election era so returns are never mapped
through a precinct vintage that did not exist for that election:

* 2008-2009: Census-2000 VTDs through the tracked NHGIS VTD00-to-VTD20 bridge.
* 2012-2021: the Census-2020/VTD20 precinct layer.
* 2023-present: the current ELECT precinct layer.

All eras use the NCPrecinctMap 0.1% sliver cutoff and candidate-specific
redistribution of non-geographic votes.  Outputs are reconciled to official
statewide totals and detected 99.9%-VAP locality clusters before promotion.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATEWIDE_CONTESTS = {
    "president",
    "us_senate",
    "governor",
    "lieutenant_governor",
    "attorney_general",
}
REPORT_FILES = {
    "manifest.json",
    "district_margin_target_report.csv",
    "district_margin_target_outliers.csv",
    "historical_nhgis_rebuild_report.json",
    "locality_component_reconciliation_report.json",
    "year_aware_rebuild_report.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Promote a passing staged rebuild to production.")
    parser.add_argument("--production-dir", default="Data/district_contests")
    parser.add_argument("--stage-dir", default="Data/district_contests_year_aware_candidate")
    parser.add_argument("--statewide-contests-dir", default="Data/contests")
    parser.add_argument("--openelections-dir", default="Data/openelections")
    parser.add_argument("--max-margin-drift", type=float, default=5.0)
    parser.add_argument("--minimum-overlay-share", type=float, default=0.001)
    return parser.parse_args()


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def contest_key(path: Path) -> tuple[str, int] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        meta = payload.get("meta", {})
        contest = str(meta.get("contest_type", ""))
        year = int(meta.get("year", 0) or 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return (contest, year) if contest in STATEWIDE_CONTESTS and year else None


def official_elections(directory: Path) -> list[tuple[str, int]]:
    elections = {key for path in directory.glob("*.json") if (key := contest_key(path))}
    if not elections:
        raise ValueError(f"No statewide contest files found in {directory}")
    return sorted(elections, key=lambda item: (item[1], item[0]))


def builder_command(
    elections: list[tuple[str, int]], precinct_geojson: str, output_dir: Path, args: argparse.Namespace
) -> list[str]:
    command = [
        sys.executable,
        "scripts/build_va_district_contests_from_crosswalks.py",
        "--openelections-dir",
        args.openelections_dir,
        "--precinct-geojson",
        precinct_geojson,
        "--minimum-overlay-share",
        str(args.minimum_overlay_share),
        "--output-dir",
        str(output_dir.relative_to(ROOT)),
    ]
    for contest in sorted({contest for contest, _ in elections}):
        command.extend(["--contest-type", contest])
    for year in sorted({year for _, year in elections}):
        command.extend(["--year", str(year)])
    return command


def result_totals(payload: dict) -> dict[str, int]:
    rows = payload.get("general", {}).get("results", {}).values()
    return {
        party: sum(int(row.get(f"{party}_votes", 0) or 0) for row in rows)
        for party in ("dem", "rep", "other")
    }


def compare(production_dir: Path, stage_dir: Path) -> list[dict]:
    report: list[dict] = []
    for staged_path in sorted(stage_dir.glob("*.json")):
        if staged_path.name in REPORT_FILES:
            continue
        staged = json.loads(staged_path.read_text(encoding="utf-8"))
        meta = staged.get("meta", {})
        if str(meta.get("contest_type", "")) not in STATEWIDE_CONTESTS:
            continue
        production_path = production_dir / staged_path.name
        production = (
            json.loads(production_path.read_text(encoding="utf-8"))
            if production_path.exists()
            else {"general": {"results": {}}}
        )
        before_rows = production.get("general", {}).get("results", {})
        after_rows = staged.get("general", {}).get("results", {})
        changes = []
        for district, row in after_rows.items():
            old = before_rows.get(district)
            if old is None:
                continue
            changes.append({
                "district": district,
                "before_margin_pct": float(old.get("margin_pct", 0) or 0),
                "rebuilt_margin_pct": float(row.get("margin_pct", 0) or 0),
                "abs_change_pct": abs(
                    float(old.get("margin_pct", 0) or 0) - float(row.get("margin_pct", 0) or 0)
                ),
            })
        changes.sort(key=lambda row: row["abs_change_pct"], reverse=True)
        report.append({
            "file": staged_path.name,
            "before_totals": result_totals(production),
            "rebuilt_totals": result_totals(staged),
            "max_abs_margin_change_pct": changes[0]["abs_change_pct"] if changes else 0.0,
            "largest_margin_changes": changes[:10],
            "match_coverage_pct": meta.get("match_coverage_pct"),
            "direct_match_coverage_pct": meta.get("direct_match_coverage_pct"),
        })
    return report


def merge_era(stage_dir: Path, era_dir: Path) -> None:
    for path in era_dir.glob("*.json"):
        if path.name not in REPORT_FILES:
            shutil.copy2(path, stage_dir / path.name)


def update_manifest(production_dir: Path, stage_dir: Path) -> None:
    manifest = json.loads((production_dir / "manifest.json").read_text(encoding="utf-8"))
    by_file = {str(row.get("file", "")): row for row in manifest.get("files", [])}
    for path in stage_dir.glob("*.json"):
        if path.name in REPORT_FILES or path.name not in by_file:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        totals = result_totals(payload)
        by_file[path.name].update({
            "dem_total": totals["dem"],
            "rep_total": totals["rep"],
            "major_party_contested": bool(totals["dem"] and totals["rep"]),
        })
    (stage_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    production_dir = ROOT / args.production_dir
    stage_dir = ROOT / args.stage_dir
    official_dir = ROOT / args.statewide_contests_dir
    elections = official_elections(official_dir)
    historical = [item for item in elections if item[1] <= 2009]
    vtd20 = [item for item in elections if 2010 <= item[1] <= 2021]
    current = [item for item in elections if item[1] >= 2022]

    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    era_root = stage_dir / "_eras"
    era_root.mkdir()

    if historical:
        historical_dir = era_root / "historical"
        historical_dir.mkdir()
        shutil.copy2(production_dir / "manifest.json", historical_dir / "manifest.json")
        run([
            sys.executable,
            "scripts/rebuild_va_historical_district_contests.py",
            "--write",
            "--openelections-dir",
            args.openelections_dir,
            "--minimum-overlay-share",
            str(args.minimum_overlay_share),
            "--output-dir",
            str(historical_dir.relative_to(ROOT)),
        ])
        merge_era(stage_dir, historical_dir)
    if vtd20:
        vtd20_dir = era_root / "vtd20"
        run(builder_command(vtd20, "Data/va_precincts.geojson", vtd20_dir, args))
        merge_era(stage_dir, vtd20_dir)
    if current:
        current_dir = era_root / "current"
        run(builder_command(current, "Data/va_precincts_current.geojson", current_dir, args))
        merge_era(stage_dir, current_dir)

    update_manifest(production_dir, stage_dir)
    run([
        sys.executable,
        "scripts/reconcile_va_district_contests.py",
        "--write",
        "--district-contests-dir",
        str(stage_dir.relative_to(ROOT)),
        "--statewide-contests-dir",
        args.statewide_contests_dir,
        "--max-margin-drift",
        str(args.max_margin_drift),
    ])
    comparison = compare(production_dir, stage_dir)
    worst = max((row["max_abs_margin_change_pct"] for row in comparison), default=0.0)
    report = {
        "mode": "promotion_requested" if args.write else "audit",
        "minimum_overlay_share": args.minimum_overlay_share,
        "max_margin_drift_guard_pct": args.max_margin_drift,
        "eras": {
            "historical_nhgis_vtd00_bridge": historical,
            "census_2020_vtd": vtd20,
            "current_elect_precincts": current,
        },
        "files": comparison,
        "worst_abs_margin_change_pct": worst,
        "margin_drift_guard_passed": worst <= args.max_margin_drift,
    }
    report_path = stage_dir / "year_aware_rebuild_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.write and worst > args.max_margin_drift:
        raise ValueError(
            f"Refusing to promote: maximum district margin drift {worst:.3f} exceeds "
            f"guard {args.max_margin_drift:.3f}. Review {report_path}"
        )
    if args.write:
        for path in stage_dir.glob("*.json"):
            if path.name != "year_aware_rebuild_report.json":
                shutil.copy2(path, production_dir / path.name)
        report["mode"] = "promoted"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(report_path, production_dir / report_path.name)
        print(f"Promoted {len(comparison)} statewide district slices to {production_dir}")
    else:
        print(f"Audited {len(comparison)} statewide district slices; production was not changed")
        if worst > args.max_margin_drift:
            print(
                f"Promotion guard failed: {worst:.3f} points exceeds "
                f"{args.max_margin_drift:.3f}; review the reported outliers"
            )
    print(f"Worst district margin change: {worst:.3f} points")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
