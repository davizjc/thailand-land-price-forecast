"""Interactive approximate land price predictor.

Usage:
    python3 scripts/07_predict_price.py
    python3 scripts/07_predict_price.py --address "999/9 Rama I Rd, Pathum Wan, Bangkok 10330" --area 830000 --unit sqm

Pipeline: parse the land-size unit -> sq.wah, geocode the address (Nominatim,
live HTTP, cached), compute distance from the Siam CBD, then either:
  - Bangkok/BMR: apply the log-linear distance-decay model trained in
    scripts/03_train_price_model.py (outputs/price_model.json).
  - Other provinces: anchor on that province's Treasury-assessed p90
    (outputs/treasury_floor_summary.csv) x a market-premium factor, since no
    radial market curve was fit outside the BMR.
  - Offline fallback: if geocoding fails, match the address text against the
    district/province centroid table (data/processed/district_centroids.csv).

This is a directional estimate, not a substitute for a real appraisal --
see data/README.md for full caveats.
"""
import argparse
import csv
import json
import math
import os
import ssl
import time
import urllib.parse
import urllib.request

import certifi
import numpy as np

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(BASE_DIR, "outputs")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
CACHE_PATH = os.path.join(PROCESSED_DIR, "geocode_cache.json")
CENTROIDS_PATH = os.path.join(PROCESSED_DIR, "district_centroids.csv")
MODEL_PATH = os.path.join(OUT_DIR, "price_model.json")
TREASURY_PATH = os.path.join(OUT_DIR, "treasury_floor_summary.csv")
STATIONS_PATH = os.path.join(PROCESSED_DIR, "transit_stations.csv")
ROADS_PATH = os.path.join(PROCESSED_DIR, "major_roads.csv")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "thailand-land-price-forecast-research-project/1.0"

# Market prices in the sourced dataset run ~2-3x the Treasury-assessed p90 in
# central areas (see data/raw/district_market_prices.csv vs
# outputs/treasury_floor_summary.csv). Used as the multiplier for provinces
# with no radial market curve of their own.
NON_BMR_MARKET_PREMIUM = 2.5

BMR_PROVINCES = {
    "Bangkok", "Samut Prakan", "Nonthaburi", "Pathum Thani",
    "Nakhon Pathom", "Samut Sakhon",
}

ALL_PROVINCES = BMR_PROVINCES | {"Ayutthaya", "Saraburi", "Chon Buri", "Chachoengsao"}

# Nominatim's accept-language=en request isn't always honored for every field
# (e.g. it can still return "จังหวัดปทุมธานี" for Pathum Thani); normalize by
# substring match against our known province list as a defensive fallback.
def normalize_province(raw_name):
    if not raw_name:
        return raw_name
    for canonical in ALL_PROVINCES:
        if canonical.lower() in raw_name.lower():
            return canonical
    thai_aliases = {
        "กรุงเทพ": "Bangkok", "สมุทรปราการ": "Samut Prakan",
        "นนทบุรี": "Nonthaburi", "ปทุมธานี": "Pathum Thani",
        "นครปฐม": "Nakhon Pathom", "สมุทรสาคร": "Samut Sakhon",
        "อยุธยา": "Ayutthaya", "สระบุรี": "Saraburi",
        "ชลบุรี": "Chon Buri", "ฉะเชิงเทรา": "Chachoengsao",
    }
    for thai, eng in thai_aliases.items():
        if thai in raw_name:
            return eng
    return raw_name

# --- Unit conversion -------------------------------------------------------

UNIT_TO_SQWAH = {
    "sqwah": 1.0, "sq.wah": 1.0, "sq wah": 1.0, "wah": 1.0,
    "ตารางวา": 1.0, "ตร.ว.": 1.0, "ตรว": 1.0,
    "sqm": 0.25, "sq.m": 0.25, "sq m": 0.25, "sqmeter": 0.25,
    "ตารางเมตร": 0.25, "ตร.ม.": 0.25, "ตรม": 0.25,
    "rai": 400.0, "ไร่": 400.0,
    "ngan": 100.0, "งาน": 100.0,
}


