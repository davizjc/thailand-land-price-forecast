# Thailand Land Price Forecast

Approximate land/property price estimation and forecasting for Bangkok and
the surrounding Bangkok Metropolitan Region (BMR), built from public data:
FRED/BIS residential property price indices, Thailand Treasury Department
per-parcel land valuations, and curated market price comps.

Given an address and a land size, the pipeline estimates a current market
price per square wah (and total price), plus a macro trend forecast of the
Bangkok property price index.

**This is a directional research estimate, not a substitute for a real
appraisal or the Treasury's own per-deed lookup** (assessprice.treasury.go.th).
See `data/README.md` for full methodology, accuracy numbers, and known
limitations.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage: predict a price for a specific address

```
python3 scripts/08_build_transit_stations.py     # once; feeds 03 + 07
python3 scripts/11_build_major_roads.py          # once; feeds 03 + 07
python3 scripts/03_train_price_model.py          # writes outputs/price_model.json
python3 scripts/06_build_district_centroids.py   # writes offline-fallback centroids
python3 scripts/07_predict_price.py --address "999/9 Rama I Rd, Pathum Wan, Bangkok 10330" --area 830000 --unit sqm
```

Or run `python3 scripts/07_predict_price.py` with no args for an
interactive prompt. Accepted area units: `sqwah`, `sqm`, `rai`, `ngan`.

After any retrain, check accuracy against a held-out real-comp set:

```
python3 scripts/10_validate_against_known_prices.py
```

## Usage: macro trend forecast

```
python3 scripts/01_download_treasury.py
python3 scripts/02_treasury_summary.py
python3 scripts/04_forecast_index.py
python3 scripts/05_current_price_report.py
```

Outputs land to `outputs/` (report, forecast plot, price-vs-distance plot,
CSVs).

## Layout

- `scripts/` — numbered pipeline scripts, run roughly in order (see above)
- `data/raw/` — sourced/curated input data (Treasury bulk downloads, market
  price comps)
- `data/processed/` — derived caches (geocoding, transit stations, major
  roads, district centroids)
- `data/README.md` — full data source documentation, model methodology,
  tuning notes, and known limitations
- `data/NOTES.md` — research notes on data sources considered and why
- `outputs/` — generated reports, plots, and the trained price model

## Known limitations (see `data/README.md` for details)

- Area/district-level estimate, not parcel-specific — cannot see road
  frontage, exact plot shape, or micro-location premiums.
- Bangkok/BMR model: ~68% MAPE on held-out 2026 comps, 4/8 within the
  predicted low-high band. Treat any single estimate as a rough
  order-of-magnitude band.
- Non-BMR provinces (Ayutthaya, Saraburi, Chon Buri, Chachoengsao) use a
  much coarser province-wide multiplier on the Treasury-assessed floor.
