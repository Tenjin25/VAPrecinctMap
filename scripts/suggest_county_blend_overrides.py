#!/usr/bin/env python3
"""
Suggest county-level party blend overrides from benchmark diagnostics.

Workflow:
1) Read benchmark targets.
2) Optionally read diagnostics CSVs to focus on high-error districts/counties.
3) For each candidate county override parameter, run one-parameter grid search.
4) Write suggested overrides with projected MAE/RMSE improvements.
"""

from __future__ import annotations

import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import build_va_district_contests_from_crosswalks as builder
import tune_district_party_blends as tuner


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def pick_candidate_counties_from_diagnostics(
    raw_report_csv: Path,
    county_contrib_csv: Path,
    target_error_threshold: float,
    min_county_share: float,
    min_alloc_share: float,
) -> dict[str, set[str]]:
    raw_rows = read_csv_rows(raw_report_csv)
    contrib_rows = read_csv_rows(county_contrib_csv)

    bad_targets: set[tuple[str, str, int, str]] = set()
    for r in raw_rows:
        try:
            abs_err = float(r.get("raw_abs_error_pct") or 0.0)
            year = int(r.get("year") or 0)
        except ValueError:
            continue
        if abs_err >= target_error_threshold:
            bad_targets.add(
                (
                    (r.get("scope") or "").strip().lower(),
                    (r.get("contest_type") or "").strip().lower(),
                    year,
                    builder.normalize_district_id(r.get("district") or ""),
                )
            )

    out: dict[str, set[str]] = {
        "congressional_by_county": set(),
        "state_house_by_county": set(),
        "state_senate_by_county": set(),
    }
    group_by_scope = {
        "congressional": "congressional_by_county",
        "state_house": "state_house_by_county",
        "state_senate": "state_senate_by_county",
    }

    for r in contrib_rows:
        scope = (r.get("scope") or "").strip().lower()
        contest_type = (r.get("contest_type") or "").strip().lower()
        try:
            year = int(r.get("year") or 0)
        except ValueError:
            continue
        district = builder.normalize_district_id(r.get("district") or "")
        target_key = (scope, contest_type, year, district)
        if target_key not in bad_targets:
            continue

        try:
            county_share = float(r.get("district_share_of_total") or 0.0)
            alloc_share = float(r.get("district_county_allocated_share") or 0.0)
        except ValueError:
            continue
        if county_share < min_county_share:
            continue
        if alloc_share < min_alloc_share:
            continue

        county = (r.get("county") or "").strip().upper()
        group = group_by_scope.get(scope)
        if county and group:
            out[group].add(county)
    return out


def ensure_default_candidates(cands: dict[str, set[str]], baseline_config: dict[str, Any]) -> None:
    for group in ("congressional_by_county", "state_house_by_county", "state_senate_by_county"):
        cands.setdefault(group, set())
        cands[group].update(baseline_config.get(group, {}).keys())


def config_get(config: dict[str, Any], group: str, county: str) -> float:
    return float(config.get(group, {}).get(county, config.get("fallback_legislative", 0.15)))


