"""Train a current-market (2026) land-price model from curated, sourced
district price points (data/raw/market_prices_2026.csv).

Model choice: with ~76 points (a mix of 2023-era report tables and fresher
2026 comps/market reports), gradient boosting / deep models would still
overfit badly. We compare several small feature sets via leave-one-out CV,
scored ONLY on the 2026-vintage rows in the training split (2023 rows are
allowed to help fit the shape of the curve via the vintage dummy below, but
we don't want stale 2023 price levels counted as "correct" when scoring
2026-market accuracy). We pick by honest LOO MAPE, not by story-plausibility:

  A. distance only (original model)                                  <- baseline to beat
  B. distance + outside_bangkok + interaction (previous adopted model)
  C. B + vintage_2023 dummy (lets 2023-priced comps shift down without
     dragging the fitted 2026 curve down with them)
  D. C + log1p(km_to_major_road) (road-frontage signal -- the Bang Kaeo
     frontage-vs-interior test showed the model had zero signal for this)
  E. same as C/D but with log1p(km_from_cbd) instead of raw km (lets the
     curve be steep near the CBD without flattening too early further out
     -- the CBD undershoot in testing suggested raw-km-linear decay in log
     space was too shallow near distance=0)
  F. E + log1p(km_to_major_road)

Ridge (L2-regularized, alpha selected via LOO grid search) is used for
every multi-term candidate. We only adopt a candidate if it beats the
simpler distance-only baseline's LOO MAPE (scored on 2026 rows) --
otherwise we fall back to the baseline and say so.

At prediction time, vintage is always treated as 2026 (vintage_2023=0) --
the dummy only exists to let old comps inform slope/shape without pulling
the absolute price level down to 2023 rates.
"""
import csv
import json
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
SRC = os.path.join(RAW_DIR, "market_prices_2026.csv")
STATIONS_SRC = os.path.join(PROCESSED_DIR, "transit_stations.csv")
ROADS_SRC = os.path.join(PROCESSED_DIR, "major_roads.csv")

# Siam Square, the reference CBD point used for all distance calculations.
SIAM_CBD_LAT = 13.7466
SIAM_CBD_LON = 100.5347


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_points(path):
    pts = []
    if os.path.exists(path):
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                pts.append((float(row["lat"]), float(row["lon"])))
    return pts


def nearest_km(lat, lon, points):
    if not points:
        return None
    return min(haversine_km(lat, lon, plat, plon) for plat, plon in points)


