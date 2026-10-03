#!/usr/bin/env python3
"""Audit or rebuild 2008-2009 district slices through the NHGIS VTD bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_va_district_contests_from_crosswalks as builder


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_CONTESTS = {
    ("president", 2008),
    ("us_senate", 2008),
    ("governor", 2009),
    ("lieutenant_governor", 2009),
    ("attorney_general", 2009),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--openelections-dir", default="Data/openelections")
    parser.add_argument("--assign-zip", default="Data/BlockAssign_ST51_VA.zip")
    parser.add_argument("--tabblock-zip", default="Data/tl_2020_51_tabblock20.zip")
    parser.add_argument("--county-geojson", default="Data/tl_2020_51_county20.geojson")
    parser.add_argument("--vtd-zip", default="Data/tl_2020_51_vtd20.zip")
    parser.add_argument("--precinct-geojson", default="Data/va_precincts.geojson")
    parser.add_argument("--congressional-geojson", default="Data/tl_2024_51_cd119.geojson")
    parser.add_argument("--state-house-geojson", default="Data/tl_2022_51_sldl.geojson")
    parser.add_argument("--state-senate-geojson", default="Data/tl_2022_51_sldu.geojson")
    parser.add_argument("--historical-crosswalk", default=builder.DEFAULT_HISTORICAL_VTD_CROSSWALK)
    parser.add_argument("--margin-targets-csv", default=builder.DEFAULT_MARGIN_TARGETS_CSV)
    parser.add_argument("--result-overrides-csv", default=builder.DEFAULT_RESULT_OVERRIDES_CSV)
    parser.add_argument("--output-dir", default="Data/district_contests")
    parser.add_argument(
        "--minimum-overlay-share",
        type=float,
        default=builder.MIN_OVERLAY_SHARE,
        help="Drop smaller overlay shares and renormalize (default: 0.001, matching NCPrecinctMap).",
    )
    parser.add_argument("--min-match-coverage", type=float, default=99.0)
    parser.add_argument("--max-margin-drift", type=float, default=20.0)
    return parser.parse_args()


def sum_results(payload: dict) -> dict[str, int]:
    rows = payload.get("general", {}).get("results", {}).values()
    return {
        bucket: sum(int(row.get(f"{bucket}_votes", 0) or 0) for row in rows)
        for bucket in ("dem", "rep", "other")
    }


def update_manifest(output_dir: Path, payloads: dict[str, dict]) -> None:
    path = output_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    by_file = {str(entry.get("file", "")): entry for entry in manifest.get("files", [])}
    for filename, payload in payloads.items():
        totals = sum_results(payload)
        entry = by_file.get(filename)
        if not entry:
            continue
        entry["dem_total"] = totals["dem"]
        entry["rep_total"] = totals["rep"]
        entry["major_party_contested"] = bool(totals["dem"] > 0 and totals["rep"] > 0)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    paths = {
        name: ROOT / value
        for name, value in {
            "openelections": args.openelections_dir,
            "assign": args.assign_zip,
            "tabblock": args.tabblock_zip,
            "county": args.county_geojson,
            "vtd": args.vtd_zip,
            "precinct": args.precinct_geojson,
            "congressional": args.congressional_geojson,
            "state_house": args.state_house_geojson,
            "state_senate": args.state_senate_geojson,
            "historical": args.historical_crosswalk,
            "margin_targets": args.margin_targets_csv,
            "overrides": args.result_overrides_csv,
            "output": args.output_dir,
        }.items()
    }

    scope_maps = builder.build_all_scope_mappings(
        paths["assign"],
        paths["tabblock"],
        paths["county"],
        paths["vtd"],
        paths["precinct"],
        paths["congressional"],
        paths["state_house"],
        paths["state_senate"],
        "overlay",
        float(args.minimum_overlay_share),
    )
    historical_maps = builder.build_historical_vtd_scope_mappings(paths["historical"], scope_maps)
    locality_aliases = builder.build_locality_alias_map(paths["county"])
    requested = {
        (scope, contest, year)
        for scope in builder.SCOPES
        for contest, year in HISTORICAL_CONTESTS
    }
    district_acc, totals, coverage = builder.build_district_contests(
        paths["openelections"],
        scope_maps,
        locality_aliases,
        benchmark_filter=requested,
        historical_scope_mappings=historical_maps,
    )
    margin_targets = builder.load_district_margin_targets(paths["margin_targets"])
    overrides = builder.load_district_result_overrides(paths["overrides"])
    builder.apply_district_margin_targets(district_acc, totals, margin_targets)
    builder.apply_district_result_overrides(district_acc, totals, overrides)

    report = []
    payloads: dict[str, dict] = {}
    for scope, contest, year in sorted(requested):
        payload, row_count = builder.render_payload_for_group(scope, contest, year, district_acc, coverage)
        if not row_count:
            continue
        payload["meta"]["historical_vtd_crosswalk"] = str(paths["historical"].relative_to(ROOT)).replace("\\", "/")
        payload["meta"]["historical_vtd_crosswalk_method"] = (
            "Census-2000 VTD to VTD20 via NHGIS 2000-2010 and 2010-2020 block relationships; "
            "area-share transfer into current district mappings."
        )
        filename = f"{scope}_{contest}_{year}.json"
        target = paths["output"] / filename
        before = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"general": {"results": {}}}
        before_rows = before.get("general", {}).get("results", {})
        after_rows = payload.get("general", {}).get("results", {})
        changes = []
        district_changes = []
        for district, after_row in after_rows.items():
            before_row = before_rows.get(district)
            if not before_row:
                continue
            before_margin = float(before_row.get("margin_pct", 0))
            after_margin = float(after_row.get("margin_pct", 0))
            change = abs(after_margin - before_margin)
            changes.append(change)
            district_changes.append({
                "district": district,
                "before_margin_pct": before_margin,
                "rebuilt_margin_pct": after_margin,
                "abs_change_pct": change,
            })
        report.append({
            "file": filename,
            "rows": row_count,
            "match_coverage_pct": payload["meta"].get("match_coverage_pct"),
            "direct_match_coverage_pct": payload["meta"].get("direct_match_coverage_pct"),
            "mean_abs_margin_change_pct": (sum(changes) / len(changes)) if changes else 0.0,
            "max_abs_margin_change_pct": max(changes, default=0.0),
            "largest_margin_changes": sorted(
                district_changes, key=lambda row: row["abs_change_pct"], reverse=True
            )[:10],
            "before_totals": sum_results(before),
            "rebuilt_totals": sum_results(payload),
        })
        payloads[filename] = payload
    if args.write:
        worst_coverage = min((float(row["match_coverage_pct"] or 0) for row in report), default=0.0)
        worst_drift = max((float(row["max_abs_margin_change_pct"] or 0) for row in report), default=0.0)
        if worst_coverage < float(args.min_match_coverage):
            raise ValueError(
                f"Refusing to write: minimum match coverage {worst_coverage:.3f}% is below "
                f"guard {float(args.min_match_coverage):.3f}%"
            )
        if worst_drift > float(args.max_margin_drift):
            raise ValueError(
                f"Refusing to write: maximum district margin drift {worst_drift:.3f} exceeds "
                f"guard {float(args.max_margin_drift):.3f}"
            )
        for filename, payload in payloads.items():
            (paths["output"] / filename).write_text(
                json.dumps(payload, indent=2) + "\n", encoding="utf-8"
            )
        update_manifest(paths["output"], payloads)
    report_path = paths["output"] / "historical_nhgis_rebuild_report.json"
    report_path.write_text(json.dumps({
        "mode": "write" if args.write else "audit",
        "historical_crosswalk": str(paths["historical"].relative_to(ROOT)).replace("\\", "/"),
        "files": report,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"{'Wrote' if args.write else 'Audited'} {len(report)} historical district slices")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
