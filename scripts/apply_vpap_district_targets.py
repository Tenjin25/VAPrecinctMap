#!/usr/bin/env python3
"""
Apply VPAP congressional district margins/percentages and statewide vote totals
as targets onto a baseline district contest slice.

Inputs
------
- VPAP district breakdown topology (e.g. Data/CD_Gov2025.json)
- Statewide contest totals (e.g. Data/contests/governor_2025.json)
- Baseline district contest JSON (crosswalk allocation)

Output
------
A clean district contest JSON whose dem/rep/total votes:
  - preserve each district's VPAP signed margin percentage (as closely as
    integer votes allow)
  - sum exactly to the statewide dem/rep totals
and whose margin / margin_pct are derived from those final votes — no separate
vpap_* fields are written.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


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


def district_num_from_code(code: str) -> str:
    raw = (code or "").strip().upper()
    m = re.search(r"(\d+)$", raw)
    if not m:
        raise ValueError(f"Could not parse district number from {code!r}")
    return str(int(m.group(1)))


def load_vpap_district_targets(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    geometries = payload.get("objects", {}).get("CD_Gov2025", {}).get("geometries")
    if not isinstance(geometries, list) or not geometries:
        raise ValueError(f"No CD_Gov2025 geometries found in {path}")

    out: dict[str, dict] = {}
    for geom in geometries:
        props = geom.get("properties") or {}
        district = district_num_from_code(str(props.get("district_code") or ""))
        dem = int(props.get("votes_dem") or 0)
        rep = int(props.get("votes_rep") or 0)
        other = int(props.get("votes_other") or 0)
        total = dem + rep + other
        if total <= 0:
            raise ValueError(f"VPAP district {district} has no votes in {path}")
        signed_margin = (rep - dem) / total
        out[district] = {
            "dem_votes": dem,
            "rep_votes": rep,
            "other_votes": other,
            "total_votes": total,
            "signed_margin": signed_margin,
            "dem_share": (1.0 - signed_margin) / 2.0,
            "dem_candidate": (props.get("candidate_dem") or "").strip(),
            "rep_candidate": (props.get("candidate_rep") or "").strip(),
            "results_from": (props.get("results_from") or "").strip(),
        }
    return out


def load_statewide_targets(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("meta") or {}
    dem = int(meta.get("dem_total") or 0)
    rep = int(meta.get("rep_total") or 0)
    other = int(meta.get("other_total") or 0)
    total = int(meta.get("total_votes") or (dem + rep + other))
    if dem + rep + other != total:
        raise ValueError(
            f"Statewide totals inconsistent in {path}: "
            f"dem({dem})+rep({rep})+other({other}) != total({total})"
        )
    if total <= 0:
        raise ValueError(f"Statewide total_votes must be positive in {path}")
    return {"dem": dem, "rep": rep, "other": other, "total": total}


def load_baseline_results(path: Path) -> tuple[dict, dict[str, dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = (payload.get("general") or {}).get("results") or {}
    if not results:
        raise ValueError(f"No baseline district results in {path}")
    cleaned: dict[str, dict] = {}
    for district, row in results.items():
        dem = int(row.get("dem_votes") or 0)
        rep = int(row.get("rep_votes") or 0)
        other = int(row.get("other_votes") or 0)
        total = int(row.get("total_votes") or (dem + rep + other))
        cleaned[str(district)] = {
            "dem_votes": dem,
            "rep_votes": rep,
            "other_votes": other,
            "total_votes": total,
            "dem_candidate": (row.get("dem_candidate") or "").strip(),
            "rep_candidate": (row.get("rep_candidate") or "").strip(),
        }
    return payload, cleaned


def solve_turnout_weights(
    seed_totals: dict[str, float],
    dem_shares: dict[str, float],
    target_dem: float,
    target_total: float,
) -> dict[str, float]:
    """
    Find district turnouts t_i = seed_i * (alpha + beta * dem_share_i) that hit
    sum(t)=target_total and sum(dem_share*t)=target_dem.
    """
    districts = list(seed_totals.keys())
    s = {k: float(seed_totals[k]) for k in districts}
    a = {k: float(dem_shares[k]) for k in districts}

    S = sum(s.values())
    Sa = sum(a[k] * s[k] for k in districts)
    Saa = sum((a[k] ** 2) * s[k] for k in districts)
    det = (S * Saa) - (Sa * Sa)
    if abs(det) < 1e-12:
        raise ValueError("Degenerate turnout system; cannot solve alpha/beta")

    alpha = ((target_total * Saa) - (target_dem * Sa)) / det
    beta = ((S * target_dem) - (Sa * target_total)) / det

    totals = {k: s[k] * (alpha + beta * a[k]) for k in districts}
    if any(v <= 0 for v in totals.values()):
        raise ValueError("Solved turnout produced non-positive district totals")
    return totals


def allocate_integer_votes(
    float_totals: dict[str, float],
    dem_shares: dict[str, float],
    target_dem: int,
    target_rep: int,
) -> dict[str, tuple[int, int, int]]:
    """
    Convert continuous turnouts into integer dem/rep votes that preserve
    district margins as closely as possible and hit statewide totals exactly.
    """
    districts = sorted(float_totals.keys(), key=lambda d: int(d))
    target_total = target_dem + target_rep

    # Largest-remainder totals.
    floors = {k: int(float_totals[k] // 1) for k in districts}
    rem = target_total - sum(floors.values())
    order = sorted(
        districts,
        key=lambda k: (float_totals[k] - floors[k], float_totals[k]),
        reverse=True,
    )
    totals = dict(floors)
    for k in order[: max(0, rem)]:
        totals[k] += 1

    # Provisional dem from share; fix statewide dem with largest-remainder on frac.
    dem_float = {k: totals[k] * dem_shares[k] for k in districts}
    dem_floor = {k: int(dem_float[k] // 1) for k in districts}
    dem_rem = target_dem - sum(dem_floor.values())
    dem_order = sorted(
        districts,
        key=lambda k: (dem_float[k] - dem_floor[k], dem_float[k]),
        reverse=True,
    )
    dem_votes = dict(dem_floor)
    # Keep dem within [0, total].
    for k in dem_order:
        if dem_rem == 0:
            break
        if dem_rem > 0 and dem_votes[k] < totals[k]:
            dem_votes[k] += 1
            dem_rem -= 1
        elif dem_rem < 0 and dem_votes[k] > 0:
            dem_votes[k] -= 1
            dem_rem += 1

    # If still off (edge clamping), nudge districts with spare capacity.
    guard = 0
    while dem_rem != 0 and guard < 10000:
        guard += 1
        moved = False
        for k in dem_order if dem_rem > 0 else reversed(dem_order):
            if dem_rem > 0 and dem_votes[k] < totals[k]:
                dem_votes[k] += 1
                dem_rem -= 1
                moved = True
                break
            if dem_rem < 0 and dem_votes[k] > 0:
                dem_votes[k] -= 1
                dem_rem += 1
                moved = True
                break
        if not moved:
            break
    if dem_rem != 0:
        raise ValueError(f"Could not hit statewide dem target; remainder={dem_rem}")

    out: dict[str, tuple[int, int, int]] = {}
    for k in districts:
        dem = dem_votes[k]
        total = totals[k]
        rep = total - dem
        out[k] = (dem, rep, total)

    if sum(v[0] for v in out.values()) != target_dem:
        raise ValueError("dem total mismatch after allocation")
    if sum(v[1] for v in out.values()) != target_rep:
        raise ValueError("rep total mismatch after allocation")
    return out


def prefer_candidate(*names: str) -> str:
    for name in names:
        cleaned = (name or "").strip()
        if cleaned:
            return cleaned
    return ""


def build_payload(
    baseline_payload: dict,
    baseline_results: dict[str, dict],
    vpap_targets: dict[str, dict],
    statewide: dict[str, int],
    allocated: dict[str, tuple[int, int, int]],
) -> dict:
    missing = sorted(set(vpap_targets) - set(allocated), key=lambda d: int(d))
    if missing:
        raise ValueError(f"Missing allocated districts for VPAP targets: {missing}")

    results: dict[str, dict] = {}
    for district in sorted(allocated.keys(), key=lambda d: int(d)):
        dem, rep, total = allocated[district]
        other = 0
        signed_margin_pct = ((rep - dem) / total) * 100.0 if total else 0.0
        if rep > dem:
            winner = "Republican"
            winner_short = "R"
        elif dem > rep:
            winner = "Democratic"
            winner_short = "D"
        else:
            winner = "Tie"
            winner_short = "T"

        base = baseline_results.get(district) or {}
        vpap = vpap_targets[district]
        dem_candidate = prefer_candidate(base.get("dem_candidate"), vpap.get("dem_candidate"))
        rep_candidate = prefer_candidate(base.get("rep_candidate"), vpap.get("rep_candidate"))

        results[district] = {
            "dem_votes": dem,
            "rep_votes": rep,
            "other_votes": other,
            "total_votes": total,
            "dem_candidate": dem_candidate,
            "rep_candidate": rep_candidate,
            "winner": winner,
            "margin": abs(rep - dem),
            "margin_pct": signed_margin_pct,
            "color": category_color_for_margin(abs(signed_margin_pct), "R" if winner_short in {"R", "T"} else "D"),
        }

    baseline_meta = dict(baseline_payload.get("meta") or {})
    # Drop prior calibration / VPAP display annotations; replace with target notes.
    for key in (
        "calibrated_to_statewide",
        "calibration_method",
        "district_display_source",
        "calibrated_dem_total",
        "calibrated_rep_total",
        "target_method",
        "target_dem_total",
        "target_rep_total",
        "vpap_source",
    ):
        baseline_meta.pop(key, None)

    source_label = next(
        (v.get("results_from") for v in vpap_targets.values() if v.get("results_from")),
        "VPAP district vote breakdown",
    )

    baseline_meta.update(
        {
            "district_count": len(results),
            "target_dem_total": statewide["dem"],
            "target_rep_total": statewide["rep"],
            "target_total_votes": statewide["total"],
            "target_method": (
                "District turnout reweighted from baseline to hit statewide dem/rep "
                "totals while preserving VPAP district signed margins; final "
                "margin_pct derived from allocated votes."
            ),
            "vpap_margin_source": source_label,
        }
    )

    return {
        "meta": baseline_meta,
        "general": {"results": results},
    }


def update_manifest_totals(manifest_path: Path, filename: str, dem_total: int, rep_total: int) -> None:
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    files = manifest.get("files") or []
    updated = False
    for entry in files:
        if entry.get("file") == filename:
            entry["dem_total"] = dem_total
            entry["rep_total"] = rep_total
            entry["major_party_contested"] = bool(dem_total > 0 and rep_total > 0)
            updated = True
            break
    if updated:
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply VPAP district margins and statewide totals as targets."
    )
    parser.add_argument(
        "--vpap-topology",
        default="Data/CD_Gov2025.json",
        help="TopoJSON with VPAP congressional district vote properties.",
    )
    parser.add_argument(
        "--statewide-contest",
        default="Data/contests/governor_2025.json",
        help="Contest JSON whose meta dem/rep/total are statewide targets.",
    )
    parser.add_argument(
        "--baseline-district",
        default="Data/district_contests/congressional_governor_2025.json",
        help="Baseline district contest JSON (turnout seed + coverage meta).",
    )
    parser.add_argument(
        "--output",
        default="Data/district_contests/congressional_governor_2025.json",
        help="Output district contest JSON path.",
    )
    parser.add_argument(
        "--seed",
        choices=("baseline", "vpap"),
        default="baseline",
        help="Turnout seed before reweighting (default: baseline totals).",
    )
    parser.add_argument(
        "--update-manifest",
        default="Data/district_contests/manifest.json",
        help="Optional district manifest to refresh dem/rep totals for the output file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    vpap_path = Path(args.vpap_topology)
    statewide_path = Path(args.statewide_contest)
    baseline_path = Path(args.baseline_district)
    output_path = Path(args.output)

    vpap_targets = load_vpap_district_targets(vpap_path)
    statewide = load_statewide_targets(statewide_path)
    if statewide["other"] != 0:
        raise ValueError(
            "This script currently allocates other_votes=0 to match the "
            f"statewide other_total target; got other_total={statewide['other']}"
        )

    baseline_payload, baseline_results = load_baseline_results(baseline_path)

    missing_baseline = sorted(set(vpap_targets) - set(baseline_results), key=lambda d: int(d))
    if missing_baseline and args.seed == "baseline":
        raise ValueError(f"Baseline missing districts present in VPAP: {missing_baseline}")

    dem_shares = {d: float(v["dem_share"]) for d, v in vpap_targets.items()}
    if args.seed == "vpap":
        seed_totals = {d: float(v["total_votes"]) for d, v in vpap_targets.items()}
    else:
        seed_totals = {d: float(baseline_results[d]["total_votes"]) for d in vpap_targets}

    float_totals = solve_turnout_weights(
        seed_totals,
        dem_shares,
        target_dem=float(statewide["dem"]),
        target_total=float(statewide["total"]),
    )
    allocated = allocate_integer_votes(
        float_totals,
        dem_shares,
        target_dem=statewide["dem"],
        target_rep=statewide["rep"],
    )

    payload = build_payload(
        baseline_payload,
        baseline_results,
        vpap_targets,
        statewide,
        allocated,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.update_manifest:
        update_manifest_totals(
            Path(args.update_manifest),
            output_path.name,
            statewide["dem"],
            statewide["rep"],
        )

    # Summary
    print(f"Wrote {output_path}")
    print(
        f"Statewide targets: dem={statewide['dem']} rep={statewide['rep']} "
        f"total={statewide['total']}"
    )
    print("District margins (final vs VPAP target):")
    for district in sorted(allocated.keys(), key=lambda d: int(d)):
        dem, rep, total = allocated[district]
        final_m = ((rep - dem) / total) * 100.0
        target_m = vpap_targets[district]["signed_margin"] * 100.0
        print(
            f"  CD-{district:>2}: votes D/R {dem}/{rep} ({total})  "
            f"margin_pct {final_m:+.6f} (target {target_m:+.6f}, "
            f"err {final_m - target_m:+.6f})"
        )


if __name__ == "__main__":
    main()
