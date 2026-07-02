"""One-time build of a major-road point layer for Greater Bangkok, used as
a location feature (distance to nearest arterial/highway frontage) in the
price model and predictor -- addresses the model's blindness to
road-frontage vs. interior-soi pricing at fixed CBD distance (see
data/NOTES.md).

Pulls motorway/trunk/primary ways from the OSM Overpass API within the BMR
bounding box, then samples each way's geometry into points roughly every
~200m so "distance to nearest sampled point" approximates "distance to
nearest major road" without needing full line-segment geometry at predict
time. Cached to data/processed/major_roads.csv so this only needs to run
once.
"""
import csv
import json
import math
import os
import ssl
import urllib.parse
import urllib.request

import certifi

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
DEST = os.path.join(PROCESSED_DIR, "major_roads.csv")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box covering Bangkok + Samut Prakan + Nonthaburi + Pathum Thani +
# Nakhon Pathom + Samut Sakhon (the BMR provinces the model is fit on).
BBOX = "13.45,100.05,14.10,100.95"

QUERY = f"""
[out:json][timeout:120];
(
  way["highway"~"^(motorway|trunk|primary)$"]({BBOX});
);
out geom;
"""

SAMPLE_SPACING_KM = 0.2


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch():
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=data, headers={
        "User-Agent": "thailand-land-price-forecast-research-project/1.0"
    })
    with urllib.request.urlopen(req, timeout=150, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read())


def sample_way(geometry, road_class, spacing_km=SAMPLE_SPACING_KM):
    """Walk a way's node geometry and emit a point roughly every
    spacing_km, so a dense highway doesn't dominate a sparse one."""
    points = []
    accumulated = 0.0
    if not geometry:
        return points
    points.append((geometry[0]["lat"], geometry[0]["lon"], road_class))
    for i in range(1, len(geometry)):
        lat1, lon1 = geometry[i - 1]["lat"], geometry[i - 1]["lon"]
        lat2, lon2 = geometry[i]["lat"], geometry[i]["lon"]
        seg_km = haversine_km(lat1, lon1, lat2, lon2)
        accumulated += seg_km
        if accumulated >= spacing_km:
            points.append((lat2, lon2, road_class))
            accumulated = 0.0
    return points


FALLBACK_ROADS = [
    # Well-known arterial/highway waypoints (manually sourced from OSM),
    # used only if the live Overpass query is unavailable.
    ("Sukhumvit Rd (CBD)", 13.7373, 100.5606, "primary"),
    ("Sukhumvit Rd (Ekkamai)", 13.7196, 100.5854, "primary"),
    ("Sukhumvit Rd (Bang Na)", 13.6680, 100.6047, "primary"),
    ("Sukhumvit Rd (Samrong)", 13.6021, 100.6472, "primary"),
    ("Rama I / Phayathai Rd", 13.7466, 100.5347, "primary"),
    ("Phetkasem Rd", 13.7150, 100.4600, "primary"),
    ("Ratchadaphisek Rd", 13.7900, 100.5750, "primary"),
    ("Vibhavadi Rangsit Rd (Don Mueang)", 13.9124, 100.6068, "trunk"),
    ("Lat Phrao Rd", 13.8080, 100.5688, "primary"),
    ("Bang Na-Trat Rd (KM6)", 13.6650, 100.6500, "trunk"),
    ("Bang Na-Trat Rd (Bang Kaeo)", 13.6620, 100.6480, "trunk"),
    ("Kanchanaphisek Ring Rd (west)", 13.8000, 100.4100, "motorway"),
    ("Kanchanaphisek Ring Rd (east)", 13.8000, 100.7500, "motorway"),
    ("Tiwanon Rd, Nonthaburi", 13.8613, 100.5147, "primary"),
    ("Chaeng Watthana Rd", 13.9038, 100.5287, "primary"),
    ("Phahonyothin Rd, Rangsit", 13.9868, 100.6167, "primary"),
    ("Ekkachai Rd, Samut Sakhon", 13.5475, 100.2740, "primary"),
    ("Petchakasem Rd, Nakhon Pathom", 13.8196, 100.0645, "primary"),
]


def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    print("Querying Overpass API for motorway/trunk/primary roads in Greater Bangkok...")
    rows = []
    try:
        data = fetch()
        for el in data.get("elements", []):
            if el.get("type") != "way":
                continue
            road_class = el.get("tags", {}).get("highway", "primary")
            for lat, lon, cls in sample_way(el.get("geometry", []), road_class):
                rows.append({"lat": lat, "lon": lon, "road_class": cls})
    except Exception as e:
        print(f"Overpass query failed: {e}")

    if not rows:
        print(f"Using {len(FALLBACK_ROADS)} hardcoded fallback road waypoints.")
        rows = [{"lat": lat, "lon": lon, "road_class": cls}
                for _, lat, lon, cls in FALLBACK_ROADS]

    # De-dupe near-identical points (overlapping ways at intersections).
    seen = set()
    deduped = []
    for r in rows:
        key = (round(r["lat"], 4), round(r["lon"], 4))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    with open(DEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lat", "lon", "road_class"])
        w.writeheader()
        for r in deduped:
            w.writerow(r)

    print(f"Wrote {DEST} ({len(deduped)} road sample points)")


if __name__ == "__main__":
    main()
