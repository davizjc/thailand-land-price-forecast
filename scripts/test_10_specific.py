"""Batch test: 10 specific, real Thai addresses (with actual building
numbers/roads, not just district names) across a range of provinces and
price tiers, to stress-test the geocoding retry ladder and pricing model."""
import importlib.util
import os

spec = importlib.util.spec_from_file_location(
    "predict_price", os.path.join(os.path.dirname(__file__), "07_predict_price.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# (label, address, area_value, unit)
CASES = [
    ("CentralWorld, CBD",
     "999/9 Rama I Rd, Pathum Wan, Bangkok 10330", 400, "sqwah"),
    ("Terminal 21 area, Asoke",
     "88 Sukhumvit Soi 19, Khlong Toei Nuea, Watthana, Bangkok 10110", 800, "sqwah"),
    ("IconSiam, Thon Buri riverside",
     "299 Charoen Nakhon Rd, Khlong Ton Sai, Khlong San, Bangkok 10600", 1200, "sqwah"),
    ("Central Ladprao, Chatuchak",
     "1691 Phahonyothin Rd, Chatuchak, Bangkok 10900", 600, "sqwah"),
    ("Central Bang Na, outer Bangkok",
     "587 Bang Na-Trat Rd, Bang Na, Bangkok 10260", 500, "sqwah"),
    ("Mega Bangna, Bang Phli, Samut Prakan",
     "39 Bang Na-Trat Rd, Bang Kaeo, Bang Phli District, Samut Prakan 10540", 700, "sqwah"),
    ("Central Westgate, Nonthaburi",
     "199 Sai Ma, Bang Yai District, Nonthaburi 11140", 500, "sqwah"),
    ("Future Park Rangsit, Pathum Thani",
     "94 Phahonyothin Rd, Prachathipat, Thanyaburi District, Pathum Thani 12130", 500, "sqwah"),
    ("Central Festival Pattaya Beach, Chon Buri",
     "333/99 Moo 9, Pattaya Sai 2 Rd, Nong Prue, Bang Lamung District, Chon Buri 20150", 500, "sqwah"),
    ("Ayutthaya Historical Park area",
     "Pa Thon Rd, Pratu Chai, Phra Nakhon Si Ayutthaya District, Ayutthaya 13000", 500, "sqwah"),
]

results = []
for label, address, area, unit in CASES:
    try:
        r = m.predict(address, area, unit)
        results.append((label, r))
    except Exception as e:
        results.append((label, {"error": str(e)}))

print(f"\n{'#':<3}{'Label':<38}{'Resolved province':<16}{'km':>6}  {'baht/sq.wah (range)':<26}{'Total price (range)':<38}{'Fallback?'}")
print("-" * 145)
for i, (label, r) in enumerate(results, 1):
    if "error" in r:
        print(f"{i:<3}{label:<38}ERROR: {r['error']}")
        continue
    prov = r["province"]
    km = r["km_from_cbd"]
    lo, hi = r["price_low_per_sqwah"], r["price_high_per_sqwah"]
    tlo, thi = r["total_low"], r["total_high"]
    fb = "offline" if r["used_offline_fallback"] else "live"
    price_s = f"{lo:,}-{hi:,}" if lo is not None else "N/A"
    total_s = f"{tlo:,}-{thi:,}" if tlo is not None else "N/A"
    print(f"{i:<3}{label:<38}{prov:<16}{km:>6.1f}  {price_s:<26}{total_s:<38}{fb}")

print("\n\nFull detail:\n")
for i, (label, r) in enumerate(results, 1):
    print(f"--- {i}. {label} ---")
    if "error" in r:
        print(f"  ERROR: {r['error']}\n")
        continue
    print(f"  Resolved: {r['resolved_location']}")
    print(f"  Province: {r['province']}   Distance: {r['km_from_cbd']} km   Fallback used: {r['used_offline_fallback']}")
    print(f"  Area: {r['area_sqwah']:,.0f} sq.wah")
    print(f"  Price/sq.wah: {r['price_low_per_sqwah']:,} - {r['price_high_per_sqwah']:,} (point {r['price_point_per_sqwah']:,})")
    print(f"  TOTAL PRICE: {r['total_low']:,} - {r['total_high']:,} baht (point {r['total_point']:,})")
    print(f"  Method: {r['method_note']}\n")
