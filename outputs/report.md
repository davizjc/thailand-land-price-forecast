# Land Price Report — Bangkok Metropolitan Region + Eastern Seaboard

Covers 10 provinces: Bangkok, Samut Prakan, Nonthaburi, Pathum Thani, Nakhon Pathom, Samut Sakhon (Bangkok Metropolitan Region) plus Ayutthaya, Saraburi, Chon Buri, Chachoengsao (Eastern Seaboard).

## 1. Official Treasury-assessed floor price, by province

Computed directly from ~6.7M real per-parcel appraisal records (catalog.treasury.go.th, dataset `land-valuation`). These are legal tax-assessment floors, well below actual market prices.

| Province | Parcels | Median (baht/sq.wah) | p90 | p99 |
|---|---|---|---|---|
| Bangkok | 2,281,482 | 30,000 | 85,000 | 300,000 |
| Samut Prakan | 625,959 | 22,000 | 38,500 | 97,000 |
| Nonthaburi | 701,099 | 20,000 | 39,500 | 80,000 |
| Pathum Thani | 784,397 | 14,000 | 28,000 | 45,000 |
| Samut Sakhon | 301,125 | 10,000 | 27,000 | 51,000 |
| Chon Buri | 984,881 | 7,000 | 20,000 | 56,000 |
| Nakhon Pathom | 546,087 | 1,600 | 15,000 | 35,000 |
| Ayutthaya | 465,874 | 1,500 | 11,000 | 27,000 |
| Saraburi | 380,137 | 1,000 | 7,500 | 25,000 |
| Chachoengsao | 407,353 | 750 | 10,000 | 20,000 |

## 2. Bangkok current market price by distance from CBD

Log-linear regression on 14 sourced district price points (Bangkok + BMR only). Leave-one-out MAPE 28.3% vs. 150.4% naive median baseline — beats baseline, see scripts/03 output.

| Distance from CBD (km) | Estimated price (baht/sq.wah) |
|---|---|
| 0 | 870,417 |
| 1 | 792,437 |
| 2 | 721,443 |
| 5 | 544,394 |
| 8 | 410,795 |
| 10 | 340,486 |
| 15 | 212,954 |
| 20 | 133,190 |
| 25 | 83,303 |
| 30 | 52,101 |

## 3. Sourced market price points, all provinces

Real cited prices from published market reports (see `source` column for each).

| Area | Province | Zone type | Price range (baht/sq.wah) |
|---|---|---|---|
| Silom/Sathorn | Bangkok | CBD | 1,000,000 - 1,200,000 |
| Ploenchit/Wireless Road | Bangkok | CBD | 900,000 - 1,100,000 |
| Ratchadamri Road | Bangkok | CBD | 750,000 - 1,000,000 |
| Rama I Road | Bangkok | CBD | 400,000 - 1,000,000 |
| Yaowarat (Chinatown) | Bangkok | Inner | 700,000 |
| Thonglor/Ekamai | Bangkok | Inner | 700,000 - 950,000 |
| Sukhumvit (main) | Bangkok | Inner | 230,000 - 750,000 |
| Asoke/Petchburi | Bangkok | Inner | 600,000 |
| Naradhiwas Rajanagarindra | Bangkok | Inner | 280,000 - 600,000 |
| Phaya Thai | Bangkok | Middle | 500,000 |
| Lat Phrao | Bangkok | Outer | 150,000 - 200,000 |
| Nonthaburi (Kaerai-Tiwanon-Rattanathibet) | Nonthaburi | Suburb | 100,000 - 250,000 |
| Nonthaburi (assessed range - provincewide) | Nonthaburi | Assessed range | 1,000 - 170,000 |
| Samut Prakan (Bangna-Theparak) | Samut Prakan | Suburb | 70,000 - 180,000 |
| Samut Prakan (assessed range - provincewide) | Samut Prakan | Assessed range | 500 - 160,000 |
| Pathum Thani (Rangsit-Khlong Luang) | Pathum Thani | Suburb | 30,000 - 90,000 |
| Pathum Thani (assessed range - provincewide) | Pathum Thani | Assessed range | 1,000 - 100,000 |
| Nakhon Pathom (assessed range - provincewide) | Nakhon Pathom | Assessed range | 200 - 80,000 |
| Samut Sakhon (assessed range - provincewide) | Samut Sakhon | Assessed range | 500 - 70,000 |
| Pattaya Beach Road | Chon Buri | Coastal prime | 610,000 |
| Pattaya (assessed avg) | Chon Buri | Assessed range | 200,000 - 220,000 |
| Sriracha (Sukhumvit - opp Robinson) | Chon Buri | Market | 95,000 |

## 4. Trend context (Bangkok index)
Most recent known nominal YoY change: 1.2579%. Holt-Winters forecast, next 4 quarters (MAPE 0.93% backtest vs 1.64% naive):
| Quarters ahead | Forecast index |
|---|---|
| 1 | 184.57 |
| 2 | 185.53 |
| 3 | 186.48 |
| 4 | 187.44 |

## Caveats
- Treasury figures are assessed values (tax basis) for ALL 10 provinces -- real, complete, computed from raw data, not estimated.
- Sourced market points (section 3) are curated from published reports, not raw transactions -- directional, not exact. Real transactions are typically 1.5-3x the assessed floor in central areas.
- The distance-decay curve (section 2) is fit to Bangkok/BMR points only; Chon Buri (Pattaya/Sriracha) is a separate urban hub and is not on the same curve -- see its points directly in section 3.
- Ayutthaya, Saraburi, Chachoengsao, Nakhon Pathom, and Samut Sakhon have Treasury floor data but limited/no sourced market points yet -- the Treasury median/p90 columns are the most reliable numbers available for those provinces right now.
