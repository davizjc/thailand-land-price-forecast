# Data Sources — Thailand / Bangkok Property Price Data

All files pulled directly from FRED (Federal Reserve Economic Data), which mirrors
BIS (Bank for International Settlements) residential property price series compiled
using Bank of Thailand data. Quarterly frequency.

| File | Series ID | Meaning | Units |
|---|---|---|---|
| `bangkok_real_property_price_index.csv` | QTHR628BIS | Real residential property price index, Bangkok | Index (2010=100 base, inflation-adjusted) |
| `bangkok_nominal_property_price_index.csv` | QTHN628BIS | Nominal residential property price index, Bangkok | Index (2010=100 base) |
| `bangkok_real_property_price_index_alt.csv` | QTHR368BIS | Real residential property prices, Bangkok | YoY % change |
| `bangkok_nominal_property_price_index_alt.csv` | QTHN368BIS | Nominal residential property prices, Bangkok | YoY % change |

## Coverage
- Index-level series: 1991-Q1 to 2026-Q1 (142 quarterly observations)
- YoY % change series: 1992-Q1 to 2026-Q1 (138 quarterly observations)

## Important caveats
- This is **residential property price data** (houses/condos), used as the closest
  reliable public proxy — Bank of Thailand's dedicated **Land Price Index** and
  REIC's **Empty Land Price Index** exist but aren't available as clean bulk-downloadable
  files; they're published via dashboards/reports (see `../NOTES.md`).
- Data is **Bangkok-specific**, not nationwide. Land prices in other provinces
  (e.g. tourist areas like Phuket/Chiang Mai) will behave differently.
- These are **aggregate indices**, not per-parcel/location prices. Good for a
  macro trend-forecasting model; not sufficient for "what's this specific plot worth."

## Source
- https://fred.stlouisfed.org/series/QTHR628BIS
- https://fred.stlouisfed.org/series/QTHN628BIS
- https://fred.stlouisfed.org/series/QTHR368BIS
- https://fred.stlouisfed.org/series/QTHN368BIS

---

# Address → Approximate Price Predictor

`scripts/07_predict_price.py` gives an approximate current land price for a
specific address + land size. Run it after the pipeline scripts below have
been run once (`pip install -r requirements.txt` first):

```
python3 scripts/08_build_transit_stations.py     # writes data/processed/transit_stations.csv (once; feeds 03 + 07)
python3 scripts/11_build_major_roads.py          # writes data/processed/major_roads.csv (once; feeds 03 + 07)
python3 scripts/03_train_price_model.py          # writes outputs/price_model.json
python3 scripts/06_build_district_centroids.py   # writes data/processed/district_centroids.csv (offline fallback)
python3 scripts/07_predict_price.py              # interactive; or pass --address/--area/--unit
python3 scripts/10_validate_against_known_prices.py  # regression test: run after any retrain
```

Example:
```
python3 scripts/07_predict_price.py --address "999/9 Rama I Rd, Pathum Wan, Bangkok 10330" --area 830000 --unit sqm
```

Accepted area units: `sqwah`/ตารางวา, `sqm`/ตารางเมตร, `rai`/ไร่, `ngan`/งาน
(1 sq.wah = 4 sq.m; 1 ngan = 100 sq.wah; 1 rai = 400 sq.wah).

## How it estimates a price
1. **Geocodes the address** via Nominatim (OpenStreetMap), live over HTTP,
   cached to `data/processed/geocode_cache.json`.
2. **Bangkok/BMR** (Bangkok, Samut Prakan, Nonthaburi, Pathum Thani, Nakhon
   Pathom, Samut Sakhon): applies the model trained in
   `scripts/03_train_price_model.py` on the `train` split of
   `data/raw/market_prices_2026.csv` (76 sourced points total: the original
   33 curated 2023-era points, plus ~40 fresher 2025/2026 comps and
   published market-report figures gathered in July 2026, 8 of which are
   held out of training as a permanent accuracy check — see
   `scripts/10_validate_against_known_prices.py`). The model is selected by
   honest leave-one-out cross-validation from several candidates (distance
   only; distance + province-interaction; + a 2023-vintage dummy so stale
   comps don't drag the fitted 2026 price level down; + log-distance;
   + road-frontage distance) — whichever beats a plain distance-only
   baseline on 2026-scored LOO MAPE is adopted; currently that's the
   distance + outside-Bangkok + interaction model (`log(price) =
   f(km_from_cbd, outside_bangkok, km_from_cbd × outside_bangkok)`), same
   functional form as before but retrained on the expanded/refreshed
   dataset. Low/high range comes from the model's residual spread.
