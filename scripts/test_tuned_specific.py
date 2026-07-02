"""Batch test of the tuned model (distance + province-interaction) against
10 new specific, real Thai addresses not used in any prior test batch,
chosen to stress the exact thing that was tuned: pairs of addresses at
similar CBD distance but on opposite sides of a BMR provincial border, plus
a spread of transit-adjacent vs. non-transit locations for context."""
import importlib.util
import os

spec = importlib.util.spec_from_file_location(
    "predict_price", os.path.join(os.path.dirname(__file__), "07_predict_price.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# (label, address, area_value, unit)
CASES = [
    ("Emquartier, Sukhumvit (BTS Phrom Phong doorstep)",
     "693, 695 Sukhumvit Rd, Khlong Tan Nuea, Watthana, Bangkok 10110", 600, "sqwah"),
    ("Chamchuri Square, Sam Yan (MRT doorstep)",
     "319 Phayathai Rd, Wang Mai, Pathum Wan, Bangkok 10330", 400, "sqwah"),
    ("Thonburi side, Wongwian Yai (BTS doorstep)",
     "1 Krung Thon Buri Rd, Khlong Ton Sai, Khlong San, Bangkok 10600", 500, "sqwah"),
    ("Bang Kapi interior, no rail access",
     "3776 Lat Phrao Rd, Khlong Chan, Bang Kapi, Bangkok 10240", 500, "sqwah"),
    ("Phra Pradaeng riverside, Samut Prakan (no rail, ~12km from CBD)",
     "Suk Sawat Rd, Bang Yo, Phra Pradaeng District, Samut Prakan 10130", 500, "sqwah"),
    ("Samrong, Samut Prakan (MRT Yellow Line doorstep, ~15km from CBD)",
     "Sukhumvit Rd, Samrong Nuea, Mueang Samut Prakan District, Samut Prakan 10270", 500, "sqwah"),
    ("Tiwanon Rd, Nonthaburi (arterial road, ~15km from CBD)",
     "Tiwanon Rd, Talat Khwan, Mueang Nonthaburi District, Nonthaburi 11000", 500, "sqwah"),
    ("Bang Bua Thong, outer Nonthaburi (~25km from CBD)",
     "Bang Bua Thong-Suphan Buri Rd, Bang Bua Thong, Nonthaburi 11110", 500, "sqwah"),
    ("Don Mueang Airport area, north Bangkok",
     "222 Vibhavadi Rangsit Rd, Sanambin, Don Mueang, Bangkok 10210", 500, "sqwah"),
    ("Sena, rural Ayutthaya (~90km from CBD)",
     "Sena District, Phra Nakhon Si Ayutthaya, Ayutthaya 13110", 800, "sqwah"),
]

results = []
for label, address, area, unit in CASES:
    try:
        r = m.predict(address, area, unit)
        results.append((label, r))
    except Exception as e:
        results.append((label, {"error": str(e)}))

print(f"\n{'#':<3}{'Label':<52}{'Province':<15}{'km':>6}  {'Nearest transit':<22}{'baht/sq.wah':<24}{'Total price'}")
print("-" * 165)
for i, (label, r) in enumerate(results, 1):
    if "error" in r:
        print(f"{i:<3}{label:<52}ERROR: {r['error']}")
        continue
    prov = r["province"]
    km = r["km_from_cbd"]
    station = f"{r['nearest_transit_station']} ({r['nearest_transit_km']}km)" if r.get("nearest_transit_station") else "-"
    lo, hi = r["price_low_per_sqwah"], r["price_high_per_sqwah"]
    tlo, thi = r["total_low"], r["total_high"]
    price_s = f"{lo:,}-{hi:,}" if lo is not None else "N/A"
    total_s = f"{tlo:,}-{thi:,}" if tlo is not None else "N/A"
    print(f"{i:<3}{label:<52}{prov:<15}{km:>6.1f}  {station:<22}{price_s:<24}{total_s}")

print("\n\nFull detail:\n")
for i, (label, r) in enumerate(results, 1):
    print(f"--- {i}. {label} ---")
    if "error" in r:
        print(f"  ERROR: {r['error']}\n")
        continue
    print(f"  Resolved: {r['resolved_location']}")
    print(f"  Province: {r['province']}   Distance: {r['km_from_cbd']} km   Fallback used: {r['used_offline_fallback']}")
    if r.get("nearest_transit_station"):
        print(f"  Nearest transit: {r['nearest_transit_station']} ({r['nearest_transit_km']} km)")
    print(f"  Area: {r['area_sqwah']:,.0f} sq.wah")
    print(f"  Price/sq.wah: {r['price_low_per_sqwah']:,} - {r['price_high_per_sqwah']:,} (point {r['price_point_per_sqwah']:,})")
    print(f"  TOTAL PRICE: {r['total_low']:,} - {r['total_high']:,} baht (point {r['total_point']:,})")
    print(f"  Method: {r['method_note']}\n")