def config_set(config: dict[str, Any], group: str, county: str, value: float) -> None:
    v = float(max(0.0, min(1.0, value)))
    config.setdefault(group, {})
    config[group][county] = v


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Suggest county-level blend overrides from benchmark diagnostics.")
    parser.add_argument("--openelections-dir", default="Data/openelections")
    parser.add_argument("--assign-zip", default="Data/BlockAssign_ST51_VA.zip")
    parser.add_argument("--tabblock-zip", default="Data/tl_2020_51_tabblock20.zip")
    parser.add_argument("--county-geojson", default="Data/tl_2020_51_county20.geojson")
    parser.add_argument("--vtd-zip", default="Data/tl_2020_51_vtd20.zip")
    parser.add_argument("--precinct-geojson", default="Data/va_precincts.geojson")
    parser.add_argument("--congressional-geojson", default="Data/tl_2024_51_cd119.geojson")
    parser.add_argument("--state-house-geojson", default="Data/tl_2022_51_sldl.geojson")
    parser.add_argument("--state-senate-geojson", default="Data/tl_2022_51_sldu.geojson")
    parser.add_argument("--margin-targets-csv", default=builder.DEFAULT_MARGIN_TARGETS_CSV)
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--contest-type", action="append", default=[])
    parser.add_argument("--year", action="append", type=int, default=[])
    parser.add_argument("--grid", default="0,0.15,0.3,0.5,0.7,0.85,1.0")
    parser.add_argument("--threshold-pct", type=float, default=1.0)
    parser.add_argument("--missing-penalty-pct", type=float, default=100.0)

    parser.add_argument("--diag-raw-report", default="")
    parser.add_argument("--diag-county-contrib", default="")
    parser.add_argument("--diag-target-error-threshold", type=float, default=8.0)
    parser.add_argument("--diag-min-county-share", type=float, default=0.08)
    parser.add_argument("--diag-min-alloc-share", type=float, default=0.40)

    parser.add_argument("--min-mae-gain", type=float, default=0.01)
    parser.add_argument("--output-dir", default="Data/benchmarks/override_suggestions")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    openelections_dir = Path(args.openelections_dir)
    assign_zip = Path(args.assign_zip)
    tabblock_zip = Path(args.tabblock_zip)
    county_geojson = Path(args.county_geojson)
    vtd_zip = Path(args.vtd_zip)
    precinct_geojson = Path(args.precinct_geojson)
    congressional_geojson = Path(args.congressional_geojson)
    state_house_geojson = Path(args.state_house_geojson)
    state_senate_geojson = Path(args.state_senate_geojson)
    margin_targets_csv = Path(args.margin_targets_csv)
    output_dir = Path(args.output_dir)

    for p in (
        openelections_dir,
        assign_zip,
        tabblock_zip,
        county_geojson,
        vtd_zip,
        precinct_geojson,
        congressional_geojson,
        state_house_geojson,
        state_senate_geojson,
        margin_targets_csv,
    ):
        if not p.exists():
            raise FileNotFoundError(f"Required input not found: {p}")

    scope_filters = {s.strip().lower() for s in args.scope if s.strip()}
    contest_filters = {c.strip().lower() for c in args.contest_type if c.strip()}
    year_filters = set(args.year) if args.year else None
    grid = tuner.parse_grid(args.grid)

    targets = tuner.load_targets(
        margin_targets_csv,
        scope_filters or None,
        contest_filters or None,
        year_filters,
    )
    benchmark_scope_filter = tuner.build_scope_filter(targets)

    scope_maps = builder.build_all_scope_mappings(
        assign_zip,
        tabblock_zip,
        county_geojson,
        vtd_zip,
        precinct_geojson,
        congressional_geojson,
        state_house_geojson,
        state_senate_geojson,
    )
    locality_alias_map = builder.build_locality_alias_map(county_geojson)

    baseline_config = tuner.current_blend_config()
    candidates = {
        "congressional_by_county": set(),
        "state_house_by_county": set(),
        "state_senate_by_county": set(),
    }

    if args.diag_raw_report and args.diag_county_contrib:
        raw_report_csv = Path(args.diag_raw_report)
        county_contrib_csv = Path(args.diag_county_contrib)
        if raw_report_csv.exists() and county_contrib_csv.exists():
            diag_cands = pick_candidate_counties_from_diagnostics(
                raw_report_csv,
                county_contrib_csv,
                float(args.diag_target_error_threshold),
                float(args.diag_min_county_share),
                float(args.diag_min_alloc_share),
            )
            for k, vals in diag_cands.items():
                candidates[k].update(vals)

    ensure_default_candidates(candidates, baseline_config)

    eval_cache: dict[str, dict[str, Any]] = {}
    eval_count = 0

    def evaluate(config: dict[str, Any]) -> dict[str, Any]:
        nonlocal eval_count
        sig = tuner.config_signature(config)
        hit = eval_cache.get(sig)
        if hit is not None:
            return hit
        result = tuner.evaluate_config(
            config,
            openelections_dir,
            scope_maps,
            locality_alias_map,
            targets,
            benchmark_scope_filter,
            float(args.threshold_pct),
            float(args.missing_penalty_pct),
        )
        eval_cache[sig] = result
        eval_count += 1
        return result

    baseline_result = evaluate(deepcopy(baseline_config))
    baseline_metrics = baseline_result["metrics"]
    baseline_rows = baseline_result["rows"]
    baseline_abs_by_key = {
        (
            (r.get("scope") or "").strip().lower(),
            (r.get("contest_type") or "").strip().lower(),
            int(r.get("year") or 0),
            builder.normalize_district_id(r.get("district") or ""),
        ): float(r.get("raw_abs_error_pct") or 0.0)
        for r in baseline_rows
    }

    suggestion_rows = []
    group_labels = {
        "congressional_by_county": "congressional",
        "state_house_by_county": "state_house",
        "state_senate_by_county": "state_senate",
    }
    min_gain = float(args.min_mae_gain)

    for group in ("congressional_by_county", "state_house_by_county", "state_senate_by_county"):
        county_list = sorted(candidates.get(group, set()))
        for county in county_list:
            current_val = config_get(baseline_config, group, county)
            local_best_val = current_val
            local_best_result = baseline_result
            for v in grid:
                trial = deepcopy(baseline_config)
                config_set(trial, group, county, v)
                trial_result = evaluate(trial)
                if tuner.metric_key(trial_result["metrics"]) < tuner.metric_key(local_best_result["metrics"]):
                    local_best_val = v
                    local_best_result = trial_result

            mae_gain = float(baseline_metrics["mae"] - local_best_result["metrics"]["mae"])
            if mae_gain < min_gain:
                continue

            trial_abs_by_key = {
                (
                    (r.get("scope") or "").strip().lower(),
                    (r.get("contest_type") or "").strip().lower(),
                    int(r.get("year") or 0),
                    builder.normalize_district_id(r.get("district") or ""),
                ): float(r.get("raw_abs_error_pct") or 0.0)
                for r in local_best_result["rows"]
            }
            diffs = []
            for key, b_abs in baseline_abs_by_key.items():
                t_abs = trial_abs_by_key.get(key, b_abs)
                improve = b_abs - t_abs
                if improve > 0:
                    scope, contest_type, year, district = key
                    diffs.append(
                        {
                            "scope": scope,
                            "contest_type": contest_type,
                            "year": year,
                            "district": district,
                            "abs_error_improvement_pct": round(improve, 3),
                            "baseline_abs_error_pct": round(b_abs, 3),
                            "trial_abs_error_pct": round(t_abs, 3),
                        }
                    )
            diffs.sort(key=lambda r: float(r["abs_error_improvement_pct"]), reverse=True)

            suggestion_rows.append(
                {
                    "scope": group_labels[group],
                    "county": county,
                    "param_group": group,
                    "current_value": round(current_val, 6),
                    "suggested_value": round(float(local_best_val), 6),
                    "delta_value": round(float(local_best_val - current_val), 6),
                    "mae_gain": round(mae_gain, 6),
                    "rmse_gain": round(float(baseline_metrics["rmse"] - local_best_result["metrics"]["rmse"]), 6),
                    "over_threshold_delta": int(
                        int(baseline_metrics["over_threshold_count"])
                        - int(local_best_result["metrics"]["over_threshold_count"])
                    ),
                    "top_improved_targets": json.dumps(diffs[:5]),
                }
            )

    suggestion_rows.sort(key=lambda r: float(r["mae_gain"]), reverse=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    suggestions_csv = output_dir / "county_blend_override_suggestions.csv"
    summary_json = output_dir / "county_blend_override_suggestions_summary.json"

    with suggestions_csv.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "scope",
            "county",
            "param_group",
            "current_value",
            "suggested_value",
            "delta_value",
            "mae_gain",
            "rmse_gain",
            "over_threshold_delta",
            "top_improved_targets",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(suggestion_rows)

    summary = {
        "targets_file": str(margin_targets_csv),
        "targets_used": len(targets),
        "scope_filters": sorted(scope_filters),
        "contest_filters": sorted(contest_filters),
        "year_filters": sorted(year_filters) if year_filters else [],
        "baseline_metrics": baseline_metrics,
        "grid": grid,
        "evaluations_run": eval_count,
        "candidate_counts": {k: len(v) for k, v in candidates.items()},
        "suggestions_count": len(suggestion_rows),
        "top_suggestions": suggestion_rows[:10],
        "outputs": {
            "suggestions_csv": str(suggestions_csv),
            "summary_json": str(summary_json),
        },
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Targets used: {len(targets)}")
    print(f"Evaluations run: {eval_count}")
    print(f"Suggestions written: {len(suggestion_rows)}")
    print(f"Wrote: {suggestions_csv}")
    print(f"Wrote: {summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
