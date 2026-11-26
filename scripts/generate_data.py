"""Generate the synthetic star schema for the FMCG sales & distribution model.

A fictional dairy and beverage company selling through distributors to retail
outlets across Bangladesh, Jan 2024 to Dec 2025. Seeded, so every figure in
the README and in the reconciliation targets is reproducible.

    python scripts/generate_data.py
"""

from __future__ import annotations

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(2021)
OUT = Path(__file__).resolve().parent.parent / "data"
START, END = date(2024, 1, 1), date(2025, 12, 31)

GEO = {  # division: [(region, [territories])]
    "Dhaka": [("Dhaka North", ["Uttara", "Mirpur", "Gulshan"]), ("Dhaka South", ["Dhanmondi", "Motijheel", "Jatrabari"]),
              ("Gazipur", ["Tongi", "Joydebpur"])],
    "Chattogram": [("Chattogram City", ["Agrabad", "Panchlaish"]), ("Cumilla", ["Cumilla Sadar", "Laksam"])],
    "Rajshahi": [("Rajshahi", ["Rajshahi Sadar", "Bogura"])],
    "Khulna": [("Khulna", ["Khulna Sadar", "Jashore"])],
    "Sylhet": [("Sylhet", ["Sylhet Sadar", "Moulvibazar"])],
    "Rangpur": [("Rangpur", ["Rangpur Sadar", "Dinajpur"])],
}
PRODUCTS = [  # sku, name, category, brand, pack, unit price (BDT), launch date
    ("SKU01", "Sweet Yogurt 80g", "Yogurt", "Doi Fresh", "80g cup", 15, START),
    ("SKU02", "Plain Yogurt 80g", "Yogurt", "Doi Fresh", "80g cup", 15, START),
    ("SKU03", "Sweet Yogurt 500g", "Yogurt", "Doi Fresh", "500g tub", 85, START),
    ("SKU04", "Mango Lassi 200ml", "Drinks", "Lassi Joy", "200ml bottle", 30, START),
    ("SKU05", "Chocolate Milk 200ml", "Drinks", "MooMoo", "200ml pack", 35, START),
    ("SKU06", "UHT Milk 1L", "Milk", "MooMoo", "1L pack", 110, START),
    ("SKU07", "Fortified Yogurt 60g", "Yogurt", "Shokti+", "60g cup", 12, START),
    ("SKU08", "Strawberry Yogurt 80g", "Yogurt", "Doi Fresh", "80g cup", 18, date(2024, 7, 1)),
    ("SKU09", "Probiotic Drink 65ml", "Drinks", "GutGood", "65ml bottle", 25, date(2025, 2, 1)),
    ("SKU10", "Butter 100g", "Dairy spreads", "MooMoo", "100g block", 140, START),
]
OUTLET_TYPES = [("Grocery", 0.55), ("Pharmacy", 0.12), ("Supermarket", 0.08), ("Tea stall", 0.15), ("Confectionery", 0.10)]
TYPE_SIZE = {"Grocery": 1.0, "Pharmacy": 0.6, "Supermarket": 3.5, "Tea stall": 0.5, "Confectionery": 0.8}


