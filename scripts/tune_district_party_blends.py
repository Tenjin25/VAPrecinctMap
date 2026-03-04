#!/usr/bin/env python3
"""
Auto-tune district party-blend parameters against benchmark district margins.

This script evaluates *raw* (pre-anchor) margin error against
Data/benchmarks/district_margin_targets.csv and performs coordinate descent
over fallback and county override blend values.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

import build_va_district_contests_from_crosswalks as builder


def parse_grid(raw: str) -> list[float]:
    vals = []
    for token in (raw or "").split(","):
        t = token.strip()
        if not t:
            continue
        try:
            v = float(t)
        except ValueError as exc:
            raise ValueError(f"Invalid grid value {t!r}") from exc
        if v < 0 or v > 1:
            raise ValueError(f"Grid value must be in [0,1], got {v}")
        vals.append(round(v, 6))
    out = sorted(set(vals))
    if not out:
        raise ValueError("Grid is empty; provide at least one value in [0,1]")
    return out


def current_blend_config() -> dict[str, Any]:
    return {
        "fallback_legislative": float(builder.PARTY_FALLBACK_BLEND),
        "fallback_congressional": float(builder.PARTY_FALLBACK_BLEND_CONGRESSIONAL),
        "congressional_by_county": {k: float(v) for k, v in builder.CONGRESSIONAL_PARTY_BLEND_BY_COUNTY.items()},
        "state_house_by_county": {k: float(v) for k, v in builder.STATE_HOUSE_PARTY_BLEND_BY_COUNTY.items()},
        "state_senate_by_county": {k: float(v) for k, v in builder.STATE_SENATE_PARTY_BLEND_BY_COUNTY.items()},
    }


def apply_blend_config(config: dict[str, Any]) -> None:
    builder.PARTY_FALLBACK_BLEND = float(config["fallback_legislative"])
    builder.PARTY_FALLBACK_BLEND_CONGRESSIONAL = float(config["fallback_congressional"])
    builder.CONGRESSIONAL_PARTY_BLEND_BY_COUNTY = dict(config["congressional_by_county"])
    builder.STATE_HOUSE_PARTY_BLEND_BY_COUNTY = dict(config["state_house_by_county"])
    builder.STATE_SENATE_PARTY_BLEND_BY_COUNTY = dict(config["state_senate_by_county"])


def config_signature(config: dict[str, Any]) -> str:
    return json.dumps(config, sort_keys=True, separators=(",", ":"))


def load_targets(
    margin_targets_csv: Path,
    scope_filters: set[str] | None,
    contest_filters: set[str] | None,
    year_filters: set[int] | None,
) -> dict[tuple[str, str, int, str], float]:
    targets = builder.load_district_margin_targets(margin_targets_csv)
    out: dict[tuple[str, str, int, str], float] = {}
    for (scope, contest_type, year, district), value in targets.items():
        if scope_filters and scope not in scope_filters:
            continue
        if contest_filters and contest_type not in contest_filters:
            continue
        if year_filters and year not in year_filters:
            continue
        out[(scope, contest_type, year, district)] = float(value)
    if not out:
        raise ValueError("No benchmark targets after filters; adjust --scope/--contest-type/--year filters.")
    return out


def build_scope_filter(targets: dict[tuple[str, str, int, str], float]) -> set[tuple[str, str, int]]:
    return {(scope, contest_type, year) for scope, contest_type, year, _ in targets.keys()}


def evaluate_config(
    config: dict[str, Any],
    openelections_dir: Path,
    scope_maps: dict[str, dict],
    locality_alias_map: dict[str, str],
    targets: dict[tuple[str, str, int, str], float],
    benchmark_scope_filter: set[tuple[str, str, int]],
    threshold_pct: float,
    missing_penalty_pct: float,
) -> dict[str, Any]:
    apply_blend_config(config)
    district_acc, _, _ = builder.build_district_contests(
        openelections_dir,
        scope_maps,
        locality_alias_map,
        benchmark_filter=benchmark_scope_filter,
    )

    rows = []
    abs_errors = []
    sq_errors = []
    missing_count = 0
    over_threshold = 0
    max_abs_error = 0.0

    for key, target_margin_pct in targets.items():
        scope, contest_type, year, district = key
        node = district_acc.get(key)
        actual = builder.compute_signed_margin_pct(node) if node is not None else None
        if actual is None:
            missing_count += 1
            abs_err = float(missing_penalty_pct)
            err = None
            status = "missing_output"
            actual_out: float | str = ""
        else:
            err = float(actual - target_margin_pct)
            abs_err = abs(err)
            status = "ok"
            actual_out = round(float(actual), 3)

        abs_errors.append(abs_err)
        sq_errors.append(abs_err * abs_err)
        if abs_err >= threshold_pct:
            over_threshold += 1
        if abs_err > max_abs_error:
            max_abs_error = abs_err

        rows.append(
            {
                "scope": scope,
                "contest_type": contest_type,
                "year": year,
                "district": district,
                "target_margin_pct": round(float(target_margin_pct), 3),
                "raw_margin_pct": actual_out,
                "raw_error_pct": round(float(err), 3) if err is not None else "",
                "raw_abs_error_pct": round(abs_err, 3),
                "needs_calibration": "yes" if abs_err >= threshold_pct else "no",
                "status": status,
            }
        )

    rows.sort(
        key=lambda r: (
            0 if r["status"] == "ok" else 1,
            -float(r["raw_abs_error_pct"]),
            builder.SCOPES.index(r["scope"]) if r["scope"] in builder.SCOPES else 99,
            r["contest_type"],
            int(r["year"]),
            builder.district_sort_key(str(r["district"])),
        )
    )

    n = max(1, len(abs_errors))
    mae = float(sum(abs_errors) / n)
    rmse = float(math.sqrt(sum(sq_errors) / n))
    metrics = {
        "target_count": len(rows),
        "missing_count": int(missing_count),
        "over_threshold_count": int(over_threshold),
        "mae": mae,
        "rmse": rmse,
        "max_abs_error": float(max_abs_error),
    }
    return {"metrics": metrics, "rows": rows}


def metric_key(metrics: dict[str, Any]) -> tuple[float, float, float, int, int]:
    return (
        float(metrics["mae"]),
        float(metrics["rmse"]),
        float(metrics["max_abs_error"]),
        int(metrics["over_threshold_count"]),
        int(metrics["missing_count"]),
    )


def build_parameters(config: dict[str, Any], include_county_overrides: bool) -> list[tuple[str, str | None]]:
    params: list[tuple[str, str | None]] = [
        ("fallback_legislative", None),
        ("fallback_congressional", None),
    ]
    if include_county_overrides:
        for county in sorted(config["congressional_by_county"].keys()):
            params.append(("congressional_by_county", county))
        for county in sorted(config["state_house_by_county"].keys()):
            params.append(("state_house_by_county", county))
        for county in sorted(config["state_senate_by_county"].keys()):
            params.append(("state_senate_by_county", county))
    return params


def get_param(config: dict[str, Any], group: str, county: str | None) -> float:
    if county is None:
        return float(config[group])
    return float(config[group][county])


def set_param(config: dict[str, Any], group: str, county: str | None, value: float) -> None:
    v = float(max(0.0, min(1.0, value)))
    if county is None:
        config[group] = v
    else:
        config[group][county] = v


def param_name(group: str, county: str | None) -> str:
    return group if county is None else f"{group}:{county}"


def write_rows_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "scope",
        "contest_type",
        "year",
        "district",
        "target_margin_pct",
        "raw_margin_pct",
        "raw_error_pct",
        "raw_abs_error_pct",
        "needs_calibration",
        "status",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-tune district party-blend parameters from benchmark targets.")
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
    parser.add_argument("--scope", action="append", default=[], help="Filter scope(s), repeatable.")
    parser.add_argument("--contest-type", action="append", default=[], help="Filter contest type(s), repeatable.")
    parser.add_argument("--year", action="append", type=int, default=[], help="Filter year(s), repeatable.")
    parser.add_argument("--grid", default="0,0.15,0.3,0.5,0.7,0.85,1.0", help="Candidate blend values in [0,1].")
    parser.add_argument("--iterations", type=int, default=1, help="Coordinate-descent passes.")
    parser.add_argument("--threshold-pct", type=float, default=1.0)
    parser.add_argument("--missing-penalty-pct", type=float, default=100.0)
    parser.add_argument("--include-county-overrides", dest="include_county_overrides", action="store_true", default=True)
    parser.add_argument("--no-county-overrides", dest="include_county_overrides", action="store_false")
    parser.add_argument("--output-dir", default="Data/benchmarks/tuning")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    t0 = time.time()

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
    grid = parse_grid(args.grid)

    targets = load_targets(
        margin_targets_csv,
        scope_filters or None,
        contest_filters or None,
        year_filters,
    )
    benchmark_scope_filter = build_scope_filter(targets)

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

    baseline_config = current_blend_config()
    params = build_parameters(baseline_config, args.include_county_overrides)

    cache: dict[str, dict[str, Any]] = {}
    eval_count = 0

    def eval_cached(config: dict[str, Any]) -> dict[str, Any]:
        nonlocal eval_count
        sig = config_signature(config)
        hit = cache.get(sig)
        if hit is not None:
            return hit
        result = evaluate_config(
            config,
            openelections_dir,
            scope_maps,
            locality_alias_map,
            targets,
            benchmark_scope_filter,
            float(args.threshold_pct),
            float(args.missing_penalty_pct),
        )
        cache[sig] = result
        eval_count += 1
        return result

    baseline_result = eval_cached(deepcopy(baseline_config))
    best_config = deepcopy(baseline_config)
    best_result = baseline_result
    history = []

    for it in range(max(0, int(args.iterations))):
        improved = False
        for group, county in params:
            local_best_config = deepcopy(best_config)
            local_best_result = best_result
            current_value = get_param(best_config, group, county)

            for cand in grid:
                if abs(cand - current_value) < 1e-12:
                    continue
                trial = deepcopy(best_config)
                set_param(trial, group, county, cand)
                trial_result = eval_cached(trial)
                if metric_key(trial_result["metrics"]) < metric_key(local_best_result["metrics"]):
                    local_best_config = trial
                    local_best_result = trial_result

            if metric_key(local_best_result["metrics"]) < metric_key(best_result["metrics"]):
                best_config = local_best_config
                best_result = local_best_result
                improved = True
                history.append(
                    {
                        "iteration": it + 1,
                        "parameter": param_name(group, county),
                        "new_value": get_param(best_config, group, county),
                        "metrics": deepcopy(best_result["metrics"]),
                    }
                )

        if not improved:
            break

    apply_blend_config(best_config)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "party_blend_tuning_summary.json"
    best_rows_path = output_dir / "party_blend_best_report.csv"
    baseline_rows_path = output_dir / "party_blend_baseline_report.csv"

    write_rows_csv(best_rows_path, best_result["rows"])
    write_rows_csv(baseline_rows_path, baseline_result["rows"])

    summary = {
        "targets_file": str(margin_targets_csv),
        "targets_used": len(targets),
        "scope_filters": sorted(scope_filters),
        "contest_filters": sorted(contest_filters),
        "year_filters": sorted(year_filters) if year_filters else [],
        "grid": grid,
        "iterations_requested": int(args.iterations),
        "include_county_overrides": bool(args.include_county_overrides),
        "parameters_tuned": [param_name(group, county) for group, county in params],
        "evaluations_run": int(eval_count),
        "baseline_metrics": baseline_result["metrics"],
        "best_metrics": best_result["metrics"],
        "baseline_config": baseline_config,
        "best_config": best_config,
        "history": history,
        "outputs": {
            "summary_json": str(summary_path),
            "best_report_csv": str(best_rows_path),
            "baseline_report_csv": str(baseline_rows_path),
        },
        "elapsed_seconds": round(time.time() - t0, 3),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Targets used: {len(targets)}")
    print(f"Evaluations run: {eval_count}")
    print(f"Baseline metrics: {json.dumps(baseline_result['metrics'])}")
    print(f"Best metrics: {json.dumps(best_result['metrics'])}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {best_rows_path}")
    print(f"Wrote: {baseline_rows_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
