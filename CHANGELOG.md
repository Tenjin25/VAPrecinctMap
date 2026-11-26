# Change history

## 2026-11-25: Virginia district aggregation

- Moved dated interface notes out of the README and added a concise aggregation overview there. The allocation below was already in the pipeline; this entry documents how it works.
- For statewide contests projected onto the displayed district lines, a county or independent city contained at least 99.9% in one district contributes its exact reported locality vote. Only split-locality components use geographic allocation. Qualifying multi-district locality clusters are reconciled to their combined official vote, and largest-remainder rounding preserves statewide party totals.
- Virginia treats independent cities as separate county-equivalent localities. The tables below come from the tracked [locality-component reconciliation report](Data/district_contests/locality_component_reconciliation_report.json); they describe statewide-race projections, not direct district races.

### Congressional districts

| District | Exact whole-locality component | Allocated split-locality component | 2024 presidential winner, before → after |
|---|---|---|---|
| VA-01 | Essex County; Gloucester County; James City County; King and Queen County; King William County; Lancaster County; Mathews County; Middlesex County; New Kent County; Northumberland County; City of Poquoson; Richmond County; Westmoreland County; City of Williamsburg; York County | Chesterfield County; Hanover County; Henrico County | Trump +4.91% → Trump +4.89% |
| VA-02 | Accomack County; City of Franklin; Isle of Wight County; Northampton County; City of Suffolk; City of Virginia Beach | City of Chesapeake; Southampton County | Trump +0.26% → Trump +0.24% |
| VA-03 | City of Hampton; City of Newport News; City of Norfolk; City of Portsmouth | City of Chesapeake | Harris +34.56% → Harris +34.58% |
| VA-04 | Brunswick County; Charles City County; City of Colonial Heights; Dinwiddie County; City of Emporia; Greensville County; City of Hopewell; City of Petersburg; Prince George County; City of Richmond; Surry County; Sussex County | Chesterfield County; Henrico County; Southampton County | Harris +32.58% → Harris +32.64% |
| VA-05 | Amelia County; Amherst County; Appomattox County; Buckingham County; Campbell County; Charlotte County; City of Charlottesville; Cumberland County; City of Danville; Fluvanna County; Goochland County; Halifax County; Louisa County; Lunenburg County; City of Lynchburg; Mecklenburg County; Nelson County; Nottoway County; Pittsylvania County; Powhatan County; Prince Edward County | Albemarle County; Bedford County; Hanover County | Trump +12.22% → Trump +12.24% |
| VA-06 | Alleghany County; Augusta County; Bath County; Botetourt County; City of Buena Vista; Clarke County; City of Covington; Frederick County; City of Harrisonburg; Highland County; City of Lexington; Page County; City of Roanoke; Rockbridge County; Rockingham County; City of Salem; Shenandoah County; City of Staunton; Warren County; City of Waynesboro; City of Winchester | Roanoke County | Trump +24.08% → Trump +24.08% |
| VA-07 | Caroline County; Culpeper County; City of Fredericksburg; Greene County; King George County; Madison County; Orange County; Spotsylvania County; Stafford County | Albemarle County; Prince William County | Harris +2.86% → Harris +2.82% |
| VA-08 | City of Alexandria; Arlington County; City of Falls Church | Fairfax County | Harris +49.28% → Harris +49.33% |
| VA-09 | Bland County; City of Bristol; Buchanan County; Carroll County; Craig County; Dickenson County; Floyd County; Franklin County; City of Galax; Giles County; Grayson County; Henry County; Lee County; City of Martinsville; Montgomery County; City of Norton; Patrick County; Pulaski County; City of Radford; Russell County; Scott County; Smyth County; Tazewell County; Washington County; Wise County; Wythe County | Bedford County; Roanoke County | Trump +43.90% → Trump +43.90% |
| VA-10 | Fauquier County; Loudoun County; City of Manassas; City of Manassas Park; Rappahannock County | Fairfax County; Prince William County | Harris +8.30% → Harris +8.32% |
| VA-11 | City of Fairfax | Fairfax County | Harris +34.00% → Harris +34.05% |

### House of Delegates districts

