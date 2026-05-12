# The Commonwealth Explorer (2008–2025)

An interactive, browser-based choropleth map of Virginia election results at the precinct, county, and legislative/congressional district level, covering every major statewide general election from 2008 through 2025.

---

## Latest Update (May 12, 2026)

- Added compact VoteHub-style hover cards for:
  - Precinct mode
  - Congressional districts
  - House of Delegates districts
  - State Senate districts
- Kept county/locality hover on the existing richer atlas-style tooltip path (unchanged).
- Added winner-line margin display (with `%`) and optional flip callouts (`Flipped R→D` / `Flipped D→R`) with party-color emphasis.
- Re-aligned compact-card decimal behavior to the existing front-end display pipeline to reduce drift between row shares and winner margin text.
- Preserved map coloring logic, selected locality panel structure, trend/timeline systems, and mobile docking behavior.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Repository Structure](#repository-structure)
4. [Data Sources](#data-sources)
5. [Methodology](#methodology)
   - [Step 1 — Convert boundary ZIPs to GeoJSON](#step-1--convert-boundary-zips-to-geojson)
   - [Step 2 — Normalize election CSVs to OpenElections format](#step-2--normalize-election-csvs-to-openelections-format)
   - [Step 3 — Build precinct polygon GeoJSON](#step-3--build-precinct-polygon-geojson)
   - [Step 4 — Build precinct centroid GeoJSON](#step-4--build-precinct-centroid-geojson)
   - [Step 5 — Build county-level contest slices](#step-5--build-county-level-contest-slices)
   - [Step 6 — Build district-level contest slices](#step-6--build-district-level-contest-slices)
6. [Color Ramp & Rating Categories](#color-ramp--rating-categories)
7. [Locality Canonicalization](#locality-canonicalization)
8. [Precinct Matching & Label Enrichment](#precinct-matching--label-enrichment)
9. [Front-End Architecture](#front-end-architecture)
10. [Index File Lineage](#index-file-lineage)
11. [Dependencies](#dependencies)
12. [Known Limitations & Future Work](#known-limitations--future-work)
13. [License](#license)

---

## Project Overview

`index.html` is the canonical production entry point for the Virginia map. It now carries the promoted NCMap-derived Virginia interface, including the aligned selected-locality focus design, Virginia locality normalization, district search shortcuts, the current desktop/mobile UI parity work, and a Virginia-specific chrome palette built around Commonwealth flag-inspired navy, red, and cream accents.

Recent `index.html` changes restored precinct-mode behavior to match the simpler Virginia-safe `.v1` matching path. In practice that means precinct dot mode again loads the precinct-detail slice, rebuilds the centroid/label indexes used for matching, and redistributes unmatched geographic precinct rows across known county precinct norms instead of falling back to flat county coloring too early.

The app expects a Mapbox token to be supplied at runtime through `window.MAPBOX_TOKEN` or `localStorage.mapbox_token`; the production entry point no longer ships with a hardcoded token fallback.

Virginia holds elections on a distinct off-year cycle (gubernatorial and state legislative races in odd years, federal races in even years), and its 133 independent cities alongside 95 counties create one of the more complex local-government geographies in the United States.  This project assembles precinct-level election returns from 2008 through 2025 into a single interactive map that lets users:

- Switch between **five election contests** (President, U.S. Senate, Governor, Lieutenant Governor, Attorney General) across **multiple years**
- View results simultaneously at the **county**, **precinct**, **congressional district**, **House of Delegates (HoD) district**, and **state-senate district** level
- See an 11-shade Democratic/Republican margin color ramp that conveys both *partisan direction* and *landslide intensity* in a single glance
- Click or tap any geographic unit for a popup showing vote totals, candidate names, winner, and margin percentage
- Search for any Virginia county or independent city and fly directly to it

---

## Features

| Feature | Details |
|---|---|
| **Map engine** | Mapbox GL JS v3.0.1 |
| **Spatial utilities** | Turf.js 6.5.0 (bounding-box fit, coordinate helpers) |
| **CSV parsing** | PapaParse 5.4.1 (used for any runtime CSV loading) |
| **Contest selector** | Dropdowns for contest type and year; manifest-driven so new contests appear automatically |
| **Map views** | County fill, precinct outline overlay, congressional district, House of Delegates (HoD) district, state-senate district |
| **Hover tooltip** | Condensed broadcast hover card for **counties, independent cities, precincts, and districts**. Shows a one-line margin call + tier, plus (when available) **Flip** context (line + chip) and an NC-style delta block with party-colored raw vote changes vs the prior comparable election, plus optional population-change lines. Shift mode adds Shift-only hover context (chip/line). Hover cards are now **non-pinnable** (no pin/close controls) and follow NCMap-style ephemeral behavior to reduce sticky/frozen overlays. Mobile keeps the tooltip docked above legend/results for readability. County overlay layers (for example, Smart Insights glow/outline) drive the same hover tooltip behavior. |
| **Selected locality panel** | Premium **Virginia Locality Focus** panel (county + independent city aware). Narrative order: margin-forward summary hero (margin call → winner → votes/shift) → **integrated vote-share bar + one-line vote share** → compact **Trajectory** list (descending years, party-color indicators, lightweight stability signal) → unified **At a glance** block (one sentence + 2–3 chips aligned with the hover tooltip terminology) → compact **Census** block (headline + one sentence) → (collapsed) extended analysis for deeper context (why it votes this way, locality profile, vote breakdown, demographics, precinct/non-geographic context, what to watch). The Locality profile’s `Geography` field uses corridor/region tagging (when available) instead of a generic “Virginia” label. |
| **Focus trend panel** | NC-style trend layout in the vote counter with `Latest`, `Closest`, `Since`, and per-year timeline cards (full vote totals; no `K`/`M` abbreviations), plus a **Trajectory Snapshot** and optional **Census insight** (Vintage 2025) with corridor tags to explain how/why a partisan lean can form |
| **Smart Insights** | Optional (default OFF) story mode that subtly highlights closest margins, biggest shifts, and population-signal localities and surfaces a short tooltip insight without overriding user selection. |
| **Focus mode** | When a locality is selected/pinned, the map subtly dims and the results panel elevates to keep attention on the active geography. |
| **Winner labeling** | Desktop winner pill shows full candidate names (for example, `Donald J. Trump (R)`), while statewide headline keeps short labels |
| **NCMap parity styling** | Desktop and mobile UI placement now mirrors NCMap structure: desktop left/right anchoring parity, mobile sheet + dock parity, synchronized overlay stacking/offset behavior, and Virginia-specific UI chrome accents for controls, tabs, ribbons, legend surfaces, and vote cards |
| **Locality search** | Free-text search with fly-to animation using turf bbox for counties, independent cities, precincts, and districts |
| **Virginia-safe alias handling** | Independent-city queries accept both `City of ...` and `... City` forms, while ambiguous bare names like `Fairfax` or `Richmond` are not auto-merged and instead require a city/county distinction |
| **Vote-card overflow fallback** | Top-right vote tiles auto-switch to stacked card layout when labels/counts overflow, preventing truncation of large totals |
| **Mobile-first layout** | iOS safe-area insets, stable viewport units (`svh`/`dvh`), touch-friendly controls, bottom-sheet legend |
| **Minimizable panels** | Controls, legend, and the top-right results panel can be collapsed to free map space |

### Latest UI parity update (April 2026)

- Adopted NCMap desktop layout variables and anchoring parity for Virginia:
  - `--desktop-left-w: 500px`
  - `--desktop-right-w: 340px`
  - `--desktop-right-gap: 14px`
  - `--desktop-vote-counter-h: 0px`
- Desktop `map-topbar` is hidden and the desktop vote counter is fixed to top-right (`top: 20px`, `right: 24px`) with no dynamic JS top positioning.
- Main controls desktop placement/minimized placement follows NCMap anchors and spacing.
- Mobile keeps the NCMap sheet/dock stack (`map-topbar`, `main-controls`, `legend`, `mobile-dock`, `vote-counter`, `hover-tooltip`).
- Mobile layering/offset parity is enforced so `hover-tooltip` sits above `vote-counter`, and `vote-counter` sits above `mobile-dock`.
- `updateMobileOverlayOffsets()` remains the source of truth for mobile open/close/minimize state offsets while preserving Virginia-specific election logic and locality normalization behavior.
- Hover tooltip opacity hierarchy now mirrors NCMap (`hover-preview` dimming and preview-card alpha treatment).
- Fly-to dropdown and legend ribbon alpha were normalized to NCMap values for visual consistency.
- Pin controls were removed from hover tooltips (county, precinct, and district) for NC-style non-sticky hover behavior.
- Shared UI chrome now uses a Virginia-forward palette: Commonwealth navy/red active states, ribbon gradients, softened cream neutrals, and matching control/legend/result-panel accents.
- The top vote summary line keeps its legacy dem/rep lead colors so quick statewide and locality margin reads still match the earlier broadcast treatment.

---

## Repository Structure

```
VAPrecinctMap/
├── index.html                          # Canonical production front-end (Mapbox GL JS, styles, JS)
├── index.v1.html                       # Virginia-only reference snapshot for earlier precinct matching behavior
├── index.lastcommit.html               # Saved historical snapshot from an earlier committed front-end state
├── index_no_rating_title_badge_fixed.html # UI snapshot preserving an earlier badge/title treatment
├── index_va_trajectory_wrap_patched.html  # Trajectory-layout experiment / patched snapshot
├── README.md
├── .gitignore
│
├── scripts/                            # Python data-pipeline scripts
│   ├── build_va_geojson_from_zips.py
│   ├── convert_va_csvs_to_openelections.py
│   ├── build_va_precincts_from_crosswalks.py
│   ├── build_precinct_centroids_geojson.py
│   ├── build_va_county_contests_from_openelections.py
│   └── build_va_district_contests_from_crosswalks.py
│
└── Data/
    ├── *.zip                           # Raw Census TIGER/Line ZIPs (git-ignored)
    ├── *.geojson                       # Derived boundary files (committed)
    ├── Virginia_Elections_Database__*.csv   # Wide-format source CSVs
    ├── Election Results_*.csv          # VADOE long-format source CSVs
    │
    ├── openelections/                  # Normalized OpenElections-style CSVs
    │   ├── manifest.json
    │   └── <year>/
    │       └── <YYYYMMDD>__va__general__precinct__<office>.csv
    │
    ├── contests/                       # County-level contest JSON slices
    │   ├── manifest.json
    │   └── <contest_type>_<year>.json
    │
    └── district_contests/              # District-level contest JSON slices
        ├── manifest.json
        └── <scope>_<contest_type>_<year>.json
```

ZIP files are excluded from version control (`.gitignore`) because the TIGER tabblock and VTD archives exceed GitHub's recommended file-size limit.

The additional `index*.html` files are snapshots and experiments, not parallel production entry points. `index.html` is the file that should be treated as current, while the others are useful for regression checks, UI comparison, or recovering a prior implementation detail.

Additional utility scripts currently in `scripts/`:

- `scripts/fix_cd01_president_2024_totals.py` (targeted CD-01/CD-02 presidential correction)
- `scripts/diagnose_district_assignment_errors.py` (benchmark diagnostics)
- `scripts/suggest_county_blend_overrides.py` (blend-override suggestions)
- `scripts/tune_district_party_blends.py` (blend tuning sweeps)

---

## Data Sources

### Election Returns

| Source | Format | Years Covered |
|---|---|---|
| **Virginia Elections Database** (VPAP / State Board of Elections) | Wide CSV — one row per locality/precinct, one column per candidate | 2008–2024 |
| **Virginia Department of Elections** (VADOE export) | Long CSV — one row per candidate per precinct | 2025 (and supplemental 2024) |
| **OpenElections Virginia** (community-contributed) | Already in OpenElections format — used as a cross-check | Various |

### Geographic Boundaries (Census TIGER/Line)

| File | Contents | Vintage |
|---|---|---|
| `tl_2020_51_county20.zip` | Virginia county and independent-city polygons | 2020 |
| `tl_2020_51_tabblock20.zip` | Census 2020 tabulation blocks (used to build precincts) | 2020 |
| `tl_2020_51_vtd20.zip` | Voting Tabulation Districts (VTD 2020) used for centroids | 2020 |
| `tl_2022_51_sldl.zip` | House of Delegates (HoD, lower chamber) district boundaries | 2022 redistricting |
| `tl_2022_51_sldu.zip` | State Senate (upper chamber) district boundaries | 2022 redistricting |
| `tl_2024_51_cd119.zip` | 119th Congress (2023–2025) congressional district boundaries | 2024 |

### Population Estimates (Census Vintage 2025)

The front-end can optionally load a cleaned county/locality population-estimates CSV to enrich the trend panel with a **Census insight** card and a short “Census check” line that can help explain **why** a county/independent city’s partisan lean may have formed or solidified (via growth/decline and corridor heuristics).

| File | Contents |
|---|---|
| `Data/CO-EST2025-POP-51-clean.csv` | Virginia county + independent-city population estimates (2020–2025) with precomputed change columns and a normalized key |

If this file is missing, the map still works; the Census insight/check sections simply won’t render.

#### Trajectory arrows

The **Trajectory Snapshot** uses arrows to summarize direction of change in the signed two-party margin (positive = more Republican; negative = more Democratic):

- `→` trending more Republican
- `←` trending more Democratic
- `↔` no clear directional change / roughly flat shift

#### Trajectory categories

The **Trajectory Snapshot** status combines a **category** (how the lean is behaving over time) with the **current side** (Republican/Democratic/Competitive), based on the trend-series margins:

- **Competitive**: latest margin is ~even; no durable lean in the current snapshot.
- **Stable**: durable lean with no sustained recent break (little directional change across cycles).
- **Reinforcing**: already leaned R/D and recent cycles strengthened that advantage.
- **Softening**: still leans R/D, but recent cycles narrowed that advantage.
- **Realigning**: crossed from D→R or R→D over the available history (a flip in long-run lean).

#### City vs county wording

The Trajectory Snapshot’s “Meaning” line uses `city` vs `county` based on the selected locality’s canonical name (e.g. `RICHMOND CITY` vs `RICHMOND COUNTY`). If a locality label arrives without a suffix, the front end falls back to Virginia’s independent-city list to decide whether it should read as a city or a county.

### Block Assignment Crosswalk

| File | Contents |
|---|---|
| `BlockAssign_ST51_VA.zip` | Census block-to-VTD assignment table (`BlockAssign_ST51_VA_VTD.txt`, pipe-delimited); also contains congressional, House of Delegates, and state-senate district assignments |

---

## Methodology

The pipeline runs in six sequential steps.  All scripts are in `scripts/` and accept command-line arguments with sensible defaults so they can be run from the repository root.

### Step 1 — Convert boundary ZIPs to GeoJSON

**Script**: `scripts/build_va_geojson_from_zips.py`

```
python scripts/build_va_geojson_from_zips.py [--data-dir Data]
```

Reads each Census TIGER/Line ZIP from `Data/`, finds the embedded `.shp` file, reprojects from NAD83 (EPSG:4269) to WGS 84 (EPSG:4326) using GeoPandas, and writes a `.geojson` alongside the ZIP.  Produces:

- `Data/tl_2020_51_county20.geojson`
- `Data/tl_2024_51_cd119.geojson`
- `Data/tl_2022_51_sldl.geojson`
- `Data/tl_2022_51_sldu.geojson`

These GeoJSON files are committed to the repository; the source ZIPs are not.

---

### Step 2 — Normalize election CSVs to OpenElections format

**Script**: `scripts/convert_va_csvs_to_openelections.py`

```
python scripts/convert_va_csvs_to_openelections.py \
    [--input-dir Data] \
    [--output-dir Data/openelections] \
    [--county-geojson Data/tl_2020_51_county20.geojson]
```

Detects input format by filename pattern and converts to a canonical 7-column OpenElections-style CSV:

```
county, precinct, office, district, party, candidate, votes
```

**Two input formats are supported:**

#### Wide format — `Virginia_Elections_Database__<YEAR>_<OFFICE>_General_Election_including_precincts.csv`

The first three rows are a multi-level header:

| Row index | Content |
|---|---|
| 0 | Candidate names (columns 3+) |
| 1 | Party affiliations |
| 2+ | Data rows: locality (col 0), precinct code (col 2), vote counts (cols 3+) |

The script skips any column whose header is `TOTAL VOTES CAST` or `TOTAL`.  Zero-vote entries are omitted.  Party strings are mapped to standardized abbreviations (`DEMOCRATIC` → `DEM`, `REPUBLICAN` → `REP`, etc.).

#### Long format — `Election Results_<GUID>.csv` (VADOE export)

One row per candidate per precinct.  Key columns used:

- `LocalityName` → county
- `PrecinctName` → precinct
- `OfficeTitle` → office
- `CandidateName` → candidate
- `Party` → party
- `TOTAL_VOTES` → votes
- `ElectionDate` → used to derive the output filename date token
- `DistrictType` / `DistrictName` → district (omitted for statewide offices)

**Output filename convention** (OpenElections standard):

```
<YYYYMMDD>__va__general__precinct__<office_slug>.csv
```

For example: `20091103__va__general__precinct__lieutenant_governor.csv`

A `manifest.json` is written to `Data/openelections/` listing every converted file with its input source and row count.

---

### Step 3 — Build precinct polygon GeoJSON

**Script**: `scripts/build_va_precincts_from_crosswalks.py`

```
python scripts/build_va_precincts_from_crosswalks.py \
    [--tabblock-zip Data/tl_2020_51_tabblock20.zip] \
    [--crosswalk-zip Data/BlockAssign_ST51_VA.zip] \
    [--county-geojson Data/tl_2020_51_county20.geojson] \
    [--openelections-dir Data/openelections] \
    [--output Data/va_precincts.geojson]
```

**How precinct polygons are built:**

1. Load Census 2020 tabulation block polygons from `tl_2020_51_tabblock20.zip`.
2. Load the VTD block-assignment crosswalk (`BlockAssign_ST51_VA_VTD.txt`) from `BlockAssign_ST51_VA.zip`.  This pipe-delimited file maps each 15-digit census block GEOID to a county FIPS code and a VTD district code.
3. Inner-join the blocks to the crosswalk on `GEOID20 == BLOCKID`.
4. Dissolve (union) all blocks sharing the same `(COUNTYFP, DISTRICT)` key.  The resulting polygon is the precinct boundary.
5. Enrich each precinct with a human-readable label sourced from the OpenElections CSVs.  The most-frequently-appearing label for a given `(county, precinct_code)` pair across all converted CSVs is selected as the canonical label.
6. Apply a legacy-code alias: if a VTD code matches the pattern `5XXX` (e.g., `5101`) and no OpenElections match is found, try stripping the leading `5` (→ `101`) before falling back to the raw VTD code.
7. Reproject to WGS 84 (EPSG:4326) and write `Data/va_precincts.geojson`.

Output GeoJSON properties per feature:

| Property | Description |
|---|---|
| `id` | Sequential integer (1-based) |
| `countyfp20` | 3-digit county FIPS code |
| `district_raw` | Raw VTD district code from crosswalk |
| `county_nam` | Canonical county/city name (e.g., `FAIRFAX COUNTY`) |
| `county_norm` | Uppercased, whitespace-normalized county name |
| `prec_id` | Canonicalized precinct code (e.g., `101`) |
| `precinct_name` | Human-readable label (e.g., `101 - ANNANDALE`) |
| `precinct_norm` | Compound key `COUNTY_NAME - PREC_ID` used for joins |

---

### Step 4 — Build precinct centroid GeoJSON

**Script**: `scripts/build_precinct_centroids_geojson.py`

```
python scripts/build_precinct_centroids_geojson.py \
    [--vtd-zip Data/tl_2020_51_vtd20.zip] \
    [--county-geojson Data/tl_2020_51_county20.geojson] \
    [--output Data/va_precinct_centroids.geojson] \
    [--openelections-dir Data/openelections]
```

Generates a lightweight point-geometry GeoJSON where each feature is located at the internal-point coordinate (`INTPTLAT20` / `INTPTLON20`) of the corresponding VTD polygon.  If the Census-supplied internal point is missing, `shapely`'s `representative_point()` is used as a fallback.

Centroid features carry the same `county_nam`, `prec_id`, `precinct_name`, and `precinct_norm` properties as the polygon GeoJSON to allow the front end to join them to election data.

---

### Step 5 — Build county-level contest slices

**Script**: `scripts/build_va_county_contests_from_openelections.py`

```
python scripts/build_va_county_contests_from_openelections.py \
    [--openelections-dir Data/openelections] \
    [--output-dir Data/contests] \
    [--county-geojson Data/tl_2020_51_county20.geojson]
```

Reads all OpenElections CSVs and aggregates votes at the county level, grouped by contest type and year.  Produces one JSON file per `(contest_type, year)` pair plus a `manifest.json`.

**Output schema per contest file** (`Data/contests/<contest_type>_<year>.json`):

```json
{
  "meta": {
    "contest_type": "president",
    "year": 2020,
    "rows": 133,
    "dem_total": 2413568,
    "rep_total": 1962430,
    "other_total": 69584,
    "total_votes": 4445582
  },
  "rows": [
    {
      "county": "ACCOMACK COUNTY",
      "dem_votes": 5832,
      "rep_votes": 7063,
      "other_votes": 226,
      "total_votes": 13121,
      "dem_candidate": "Joseph R. Biden",
      "rep_candidate": "Donald J. Trump",
      "winner": "Republican",
      "margin": 1231,
      "margin_pct": 9.38,
      "color": "#ef3b2c"
    },
    ...
  ]
}
```

Vote totals are bucketed into `dem`, `rep`, and `other`.  The leading Democratic and Republican candidates are identified by the highest vote total within each bucket per county.

---

### Step 6 — Build district-level contest slices

**Script**: `scripts/build_va_district_contests_from_crosswalks.py`

```
python scripts/build_va_district_contests_from_crosswalks.py \
    [--openelections-dir Data/openelections] \
    [--output-dir Data/district_contests] \
    [--result-overrides-csv Data/benchmarks/district_result_overrides.csv] \
    [--county-geojson Data/tl_2020_51_county20.geojson] \
    [--tabblock-zip Data/tl_2020_51_tabblock20.zip] \
    [--assign-zip Data/BlockAssign_ST51_VA.zip] \
    [--cd-geojson Data/tl_2024_51_cd119.geojson] \
    [--sldl-geojson Data/tl_2022_51_sldl.geojson] \
    [--sldu-geojson Data/tl_2022_51_sldu.geojson] \
    [--precinct-geojson Data/va_precincts.geojson]
```

This is the most complex script.  It answers: *"How did each congressional / House of Delegates / state-senate district vote in each statewide election?"*

Because statewide election results are reported by precinct (not by legislative district), votes must be **apportioned** from precincts into districts.

#### Geographic overlay method

For statewide contests (President, U.S. Senate, Governor, Lieutenant Governor, Attorney General):

1. Each VTD polygon is spatially intersected with each district polygon (projected to Web Mercator EPSG:3857 for area calculations).
2. For each VTD, the fraction of its total area that falls within each district is computed (`intersection_area / vtd_total_area`).
3. If a precinct falls entirely within one district (share ≈ 1.0), its votes go entirely to that district.
4. If a precinct straddles a district boundary, its votes are split proportionally by area share.
5. County-level fallback shares are computed simultaneously and blended in for precincts whose geometry cannot be reliably matched to any OpenElections precinct code.

#### County-specific blend factors

Some precincts in certain counties produce systematically poor area-share matches due to changed precinct boundaries between the Census 2020 VTD vintage and the election year.  A per-county `PARTY_FALLBACK_BLEND` factor (ranging from 0.15 to 1.00) controls how much of the district total is anchored to the county-wide party share rather than the precinct-centroid spatial match:

| County | Scope | Blend factor |
|---|---|---|
| Chesapeake City | Congressional | 0.55 |
| Stafford County | House of Delegates (HoD) | 1.00 |
| Chesterfield County | State Senate | 0.95 |
| Montgomery County | State Senate | 0.70 |
| Roanoke County | State Senate | 0.70 |
| Roanoke City | State Senate | 0.70 |
| Salem City | State Senate | 0.70 |

The default global blend for congressional districts is 0.35; for House of Delegates and state-senate districts it is 0.15.

#### Direct district contests (2023, 2025)

For contests that are *themselves* legislative-district races (Virginia House of Delegates 2023/2025, state Senate 2023), the office name encodes the district number directly (e.g., `Member, House of Delegates (13th District)`).  These are extracted via regex and aggregated without any geographic apportionment.

#### Output

One JSON file is written per `(scope, contest_type, year)` triple into `Data/district_contests/`, using the naming convention `<scope>_<contest_type>_<year>.json` where the scope key is one of `congressional`, `state_house` (House of Delegates), or `state_senate`.  A `manifest.json` index is also written.

#### Targeted district-result correction workflow

For the 2024 presidential congressional-district corrections (CD-01 and CD-02), run:

```
python scripts/fix_cd01_president_2024_totals.py
```

This utility:

1. Repairs known CSV newline corruption in `Data/benchmarks/district_result_overrides.csv`
2. Upserts exact override rows for `congressional/president/2024` districts `1` and `2`
3. Patches `Data/district_contests/congressional_president_2024.json`
4. Recomputes the corresponding manifest `dem_total` and `rep_total` values

Corrected totals applied by the script:

- CD-01: Dem `227,074`, Rep `250,992`, Other `8,529`
- CD-02: Dem `203,182`, Rep `204,265`, Other `6,695`

---

## Color Ramp & Rating Categories

### Visualization modes

The map supports three distinct visualization modes selectable from the controls panel:

| Mode | Description |
|---|---|
| **Margins** | Choropleth colored by the absolute two-party margin.  Encodes both *partisan direction* (red vs. blue) and *competitive intensity* (light = close, dark = blowout) in a single color. |
| **Winners** | Flat solid color by winning party (uniform red or blue), regardless of margin size. Useful for quickly reading which party carried each unit. |
| **Shift** | Change in the *signed* margin compared to the nearest prior election for the same contest type (e.g. 2020 → 2024 for President).  Positive shift = more Republican; negative shift = more Democratic. |

### Rating category system

Rather than using standard Cook Political Report-style labels, this project defines its own **8-tier rating vocabulary** that describes the *intensity* of a margin rather than just predicting a future outcome.  Each tier has a name that applies symmetrically to both parties.

| Category | Margin range | Rationale |
|---|---|---|
| **Annihilation** | ≥ 40.00 % | One party effectively has no opposition |
| **Dominant** | 30.00 – 39.99 % | One party is structurally dominant; the other is not competitive |
| **Stronghold** | 20.00 – 29.99 % | Very safe territory; base-vote geography |
| **Safe** | 10.00 – 19.99 % | Safely in hand barring a wave; roughly equivalent to "Safe" in standard ratings |
| **Likely** | 5.50 – 9.99 % | Favored, but a modest wave can flip it; equivalent to "Likely" in standard ratings |
| **Lean** | 1.00 – 5.49 % | Competitive with a clear lean; equivalent to "Lean" in standard ratings |
| **Tilt** | 0.50 – 0.99 % | Extremely close; a small shift in turnout or late-deciding voters could flip the result |
| **Tossup** | < 0.50 % | Statistical tie; shown in neutral grey |

Category names are shorthand for margin ranges only — they carry no predictive or future-race connotation.

### Color values

| Category | Republican color | Democrat color |
|---|---|---|
| Annihilation (≥ 40 %) | `#67000d` | `#08306b` |
| Dominant (30 – 39.99 %) | `#a50f15` | `#08519c` |
| Stronghold (20 – 29.99 %) | `#cb181d` | `#3182bd` |
| Safe (10 – 19.99 %) | `#ef3b2c` | `#6baed6` |
| Likely (5.50 – 9.99 %) | `#fb6a4a` | `#9ecae1` |
| Lean (1.00 – 5.49 %) | `#fcae91` | `#c6dbef` |
| Tilt (0.50 – 0.99 %) | `#fee8c8` | `#e1f5fe` |
| Tossup (< 0.50 %) | `#f7f7f7` (neutral grey) | `#f7f7f7` (neutral grey) |

The red palette is drawn from the ColorBrewer `Reds` sequential scheme; the blue palette from `Blues`.  Both use the same 8-stop progression so that equivalent margins read as perceptually equivalent intensities across party lines.

Margin is calculated as `|rep_votes - dem_votes| / total_votes × 100`.

---

## Locality Canonicalization

Virginia's election data uses several inconsistent forms for the same jurisdiction (e.g., `City of Alexandria`, `ALEXANDRIA CITY`, `Alexandria`).  Every script that reads locality names builds a single **alias map** derived from the Census TIGER county GeoJSON (`NAMELSAD20` field):

1. Parse `NAMELSAD20` to extract a `(base_name, suffix)` pair where suffix is `COUNTY`, `CITY`, or `TOWN`.
2. Generate all known alias forms for the canonical name:
   - `FAIRFAX COUNTY` → also matches `FAIRFAX`
   - `ALEXANDRIA CITY` → also matches `ALEXANDRIA`, `CITY OF ALEXANDRIA`
3. Keep only aliases that map unambiguously to a single canonical locality.

This alias map is applied to every `county` field in source CSVs before any aggregation, ensuring that all scripts use identical locality keys for joins.

This also handles county/city name collisions: if both `RICHMOND COUNTY` and `RICHMOND CITY` exist, the bare alias `RICHMOND` is considered ambiguous and is dropped, so joins stay deterministic.

On the front end, the same principle now applies to search, hover, tooltip, vote-counter pinning, and the selected-locality detail panel:

- Independent cities are always treated as distinct geographic units, never as part of counties
- Display labels keep the Virginia suffix explicit (`Richmond City`, `Richmond County`, `Fairfax City`, `Fairfax County`)
- Bare ambiguous names are surfaced as suggestions rather than silently resolving to the wrong locality
- County-style suffix localities such as `James City County` and `Charles City County` remain counties and are not mis-normalized into independent cities

### Selected locality storytelling

When a county or independent city is selected, the atlas now presents a newsroom-style focus panel designed to answer the locality question quickly:

- **Top line**: winner, margin, and a one-sentence takeaway
- **Confidence**: low / medium / high based on margin strength and trend stability
- **Compared with Virginia**: how far left or right of the statewide result the locality voted
- **Archetype + explanation**: a human-readable Virginia-specific profile such as a Northern Virginia Democratic stronghold, Richmond-area suburban battleground, Tidewater swing locality, military-heavy coastal locality, or Appalachian Republican base
- **Why It Votes This Way**: short analyst-style copy tying together geography, trend, and population change
- **Deeper context**: collapsible vote breakdown, recent history, demographics, and non-geographic vote buckets

---

## Precinct Matching & Label Enrichment

Precinct identifiers in source CSVs often differ from Census VTD codes:

- Leading zeros may be present or absent (`101` vs. `0101`)
- Some counties use a 4-digit prefix matching the Census state+county FIPS (`5101` → real code `101` for county FIPS 051)
- Precinct names may include trailing district annotations like `(CD 2)` that must be stripped

The pipeline normalizes precinct codes with the following rules:

1. Strip all characters except `A-Z`, `0-9`, `.`, `-`
2. If the result is purely numeric, convert to integer string to remove leading zeros (`0101` → `101`)
3. If the VTD code matches `5\d{2,}` and the truncated form (dropping the leading `5`) exists in OpenElections data for the same county, use the truncated form

For polygon and centroid GeoJSON features the `precinct_norm` compound key `COUNTY_NAME - PREC_ID` is stored to enable O(1) map lookups at render time.

---

## Front-End Architecture

The entire front end lives in `index.html` — a single self-contained file with no build toolchain.

### Recent `index.html` maintenance

- Reverted precinct normalization away from NC-specific alias and override hooks so Virginia precinct codes are matched using the narrower `.v1`-style rules.
- Restored precinct-detail row loading in precinct mode so statewide dot mode colors from precinct rows instead of county rows.
- Reintroduced centroid-backed precinct norm indexes and label-based fallback matching used to resolve rows whose code token drifted but whose precinct label still matches loaded geometry.
- Added county-level redistribution/backfill for unmatched geographic precinct rows so renamed or split precincts still receive a bounded color assignment instead of dropping out entirely.

Those changes are the reason the current `main` branch once again populates precinct colors correctly in precinct mode.

---

## Index File Lineage

The repository contains several HTML snapshots that reflect how the front end evolved:

| File | Status | Purpose |
|---|---|---|
| `index.html` | Current | Canonical production front end on `main` |
| `index.v1.html` | Reference | Earlier Virginia-only baseline used to compare precinct centroid behavior and matching logic |
| `index.lastcommit.html` | Archive | Saved prior committed state for rollback/comparison |
| `index_no_rating_title_badge_fixed.html` | Archive | UI variant preserving an earlier rating-title/badge fix |
| `index_va_trajectory_wrap_patched.html` | Archive | Trajectory-layout patch snapshot |

The most important practical distinction is between `index.html` and `index.v1.html`:

- `index.v1.html` is the clean Virginia reference for older centroid matching behavior.
- `index.html` is the living front end, but its current precinct-mode logic was intentionally brought back into alignment with `.v1` after NC-specific normalization drift caused precinct dots to stop populating reliably.

When debugging future precinct regressions, compare `index.html` against `index.v1.html` first before assuming the broader NCMap-derived behavior is correct for Virginia.

**Runtime dependencies (CDN):**

| Library | Version | Purpose |
|---|---|---|
| Mapbox GL JS | 3.0.1 | WebGL map rendering |
| Turf.js | 6.5.0 | Bounding-box computation for fly-to |
| PapaParse | 5.4.1 | CSV parsing |
| Google Fonts (Manrope, IBM Plex Sans) | — | Typography |

**Data loading:**

- All GeoJSON boundary files and contest JSON slices are loaded at startup or on-demand via `fetch()`.
- A `manifest.json` in each data directory tells the front end which contest/year combinations exist, enabling the contest dropdowns to be populated dynamically.

**Map layers (Mapbox GL sources and layers):**

| Source | Layer type | Purpose |
|---|---|---|
| County GeoJSON | Fill + line | County choropleth base, hover state |
| Precinct GeoJSON | Fill + line | Precinct-level overlay (toggled) |
| Congressional GeoJSON | Fill + line | Congressional district choropleth |
| SLDL GeoJSON | Fill + line | House of Delegates district choropleth |
| SLDU GeoJSON | Fill + line | State Senate district choropleth |
| Precinct centroids GeoJSON | Circle / symbol | Precinct dot mode at low zoom |

**Responsive design:**

- CSS custom properties `--safe-top/right/bottom/left` are set from `env(safe-area-inset-*)` for iOS notch and home-indicator clearance.
- Stable and dynamic viewport units (`svh`, `dvh`) prevent chrome-bar resize jumps on mobile browsers.
- Font inputs are locked at `font-size: 16px` on mobile to prevent iOS auto-zoom on focus.
- Panels (controls, legend) are repositioned to top-sheet and bottom-sheet cards on screens ≤ 768 px.
- Android Chrome receives separate inset adjustments via `VisualViewport` API events.

**Vote counter layout safeguards:**

- The top-right vote breakdown uses tabular numerals and constrained card geometry to keep totals visually aligned.
- A runtime overflow check measures each vote tile (`label`, `count`, and header width). When overflow is detected, the tile gets a `layout-stacked` class so text wraps instead of clipping.
- Overflow checks run after counter animations complete, on viewport resize, and after candidate-label updates.

### Hover Tooltip UX

The hover tooltip is designed to be **fast, low-clutter, and Virginia-safe** (county vs. independent-city naming).

**Desktop (fine pointer / mouse):**

- Moving the cursor over a feature shows a compact tooltip near the cursor.
- The tooltip is intentionally “read-only” until you `Pin` it; this keeps hover responsive and avoids accidental UI captures while panning.
- `Pin` freezes the tooltip (it stops following the cursor and stops hover-refresh) and reveals the expandable `Details` section and the `Close` button.
- `Close` dismisses the tooltip and suppresses immediate re-open for the same hovered feature until the pointer moves (prevents “close → instantly re-open” flicker).

**Mobile / touch (coarse pointer):**

- Tapping a feature pins the tooltip (so you can scroll the tooltip and interact with its controls).
- The tooltip docks above the legend and vote counter to avoid UI stacking/overlap on small screens.

**What the tooltip shows:**

- **Winner call line** (e.g., `Trump +3.12%`) with party-tinted text on the dark tooltip surface.
- **Flip context** (when a flip occurred vs the prior comparable election):
  - A Flip line (e.g., `Flip: D→R (20→24)`).
  - A Flip chip (desktop) to make flips scannable without expanding.
- **Delta block** (when prior-cycle county totals exist):
  - `Raw votes (YY→YY): R ±… • D ±… • Total ±…` (party-colored, NC-style).
  - Optional population-change lines (from `Data/CO-EST2025-POP-51-clean.csv`), when loaded.
- **Details (pinned only):** a full result card with vote totals and percent shares, plus meta chips (winner, rating tier, and—depending on context—shift/flip).

**Flip vs. shift context (to reduce clutter):**

- In `Shift` mode, the meta-chip row swaps in a Shift chip (vs the prior comparable election).
- In `Flips` mode, the tooltip surfaces flip-specific context.
- District hover cards use the same chip vocabulary (Winner/Tier/Shift/Flip) so counties and districts read consistently.

**County vs. precinct vs. district:**

- **Counties / independent cities:** compact margin call + tier, optional Flip line/chip, and (when available) the NC-style raw vote delta block; pinned `Details` expands to the full result card + chips.
- **Districts (CD / HoD / State Senate):** desktop hover uses the chip row + full result card; compact (mobile) shows quickline + Flip line when applicable.
- **Precincts:** compact hover call; Flip line appears when prior precinct margins are available (typically in `Shift`/`Flips` contexts where prior-precinct caches are loaded).

**Color conventions inside the tooltip:**

- Democratic: blues; Republican: reds; Other/third-party: grays; tossups: neutral.
- Vote-share bars use solid colors: Dem `#3b82f6`, Other `#9ca3af`, Rep `#ef4444`.
- Raw vote deltas in the delta block tint `R` red and `D` blue to match the hover call line.

**Validation:**

- The selected-locality experience was smoke-tested in headless Chrome against the live single-file app served locally.
- The smoke pass verified exact matching and distinct rendering for `Fairfax City` vs `Fairfax County`, `Richmond City` vs `Richmond County`, and `James City County`.
- The same pass also verified that ambiguous bare-name searches do not auto-merge and that the upgraded locality panel renders its `Confidence`, `Compared with Virginia`, and `Why It Votes This Way` sections.

---

## Dependencies

### Python (data pipeline)

| Package | Minimum version | Purpose |
|---|---|---|
| `geopandas` | 0.13 | Shapefile I/O, CRS reprojection, spatial dissolve |
| `shapely` | 2.0 | Geometry operations, representative points |
| `pandas` | 2.0 | Tabular data manipulation, merges |

Standard library only (`csv`, `json`, `re`, `zipfile`, `argparse`, `collections`, `pathlib`) — no additional installs beyond the above.

### JavaScript (front end, CDN)

- Mapbox GL JS 3.0.1
- Turf.js 6.5.0
- PapaParse 5.4.1

---

## Known Limitations & Future Work

- **Precinct boundary vintage mismatch** — The precinct polygons are based on Census 2020 VTDs.  Precincts are routinely redrawn between elections, so boundaries may not exactly match the practical precincts used in 2009, 2017, or 2025.  The county-specific blend factors in Step 6 partially mitigate this for district apportionment.

- **Absentee / provisional / early-vote precincts** — Non-geographic precincts (absentee, provisional, mail, curbside) are excluded from district apportionment because they cannot be assigned a spatial location.  Their votes are included in county-level totals but cannot be attributed to a sub-county district.

- **District boundary mismatch** — Congressional and state legislative boundaries change after each decennial redistricting cycle.  The 2022 redistricting lines are used for all years shown, which introduces a known anachronism for pre-2022 election results.

- **2023 state legislative districts** — Returns for the 2023 Virginia House of Delegates and Senate of Virginia elections are available in the district contest files, but some precinct-to-district boundary edge cases may affect margins in split precincts.

- **Possible additions** — presidential primary results, special elections, swing-shift annotation (margin change between election cycles), downloadable data tables per district.

- **Newly added (May 2026)** — U.S. House district contest slices aligned to current congressional lines for 2022 and 2024 are now included in `Data/district_contests/` as `congressional_us_house_2022.json` and `congressional_us_house_2024.json`.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

