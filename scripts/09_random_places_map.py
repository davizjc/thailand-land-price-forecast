"""Pick N random real locations from the district/province centroids
(covering Bangkok's districts plus BMR + Eastern Seaboard provinces),
run each through the price predictor, and plot a map colored by
estimated price per sq.wah."""
import csv
import importlib.util
import os
import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location(
    "predict_price", os.path.join(HERE, "07_predict_price.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

CENTROIDS_PATH = os.path.join(HERE, "..", "data", "processed", "district_centroids.csv")
OUT_PNG = os.path.join(HERE, "..", "outputs", "random_places_map.png")
OUT_CSV = os.path.join(HERE, "..", "outputs", "random_places_prices.csv")

N = 15
AREA = 100  # sq.wah, arbitrary standard lot size for comparison
random.seed()

with open(CENTROIDS_PATH) as f:
    rows = list(csv.DictReader(f))

sample = random.sample(rows, N)

results = []
for row in sample:
    label = f"{row['name']}, {row['province']}"
    address = f"{row['name']}, {row['province']}, Thailand"
    try:
        r = m.predict(address, AREA, "sqwah")
        results.append({
            "label": label,
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "province": r["province"],
            "km_from_cbd": r["km_from_cbd"],
            "price_low": r["price_low_per_sqwah"],
            "price_high": r["price_high_per_sqwah"],
            "price_point": r["price_point_per_sqwah"],
        })
    except Exception as e:
        print(f"skip {label}: {e}")

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
    w.writeheader()
    w.writerows(results)

print(f"\n{'Location':<35}{'Province':<15}{'km':>6}  {'baht/sq.wah (point)':>22}")
print("-" * 82)
for r in results:
    print(f"{r['label']:<35}{r['province']:<15}{r['km_from_cbd']:>6.1f}  {r['price_point']:>22,}")

# --- map ---
lats = [r["lat"] for r in results]
lons = [r["lon"] for r in results]
prices = [r["price_point"] for r in results]

fig, ax = plt.subplots(figsize=(9, 11))
sc = ax.scatter(lons, lats, c=prices, cmap="viridis",
                 norm=matplotlib.colors.LogNorm(vmin=min(prices), vmax=max(prices)),
                 s=140, edgecolors="black", linewidths=0.6, zorder=3)

for r in results:
    ax.annotate(r["label"], (r["lon"], r["lat"]), fontsize=7,
                xytext=(4, 4), textcoords="offset points")

cbar = fig.colorbar(sc, ax=ax, shrink=0.7)
cbar.set_label("Estimated price (baht / sq.wah, log scale)")

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title(f"Thailand land price estimate — {N} random locations")
ax.set_aspect("equal")
ax.grid(True, alpha=0.3)

fig.tight_layout()
fig.savefig(OUT_PNG, dpi=150)
print(f"\nSaved map to {OUT_PNG}")
print(f"Saved data to {OUT_CSV}")