| District | Exact whole-locality component | Allocated split-locality component | 2024 presidential winner, before → after |
|---|---|---|---|
| HD-11 | City of Fairfax | Fairfax County | Harris +35.40% → Harris +35.39% |
| HD-13 | City of Falls Church | Fairfax County | Harris +46.26% → Harris +46.25% |
| HD-20 | City of Manassas; City of Manassas Park | Prince William County | Harris +13.71% → Harris +13.71% |
| HD-31 | Clarke County | Frederick County; Warren County | Trump +27.31% → Trump +27.33% |
| HD-32 | City of Winchester | Frederick County | Trump +20.70% → Trump +20.74% |
| HD-33 | Page County; Shenandoah County | Rockingham County; Warren County | Trump +47.65% → Trump +47.65% |
| HD-34 | City of Harrisonburg | Rockingham County | Trump +7.74% → Trump +7.78% |
| HD-35 | Bath County; Highland County | Augusta County; Rockingham County | Trump +43.99% → Trump +44.01% |
| HD-36 | City of Staunton; City of Waynesboro | Augusta County; Rockbridge County | Trump +18.76% → Trump +18.80% |
| HD-37 | Alleghany County; Botetourt County; City of Buena Vista; City of Covington; Craig County; City of Lexington | Rockbridge County | Trump +39.90% → Trump +39.90% |
| HD-39 | Franklin County | Roanoke County | Trump +40.72% → Trump +40.72% |
| HD-40 | City of Salem | City of Roanoke; Roanoke County | Trump +9.25% → Trump +9.25% |
| HD-42 | Giles County; City of Radford | Montgomery County; Pulaski County | Trump +24.80% → Trump +24.80% |
| HD-43 | Bland County; Buchanan County; Tazewell County | Dickenson County; Russell County | Trump +68.37% → Trump +68.37% |
| HD-44 | City of Bristol; Washington County | Russell County | Trump +52.99% → Trump +53.01% |
| HD-45 | Lee County; City of Norton; Scott County; Wise County | Dickenson County | Trump +66.94% → Trump +66.94% |
| HD-46 | Grayson County; Smyth County; Wythe County | Pulaski County | Trump +58.11% → Trump +58.11% |
| HD-47 | Carroll County; Floyd County; City of Galax; Patrick County | Henry County | Trump +53.82% → Trump +53.82% |
| HD-48 | City of Martinsville | Henry County; Pittsylvania County | Trump +27.74% → Trump +27.78% |
| HD-49 | City of Danville | Halifax County; Pittsylvania County | Trump +8.32% → Trump +8.36% |
| HD-50 | Charlotte County; Lunenburg County; Mecklenburg County | Halifax County; Prince Edward County | Trump +19.29% → Trump +19.29% |
| HD-52 | City of Lynchburg | Campbell County | Trump +11.75% → Trump +11.75% |
| HD-53 | Amherst County | Bedford County; Nelson County | Trump +38.54% → Trump +38.56% |
| HD-54 | City of Charlottesville | Albemarle County | Harris +60.78% → Harris +60.77% |
| HD-56 | Appomattox County; Buckingham County; Cumberland County | Fluvanna County; Goochland County; Prince Edward County | Trump +22.33% → Trump +22.33% |
| HD-61 | Rappahannock County | Culpeper County; Fauquier County | Trump +25.86% → Trump +25.88% |
| HD-62 | Greene County; Madison County | Culpeper County; Orange County | Trump +23.26% → Trump +23.26% |
| HD-65 | City of Fredericksburg | Spotsylvania County; Stafford County | Harris +9.52% → Harris +9.49% |
| HD-67 | King George County; Lancaster County; Northumberland County; Richmond County; Westmoreland County | Caroline County | Trump +20.05% → Trump +20.05% |
| HD-68 | Essex County; King and Queen County; King William County; Mathews County; Middlesex County | Gloucester County | Trump +33.75% → Trump +33.77% |
| HD-71 | City of Williamsburg | James City County; New Kent County | Harris +4.92% → Harris +4.90% |
| HD-72 | Amelia County; Nottoway County; Powhatan County | Chesterfield County | Trump +23.38% → Trump +23.36% |
| HD-74 | City of Colonial Heights | Chesterfield County | Trump +8.27% → Trump +8.27% |
| HD-75 | City of Hopewell | Chesterfield County; Prince George County | Harris +6.57% → Harris +6.55% |
| HD-81 | Charles City County | Chesterfield County; Henrico County | Harris +34.56% → Harris +34.56% |
| HD-82 | City of Petersburg; Surry County | Dinwiddie County; Prince George County | Harris +4.14% → Harris +4.08% |
| HD-83 | Brunswick County; City of Emporia; Greensville County; Southampton County; Sussex County | Dinwiddie County; Isle of Wight County | Trump +7.93% → Trump +7.95% |
| HD-84 | City of Franklin | Isle of Wight County; City of Suffolk | Harris +14.44% → Harris +14.42% |
| HD-86 | City of Poquoson | City of Hampton; York County | Harris +1.55% → Harris +1.57% |
| HD-100 | Accomack County; Northampton County | City of Virginia Beach | Trump +5.19% → Trump +5.21% |

