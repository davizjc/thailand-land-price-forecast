# Data source research notes

Summary of Thailand land/property price sources investigated, and why the
final pipeline uses what it uses.

## Bank of Thailand / BIS residential property price index (used)
Quarterly, 1991-2026, Bangkok-specific, nominal + real index + YoY series.
Bulk-downloadable as clean CSV via FRED. See `README.md` for the four files.
Used as the market-trend layer (`scripts/04_forecast_index.py`).

## Treasury Department (กรมธนารักษ์) land valuation, per-parcel (used)
`catalog.treasury.go.th`, dataset id `land-valuation`, CKAN API at
`/api/3/action/package_show?id=land-valuation`. 77 resources, one CSV per
province -- columns `UTMMAP1-4, UTMSCALE, LAND_NO, EVAPRICE` (assessed
baht/sq.wah). This is real per-parcel data but keyed to UTM 1:1000
survey-grid sheet codes with **no public lookup table** to
district/subdistrict names, so it can only be used in aggregate (per-province
floor-price percentiles, `scripts/02_treasury_summary.py`) rather than joined
to named areas. If a UTM-grid-to-district shapefile is ever found, this
dataset could be broken down to street/soi level.

Downloaded for 10 provinces (~6.7M parcels total): Bangkok, Samut Prakan,
Nonthaburi, Pathum Thani, Nakhon Pathom, Samut Sakhon (Bangkok Metropolitan
Region) + Ayutthaya, Saraburi, Chon Buri, Chachoengsao (Eastern Seaboard).
All 77 provinces are available in the catalog if wider coverage is wanted
later -- just add resource URLs to `scripts/01_download_treasury.py`.

## District-level market prices (used, curated not scraped)
No clean bulk dataset of *asking/transaction* prices by district exists for
free. Building a scraper against DDproperty/Baania/LivingInsider was in the
original plan but was dropped in favor of directly citing published
market-report price tables (primo.co.th, futuredeveloperacademy.com,
urbanhomeplk.com — see `data/raw/district_market_prices.csv` for the
per-row source URLs). This gives 14 real, sourced price points spanning CBD
to outer suburbs, used to fit the distance-decay model
(`scripts/03_train_price_model.py`). Revisit with a proper scraper if more
data points / finer granularity are needed later.

## REIC Empty Land Price Index (not used)
Published via dashboard/PDF reports, not bulk CSV. Would need manual
transcription or a PDF-parsing scraper — skipped for this iteration.

## data.go.th (checked, redundant)
Mirrors the same Treasury catalog datasets; catalog.treasury.go.th's CKAN
API was used directly instead.

## July 2026 retune: expanded/refreshed market comps (used)
`data/raw/market_prices_2026.csv` supersedes `district_market_prices.csv`
as the training source for `scripts/03_train_price_model.py`. It carries
forward the original 33 points (tagged `data_vintage=2023`) and adds ~40
more: real address-level 2026 comps and BMR distance-decay market figures
supplied directly by the project owner (tagged `data_vintage=2026`,
`source` = "user-provided ..."), plus a handful of freshly web-searched
2026 published figures (Colliers/Nation Thailand CBD land-price coverage,
a FazWaz Nong Chok raw-land listing, DDproperty's Rangsit market average —
see the `source` column for each). 8 points are marked `split=holdout` and
permanently excluded from training; `scripts/10_validate_against_known_prices.py`
scores the model against them after every retrain. A `frontage_note` column
(`frontage`/`interior`) marks a matched Bang Kaeo, Samut Prakan pair used
to test road-frontage sensitivity specifically.

## OSM major roads (used)
`scripts/11_build_major_roads.py` pulls `highway=motorway|trunk|primary`
ways from the Overpass API within the BMR bounding box and samples their
geometry into points every ~200m, written to
`data/processed/major_roads.csv`. Built to test whether distance-to-nearest-
major-road could serve as a road-frontage proxy feature for the price
model; as of the July 2026 retune it's computed and shown at prediction
time but didn't earn a place in the adopted regression (see
`data/README.md` tuning notes) — kept in the pipeline for future retunes
once more frontage-specific market comps are available.
