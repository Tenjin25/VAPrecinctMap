# Change history

## 2026-11-25: Virginia district aggregation

- Moved dated interface notes out of the README and added a concise aggregation overview there. The allocation below was already in the pipeline; this entry documents how it works.
- For statewide contests projected onto the displayed district lines, a county or independent city contained at least 99.9% in one district contributes its exact reported locality vote. Only split-locality components use geographic allocation. Qualifying multi-district locality clusters are reconciled to their combined official vote, and largest-remainder rounding preserves statewide party totals.
- Virginia treats independent cities as separate county-equivalent localities. The tables below come from the tracked [locality-component reconciliation report](Data/district_contests/locality_component_reconciliation_report.json); they describe statewide-race projections, not direct district races.

### Congressional districts

| District | Exact whole-locality component | Allocated split-locality component | Example before → after |
|---|---|---|---|
| VA-01 | Essex County; Gloucester County; James City County; King and Queen County; King William County; Lancaster County; Mathews County; Middlesex County; New Kent County; Northumberland County; City of Poquoson; Richmond County; Westmoreland County; City of Williamsburg; York County | Chesterfield County; Hanover County; Henrico County | — |
| VA-02 | Accomack County; City of Franklin; Isle of Wight County; Northampton County; City of Suffolk; City of Virginia Beach | City of Chesapeake; Southampton County | 2024 president: R+0.260% → R+0.233% |
| VA-03 | City of Hampton; City of Newport News; City of Norfolk; City of Portsmouth | City of Chesapeake | — |
| VA-04 | Brunswick County; Charles City County; City of Colonial Heights; Dinwiddie County; City of Emporia; Greensville County; City of Hopewell; City of Petersburg; Prince George County; City of Richmond; Surry County; Sussex County | Chesterfield County; Henrico County; Southampton County | — |
| VA-05 | Amelia County; Amherst County; Appomattox County; Buckingham County; Campbell County; Charlotte County; City of Charlottesville; Cumberland County; City of Danville; Fluvanna County; Goochland County; Halifax County; Louisa County; Lunenburg County; City of Lynchburg; Mecklenburg County; Nelson County; Nottoway County; Pittsylvania County; Powhatan County; Prince Edward County | Albemarle County; Bedford County; Hanover County | — |
| VA-06 | Alleghany County; Augusta County; Bath County; Botetourt County; City of Buena Vista; Clarke County; City of Covington; Frederick County; City of Harrisonburg; Highland County; City of Lexington; Page County; City of Roanoke; Rockbridge County; Rockingham County; City of Salem; Shenandoah County; City of Staunton; Warren County; City of Waynesboro; City of Winchester | Roanoke County | — |
| VA-07 | Caroline County; Culpeper County; City of Fredericksburg; Greene County; King George County; Madison County; Orange County; Spotsylvania County; Stafford County | Albemarle County; Prince William County | — |
| VA-08 | City of Alexandria; Arlington County; City of Falls Church | Fairfax County | — |
| VA-09 | Bland County; City of Bristol; Buchanan County; Carroll County; Craig County; Dickenson County; Floyd County; Franklin County; City of Galax; Giles County; Grayson County; Henry County; Lee County; City of Martinsville; Montgomery County; City of Norton; Patrick County; Pulaski County; City of Radford; Russell County; Scott County; Smyth County; Tazewell County; Washington County; Wise County; Wythe County | Bedford County; Roanoke County | — |
| VA-10 | Fauquier County; Loudoun County; City of Manassas; City of Manassas Park; Rappahannock County | Fairfax County; Prince William County | — |
| VA-11 | City of Fairfax | Fairfax County | 2024 president: D+34.000% → D+34.059%; 2026 Senate breakdown below |

### House of Delegates districts