### State Senate districts

| District | Exact whole-locality component | Allocated split-locality component | 2024 presidential winner, before → after |
|---|---|---|---|
| SD-2 | Bath County; City of Harrisonburg; Highland County; Page County; Rockingham County | Augusta County | Trump +33.53% → Trump +33.51% |
| SD-3 | Alleghany County; Botetourt County; City of Buena Vista; City of Covington; Craig County; City of Lexington; Rockbridge County; City of Staunton; City of Waynesboro | Augusta County; Roanoke County | Trump +28.97% → Trump +28.95% |
| SD-4 | City of Roanoke; City of Salem | Montgomery County; Roanoke County | Trump +1.29% → Trump +1.25% |
| SD-5 | Bland County; Giles County; Pulaski County; City of Radford; Smyth County; Tazewell County | Montgomery County; Wythe County | Trump +36.34% → Trump +36.32% |
| SD-7 | Carroll County; Floyd County; Franklin County; City of Galax; Grayson County; Henry County; City of Martinsville; Patrick County | Wythe County | Trump +45.07% → Trump +45.07% |
| SD-9 | Charlotte County; City of Danville; Halifax County; Lunenburg County; Mecklenburg County; Nottoway County; Pittsylvania County | Prince Edward County | Trump +21.56% → Trump +21.56% |
| SD-10 | Amelia County; Appomattox County; Buckingham County; Cumberland County; Fluvanna County; Goochland County; Powhatan County | Hanover County; Louisa County; Prince Edward County | Trump +26.57% → Trump +26.55% |
| SD-11 | Albemarle County; Amherst County; City of Charlottesville; Nelson County | Louisa County | Harris +25.52% → Harris +25.54% |
| SD-12 | City of Colonial Heights | Chesterfield County | Harris +0.17% → Harris +0.25% |
| SD-13 | Charles City County; City of Hopewell; City of Petersburg; Prince George County; Surry County; Sussex County | Dinwiddie County; Henrico County | Harris +21.66% → Harris +21.70% |
| SD-17 | Brunswick County; City of Emporia; City of Franklin; Greensville County; Isle of Wight County; Southampton County; City of Suffolk | Dinwiddie County; City of Portsmouth | Harris +4.65% → Harris +4.65% |
| SD-20 | Accomack County; Northampton County | City of Norfolk; City of Virginia Beach | Trump +3.09% → Trump +3.03% |
| SD-23 | City of Hampton | City of Newport News | Harris +39.49% → Harris +39.51% |
| SD-24 | City of Poquoson; City of Williamsburg; York County | James City County; City of Newport News | Harris +8.13% → Harris +8.17% |
| SD-25 | Caroline County; Essex County; King George County; King William County; Lancaster County; Middlesex County; Northumberland County; Richmond County; Westmoreland County | King and Queen County; Spotsylvania County | Trump +15.30% → Trump +15.28% |
| SD-26 | Gloucester County; Mathews County; New Kent County | Hanover County; James City County; King and Queen County | Trump +19.18% → Trump +19.12% |
| SD-27 | City of Fredericksburg | Spotsylvania County; Stafford County | Harris +3.09% → Harris +3.17% |
| SD-28 | Culpeper County; Greene County; Madison County; Orange County; Rappahannock County | Fauquier County; Spotsylvania County | Trump +25.42% → Trump +25.38% |
| SD-30 | City of Manassas; City of Manassas Park | Prince William County | Harris +8.66% → Harris +8.72% |
| SD-37 | City of Fairfax; City of Falls Church | Fairfax County | Harris +40.78% → Harris +40.84% |
| SD-39 | City of Alexandria | Arlington County; Fairfax County | Harris +55.15% → Harris +55.15% |