def load(stations, roads):
    """Load Bangkok + BMR (Bangkok Metropolitan Region) TRAIN-split points
    only. Chon Buri/Pattaya is a separate urban hub, not on the same
    distance-from-Siam-CBD decay curve, so it's excluded from the
    regression (see 05_current_price_report.py). Provincewide 'Assessed
    range' rows are excluded too -- they're broad tax-appraisal ranges, not
    comparable point-estimates to the specific named-area market prices
    used for the curve fit. Holdout-split rows are excluded entirely --
    those are reserved for scripts/10_validate_against_known_prices.py.
    """
    areas, km, road_km, outside_bkk, vintage_2023, price, vintage = [], [], [], [], [], [], []
    with open(SRC, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["zone_type"] == "Assessed range" or row["province"] == "Chon Buri":
                continue
            if row.get("split", "train") != "train":
                continue
            areas.append(row["area"])
            km.append(float(row["km_from_siam_cbd"]))
            lat, lon = float(row["lat"]), float(row["lon"])
            r_km = nearest_km(lat, lon, roads)
            road_km.append(r_km if r_km is not None else 5.0)
            outside_bkk.append(0.0 if row["province"] == "Bangkok" else 1.0)
            vintage_2023.append(1.0 if row.get("data_vintage") == "2023" else 0.0)
            vintage.append(row.get("data_vintage", "2026"))
            lo = float(row["price_low_baht_per_sqwah"])
            hi = float(row["price_high_baht_per_sqwah"])
            price.append((lo + hi) / 2)
    return {
        "areas": areas,
        "km": np.array(km),
        "road_km": np.array(road_km),
        "outside": np.array(outside_bkk),
        "vintage_2023": np.array(vintage_2023),
        "vintage": vintage,
        "price": np.array(price),
    }


# --- Candidate feature builders ---------------------------------------------
# Each builder takes the raw column arrays and returns (X, feature_names).
# predict_row() mirrors this for a single new point at prediction time
# (always vintage_2023=0, i.e. "predict at 2026 price level").

def build_A(d):
    return d["km"].reshape(-1, 1), ["km_from_cbd"]

def build_B(d):
    km, outside = d["km"], d["outside"]
    return np.column_stack([km, outside, km * outside]), \
        ["km_from_cbd", "outside_bangkok", "km_from_cbd_x_outside_bangkok"]

def build_C(d):
    km, outside, vin = d["km"], d["outside"], d["vintage_2023"]
    return np.column_stack([km, outside, km * outside, vin]), \
        ["km_from_cbd", "outside_bangkok", "km_from_cbd_x_outside_bangkok", "vintage_2023"]

def build_D(d):
    km, outside, vin, road = d["km"], d["outside"], d["vintage_2023"], d["road_km"]
    log_road = np.log1p(road)
    return np.column_stack([km, outside, km * outside, vin, log_road]), \
        ["km_from_cbd", "outside_bangkok", "km_from_cbd_x_outside_bangkok", "vintage_2023", "log1p_km_to_major_road"]

def build_E(d):
    logkm = np.log1p(d["km"])
    outside, vin = d["outside"], d["vintage_2023"]
    return np.column_stack([logkm, outside, logkm * outside, vin]), \
        ["log1p_km_from_cbd", "outside_bangkok", "log1p_km_from_cbd_x_outside_bangkok", "vintage_2023"]

def build_F(d):
    logkm = np.log1p(d["km"])
    outside, vin, road = d["outside"], d["vintage_2023"], d["road_km"]
    log_road = np.log1p(road)
    return np.column_stack([logkm, outside, logkm * outside, vin, log_road]), \
        ["log1p_km_from_cbd", "outside_bangkok", "log1p_km_from_cbd_x_outside_bangkok", "vintage_2023", "log1p_km_to_major_road"]


CANDIDATES = [
    ("A_distance_only", build_A, False),
    ("B_distance_outside_interaction", build_B, True),
    ("C_B_plus_vintage", build_C, True),
    ("D_C_plus_road", build_D, True),
    ("E_logdistance_outside_vintage", build_E, True),
    ("F_E_plus_road", build_F, True),
]

ALPHA_GRID = [0.05, 0.1, 0.3, 1.0, 3.0, 10.0]


def loo_eval_scored_on_2026(model_cls, X, log_y, y, vintage_list, **kwargs):
    """LOO CV: fit leaving one point out (from the full mixed-vintage
    training set), predict it, but only score error for 2026-vintage rows
    -- we care about 2026-market accuracy, and 2023 rows are only there to
    help fit curve shape, not to be treated as "correct" 2026 targets."""
    loo = LeaveOneOut()
    preds = np.zeros_like(y)
    for train_idx, test_idx in loo.split(X):
        m = model_cls(**kwargs).fit(X[train_idx], log_y[train_idx])
        preds[test_idx] = np.exp(m.predict(X[test_idx]))
    mask = np.array([v == "2026" for v in vintage_list])
    mae = mean_absolute_error(y[mask], preds[mask])
    mape = mean_absolute_percentage_error(y[mask], preds[mask])
    return mae, mape


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    stations = load_points(STATIONS_SRC)
    roads = load_points(ROADS_SRC)
    d = load(stations, roads)
    y = d["price"]
    log_y = np.log(y)
    vintage_list = d["vintage"]
    n_2026 = sum(1 for v in vintage_list if v == "2026")

    print(f"Training on n={len(y)} sourced Bangkok/BMR train-split points "
          f"({n_2026} are 2026-vintage, scored on those only; "
          f"{len(stations)} transit stations, {len(roads)} road sample points loaded)\n")

    baseline_preds = np.array([np.median(np.delete(y, i)) for i in range(len(y))])
    mask_2026 = np.array([v == "2026" for v in vintage_list])
    base_mape = mean_absolute_percentage_error(y[mask_2026], baseline_preds[mask_2026])
    print(f"  Median baseline (2026-scored)            : MAPE={base_mape:.1%}")

    results = {}
    for name, builder, standardize in CANDIDATES:
        X, feat_names = builder(d)
        if standardize:
            X_mean, X_std = X.mean(axis=0), X.std(axis=0)
            X_std = np.where(X_std == 0, 1.0, X_std)
            X_scaled = (X - X_mean) / X_std
            best_alpha, best_mae, best_mape = None, None, None
            for alpha in ALPHA_GRID:
                mae, mape = loo_eval_scored_on_2026(Ridge, X_scaled, log_y, y, vintage_list, alpha=alpha)
                if best_mape is None or mape < best_mape:
                    best_alpha, best_mae, best_mape = alpha, mae, mape
            results[name] = dict(feat_names=feat_names, X=X, X_mean=X_mean, X_std=X_std,
                                  alpha=best_alpha, mae=best_mae, mape=best_mape, ridge=True)
            print(f"  {name:<32}: MAE={best_mae:,.0f} baht/sq.wah  MAPE={best_mape:.1%}  (Ridge alpha={best_alpha})")
        else:
            mae, mape = loo_eval_scored_on_2026(LinearRegression, X, log_y, y, vintage_list)
            results[name] = dict(feat_names=feat_names, X=X, mae=mae, mape=mape, ridge=False)
            print(f"  {name:<32}: MAE={mae:,.0f} baht/sq.wah  MAPE={mape:.1%}")

    baseline_name = "A_distance_only"
    baseline_mape = results[baseline_name]["mape"]
    best_name = min(results, key=lambda k: results[k]["mape"])
    best = results[best_name]

    if best_name != baseline_name and best["mape"] < baseline_mape:
        print(f"\n  -> {best_name} beats the distance-only baseline on 2026-scored LOO MAPE, adopting it.")
        chosen_name = best_name
    else:
        print(f"\n  -> No candidate beat the distance-only baseline; keeping {baseline_name}.")
        chosen_name = baseline_name

    chosen = results[chosen_name]
    X = chosen["X"]
    feat_names = chosen["feat_names"]

    if chosen["ridge"]:
        X_scaled = (X - chosen["X_mean"]) / chosen["X_std"]
        final = Ridge(alpha=chosen["alpha"]).fit(X_scaled, log_y)
        residuals = log_y - final.predict(X_scaled)
    else:
        final = LinearRegression().fit(X, log_y)
        residuals = log_y - final.predict(X)
    residual_std = float(np.std(residuals, ddof=1))

    model_json = {
        "model_id": chosen_name,
        "features": feat_names,
        "intercept": float(final.intercept_),
        "coef": final.coef_.tolist(),
        "residual_std_log": residual_std,
        "cbd_lat": SIAM_CBD_LAT,
        "cbd_lon": SIAM_CBD_LON,
        "training_areas": d["areas"],
        "training_km": d["km"].tolist(),
        "training_price": y.tolist(),
        "training_vintage": vintage_list,
        "loo_mape_2026_scored": float(chosen["mape"]),
        "baseline_mape_2026_scored": float(base_mape),
        "candidates_tried": {k: v["mape"] for k, v in results.items()},
        "valid_km_range": [0, float(d["km"].max())],
        "note": (
            f"Model '{chosen_name}': log(price) = intercept + sum(coef_i * feature_i), "
            "where multi-term models are Ridge-fit on standardized features "
            "(feature_mean/feature_std) and single-term is plain OLS. Trained on "
            "data/raw/market_prices_2026.csv train split (Bangkok/BMR only; Chon Buri "
            "and provincewide 'Assessed range' rows excluded). A vintage_2023 dummy "
            "lets older (2023-era) sourced comps inform curve shape without dragging "
            "the fitted 2026 price level down -- prediction always assumes vintage_2023=0 "
            "(current 2026 market). LOO MAPE above is scored only on 2026-vintage rows, "
            "since that's the accuracy that matters for current predictions. See "
            "outputs/treasury_floor_summary.csv for non-BMR provinces instead."
        ),
    }
    if chosen["ridge"]:
        model_json["feature_mean"] = chosen["X_mean"].tolist()
        model_json["feature_std"] = chosen["X_std"].tolist()
        model_json["ridge_alpha"] = chosen["alpha"]

    with open(os.path.join(OUT_DIR, "price_model.json"), "w") as f:
        json.dump(model_json, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {os.path.join(OUT_DIR, 'price_model.json')} (model: {chosen_name}, features: {feat_names})")

    # --- Plot: price vs distance, split Bangkok vs outside-Bangkok, 2026 points only ---
    km_arr = d["km"]
    outside_arr = d["outside"]
    is_2026 = mask_2026
    plt.figure(figsize=(8, 5))
    for outside_flag, marker, label in [(0, "o", "Bangkok"), (1, "^", "Other BMR province")]:
        m2026 = (outside_arr == outside_flag) & is_2026
        m2023 = (outside_arr == outside_flag) & ~is_2026
        if m2026.any():
            plt.scatter(km_arr[m2026], y[m2026], marker=marker, zorder=3, label=f"Sourced 2026 points ({label})")
        if m2023.any():
            plt.scatter(km_arr[m2023], y[m2023], marker=marker, zorder=2, alpha=0.35, label=f"Sourced 2023 points ({label})")

    curve_km = np.linspace(0.01, km_arr.max(), 100)
    road_default = float(np.median(d["road_km"])) if len(d["road_km"]) else 0.3
    for outside_flag, color, label in [(0, "crimson", "Fitted curve (Bangkok, 2026)"),
                                         (1, "darkorange", "Fitted curve (outside Bangkok, 2026)")]:
        flag_arr = np.full_like(curve_km, outside_flag)
        vin_arr = np.zeros_like(curve_km)
        if chosen_name == "A_distance_only":
            curve_X = curve_km.reshape(-1, 1)
            curve_price = np.exp(final.predict(curve_X))
        elif "log1p_km_from_cbd" in feat_names:
            logkm = np.log1p(curve_km)
            cols = [logkm, flag_arr, logkm * flag_arr, vin_arr]
            if "log1p_km_to_major_road" in feat_names:
                cols.append(np.full_like(curve_km, np.log1p(road_default)))
            curve_X = np.column_stack(cols)
            curve_X_scaled = (curve_X - chosen["X_mean"]) / chosen["X_std"]
            curve_price = np.exp(final.predict(curve_X_scaled))
        else:
            cols = [curve_km, flag_arr, curve_km * flag_arr]
            if "vintage_2023" in feat_names:
                cols.append(vin_arr)
            if "log1p_km_to_major_road" in feat_names:
                cols.append(np.full_like(curve_km, np.log1p(road_default)))
            curve_X = np.column_stack(cols)
            curve_X_scaled = (curve_X - chosen["X_mean"]) / chosen["X_std"]
            curve_price = np.exp(final.predict(curve_X_scaled))
        plt.plot(curve_km, curve_price, color=color, label=label)

    plt.yscale("log")
    plt.xlabel("Distance from Siam CBD (km)")
    plt.ylabel("Price (baht / sq.wah, log scale)")
    plt.title(f"Bangkok/BMR land price vs. distance from CBD ({chosen_name})")
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "price_vs_distance.png"), dpi=120)
    print(f"Saved plot to {os.path.join(OUT_DIR, 'price_vs_distance.png')}")

    # Write a lookup table for current (2026) price estimate at round-number
    # distances, inside Bangkok proper, at median road distance.
    dest = os.path.join(OUT_DIR, "current_price_by_distance.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["distance_km_from_cbd", "estimated_baht_per_sqwah"])
        for km_val in [0, 1, 2, 5, 8, 10, 15, 20, 25, 30]:
            if chosen_name == "A_distance_only":
                est = float(np.exp(final.predict([[km_val]]))[0])
            elif "log1p_km_from_cbd" in feat_names:
                logkm = math.log1p(km_val)
                cols = [logkm, 0.0, 0.0, 0.0]
                if "log1p_km_to_major_road" in feat_names:
                    cols.append(math.log1p(road_default))
                x_scaled = (np.array([cols]) - chosen["X_mean"]) / chosen["X_std"]
                est = float(np.exp(final.predict(x_scaled))[0])
            else:
                cols = [km_val, 0.0, 0.0]
                if "vintage_2023" in feat_names:
                    cols.append(0.0)
                if "log1p_km_to_major_road" in feat_names:
                    cols.append(math.log1p(road_default))
                x_scaled = (np.array([cols]) - chosen["X_mean"]) / chosen["X_std"]
                est = float(np.exp(final.predict(x_scaled))[0])
            w.writerow([km_val, round(est)])
    print(f"Wrote {dest}")


if __name__ == "__main__":
    main()
