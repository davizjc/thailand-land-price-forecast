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

## Test results

20 real 2026 address comps (province, district, exact lat/lon, land size,
actual price) across Bangkok and the BMR, run through the current model
via `scripts/12_test_20_real_comps.py`. "In band" = actual price falls
within the model's predicted low-high range.

| # | District | Actual (baht/wah) | Predicted range | Predicted point | Error % | In band |
|--:|---|--:|--:|--:|--:|:--:|
| 1 | Watthana | 410,000 | 265,924–900,097 | 489,242 | +19.3% | ✓ |
| 2 | Khlong Toei | 620,000 | 327,348–1,108,002 | 602,247 | -2.9% | ✓ |
| 3 | Pathum Wan | 700,000 | 528,435–1,788,638 | 972,203 | +38.9% | ✓ |
| 4 | Huai Khwang | 180,000 | 264,333–894,711 | 486,314 | +170.2% | |
| 5 | Chatuchak | 190,000 | 144,169–487,981 | 265,239 | +39.6% | ✓ |
| 6 | Bang Kapi | 110,000 | 129,139–437,108 | 237,587 | +116.0% | |
| 7 | Suan Luang | 145,000 | 126,621–428,585 | 232,955 | +60.7% | ✓ |
| 8 | Lat Krabang | 75,000 | 16,723–56,604 | 30,767 | -59.0% | |
| 9 | Bang Na | 180,000 | 93,505–316,496 | 172,029 | -4.4% | ✓ |
| 10 | Bang Khae | 85,000 | 60,182–203,702 | 110,721 | +30.3% | ✓ |
| 11 | Taling Chan | 72,000 | 108,775–368,181 | 200,122 | +177.9% | |
| 12 | Min Buri | 48,000 | 28,925–97,905 | 53,216 | +10.9% | ✓ |
| 13 | Nong Chok | 20,000 | 4,642–15,714 | 8,541 | -57.3% | |
| 14 | Pak Kret | 130,000 | 57,269–193,843 | 105,362 | -19.0% | ✓ |
| 15 | Bang Yai | 62,000 | 53,175–179,986 | 97,830 | +57.8% | ✓ |
| 16 | Khlong Luang | 38,000 | 30,873–104,499 | 56,800 | +49.5% | ✓ |
| 17 | Bang Phli | 82,000 | 49,075–166,108 | 90,287 | +10.1% | ✓ |
| 18 | Mueang | 125,000 | 64,406–218,002 | 118,493 | -5.2% | ✓ |
| 19 | Krathum Baen | 36,000 | 42,472–143,757 | 78,138 | +117.1% | |
| 20 | Sam Phran | 34,000 | 40,527–137,174 | 74,560 | +119.3% | |

**MAPE = 58.3%, 13/20 within the predicted low-high band.** Some of these
20 points are also used in training (see `data/raw/market_prices_2026.csv`
`split` column), so this is a mix of in-sample and out-of-sample accuracy —
`scripts/10_validate_against_known_prices.py` is the honest
never-seen-in-training version (8 points, currently 68.5% MAPE, 4/8 in
band). The clear failure pattern here: the model overshoots ordinary
residential interior locations at 6-15km with no major-road frontage
(Huai Khwang, Bang Kapi, Taling Chan — all +100%+), and undershoots far
outer-suburb points (Lat Krabang, Nong Chok, Krathum Baen, Sam Phran). See
`data/README.md` for the full tuning history and why a road-frontage
feature hasn't yet earned its place in the model.

## Known limitations (see `data/README.md` for details)

- Area/district-level estimate, not parcel-specific — cannot see road
  frontage, exact plot shape, or micro-location premiums.
- Bangkok/BMR model: ~68% MAPE on held-out 2026 comps, 4/8 within the
  predicted low-high band. Treat any single estimate as a rough
  order-of-magnitude band.
- Non-BMR provinces (Ayutthaya, Saraburi, Chon Buri, Chachoengsao) use a
  much coarser province-wide multiplier on the Treasury-assessed floor.