These tables list all 72 mixed districts in the tracked report. Districts containing only split localities are excluded because they have no exact whole-locality component. The component classification uses 2020 Census voting-age population assigned to the official 2021 district plan. Every comparison uses the 2024 presidential contest from the first reconciliation commit (`4cdfcc7`) and its parent. Each cell uses the front end's compact winner surname and displayed margin. In 23 rows, votes changed but the displayed lead did not. These are historical comparisons, not 2026 changes.

For a numeric example, the 2024 presidential result in **VA-11** keeps the City of Fairfax's reported **8,797 Democratic / 4,302 Republican / 468 other** votes exact. Its allocated Fairfax County portion adds **258,618 / 123,431 / 14,505**, producing the published district total of **267,415 / 127,733 / 14,973**. The county portion is estimated; the independent city's vote is not reweighted.

The 2024 U.S. Senate projection had larger movements in some House districts. Using the front end's displayed precision, **HD-45** moved from Cao +66.94% to Cao +54.06%, and **HD-84** moved from Kaine +14.44% to Kaine +17.81% in the first reconciliation commit.

### Recent cross-contest comparisons

The before → after columns above show the first 2024 reconciliation run. The tables below use current district files to compare different elections on the displayed lines; some 2024 values differ from the historical columns above because later rebuilds changed the district data. Every listed district voted Republican for president in 2024, then Democratic for governor in 2025 and U.S. Senate in 2026. Each cell uses the front end's compact winner surname and displayed margin.

#### Congressional districts

| District | 2020 president | 2024 president | 2024 U.S. House | 2025 governor | 2026 U.S. Senate | 2026 U.S. House |
|---|---|---|---|---|---|---|
| VA-01 | Trump +6.67% | Trump +4.89% | Wittman +12.79% | Spanberger +2.24% | Warner +9.95% | Taylor +2.93% |
| VA-02 | Biden +2.04% | Trump +0.24% | Kiggans +3.84% | Spanberger +7.42% | Warner +15.24% | Luria +8.96% |

Both districts elected a Republican to the U.S. House in 2024 and a Democrat in 2026. VA-01 was the only one of Virginia's 11 congressional districts to move toward Democrats between the 2020 and 2024 presidential results on the displayed lines: Trump's lead narrowed from 6.67% to 4.89%, a 1.78-point shift.

The largest locality contributions to each congressional district's **2026 U.S. Senate vote** show how different county and city geography feeds the district totals. Shares are percentages of that district's votes; a split locality contributes only its portion inside the district.

| District | Largest locality contributions |
|---|---|
| VA-01 | Henrico County 22.6%; Chesterfield County 21.1%; Hanover County 12.5% |
| VA-02 | City of Virginia Beach 54.6%; City of Chesapeake 17.6%; City of Suffolk 13.4% |
| VA-03 | City of Norfolk 27.2%; City of Newport News 23.5%; City of Hampton 19.8% |
| VA-04 | City of Richmond 29.6%; Chesterfield County 28.4%; Henrico County 19.7% |
| VA-05 | Albemarle County 16.5%; City of Lynchburg 8.6%; Pittsylvania County 7.3% |
| VA-06 | Frederick County 12.6%; Rockingham County 11.7%; Augusta County 10.7% |
| VA-07 | Prince William County 31.8%; Stafford County 20.6%; Spotsylvania County 19.1% |
| VA-08 | Fairfax County 44.6%; Arlington County 32.3%; City of Alexandria 20.6% |
| VA-09 | Montgomery County 12.8%; Bedford County 10.1%; Franklin County 7.9% |
| VA-10 | Loudoun County 55.6%; Prince William County 24.4%; Fauquier County 10.6% |
| VA-11 | Fairfax County 96.7%; City of Fairfax 3.3% |

For **VA-01**, the 2026 Senate vote breaks down further:

| Geographic component | Democratic | Republican | Other | Share of VA-01 votes | Net margin votes |
|---|---:|---:|---:|---:|---:|
| 15 whole counties and independent cities | 87,803 | 88,845 | 345 | 43.8% | R+1,042 |
| Henrico County portion | 62,097 | 29,252 | 227 | 22.6% | D+32,845 |
| Chesterfield County portion | 49,595 | 35,617 | 201 | 21.1% | D+13,978 |
| Hanover County portion | 22,382 | 27,916 | 89 | 12.5% | R+5,534 |
| Newport News City overlay edge | 4 | 2 | 0 | <0.01% | D+2 |
| **VA-01 total** | **221,881** | **181,632** | **862** | **100%** | **D+40,249** |

