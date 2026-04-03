# The Commonwealth Explorer (2008–2025)

An interactive, browser-based choropleth map of Virginia election results at the precinct, county, and legislative/congressional district level, covering every major statewide general election from 2008 through 2025.

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
10. [Dependencies](#dependencies)
11. [Known Limitations & Future Work](#known-limitations--future-work)

---

## Project Overview

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
| **Hover tooltip** | Shows locality/district quick results; tap/click holds tooltip and `Close` dismisses it (no pin/unpin control) |
| **Selected locality panel** | Newsroom-style county/city focus panel with a dominant winner/margin summary, confidence meter, Virginia comparison, dynamic archetype, and a collapsible deeper-context section |
| **Focus trend panel** | NC-style trend layout in the vote counter with `Latest`, `Closest`, `Since`, and per-year timeline cards, plus a **Trajectory Snapshot** and optional **Census insight** (Vintage 2025) with corridor tags to explain how/why a partisan lean can form |
| **Winner labeling** | Desktop winner pill shows full candidate names (for example, `Donald J. Trump (R)`), while statewide headline keeps short labels |
| **NCMap parity styling** | Right-rail controls, legend, and vote counter surfaces are aligned with the latest `NCMap.html` layout language |
| **Locality search** | Free-text search with fly-to animation using turf bbox for counties, independent cities, precincts, and districts |
| **Virginia-safe alias handling** | Independent-city queries accept both `City of ...` and `... City` forms, while ambiguous bare names like `Fairfax` or `Richmond` are not auto-merged and instead require a city/county distinction |
| **Vote-card overflow fallback** | Top-right vote tiles auto-switch to stacked card layout when labels/counts overflow, preventing truncation of large totals |
| **Mobile-first layout** | iOS safe-area insets, stable viewport units (`svh`/`dvh`), touch-friendly controls, bottom-sheet legend |
| **Minimizable panels** | Controls, legend, and the top-right results panel can be collapsed to free map space |

---

## Repository Structure

```
VAPrecinctMap/
├── index.html                          # Single-file front-end (Mapbox GL JS, styles, JS)
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

- **Possible additions** — presidential primary results, special elections, U.S. House of Representatives by district, swing-shift annotation (margin change between election cycles), downloadable data tables per district.
