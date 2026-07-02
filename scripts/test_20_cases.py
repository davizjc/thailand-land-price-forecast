"""Ad-hoc batch test: run 20 diverse addresses through the predictor and
compare against an expected price range (from independently known reference
points, not from the model's own training data) to judge correctness.
"""
import importlib.util
import os

spec = importlib.util.spec_from_file_location(
    "predict_price", os.path.join(os.path.dirname(__file__), "07_predict_price.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# (address, area, unit, expected_low, expected_high, expected_note)
CASES = [
    # --- Bangkok CBD / prime (should be very high, roughly matches training data itself) ---
    ("Siam Paragon, Pathum Wan, Bangkok", 100, "sqwah", 700000, 1300000, "CBD core"),
    ("Sukhumvit Soi 11, Watthana, Bangkok", 100, "sqwah", 300000, 900000, "inner Sukhumvit"),
    ("Silom Complex, Bang Rak, Bangkok", 100, "sqwah", 500000, 1200000, "Silom CBD"),
    ("Chidlom, Bangkok", 100, "sqwah", 600000, 1200000, "Ploenchit/Chidlom prime"),
    ("Asoke, Bangkok", 100, "sqwah", 400000, 900000, "Asoke inner"),
    # --- Bangkok inner-middle ring ---
    ("Ari, Phaya Thai, Bangkok", 100, "sqwah", 250000, 600000, "Ari trendy mid-ring"),
    ("Ratchada, Huai Khwang, Bangkok", 100, "sqwah", 150000, 450000, "Ratchada mid-ring"),
    ("Ekkamai, Bangkok", 100, "sqwah", 400000, 900000, "Ekkamai inner"),
    ("On Nut, Suan Luang, Bangkok", 100, "sqwah", 150000, 400000, "On Nut mid-outer"),
    # --- Bangkok outer districts ---
    ("Bang Kapi, Bangkok", 100, "sqwah", 80000, 250000, "outer-mid"),
    ("Min Buri, Bangkok", 100, "sqwah", 30000, 150000, "outer east"),
    ("Bang Khun Thian, Bangkok", 100, "sqwah", 30000, 150000, "outer south"),
    ("Nong Chok, Bangkok", 100, "sqwah", 10000, 80000, "far outer"),
    # --- BMR provinces ---
    ("Muang Nonthaburi, Nonthaburi", 100, "sqwah", 50000, 250000, "Nonthaburi urban core"),
    ("Bang Na, Samut Prakan", 100, "sqwah", 30000, 180000, "Samut Prakan near Bangkok"),
    ("Sam Khok, Pathum Thani", 100, "sqwah", 10000, 90000, "Pathum Thani outer"),
    ("Nakhon Chai Si, Nakhon Pathom", 100, "sqwah", 5000, 80000, "Nakhon Pathom rural-ish"),
    ("Mahachai, Samut Sakhon", 100, "sqwah", 10000, 70000, "Samut Sakhon urban"),
    # --- Eastern Seaboard (coarse method expected) ---
    ("Sriracha, Chon Buri", 100, "sqwah", 40000, 150000, "Sriracha industrial/urban"),
    ("Phra Nakhon Si Ayutthaya, Ayutthaya", 100, "sqwah", 2000, 30000, "Ayutthaya provincial town"),
]

results = []
for address, area, unit, lo_exp, hi_exp, label in CASES:
    try:
        r = m.predict(address, area, unit)
        point = r["price_point_per_sqwah"]
        if point is None:
            verdict = "NO ESTIMATE"
        elif lo_exp <= point <= hi_exp:
            verdict = "MATCH"
        elif (lo_exp * 0.5) <= point <= (hi_exp * 2):
            verdict = "CLOSE"
        else:
            verdict = "OFF"
        results.append((label, address, r["province"], r["km_from_cbd"], point, lo_exp, hi_exp, verdict, r["method_note"][:35]))
    except Exception as e:
        results.append((label, address, "ERROR", None, None, lo_exp, hi_exp, "ERROR", str(e)[:35]))

print(f"{'Label':<22} {'Province':<14} {'km':>6} {'Predicted':>12} {'Expected range':>22} {'Verdict':<8}")
print("-" * 100)
for label, address, prov, km, point, lo, hi, verdict, note in results:
    km_s = f"{km:.1f}" if km is not None else "-"
    point_s = f"{point:,}" if point is not None else "-"
    print(f"{label:<22} {prov:<14} {km_s:>6} {point_s:>12} {lo:>10,}-{hi:<10,} {verdict:<8}")

n_match = sum(1 for r in results if r[7] == "MATCH")
n_close = sum(1 for r in results if r[7] == "CLOSE")
n_off = sum(1 for r in results if r[7] == "OFF")
n_err = sum(1 for r in results if r[7] in ("ERROR", "NO ESTIMATE"))
print(f"\n{len(results)} cases: {n_match} MATCH, {n_close} CLOSE, {n_off} OFF, {n_err} ERROR/NO ESTIMATE")