The county portions are estimates from the same precinct overlay and party-specific unmatched-vote allocation used by the district builder. Their displayed integer votes use largest-remainder rounding so the components sum to the published VA-01 total. The six-vote Newport News City edge comes from the precinct overlay; the official locality/district assignment puts Newport News City in VA-03.

The **VA-01 U.S. House returns** show the geographic shift in the contest itself. These are votes cast for the district's House candidates in each locality or district portion, so no precinct overlay allocation is needed. Margins use the same winner-surname format as the map; the last column is the 2026 Democratic minus Republican vote margin.

| VA-01 component | 2022 House | 2024 House | 2026 House | 2024 → 2026 shift | 2026 net votes |
|---|---:|---:|---:|---:|---:|
| Henrico County portion | Jones +7.52% | Mehta +8.77% | Taylor +25.93% | D+17.16 pp | D+23,395 |
| Chesterfield County portion | Wittman +5.59% | Wittman +3.36% | Taylor +12.41% | D+15.77 pp | D+11,705 |
| Hanover County portion | Wittman +32.40% | Wittman +31.62% | Wittman +18.09% | D+13.53 pp | R+9,305 |
| Other 15 counties and independent cities | Wittman +21.50% | Wittman +22.70% | Wittman +7.72% | D+14.98 pp | R+13,688 |
| **VA-01 total** | **Wittman +13.01%** | **Wittman +12.78%** | **Taylor +2.93%** | **D+15.71 pp** | **D+12,107** |

Henrico and Chesterfield together gave Taylor a **35,100-vote** lead in 2026, exceeding Wittman's combined **22,993-vote** lead in Hanover and the other 15 localities. Chesterfield changed from a Wittman lead in both earlier House races to a Taylor lead; Wittman's Hanover lead also narrowed. The table describes where the winning margin came from, not why individual voters changed their choices. Sources: Virginia's [2022 official VA-01 results by locality](https://results.elections.virginia.gov/vaelections/2022%20November%20General/Site/Member_House_of_Representatives_(01).html), [2024 VA-01 results by locality](https://historical.elections.virginia.gov/contest/161739), and the repository's [2026 election export](Data/openelections/2026/20261103__va__general__precinct__multi_office__export_2026_november_general.csv), which sums to the [published 2026 district result](Data/district_contests/congressional_us_house_2026.json).

#### House of Delegates districts

| District | 2024 president | 2025 governor | 2025 House race | 2026 U.S. Senate |
|---|---|---|---|---|
| HD-30 | Trump +1.28% | Spanberger +5.04% | McAuliff +1.94% | Warner +13.73% |
| HD-34 | Trump +6.97% | Spanberger +3.06% | Wilt +0.88% | Warner +14.42% |
| HD-41 | Trump +2.88% | Spanberger +9.74% | Franklin +6.70% | Warner +16.02% |
| HD-64 | Trump +2.02% | Spanberger +9.32% | Carroll +6.50% | Warner +19.18% |
| HD-66 | Trump +2.45% | Spanberger +9.72% | Cole +4.38% | Warner +19.18% |
| HD-69 | Trump +1.58% | Spanberger +4.52% | Downey +3.31% | Warner +9.93% |
| HD-74 | Trump +8.25% | Spanberger +1.28% | Cherry +5.06% | Warner +9.63% |
| HD-99 | Trump +4.74% | Spanberger +0.48% | Tata +7.92% | Warner +11.84% |
| HD-100 | Trump +5.19% | Spanberger +0.68% | Bloxom +5.86% | Warner +7.92% |

#### State Senate districts

| District | 2024 president | 2025 governor | 2026 U.S. Senate |
|---|---|---|---|
| SD-4 | Trump +0.49% | Spanberger +8.12% | Warner +17.85% |
| SD-20 | Trump +3.03% | Spanberger +5.34% | Warner +12.56% |

The 2024 and 2026 U.S. House columns and the 2025 House of Delegates column are directly reported district races. The presidential, governor, and U.S. Senate columns are statewide contests projected onto district lines. Five of the nine listed House of Delegates districts also elected a Democratic delegate in 2025.

The 2026 Senate slice is outside the tracked 78-slice reconciliation report.

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
