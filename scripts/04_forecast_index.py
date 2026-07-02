"""Forecast the Bangkok nominal property price index (proxy for market trend)
using Holt-Winters exponential smoothing, backtested with a rolling-origin
scheme against a naive (last-value) baseline. Only 141 quarterly points, so
a classical model is the right choice over deep learning.
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from statsmodels.tsa.holtwinters import ExponentialSmoothing

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
SRC = os.path.join(DATA_DIR, "bangkok_property_prices_combined.csv")


def load_series():
    dates, values = [], []
    with open(SRC, newline="") as f:
        for row in csv.DictReader(f):
            v = row["nominal_price_index"]
            if v:
                dates.append(row["date"])
                values.append(float(v))
    return dates, np.array(values)


def rolling_backtest(values, horizon=4, n_origins=20):
    """Roll the origin over the last n_origins quarters, forecasting `horizon`
    steps ahead each time; compare Holt-Winters vs naive last-value baseline."""
    model_errs, naive_errs = [], []
    n = len(values)
    start = n - n_origins - horizon
    for origin in range(start, n - horizon):
        train = values[: origin + 1]
        actual = values[origin + 1 : origin + 1 + horizon]
        try:
            fit = ExponentialSmoothing(train, trend="add", seasonal=None).fit()
            pred = fit.forecast(horizon)
        except Exception:
            continue
        naive = np.full(horizon, train[-1])
        model_errs.append(np.mean(np.abs((actual - pred) / actual)))
        naive_errs.append(np.mean(np.abs((actual - naive) / actual)))
    return np.mean(model_errs), np.mean(naive_errs)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    dates, values = load_series()

    model_mape, naive_mape = rolling_backtest(values)
    print(f"Rolling-origin backtest (4-quarter horizon, 20 origins):")
    print(f"  Holt-Winters MAPE : {model_mape:.2%}")
    print(f"  Naive baseline MAPE: {naive_mape:.2%}")
    if model_mape < naive_mape:
        print("  -> Holt-Winters beats naive, using it for the final forecast.")
    else:
        print("  -> WARNING: Holt-Winters does not beat naive; report both.")

    # Held-out test: last 8 quarters entirely withheld.
    train, test = values[:-8], values[-8:]
    fit = ExponentialSmoothing(train, trend="add", seasonal=None).fit()
    test_pred = fit.forecast(8)
    test_mape = np.mean(np.abs((test - test_pred) / test))
    print(f"Held-out last-8-quarter test MAPE: {test_mape:.2%}")

    # Final forecast: next 4 quarters beyond all available data.
    final_fit = ExponentialSmoothing(values, trend="add", seasonal=None).fit()
    future = final_fit.forecast(4)
    print("Forecast next 4 quarters (nominal index):", [round(v, 1) for v in future])

    dest = os.path.join(OUT_DIR, "index_forecast.csv")
    with open(dest, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quarter_ahead", "forecast_nominal_index"])
        for i, v in enumerate(future, 1):
            w.writerow([i, round(v, 2)])
    print(f"Wrote {dest}")

    plt.figure(figsize=(9, 5))
    x_hist = np.arange(len(values))
    x_test = np.arange(len(train), len(values))
    x_future = np.arange(len(values), len(values) + 4)
    plt.plot(x_hist, values, label="Actual", color="steelblue")
    plt.plot(x_test, test_pred, label="Backtest forecast (last 8q, held out)", color="orange")
    plt.plot(x_future, future, label="Forecast (next 4q)", color="crimson", linestyle="--")
    plt.xlabel("Quarter index")
    plt.ylabel("Nominal property price index")
    plt.title("Bangkok property price index: backtest + forecast")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "index_forecast.png"), dpi=120)
    print(f"Saved plot to {os.path.join(OUT_DIR, 'index_forecast.png')}")


if __name__ == "__main__":
    main()
