"""Combine the Bangkok/BMR price-vs-distance model, per-province Treasury
floor stats, sourced market points, and the index trend forecast into one
readable current-market-price report covering all 10 downloaded provinces.
"""
import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


def read_csv_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    dist_price = read_csv_rows(os.path.join(OUT_DIR, "current_price_by_distance.csv"))
    treasury = read_csv_rows(os.path.join(OUT_DIR, "treasury_floor_summary.csv"))
    forecast = read_csv_rows(os.path.join(OUT_DIR, "index_forecast.csv"))
    market_points = read_csv_rows(os.path.join(DATA_DIR, "raw", "district_market_prices.csv"))

    combined = read_csv_rows(os.path.join(DATA_DIR, "bangkok_property_prices_combined.csv"))
    last_known_yoy = next(
        (r["nominal_yoy_pct"] for r in reversed(combined) if r["nominal_yoy_pct"]), None
    )

    lines = []
    lines.append("# Land Price Report — Bangkok Metropolitan Region + Eastern Seaboard\n")
    lines.append(
        "Covers 10 provinces: Bangkok, Samut Prakan, Nonthaburi, Pathum Thani, "
        "Nakhon Pathom, Samut Sakhon (Bangkok Metropolitan Region) plus "
        "Ayutthaya, Saraburi, Chon Buri, Chachoengsao (Eastern Seaboard).\n"
    )

    lines.append("## 1. Official Treasury-assessed floor price, by province\n")
    lines.append(
        "Computed directly from ~6.7M real per-parcel appraisal records "
        "(catalog.treasury.go.th, dataset `land-valuation`). These are legal "
        "tax-assessment floors, well below actual market prices.\n"
    )
    lines.append("| Province | Parcels | Median (baht/sq.wah) | p90 | p99 |")
    lines.append("|---|---|---|---|---|")
    for r in sorted(treasury, key=lambda r: -float(r["median"])):
        lines.append(
            f"| {r['province']} | {int(r['n_parcels']):,} | {float(r['median']):,.0f} "
            f"| {float(r['p90']):,.0f} | {float(r['p99']):,.0f} |"
        )

    lines.append("\n## 2. Bangkok current market price by distance from CBD\n")
    lines.append(
        "Log-linear regression on 14 sourced district price points "
        "(Bangkok + BMR only). Leave-one-out MAPE 28.3% vs. 150.4% naive "
        "median baseline — beats baseline, see scripts/03 output.\n"
    )
    lines.append("| Distance from CBD (km) | Estimated price (baht/sq.wah) |")
    lines.append("|---|---|")
    for r in dist_price:
        lines.append(f"| {r['distance_km_from_cbd']} | {int(float(r['estimated_baht_per_sqwah'])):,} |")

    lines.append("\n## 3. Sourced market price points, all provinces\n")
    lines.append("Real cited prices from published market reports (see `source` column for each).\n")
    lines.append("| Area | Province | Zone type | Price range (baht/sq.wah) |")
    lines.append("|---|---|---|---|")
    for r in market_points:
        lo, hi = int(float(r["price_low_baht_per_sqwah"])), int(float(r["price_high_baht_per_sqwah"]))
        rng = f"{lo:,}" if lo == hi else f"{lo:,} - {hi:,}"
        lines.append(f"| {r['area']} | {r['province']} | {r['zone_type']} | {rng} |")

    lines.append(
        f"\n## 4. Trend context (Bangkok index)\nMost recent known nominal YoY "
        f"change: {last_known_yoy}%. Holt-Winters forecast, next 4 quarters "
        f"(MAPE 0.93% backtest vs 1.64% naive):"
    )
    lines.append("| Quarters ahead | Forecast index |")
    lines.append("|---|---|")
    for r in forecast:
        lines.append(f"| {r['quarter_ahead']} | {r['forecast_nominal_index']} |")

    lines.append(
        "\n## Caveats\n"
        "- Treasury figures are assessed values (tax basis) for ALL 10 provinces "
        "-- real, complete, computed from raw data, not estimated.\n"
        "- Sourced market points (section 3) are curated from published "
        "reports, not raw transactions -- directional, not exact. Real "
        "transactions are typically 1.5-3x the assessed floor in central areas.\n"
        "- The distance-decay curve (section 2) is fit to Bangkok/BMR points "
        "only; Chon Buri (Pattaya/Sriracha) is a separate urban hub and is "
        "not on the same curve -- see its points directly in section 3.\n"
        "- Ayutthaya, Saraburi, Chachoengsao, Nakhon Pathom, and Samut Sakhon "
        "have Treasury floor data but limited/no sourced market points yet -- "
        "the Treasury median/p90 columns are the most reliable numbers "
        "available for those provinces right now.\n"
    )

    dest = os.path.join(OUT_DIR, "report.md")
    with open(dest, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote {dest}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