def parse_area(area_value, unit_text):
    """area_value: numeric string/float. unit_text: free-text unit label."""
    unit_key = unit_text.strip().lower().replace(" ", "")
    # Try exact match first, then loose match against known unit keys.
    normalized = {k.replace(" ", "").lower(): v for k, v in UNIT_TO_SQWAH.items()}
    if unit_key in normalized:
        factor = normalized[unit_key]
    else:
        factor = None
        for k, v in normalized.items():
            if k in unit_key or unit_key in k:
                factor = v
                break
    if factor is None:
        raise ValueError(
            f"Unrecognized unit {unit_text!r}. Use sq.wah, sq.m, rai, or ngan "
            f"(or ตารางวา / ตารางเมตร / ไร่ / งาน)."
        )
    area = float(str(area_value).replace(",", ""))
    return area * factor


# --- Geocoding ---------------------------------------------------------------

def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_cache(cache):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def _geocode_query(query):
    """Single Nominatim lookup. Returns a result dict or None (no match /
    network error). Sleeps to respect the 1 req/sec usage policy."""
    params = urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "addressdetails": 1,
        "accept-language": "en",
    })
    url = f"{NOMINATIM_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  (live geocoding error for {query!r}: {e})")
        return "NETWORK_ERROR"
    finally:
        time.sleep(1.1)
    if not data:
        return None
    d = data[0]
    addr = d.get("address", {})
    return {
        "lat": float(d["lat"]),
        "lon": float(d["lon"]),
        "display_name": d.get("display_name", ""),
        "province": addr.get("province") or addr.get("state") or "",
        "district": addr.get("city_district") or addr.get("suburb") or addr.get("county") or "",
    }


def geocode_address(address, cache):
    """Try the full address; if Nominatim finds nothing (common for very
    specific addresses with house/moo numbers + road name all combined),
    progressively drop leading comma-separated segments (house number, road
    name) and retry, keeping at least the last 2 segments (typically
    district + province/postcode)."""
    if address in cache and cache[address] is not None:
        return cache[address]

    segments = [s.strip() for s in address.split(",") if s.strip()]
    queries = [address]
    for i in range(1, len(segments) - 1):
        queries.append(", ".join(segments[i:]))

    for query in queries:
        result = _geocode_query(query)
        if result == "NETWORK_ERROR":
            return None  # don't keep retrying if the network itself is down
        if result is not None:
            cache[address] = result
            save_cache(cache)
            return result
    return None


