# Change history

## 2026-10-23

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

## March–October 2026

**Last updated:** October 4, 2026

### Consistent District Demographic Pill Sizing (October 4, 2026)

- Applied the populated Demographics-mode compact pill styling to district demographic cards before election results load.
- Preserved the original natural popup dimensions and complete highest-to-lowest demographic layout; only the pill scale and spacing are unified.

### Descending Demographic Percentages (October 4, 2026)

- Sorted demographic race/ethnicity percentages from highest to lowest across the atlas's demographic cards.
- Kept unavailable Hispanic data at the end of the list so known percentages remain easy to scan.
