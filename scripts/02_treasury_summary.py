"""Summarize each province's raw Treasury per-parcel appraisal file into
floor-price statistics. EVAPRICE is baht per square wah (assessed value).

We can't break these down by district within a province (no UTM-to-district
lookup available), so this produces one distribution per province, used to
sanity-check the market-price model: real transaction/asking prices should
sit at or above these assessed floors almost everywhere.
"""
import csv
import glob
import os
import statistics

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
DEST = os.path.join(OUT_DIR, "treasury_floor_summary.csv")

PROVINCE_LABELS = {
    "bangkok": "Bangkok",
    "samut_prakan": "Samut Prakan",
    "nonthaburi": "Nonthaburi",
    "pathum_thani": "Pathum Thani",
    "ayutthaya": "Ayutthaya",
    "saraburi": "Saraburi",
    "chon_buri": "Chon Buri",
    "chachoengsao": "Chachoengsao",
    "nakhon_pathom": "Nakhon Pathom",
    "samut_sakhon": "Samut Sakhon",
}


def summarize(path):
    prices = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                p = float(row["EVAPRICE"])
            except (KeyError, ValueError):
                continue
            if p > 0:
                prices.append(p)
    prices.sort()
    n = len(prices)
    if n == 0:
        return None
    return {
        "n_parcels": n,
        "min": prices[0],
        "p10": prices[int(n * 0.10)],
        "p25": prices[int(n * 0.25)],
        "median": statistics.median(prices),
        "p75": prices[int(n * 0.75)],
        "p90": prices[int(n * 0.90)],
        "p99": prices[int(n * 0.99)],
        "max": prices[-1],
        "mean": statistics.mean(prices),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "land_valuation_*.csv"))):
        key = os.path.basename(path)[len("land_valuation_"):-len(".csv")]
        label = PROVINCE_LABELS.get(key, key)
        print(f"Summarizing {label}...")
        stats = summarize(path)
        if stats is None:
            print(f"  no valid rows, skipping")
            continue
        stats["province"] = label
        rows.append(stats)
        print(f"  n={stats['n_parcels']:,}  median={stats['median']:,.0f}  p90={stats['p90']:,.0f}")

    fields = ["province", "n_parcels", "min", "p10", "p25", "median", "p75", "p90", "p99", "max", "mean"]
    with open(DEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nWrote {DEST}")


if __name__ == "__main__":
    main()