3. **Other provinces** (Ayutthaya, Saraburi, Chon Buri, Chachoengsao): no
   radial market curve exists, so the estimate is that province's
   Treasury-assessed p90 (`outputs/treasury_floor_summary.csv`, computed from
   real per-parcel data) times a 2.5x market-premium factor observed between
   sourced market points and Treasury floors elsewhere. Labeled "coarse" in
   the output.
4. **Offline fallback**: if live geocoding fails, matches district/province
   names in the address text against `data/processed/district_centroids.csv`
   (pre-geocoded Bangkok's 50 districts + all 10 province centroids).
5. **Nearest transit station** (`scripts/08_build_transit_stations.py`,
   ~150 BTS/MRT/ARL stations from OpenStreetMap) and **nearest major road**
   (`scripts/11_build_major_roads.py`, sampled OSM motorway/trunk/primary
   geometry) are computed and shown for context on every result. Road
   distance is tried as a regression feature (road-frontage proxy) at
   training time but is currently **not** part of the adopted model — see
   tuning notes below.

## Model tuning notes (July 2026 retune)
Prompted by three real-world test batches (20 exact-address comps, 10 BMR
distance-decay comps, and a matched road-frontage/interior pair in Bang
Kaeo) that exposed three failure modes in the original 33-point model:
systematic overshoot on mid-distance interior sois, systematic undershoot
near the CBD and in outer suburbs (stale 2023 price levels), and zero
sensitivity to road frontage. The dataset was expanded to 76 points with a
`data_vintage` column and a permanent 8-point holdout split
(`data/raw/market_prices_2026.csv`), and `03_train_price_model.py` now
compares 6 candidate feature sets via leave-one-out CV, **scored only on
2026-vintage rows** (2023 rows are allowed to inform curve shape via a
vintage dummy, but aren't counted as correct 2026 answers):

| Candidate | 2026-scored LOO MAPE |
|---|---|
| A. distance only | 81.4% |
| B. distance + outside-Bangkok + interaction (adopted) | **66.4%** |
| C. B + 2023-vintage dummy | 80.5% |
| D. C + log(road-frontage distance) | 76.7% |
| E. log-distance + outside + interaction + vintage | 108.0% |
| F. E + road distance | 94.4% |

B still wins, same as before the retune — none of the vintage or road
candidates beat it on honest LOO CV with this dataset size. Held-out
accuracy (`scripts/10_validate_against_known_prices.py`, 8 points never
seen in training) is **69% MAPE, 4/8 within the predicted low-high band**,
and the road-frontage assertion (frontage parcel should price >= 2x its
paired interior parcel at the same CBD distance) **fails** (predicted
ratio 1.02x vs. real ~5.8x) because the road-distance feature didn't earn
its place in the adopted model. This is reported honestly rather than
force-adopting a feature that doesn't generalize: with only ~27
2026-vintage points spanning three orders of magnitude (CBD ~3.8M down to
far-outer-suburb ~6,000 baht/sq.wah), the regression is data-starved,
especially for CBD-core and road-frontage effects. More sourced 2026
comps — particularly matched frontage/interior pairs and more CBD points —
are the highest-leverage next step, not more model complexity.

## Limitations
- **Area/district-level, not parcel-specific.** Two addresses at the same
  distance from the CBD *and* on the same side of a provincial border get
  the same estimate regardless of exact plot, road frontage, or transit
  proximity — confirmed by a real test case (Bang Kaeo, Samut Prakan) where
  a highway-frontage parcel and an interior soi parcel ~500m apart, at
  near-identical CBD distance, priced ~5.8x apart in reality but the model
  predicts them within 2%. See tuning notes above.
- **69% MAPE on held-out 2026 comps**, with only 4/8 within the predicted
  low-high band — treat any single estimate as a rough order-of-magnitude
  band, not a valuation. The model tends to overshoot ordinary residential
  interior locations at 6-15km and undershoot both the CBD core and
  far-outer suburbs; see `scripts/10_validate_against_known_prices.py` for
  the current per-point breakdown.
- **Non-BMR provinces are much coarser** — a single province-wide multiplier
  on the assessed floor, not a location-sensitive estimate.
- **This is not a substitute for a real appraisal or the Treasury's own
  per-deed lookup** (assessprice.treasury.go.th), which is the authoritative
  source for a specific title deed.
