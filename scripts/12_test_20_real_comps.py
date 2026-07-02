"""Test the trained model against 20 real-world address comps (province,
district, exact lat/lon, land size, actual 2026 price) spanning Bangkok and
the BMR. Uses lat/lon directly (bypassing geocoding, since exact
coordinates are already known) and prints a markdown table -- this is what
backs the "Test results" table in README.md; rerun and paste in after any
retrain.
"""
import importlib.util
import os

HERE = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location(
    "predict_price", os.path.join(HERE, "07_predict_price.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# (id, province, district, location, lat, lon, size_sqwah, actual_price_per_sqwah, actual_total)
CASES = [
    (1, "Bangkok", "Watthana", "Soi Sukhumvit 63 (Ekkamai 12)", 13.7308, 100.5884, 95, 410000, 38950000),
    (2, "Bangkok", "Khlong Toei", "Soi Sukhumvit 24", 13.7253, 100.5705, 72, 620000, 44640000),
    (3, "Bangkok", "Pathum Wan", "Soi Chula 5", 13.7389, 100.5296, 80, 700000, 56000000),
    (4, "Bangkok", "Huai Khwang", "Pracha Uthit Road", 13.7759, 100.5825, 140, 180000, 25200000),
    (5, "Bangkok", "Chatuchak", "Soi Ratchadaphisek 36", 13.8280, 100.5850, 120, 190000, 22800000),
    (6, "Bangkok", "Bang Kapi", "Soi Ramkhamhaeng 60", 13.7697, 100.6372, 180, 110000, 19800000),
    (7, "Bangkok", "Suan Luang", "Soi On Nut 44", 13.7125, 100.6353, 150, 145000, 21750000),
    (8, "Bangkok", "Lat Krabang", "Lat Krabang Road Soi 54", 13.7244, 100.7778, 240, 75000, 18000000),
    (9, "Bangkok", "Bang Na", "Soi Bang Na-Trat 23", 13.6672, 100.6321, 160, 180000, 28800000),
    (10, "Bangkok", "Bang Khae", "Phetkasem Soi 69", 13.7095, 100.3823, 220, 85000, 18700000),
    (11, "Bangkok", "Taling Chan", "Borommaratchachonnani Soi 74", 13.7816, 100.4235, 320, 72000, 23040000),
    (12, "Bangkok", "Min Buri", "Suwinthawong Road Soi 28", 13.8097, 100.7312, 450, 48000, 21600000),
    (13, "Bangkok", "Nong Chok", "Mit Maitri Road", 13.8556, 100.8465, 600, 20000, 12000000),
    (14, "Nonthaburi", "Pak Kret", "Chaeng Watthana Soi 35", 13.9038, 100.5287, 180, 130000, 23400000),
    (15, "Nonthaburi", "Bang Yai", "Kanchanaphisek Road", 13.8768, 100.4094, 300, 62000, 18600000),
    (16, "Pathum Thani", "Khlong Luang", "Phahonyothin Rd near Thammasat", 14.0713, 100.6030, 420, 38000, 15960000),
    (17, "Samut Prakan", "Bang Phli", "King Kaew Road Soi 21", 13.6421, 100.7112, 260, 82000, 21320000),
    (18, "Samut Prakan", "Mueang", "Sukhumvit Soi 115", 13.6465, 100.6104, 150, 125000, 18750000),
    (19, "Samut Sakhon", "Krathum Baen", "Phutthamonthon Sai 4", 13.7002, 100.2907, 500, 36000, 18000000),
    (20, "Nakhon Pathom", "Sam Phran", "Rai Khing Temple Area", 13.7318, 100.2729, 550, 34000, 18700000),
]


def predict_from_latlon(province, lat, lon):
    model = m.load_json(m.MODEL_PATH, None)
    treasury_stats = m.load_treasury_stats()
    roads = m.load_roads()
    province = m.normalize_province(province)
    km = m.haversine_km(model["cbd_lat"], model["cbd_lon"], lat, lon) if model else 0.0
    road_km = m.nearest_road_km(lat, lon, roads)
    low, point, high, note = m.estimate_price_per_sqwah(province, km, model, treasury_stats, road_km)
    return low, point, high


def main():
    lines = [
        "| # | District | Actual (baht/wah) | Predicted range | Predicted point | Error % | In band |",
        "|--:|---|--:|--:|--:|--:|:--:|",
    ]
    errs, in_band = [], 0
    for cid, prov, dist, loc, lat, lon, size, actual, total in CASES:
        low, pt, high = predict_from_latlon(prov, lat, lon)
        within = low is not None and low <= actual <= high
        err = (pt - actual) / actual * 100
        errs.append(abs(err))
        if within:
            in_band += 1
        lines.append(f"| {cid} | {dist} | {actual:,} | {low:,.0f}–{high:,.0f} | {pt:,.0f} | {err:+.1f}% | {'✓' if within else ''} |")

    mape = sum(errs) / len(errs)
    print("\n".join(lines))
    print(f"\nMAPE={mape:.1f}%  in_band={in_band}/{len(CASES)}")


if __name__ == "__main__":
    main()
