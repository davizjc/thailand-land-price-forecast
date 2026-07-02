"""One-time build of a BTS/MRT/ARL station table for Greater Bangkok, used
as a location feature (distance to nearest mass-transit station) in the
price model and predictor.

Pulls station nodes from the OSM Overpass API (station=subway/light_rail
plus railway=station within a bounding box covering the BMR). Cached to
data/processed/transit_stations.csv so this only needs to run once.
"""
import csv
import json
import os
import ssl
import urllib.parse
import urllib.request

import certifi

SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
DEST = os.path.join(PROCESSED_DIR, "transit_stations.csv")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Bounding box covering Bangkok + Samut Prakan + Nonthaburi + Pathum Thani
# (south, west, north, east)
BBOX = "13.55,100.30,14.05,100.85"

QUERY = f"""
[out:json][timeout:60];
(
  node["railway"="station"]["station"~"subway|light_rail"]({BBOX});
  node["railway"="station"]["network"~"BTS|MRT|Airport Rail Link|SRT", i]({BBOX});
);
out body;
"""


def fetch():
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=data, headers={
        "User-Agent": "thailand-land-price-forecast-research-project/1.0"
    })
    with urllib.request.urlopen(req, timeout=90, context=SSL_CONTEXT) as resp:
        return json.loads(resp.read())


def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    print("Querying Overpass API for BTS/MRT/ARL stations in Greater Bangkok...")
    try:
        data = fetch()
    except Exception as e:
        print(f"Overpass query failed: {e}")
        print("Falling back to a hardcoded list of major interchange/CBD stations.")
        data = {"elements": []}

    rows = []
    seen = set()
    for el in data.get("elements", []):
        name = el.get("tags", {}).get("name:en") or el.get("tags", {}).get("name")
        if not name:
            continue
        lat, lon = el.get("lat"), el.get("lon")
        if lat is None or lon is None:
            continue
        key = (round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)
        network = el.get("tags", {}).get("network", "")
        rows.append({"name": name, "network": network, "lat": lat, "lon": lon})

    if not rows:
        # Fallback: well-known interchange/CBD station coordinates (manually
        # sourced from OSM/Google Maps), used only if the live Overpass query
        # is unavailable, so the pipeline still works offline.
        FALLBACK_STATIONS = [
            ("Siam", "BTS", 13.7456, 100.5342),
            ("Chit Lom", "BTS", 13.7440, 100.5440),
            ("Asok", "BTS", 13.7367, 100.5602),
            ("Phrom Phong", "BTS", 13.7301, 100.5697),
            ("Thong Lo", "BTS", 13.7239, 100.5810),
            ("Ekkamai", "BTS", 13.7196, 100.5854),
            ("On Nut", "BTS", 13.7053, 100.6014),
            ("Bang Na", "BTS", 13.6680, 100.6047),
            ("Bearing", "BTS", 13.6607, 100.6046),
            ("Samrong", "BTS", 13.6489, 100.5972),
            ("Chong Nonsi", "BTS", 13.7238, 100.5296),
            ("Saphan Taksin", "BTS", 13.7188, 100.5145),
            ("Wongwian Yai", "BTS", 13.7204, 100.4966),
            ("Mo Chit", "BTS", 13.8025, 100.5535),
            ("Ha Yaek Lat Phrao", "MRT", 13.8168, 100.5610),
            ("Lat Phrao", "MRT", 13.8080, 100.5688),
            ("Sukhumvit", "MRT", 13.7373, 100.5606),
            ("Silom", "MRT", 13.7280, 100.5346),
            ("Sam Yan", "MRT", 13.7332, 100.5296),
            ("Hua Lamphong", "MRT", 13.7373, 100.5170),
            ("Bang Sue", "MRT", 13.8025, 100.5375),
            ("Suvarnabhumi", "ARL", 13.6900, 100.7501),
            ("Makkasan", "ARL", 13.7539, 100.5651),
            ("Phaya Thai", "BTS/ARL", 13.7566, 100.5335),
            ("Pak Kret", "MRT", 13.9127, 100.4996),
            ("Nonthaburi Civic Center", "MRT", 13.8613, 100.5147),
            ("Bang Yai", "MRT", 13.8697, 100.4159),
            ("Rangsit", "SRT", 13.9868, 100.6167),
            ("Bang Phli", "MRT", 13.6021, 100.6472),
            ("Kheha", "MRT", 13.5917, 100.6280),
        ]
        rows = [{"name": n, "network": net, "lat": lat, "lon": lon}
                for n, net, lat, lon in FALLBACK_STATIONS]
        print(f"Using {len(rows)} hardcoded fallback stations.")

    with open(DEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "network", "lat", "lon"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"Wrote {DEST} ({len(rows)} stations)")


if __name__ == "__main__":
    main()