| District | Exact whole-locality component | Allocated split-locality component | Example before → after |
|---|---|---|---|
| HD-11 | City of Fairfax | Fairfax County | — |
| HD-13 | City of Falls Church | Fairfax County | — |
| HD-20 | City of Manassas; City of Manassas Park | Prince William County | — |
| HD-31 | Clarke County | Frederick County; Warren County | — |
| HD-32 | City of Winchester | Frederick County | — |
| HD-33 | Page County; Shenandoah County | Rockingham County; Warren County | — |
| HD-34 | City of Harrisonburg | Rockingham County | — |
| HD-35 | Bath County; Highland County | Augusta County; Rockingham County | — |
| HD-36 | City of Staunton; City of Waynesboro | Augusta County; Rockbridge County | — |
| HD-37 | Alleghany County; Botetourt County; City of Buena Vista; City of Covington; Craig County; City of Lexington | Rockbridge County | — |
| HD-39 | Franklin County | Roanoke County | — |
| HD-40 | City of Salem | City of Roanoke; Roanoke County | — |
| HD-42 | Giles County; City of Radford | Montgomery County; Pulaski County | — |
| HD-43 | Bland County; Buchanan County; Tazewell County | Dickenson County; Russell County | — |
| HD-44 | City of Bristol; Washington County | Russell County | — |
| HD-45 | Lee County; City of Norton; Scott County; Wise County | Dickenson County | 2024 U.S. Senate: R+66.940% → R+54.061% |
| HD-46 | Grayson County; Smyth County; Wythe County | Pulaski County | — |
| HD-47 | Carroll County; Floyd County; City of Galax; Patrick County | Henry County | — |
| HD-48 | City of Martinsville | Henry County; Pittsylvania County | — |
| HD-49 | City of Danville | Halifax County; Pittsylvania County | — |
| HD-50 | Charlotte County; Lunenburg County; Mecklenburg County | Halifax County; Prince Edward County | — |
| HD-52 | City of Lynchburg | Campbell County | — |
| HD-53 | Amherst County | Bedford County; Nelson County | — |
| HD-54 | City of Charlottesville | Albemarle County | — |
| HD-56 | Appomattox County; Buckingham County; Cumberland County | Fluvanna County; Goochland County; Prince Edward County | — |
| HD-61 | Rappahannock County | Culpeper County; Fauquier County | — |
| HD-62 | Greene County; Madison County | Culpeper County; Orange County | — |
| HD-65 | City of Fredericksburg | Spotsylvania County; Stafford County | — |
| HD-67 | King George County; Lancaster County; Northumberland County; Richmond County; Westmoreland County | Caroline County | — |
| HD-68 | Essex County; King and Queen County; King William County; Mathews County; Middlesex County | Gloucester County | — |
| HD-71 | City of Williamsburg | James City County; New Kent County | — |
| HD-72 | Amelia County; Nottoway County; Powhatan County | Chesterfield County | — |
| HD-74 | City of Colonial Heights | Chesterfield County | — |
| HD-75 | City of Hopewell | Chesterfield County; Prince George County | — |
| HD-81 | Charles City County | Chesterfield County; Henrico County | — |
| HD-82 | City of Petersburg; Surry County | Dinwiddie County; Prince George County | — |
| HD-83 | Brunswick County; City of Emporia; Greensville County; Southampton County; Sussex County | Dinwiddie County; Isle of Wight County | — |
| HD-84 | City of Franklin | Isle of Wight County; City of Suffolk | 2024 U.S. Senate: D+14.438% → D+17.808% |
| HD-86 | City of Poquoson | City of Hampton; York County | — |
| HD-100 | Accomack County; Northampton County | City of Virginia Beach | — |

### State Senate districts

| District | Exact whole-locality component | Allocated split-locality component | Example before → after |
|---|---|---|---|
| SD-2 | Bath County; City of Harrisonburg; Highland County; Page County; Rockingham County | Augusta County | — |
| SD-3 | Alleghany County; Botetourt County; City of Buena Vista; City of Covington; Craig County; City of Lexington; Rockbridge County; City of Staunton; City of Waynesboro | Augusta County; Roanoke County | — |
| SD-4 | City of Roanoke; City of Salem | Montgomery County; Roanoke County | 2024 president: R+1.291% → R+1.248% |
| SD-5 | Bland County; Giles County; Pulaski County; City of Radford; Smyth County; Tazewell County | Montgomery County; Wythe County | — |
| SD-7 | Carroll County; Floyd County; Franklin County; City of Galax; Grayson County; Henry County; City of Martinsville; Patrick County | Wythe County | — |
| SD-9 | Charlotte County; City of Danville; Halifax County; Lunenburg County; Mecklenburg County; Nottoway County; Pittsylvania County | Prince Edward County | — |
| SD-10 | Amelia County; Appomattox County; Buckingham County; Cumberland County; Fluvanna County; Goochland County; Powhatan County | Hanover County; Louisa County; Prince Edward County | — |
| SD-11 | Albemarle County; Amherst County; City of Charlottesville; Nelson County | Louisa County | — |
| SD-12 | City of Colonial Heights | Chesterfield County | — |
| SD-13 | Charles City County; City of Hopewell; City of Petersburg; Prince George County; Surry County; Sussex County | Dinwiddie County; Henrico County | — |
| SD-17 | Brunswick County; City of Emporia; City of Franklin; Greensville County; Isle of Wight County; Southampton County; City of Suffolk | Dinwiddie County; City of Portsmouth | — |
| SD-20 | Accomack County; Northampton County | City of Norfolk; City of Virginia Beach | 2024 president: R+3.090% → R+3.021% |
| SD-23 | City of Hampton | City of Newport News | — |
| SD-24 | City of Poquoson; City of Williamsburg; York County | James City County; City of Newport News | — |
| SD-25 | Caroline County; Essex County; King George County; King William County; Lancaster County; Middlesex County; Northumberland County; Richmond County; Westmoreland County | King and Queen County; Spotsylvania County | — |
| SD-26 | Gloucester County; Mathews County; New Kent County | Hanover County; James City County; King and Queen County | — |
| SD-27 | City of Fredericksburg | Spotsylvania County; Stafford County | — |
| SD-28 | Culpeper County; Greene County; Madison County; Orange County; Rappahannock County | Fauquier County; Spotsylvania County | — |
| SD-30 | City of Manassas; City of Manassas Park | Prince William County | — |
| SD-37 | City of Fairfax; City of Falls Church | Fairfax County | — |
| SD-39 | City of Alexandria | Arlington County; Fairfax County | — |