def load_centroids():
    rows = []
    if os.path.exists(CENTROIDS_PATH):
        with open(CENTROIDS_PATH, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    return rows


# Segments containing these are road/street/unit descriptors, not place
# names -- e.g. "Bang Na-Trat Frontage Rd" contains the district name "Bang
# Na" but is not itself a location, so it must be excluded before matching.
_ROAD_KEYWORDS = (
    "road", " rd", "rd.", "highway", "frontage", "ถนน", "หมู่ที่", "หมู่",
    "moo ", "soi ", "ซอย",
)


def _place_segments(address):
    """Comma-separated segments of the address, minus ones that are house
    numbers / road names / unit descriptors rather than place names."""
    segments = [s.strip() for s in address.split(",") if s.strip()]
    place_segments = []
    for seg in segments:
        seg_lower = seg.lower()
        if any(kw in seg_lower for kw in _ROAD_KEYWORDS):
            continue
        if any(ch.isdigit() for ch in seg) and len(seg) < 12:
            # short numeric-heavy segment, e.g. a house/unit number
            continue
        place_segments.append(seg)
    return place_segments


def fallback_lookup(address, centroids):
    """Match a district or province name mentioned in the address text
    against the centroid table -- used when live geocoding fails.

    Only matches against place-name segments (road names and house/unit
    numbers are excluded first, since e.g. "Bang Na-Trat Frontage Rd"
    contains the Bangkok district name "Bang Na" as a false positive).
    An explicit province mention takes priority and scopes which district
    rows are eligible, so a Samut Prakan address can't match a Bangkok
    district just because a road name happens to overlap.
    """
    place_segments = _place_segments(address)
    place_text = " | ".join(place_segments).lower()
    if not place_text:
        place_text = address.lower()  # nothing survived filtering; fall back to raw text

    provinces = {r["province"] for r in centroids}
    matched_province = None
    for province in sorted(provinces, key=len, reverse=True):
        if province.lower() in place_text:
            matched_province = province
            break

    candidates = centroids
    if matched_province:
        candidates = [r for r in centroids if r["province"] == matched_province]

    # Prefer district-level matches (more specific) over province-level.
    for row in sorted(candidates, key=lambda r: r["level"] != "district"):
        if row["name"].lower() in place_text:
            return {
                "lat": float(row["lat"]), "lon": float(row["lon"]),
                "display_name": f"{row['name']}, {row['province']} (offline fallback match)",
                "province": row["province"], "district": row["name"],
            }

    # No district-level match, but we did find an explicit province mention.
    if matched_province:
        row = next(r for r in centroids if r["province"] == matched_province and r["level"] == "province")
        return {
            "lat": float(row["lat"]), "lon": float(row["lon"]),
            "display_name": f"{matched_province} (offline fallback match, province-level only)",
            "province": matched_province, "district": "",
        }
    return None


# --- Distance & pricing ------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_treasury_stats():
    stats = {}
    if os.path.exists(TREASURY_PATH):
        with open(TREASURY_PATH, newline="") as f:
            for row in csv.DictReader(f):
                stats[row["province"]] = row
    return stats


def load_stations():
    stations = []
    if os.path.exists(STATIONS_PATH):
        with open(STATIONS_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                stations.append({"name": row["name"], "lat": float(row["lat"]), "lon": float(row["lon"])})
    return stations


def load_roads():
    roads = []
    if os.path.exists(ROADS_PATH):
        with open(ROADS_PATH, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                roads.append({"lat": float(row["lat"]), "lon": float(row["lon"])})
    return roads


def nearest_transit(lat, lon, stations):
    """Returns (station_name, distance_km) for the closest BTS/MRT/ARL
    station, or (None, None) if no station table is available. Shown for
    context in the output; not currently used by the pricing model itself
    (adding it as a regression feature made LOO MAPE worse with this
    dataset size -- see scripts/03_train_price_model.py)."""
    if not stations:
        return None, None
    best = min(stations, key=lambda s: haversine_km(lat, lon, s["lat"], s["lon"]))
    return best["name"], haversine_km(lat, lon, best["lat"], best["lon"])


def nearest_road_km(lat, lon, roads):
    """Distance to the nearest sampled motorway/trunk/primary road point
    (data/processed/major_roads.csv), used as a road-frontage proxy feature
    by some trained model variants (see scripts/03_train_price_model.py).
    Returns None if no road table is available."""
    if not roads:
        return None
    return min(haversine_km(lat, lon, r["lat"], r["lon"]) for r in roads)


# Maps a feature name (as written by scripts/03_train_price_model.py's
# model_json["features"]) to its raw (pre-standardization) value, given the
# point being predicted. Prediction always assumes vintage_2023=0 -- i.e.
# "what would this cost at today's (2026) market level".
def _feature_value(name, km_from_cbd, outside_bangkok, road_km):
    if name == "km_from_cbd":
        return km_from_cbd
    if name == "outside_bangkok":
        return outside_bangkok
    if name == "km_from_cbd_x_outside_bangkok":
        return km_from_cbd * outside_bangkok
    if name == "vintage_2023":
        return 0.0
    if name == "log1p_km_from_cbd":
        return math.log1p(km_from_cbd)
    if name == "log1p_km_from_cbd_x_outside_bangkok":
        return math.log1p(km_from_cbd) * outside_bangkok
    if name == "log1p_km_to_major_road":
        return math.log1p(road_km if road_km is not None else 0.3)
    raise ValueError(f"Unknown model feature {name!r}")


def _log_price_from_model(model, km_from_cbd, outside_bangkok, road_km=None):
    """Evaluate the trained model at a given point, returning the
    log-price. Handles any feature combination produced by
    scripts/03_train_price_model.py's CANDIDATES, plus the oldest
    "slope"-only format for backward compatibility."""
    features = model.get("features")
    if not features:
        return model["intercept"] + model["slope"] * km_from_cbd  # oldest format

    raw = np.array([_feature_value(f, km_from_cbd, outside_bangkok, road_km) for f in features])
    if "feature_mean" in model:
        mean = np.array(model["feature_mean"])
        std = np.array(model["feature_std"])
        scaled = (raw - mean) / std
        return model["intercept"] + float(np.dot(model["coef"], scaled))
    return model["intercept"] + float(np.dot(model["coef"], raw))


def estimate_price_per_sqwah(province, km_from_cbd, model, treasury_stats, road_km=None):
    """Returns (low, point, high, method_note)."""
    if province in BMR_PROVINCES and model is not None:
        lo_km, hi_km = model["valid_km_range"]
        km_clamped = min(max(km_from_cbd, lo_km), hi_km)
        outside_bangkok = 0.0 if province == "Bangkok" else 1.0
        log_point = _log_price_from_model(model, km_clamped, outside_bangkok, road_km)
        std = model["residual_std_log"]
        point = math.exp(log_point)
        low = math.exp(log_point - std)
        high = math.exp(log_point + std)
        n_points = len(model.get("training_areas", []))
        mape = model.get("loo_mape_2026_scored", model.get("loo_mape", 0))
        if model.get("features") and len(model["features"]) > 1:
            uses_road = "log1p_km_to_major_road" in model["features"]
            road_bit = " and road-frontage proximity" if uses_road else ""
            note = (
                f"Bangkok/BMR model '{model.get('model_id', '')}': log-linear distance decay "
                f"with a separate slope outside Bangkok proper{road_bit} "
                f"(Ridge, fit on {n_points} sourced points, 2026-scored LOO MAPE {mape:.0%})"
            )
        else:
            note = f"Bangkok/BMR distance-decay model (log-linear, fit on {n_points} sourced points)"
        if km_from_cbd > hi_km:
            note += f"; distance {km_from_cbd:.1f}km exceeds the model's fitted range (0-{hi_km}km), clamped"
        return low, point, high, note

    stat = treasury_stats.get(province)
    if stat is None:
        return None, None, None, f"No data available for province {province!r}"
    p90 = float(stat["p90"])
    median = float(stat["median"])
    point = p90 * NON_BMR_MARKET_PREMIUM
    low = median * NON_BMR_MARKET_PREMIUM
    high = p90 * NON_BMR_MARKET_PREMIUM * 1.5
    note = (
        f"Coarse estimate: {province} Treasury-assessed p90 x {NON_BMR_MARKET_PREMIUM} "
        f"market premium (no radial market curve fit outside Bangkok/BMR)"
    )
    return low, point, high, note


# --- Main prediction flow ----------------------------------------------------

def predict(address, area_value, unit_text):
    model = load_json(MODEL_PATH, None)
    treasury_stats = load_treasury_stats()
    cache = load_json(CACHE_PATH, {})
    centroids = load_centroids()
    stations = load_stations()
    roads = load_roads()

    area_sqwah = parse_area(area_value, unit_text)

    geo = geocode_address(address, cache)
    used_fallback = False
    if geo is None:
        geo = fallback_lookup(address, centroids)
        used_fallback = True
    if geo is None:
        raise RuntimeError(
            f"Could not geocode {address!r} online or offline. "
            f"Try including a Bangkok district name (e.g. 'Pathum Wan') "
            f"or a province name."
        )

    province = geo["province"] or "Bangkok"
    # Nominatim sometimes returns "Krung Thep Maha Nakhon" for Bangkok.
    if "bangkok" in province.lower() or "krung thep" in province.lower():
        province = "Bangkok"
    province = normalize_province(province)

    km = haversine_km(model["cbd_lat"], model["cbd_lon"], geo["lat"], geo["lon"]) if model else None
    if km is None:
        km = 0.0

    road_km = nearest_road_km(geo["lat"], geo["lon"], roads)
    low, point, high, note = estimate_price_per_sqwah(province, km, model, treasury_stats, road_km)

    station_name, station_km = nearest_transit(geo["lat"], geo["lon"], stations)

    result = {
        "address_input": address,
        "resolved_location": geo["display_name"],
        "province": province,
        "district": geo.get("district", ""),
        "lat": geo["lat"], "lon": geo["lon"],
        "km_from_cbd": round(km, 2),
        "nearest_transit_station": station_name,
        "nearest_transit_km": None if station_km is None else round(station_km, 2),
        "nearest_major_road_km": None if road_km is None else round(road_km, 2),
        "used_offline_fallback": used_fallback,
        "area_sqwah": round(area_sqwah, 2),
        "price_low_per_sqwah": None if low is None else round(low),
        "price_point_per_sqwah": None if point is None else round(point),
        "price_high_per_sqwah": None if high is None else round(high),
        "total_low": None if low is None else round(low * area_sqwah),
        "total_point": None if point is None else round(point * area_sqwah),
        "total_high": None if high is None else round(high * area_sqwah),
        "method_note": note,
        "large_parcel_warning": area_sqwah > 5000,  # ~12.5 rai
    }
    return result


def print_result(r):
    print("\n" + "=" * 70)
    print("APPROXIMATE LAND PRICE ESTIMATE")
    print("=" * 70)
    print(f"Input address     : {r['address_input']}")
    print(f"Resolved location : {r['resolved_location']}")
    print(f"Province          : {r['province']}")
    print(f"Distance from CBD : {r['km_from_cbd']} km")
    if r.get("nearest_transit_station"):
        print(f"Nearest transit   : {r['nearest_transit_station']} ({r['nearest_transit_km']} km)")
    if r.get("nearest_major_road_km") is not None:
        print(f"Nearest major road: {r['nearest_major_road_km']} km")
    if r["used_offline_fallback"]:
        print("(offline fallback: matched by district/province name, not live geocoding)")
    print(f"\nLand area         : {r['area_sqwah']:,.2f} sq.wah")
    if r["large_parcel_warning"]:
        print(f"  ! This is a very large parcel ({r['area_sqwah']/400:,.1f} rai) -- "
              f"double check the unit you entered.")

    if r["price_point_per_sqwah"] is None:
        print(f"\nNo price estimate available: {r['method_note']}")
        return

    print(f"\nEstimated price   : {r['price_low_per_sqwah']:,} - {r['price_high_per_sqwah']:,} baht/sq.wah "
          f"(point estimate: {r['price_point_per_sqwah']:,})")
    print(f"Estimated total   : {r['total_low']:,} - {r['total_high']:,} baht "
          f"(point estimate: {r['total_point']:,})")
    print(f"\nMethod: {r['method_note']}")
    print(
        "\nCaveats: this is a directional area-level estimate, not a parcel "
        "appraisal. Same-distance addresses get the same estimate regardless "
        "of exact plot, road frontage, or transit proximity. See "
        "data/README.md for full limitations."
    )
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Approximate Thai land price predictor")
    parser.add_argument("--address", help="Property address")
    parser.add_argument("--area", help="Land area (numeric)")
    parser.add_argument("--unit", help="Area unit: sqwah, sqm, rai, or ngan")
    args = parser.parse_args()

    address = args.address
    area_value = args.area
    unit_text = args.unit

    if not address:
        address = input("Enter the property address: ").strip()
    if not area_value:
        area_value = input("Enter the land area (number): ").strip()
    if not unit_text:
        unit_text = input("Enter the unit (sq.wah / sq.m / rai / ngan): ").strip()

    result = predict(address, area_value, unit_text)
    print_result(result)


if __name__ == "__main__":
    main()
