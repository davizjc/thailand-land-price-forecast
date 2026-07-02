"""Download the official Treasury Department (กรมธนารักษ์) land valuation
dataset for Bangkok + the Bangkok Metropolitan Region + Eastern Seaboard
provinces, from the open-data catalog (catalog.treasury.go.th).

This is per-parcel data used for tax assessment: reliable price *floors*,
but keyed to UTM survey-grid codes with no public lookup to district names
-- so it's used only for per-province floor-price statistics
(see 02_treasury_summary.py), not district-level breakdowns.
"""
import os
import subprocess

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

# province_key -> (Thai name, CSV resource URL)
PROVINCES = {
    "bangkok": ("กรุงเทพมหานคร",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/00da1ca3-2c41-436d-a426-d0c06f8cae03/download/land_10_bangkok.csv"),
    "samut_prakan": ("สมุทรปราการ",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/9919be07-ecdd-4542-bd67-6d408691dbd0/download/land_11_samut-prakan.csv"),
    "nonthaburi": ("นนทบุรี",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/1385f623-15c9-4253-b659-093ace6840da/download/land_12_nonthaburi.csv"),
    "pathum_thani": ("ปทุมธานี",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/bb55833f-6dd0-491a-bbce-48a3301fb303/download/land_13_pathum-thani.csv"),
    "ayutthaya": ("พระนครศรีอยุธยา",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/6316d19b-2c3f-4dfc-90d7-10928af87254/download/land_14_phra-nakhon-si-ayutthaya.csv"),
    "saraburi": ("สระบุรี",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/706137e2-5ca9-468e-8ea4-d7545b4b7e31/download/land_19_saraburi.csv"),
    "chon_buri": ("ชลบุรี",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/26af9fa1-75f5-442e-bf45-4aabbae47c6a/download/land_20_chon-buri.csv"),
    "chachoengsao": ("ฉะเชิงเทรา",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/038b5bbc-6c46-4edf-a8cc-b5334d1230bc/download/land_24_chachoengsao.csv"),
    "nakhon_pathom": ("นครปฐม",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/16b9866c-c457-4845-8437-d6694bbe8338/download/land_73_nakhon-pathom.csv"),
    "samut_sakhon": ("สมุทรสาคร",
        "https://catalog.treasury.go.th/dataset/f5072145-2f1a-4500-bf60-d122b866ac2f/"
        "resource/0355472e-c037-41bd-a34c-d6006d4dd79d/download/land_74_samut-sakhon.csv"),
}


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    for key, (thai_name, url) in PROVINCES.items():
        dest = os.path.join(RAW_DIR, f"land_valuation_{key}.csv")
        if os.path.exists(dest):
            print(f"Already have {key} ({thai_name}): {os.path.getsize(dest) / 1e6:.1f} MB")
            continue
        print(f"Downloading {key} ({thai_name})...")
        subprocess.run(["curl", "-sL", url, "-o", dest], check=True)
        print(f"  Saved to {dest} ({os.path.getsize(dest) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