These tables list all 72 mixed districts in the tracked report. Districts containing only split localities are excluded because they have no exact whole-locality component. The component classification uses 2020 Census voting-age population assigned to the official 2021 district plan. The before → after examples compare vote-derived margins in the first reconciliation commit (`4cdfcc7`) with its parent; they are historical comparisons, not 2026 changes.

For a numeric example, the 2024 presidential result in **VA-11** keeps the City of Fairfax's reported **8,797 Democratic / 4,302 Republican / 468 other** votes exact. Its allocated Fairfax County portion adds **258,618 / 123,431 / 14,505**, producing the published district total of **267,415 / 127,733 / 14,973**. The county portion is estimated; the independent city's vote is not reweighted.

For a recent example, the current **2026 U.S. Senate** files give VA-11 the City of Fairfax's **8,540 Democratic / 2,800 Republican / 27 other** votes plus an allocated Fairfax County portion of **249,707 / 78,012 / 1,320**, totaling **258,247 / 80,812 / 1,347** (D+52.125%). This is a breakdown of the current district result; the 2026 contest is outside the tracked 78-slice reconciliation report.

The original reconciliation commit and the later tracked report capture different comparisons:

| Comparison | Observed result |
|---|---|
| First reconciliation commit (`4cdfcc7` versus its parent) | Votes changed in 2,080 district rows across 78 statewide slices. The largest vote-derived margin movement was 12.879 percentage points (HD-45, 2024 U.S. Senate). Five split-only House districts changed winner in that Senate projection: HD-30, HD-41, HD-64, HD-66, and HD-69. |
| Later tracked reconciliation report | Official Democratic, Republican, and other statewide totals match in all 78 slices. Margin changes appear in 157 district rows across four slices; the largest was 0.0313 percentage point (HD-35, 2016 presidential result), and no winners changed in that later run. |

## 2026-11-20

- Refresh November 2026 Senate, House, and three constitutional amendment returns from Virginia's November 20 official export; rebuild county, district, and DRA files, preserve the April amendment and HD-20, and bump the cache token to `2026-11-20-va-results-refresh-v1`.

## 2026-11-14

- Refresh the November 2026 U.S. Senate, U.S. House, and constitutional-amendment results from Virginia's November 13 post-canvass media export; rebuild the county, district, and block-level DRA files while leaving HD-20 unchanged; and bump the cache token to `2026-11-14-post-canvass-2026-results-v1`.

## 2026-11-06

- Pre-aggregate identical precinct/candidate rows before crosswalk allocation and restrict multi-office inputs to the active exports listed in the OpenElections manifest, preventing superseded snapshots from being merged twice.
- Show each constitutional amendment by its descriptive ballot title, use shortened Q1/Q2/Q3 labels in the dropdown, keep the April redistricting amendment in the shared amendment group, use compact legend headings, allow Statewide contest labels to wrap, omit the redundant year from space-limited amendment labels, and bump the cache token to `2026-11-06-unofficial-2026-results-v8`.
- Refresh the 2026 statewide, congressional, and November amendment returns from Virginia's 1:08 PM unofficial media export while leaving HD-20 unchanged.
- Restore the voided April congressional-redistricting referendum as a separately labeled historical layer and give all three November amendments descriptive ballot-subject labels.
- Rebuild DRA imports at 2020 Census block level to prevent DRA's VTD disaggregation from displaying negative Other votes, and bump the cache token to `2026-11-06-unofficial-2026-results-v3`.

## 2026-11-05

- Add unofficial 2026 U.S. Senate results by county, congressional district, House of Delegates district, and state Senate district.
- Add unofficial 2026 U.S. House results for all eleven congressional districts and the House of Delegates District 20 special election.
- Keep district result keys and manifest entries in numerical order and refresh the application/data cache token to `2026-11-05-unofficial-2026-results-v1`.
- Refresh every 2026 statewide and congressional result except HD-20 from Virginia's 8:46 PM official media export, including write-ins.
- Replace the voided April referendum layer with November Constitutional Amendment Questions 1, 2, and 3, rebuild DRA import CSVs, and bump the cache token to `2026-11-05-unofficial-2026-results-v2`.