def write(name, header, rows):
    with open(OUT / f"{name}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def main():
    OUT.mkdir(exist_ok=True)
    # --- territories, distributors, reps
    territories, distributors, reps = [], [], []
    tid = did = rid = 0
    for division, regions in GEO.items():
        for region, terrs in regions:
            for t in terrs:
                tid += 1
                urban = division in ("Dhaka", "Chattogram")
                territories.append((tid, t, region, division, "Urban" if urban else "Semi-urban"))
                did += 1
                distributors.append((did, f"{t} Distribution House", tid))
                for _ in range(2 if urban else 1):
                    rid += 1
                    reps.append((rid, f"Sales Officer {rid:02d}", tid, random.choice(["2019", "2021", "2022", "2023", "2024"])))
    # --- outlets
    outlets = []
    oid = 0
    for t in territories:
        n = random.randint(55, 80) if t[4] == "Urban" else random.randint(35, 55)
        for _ in range(n):
            oid += 1
            otype = random.choices([o[0] for o in OUTLET_TYPES], weights=[o[1] for o in OUTLET_TYPES])[0]
            outlets.append((oid, f"Outlet {oid:04d}", otype, t[0], random.choice(["A", "B", "B", "C", "C", "C"])))
    terr_reps = {}
    for r in reps:
        terr_reps.setdefault(r[2], []).append(r[0])
    rep_skill = {r[0]: random.uniform(0.75, 1.2) for r in reps}

    # --- dates
    dates, d = [], START
    while d <= END:
        dates.append((d.strftime("%Y%m%d"), d.isoformat(), d.year, f"Q{(d.month - 1) // 3 + 1}", d.month,
                      d.strftime("%b"), d.strftime("%Y-%m"), d.isoweekday(), d.strftime("%a"), int(d.weekday() == 4)))
        d += timedelta(days=1)

    # --- visits and sales (each outlet visited weekly on a fixed weekday)
    visits, sales, targets = [], [], []
    vid = lid = 0
    rep_month_sales = {}
    for o in outlets:
        o_id, _, otype, t_id, grade = o
        weekday = random.randint(0, 5)          # Friday (4) is the weekend; reps skip it below
        if weekday == 4:
            weekday = 5
        rep = random.choice(terr_reps[t_id])
        size = TYPE_SIZE[otype] * {"A": 1.6, "B": 1.0, "C": 0.6}[grade]
        listed = [p for p in PRODUCTS if random.random() < (0.9 if p[2] == "Yogurt" else 0.55)]
        d = START + timedelta(days=(weekday - START.weekday()) % 7)
        while d <= END:
            month_idx = (d.year - 2024) * 12 + d.month - 1
            season = 1 + 0.18 * math.sin((d.month - 3) / 12 * 2 * math.pi)   # summer peak for drinks/yogurt
            ramadan = 1.12 if (d.year == 2024 and date(2024, 3, 11) <= d <= date(2024, 4, 9)) or \
                              (d.year == 2025 and date(2025, 3, 1) <= d <= date(2025, 3, 30)) else 1.0
            growth = 1 + month_idx * 0.008
            vid += 1
            visited = random.random() < 0.93
            productive = visited and random.random() < min(0.95, 0.62 * rep_skill[rep] * (1.1 if grade == "A" else 1))
            gps_ok = random.random() > 0.03
            visits.append((vid, d.strftime("%Y%m%d"), o_id, rep, int(visited), int(productive), int(gps_ok)))
            if productive:
                for p in listed:
                    if p[6] > d or random.random() > 0.6:
                        continue
                    raw = max(0.0, random.gauss(8, 3)) * size * season * ramadan * growth
                    qty = max(1, int(raw) + (random.random() < raw - int(raw)))  # stochastic rounding: no threshold jumps
                    if p[0] in ("SKU06", "SKU10"):
                        qty = max(1, qty // 4)
                    gross = qty * p[5]
                    disc = round(gross * (0.04 if grade == "A" else 0.02 if grade == "B" else 0), 2)
                    returned = qty if random.random() < 0.012 else 0
                    lid += 1
                    sales.append((lid, d.strftime("%Y%m%d"), vid, o_id, p[0], rep, qty, gross, disc,
                                  round(gross - disc, 2), returned, round(returned * p[5], 2)))
                    key = (rep, d.strftime("%Y-%m"))
                    rep_month_sales[key] = rep_month_sales.get(key, 0) + gross - disc
            d += timedelta(days=7)
    # --- monthly targets per rep (set from last year's run-rate + stretch, as a sales ops team would)
    rep_terr = {r[0]: r[2] for r in reps}
    for (rep, month), actual in sorted(rep_month_sales.items()):
        stretch = random.uniform(0.92, 1.15)
        targets.append((rep, rep_terr[rep], month, month.replace("-", "") + "01", round(actual * stretch / 1000) * 1000))

    write("dim_date", ["date_key", "date", "year", "quarter", "month_no", "month", "year_month", "weekday_no", "weekday", "is_weekend"], dates)
    write("dim_product", ["sku", "product_name", "category", "brand", "pack", "unit_price_bdt", "launch_date"],
          [p[:6] + (p[6].isoformat(),) for p in PRODUCTS])
    write("dim_territory", ["territory_id", "territory", "region", "division", "area_type"], territories)
    write("dim_distributor", ["distributor_id", "distributor", "territory_id"], distributors)
    write("dim_sales_rep", ["rep_id", "rep_name", "territory_id", "joined_year"], reps)
    write("dim_outlet", ["outlet_id", "outlet_name", "outlet_type", "territory_id", "grade"], outlets)
    write("fact_visits", ["visit_id", "date_key", "outlet_id", "rep_id", "visited", "productive", "gps_verified"], visits)
    write("fact_sales", ["line_id", "date_key", "visit_id", "outlet_id", "sku", "rep_id", "qty", "gross_bdt",
                         "discount_bdt", "net_bdt", "returned_qty", "returned_bdt"], sales)
    write("fact_targets", ["rep_id", "territory_id", "year_month", "date_key", "target_bdt"], targets)
    print(f"outlets={len(outlets)} reps={len(reps)} visits={len(visits)} sales_lines={len(sales)}")


if __name__ == "__main__":
    main()
