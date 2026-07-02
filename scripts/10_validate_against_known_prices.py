"""Permanent regression test: validate the trained model against the
held-out (split=holdout) rows of data/raw/market_prices_2026.csv. These
rows are never used in scripts/03_train_price_model.py, so this is an
honest out-of-sample check. Uses each row's lat/lon directly (bypassing
geocoding, since exact coordinates are already known).

Also checks the Bang Kaeo frontage-vs-interior assertion: at nearly
identical CBD distance, the frontage parcel should price notably higher
than the interior parcel (>= 2x) if the road-frontage feature is doing
its job. Run this after any retrain (scripts/03_train_price_model.py).
"""
import csv
import importlib.util
import os

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location(
    "predict_price", os.path.join(HERE, "07_predict_price.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SRC = os.path.join(HERE, "..", "data", "raw", "market_prices_2026.csv")
FRONTAGE_RATIO_MIN = 2.0


def predict_from_latlon(province, lat, lon):
    model = m.load_json(m.MODEL_PATH, None)
    treasury_stats = m.load_treasury_stats()
    roads = m.load_roads()
    province = m.normalize_province(province)
    km = m.haversine_km(model["cbd_lat"], model["cbd_lon"], lat, lon) if model else 0.0
    road_km = m.nearest_road_km(lat, lon, roads)
    low, point, high, note = m.estimate_price_per_sqwah(province, km, model, treasury_stats, road_km)
    return km, low, point, high


def main():
    holdout, frontage_pair = [], {}
    with open(SRC, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            price = (float(row["price_low_baht_per_sqwah"]) + float(row["price_high_baht_per_sqwah"])) / 2
            entry = (row["area"], row["province"], float(row["lat"]), float(row["lon"]), price, row.get("frontage_note", ""))
            if row.get("split") == "holdout":
                holdout.append(entry)
            if row.get("frontage_note") in ("frontage", "interior"):
                frontage_pair[row["frontage_note"]] = entry

    print(f"{'Area':<45}{'Province':<14}{'km':>6}  {'Actual':>10}  {'Pred low-high':>25}  {'Pred pt':>10}  {'Err%':>8}  {'In band'}")
    print("-" * 130)
    errs, in_band = [], 0
    for area, province, lat, lon, actual, _ in holdout:
        km, low, pt, high = predict_from_latlon(province, lat, lon)
        within = low is not None and low <= actual <= high
        err = (pt - actual) / actual * 100 if pt is not None else None
        if err is not None:
            errs.append(abs(err))
        if within:
            in_band += 1
        band = f"{low:,.0f}-{high:,.0f}" if low is not None else "N/A"
        pt_s = f"{pt:,.0f}" if pt is not None else "N/A"
        err_s = f"{err:+.1f}%" if err is not None else "N/A"
        print(f"{area:<45}{province:<14}{km:>6.1f}  {actual:>10,.0f}  {band:>25}  {pt_s:>10}  {err_s:>8}  {'YES' if within else 'no'}")

    print(f"\nHoldout MAPE (point estimate vs actual): {sum(errs)/len(errs):.1f}%")
    print(f"Actual price within predicted low-high band: {in_band}/{len(holdout)}")

    if "frontage" in frontage_pair and "interior" in frontage_pair:
        f_area, f_prov, f_lat, f_lon, _, _ = frontage_pair["frontage"]
        i_area, i_prov, i_lat, i_lon, _, _ = frontage_pair["interior"]
        _, _, f_pt, _ = predict_from_latlon(f_prov, f_lat, f_lon)
        _, _, i_pt, _ = predict_from_latlon(i_prov, i_lat, i_lon)
        ratio = f_pt / i_pt if i_pt else float("nan")
        passed = ratio >= FRONTAGE_RATIO_MIN
        print(f"\nFrontage/interior assertion: {f_area} (pt {f_pt:,.0f}) vs {i_area} (pt {i_pt:,.0f})")
        print(f"  ratio = {ratio:.2f}x (requires >= {FRONTAGE_RATIO_MIN}x): {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()
