"""One-time build of a district/province centroid lookup table, used as the
offline fallback when live geocoding isn't available or an address is too
vague to geocode precisely (e.g. just "Bang Na, Bangkok").

Geocodes Bangkok's 50 districts (เขต) plus the centroid of each of the 10
provinces already covered by the Treasury data, via Nominatim (OpenStreetMap).
Results are cached to data/processed/geocode_cache.json so re-running this
script is instant after the first pass.
"""
import csv
import json
import math
import os
import ssl
import time
import urllib.parse
import urllib.request

import certifi

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
CACHE_PATH = os.path.join(PROCESSED_DIR, "geocode_cache.json")
DEST = os.path.join(PROCESSED_DIR, "district_centroids.csv")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "thailand-land-price-forecast-research-project/1.0"

SIAM_CBD_LAT = 13.7466
SIAM_CBD_LON = 100.5347

BANGKOK_DISTRICTS = [
    "Phra Nakhon", "Dusit", "Nong Chok", "Bang Rak", "Bang Khen", "Bang Kapi",
    "Pathum Wan", "Pom Prap Sattru Phai", "Phra Khanong", "Min Buri",
    "Lat Krabang", "Yan Nawa", "Samphanthawong", "Phaya Thai", "Thon Buri",
    "Bangkok Yai", "Huai Khwang", "Khlong San", "Taling Chan", "Bangkok Noi",
    "Bang Khun Thian", "Phasi Charoen", "Nong Khaem", "Rat Burana",
    "Bang Phlat", "Din Daeng", "Bueng Kum", "Sathon", "Bang Sue",
    "Chatuchak", "Bang Kho Laem", "Prawet", "Khlong Toei", "Suan Luang",
    "Chom Thong", "Don Mueang", "Ratchathewi", "Lat Phrao", "Watthana",
    "Bang Khae", "Lak Si", "Sai Mai", "Khan Na Yao", "Saphan Sung",
    "Wang Thonglang", "Khlong Sam Wa", "Bang Na", "Thawi Watthana",
    "Thung Khru", "Bang Bon",
]

PROVINCES = [
    "Bangkok", "Samut Prakan", "Nonthaburi", "Pathum Thani", "Nakhon Pathom",
    "Samut Sakhon", "Ayutthaya", "Saraburi", "Chon Buri", "Chachoengsao",
]


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def save_cache(cache):
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def geocode(query, cache):
    if query in cache:
        return cache[query]
    params = urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "accept-language": "en",
    })
    url = f"{NOMINATIM_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10, context=SSL_CONTEXT) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f"  geocode failed for {query!r}: {e}")
        cache[query] = None
        return None
    time.sleep(1.1)  # Nominatim usage policy: max 1 request/second
    if not data:
        print(f"  no result for {query!r}")
        cache[query] = None
        return None
    result = {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"])}
    cache[query] = result
    return result


def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    cache = load_cache()
    rows = []

    for prov in PROVINCES:
        query = f"{prov}, Thailand"
        print(f"Geocoding province centroid: {query}")
        r = geocode(query, cache)
        if r is None:
            continue
        km = haversine_km(SIAM_CBD_LAT, SIAM_CBD_LON, r["lat"], r["lon"])
        rows.append({
            "name": prov, "level": "province", "province": prov,
            "lat": r["lat"], "lon": r["lon"], "km_from_cbd": round(km, 2),
        })
        save_cache(cache)

    for district in BANGKOK_DISTRICTS:
        query = f"{district}, Bangkok, Thailand"
        print(f"Geocoding district: {query}")
        r = geocode(query, cache)
        if r is None:
            continue
        km = haversine_km(SIAM_CBD_LAT, SIAM_CBD_LON, r["lat"], r["lon"])
        rows.append({
            "name": district, "level": "district", "province": "Bangkok",
            "lat": r["lat"], "lon": r["lon"], "km_from_cbd": round(km, 2),
        })
        save_cache(cache)

    with open(DEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "level", "province", "lat", "lon", "km_from_cbd"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"\nWrote {DEST} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