## 2026-10-23

- Wire the precinct-level 2020–2024 ACS CVAP aggregate into demographics shading and precinct hover totals.
- Reject empty fetch paths instead of accidentally downloading and parsing `index.html` as CSV.
- Add the validated 2,465-row precinct CVAP deployment artifact and refresh the cache token to `2026-10-23-precinct-cvap-loader-v4`.
- Match the expanded **The Commonwealth Explorer** title dot to the minimized title pill's gold marker.
- Explicitly include Virginia independent cities in the Fly-to headline, accessible search label, and control-panel guidance.
- Refresh the application and data cache token to `2026-10-23-expanded-title-dot-v3`.
- Move **The Commonwealth Explorer** into the control panel's primary title pill, matching the NCPrecinctMap control hierarchy.
- Use the search panel headline for its action—flying to a county, independent city, district, or precinct—and keep the project title visible in the collapsed controls state.
- Retry JSON and CSV requests after transient network failures, rate limits, and HTTP `5xx` responses before failing application startup.
- Use a cache reload for retry attempts so an initial service error cannot strand the current page load.
- Remove the stale North Carolina county-geometry fallback from Virginia startup and search initialization.
- Surface a Virginia-specific loading error if the county geometry remains unavailable after all retry attempts.
- Refresh the application and data cache token to `2026-10-23-transient-data-retry-v1`.

## 2026-10-18

- Prevent bare locality searches from silently selecting the first matching Virginia geography when a county and independent city share a base name.
- Show explicit county and independent-city choices for the four Census-name collisions: Fairfax, Franklin, Richmond, and Roanoke.
- Match qualified searches such as `Richmond County`, `City of Richmond`, and `Richmond City` directly to their canonical geography.
- Build Fly-to suggestions from full Census locality labels instead of ambiguous base names and identify independent cities in suggestion metadata.
- Keep the mobile search sheet open while the user resolves an ambiguous locality.
- Refresh the application and data cache token to `2026-10-18-locality-search-disambiguation-v1`.

## 2026-10-07

- Add the 2026 constitutional-amendment contest with VAP-weighted county, congressional, House of Delegates, and state Senate results.
- Simplify Quick Jumps to six primary destinations with additional Virginia regions grouped under an expandable **More regions** control.
- Add Fredericksburg, Lynchburg, Northern Neck & Middle Peninsula, Northern Piedmont, and Alleghany Highlands regional jumps.
- Expand the Southside jump west through Martinsville, Henry, and Patrick and east through Brunswick, Greensville, and Emporia.
- Add active-region styling, a live geography breadcrumb, automatic region clearing after out-of-region pans, and mobile-sheet settling after map navigation.
- Standardize the Fly-to suggestions to the spaced `CD 2`, `HD 57`, and `SD 31` style while retaining support for hyphenated searches.
- Preserve the latest compact winner-name changes from `main` and refresh the application/data cache token to `2026-10-07-district-labels-v9`.

## 2026-10-06

- Unlock the contest selector as soon as its manifest is ready instead of waiting for optional district geometry and demographic files.
- Begin fetching the contest manifest immediately instead of waiting for map-idle and browser-idle delays.
- Automatically collapse the mobile legend after selected election results finish loading.
- Start atlas hydration as soon as the Mapbox map is ready, avoiding mobile delays caused by waiting for every window asset.
- Preserve two-decimal margin precision for close results and competitiveness thresholds (for example, 0.45%).
- Refresh application and data cache tokens, plus shared-module asset tokens where present; repair shared module loading where needed.

## 2026-05-12

- Add compact VoteHub-style hover cards for precincts, congressional districts, House of Delegates districts, and state Senate districts; retain the richer locality tooltip.
- Show the winner-line margin with `%` and optional party-colored flip callouts.
- Align compact-card decimals with the front-end display pipeline while preserving map colors, the selected-locality panel, trends, and mobile docking.

## March–October 2026

**Last updated:** October 4, 2026

### Consistent District Demographic Pill Sizing (October 4, 2026)

- Applied the populated Demographics-mode compact pill styling to district demographic cards before election results load.
- Preserved the original natural popup dimensions and complete highest-to-lowest demographic layout; only the pill scale and spacing are unified.

### Descending Demographic Percentages (October 4, 2026)

- Sorted demographic race/ethnicity percentages from highest to lowest across the atlas's demographic cards.
- Kept unavailable Hispanic data at the end of the list so known percentages remain easy to scan.
