"""Simulate the raw order export from the field sales app.

Built from fact_sales, then roughened the way real mobile-app exports are:
offline re-syncs create duplicate submissions, typos in outlet codes, a
fat-fingered quantity, orders entered without a check-in, a wrong device
clock, and prices that don't match the price list.
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def build_export(n_orders: int = 4000, seed: int = 11) -> pd.DataFrame:
    rng = random.Random(seed)
    sales = pd.read_csv(ROOT / "data" / "fact_sales.csv")
    prices = pd.read_csv(ROOT / "data" / "dim_product.csv").set_index("sku").unit_price_bdt
    visit_ids = sorted(rng.sample(sorted(sales.visit_id.unique()), n_orders))
    df = sales[sales.visit_id.isin(visit_ids)].copy()
    df["order_id"] = "ORD" + df.visit_id.astype(str)
    df["submitted_at"] = pd.to_datetime(df.date_key.astype(str)) + pd.to_timedelta(
        df.visit_id.map(lambda v: 9 * 60 + (v * 37) % (9 * 60)), unit="m")
    df["unit_price"] = df.sku.map(prices).astype(float)
    df["outlet_code"] = "OUT" + df.outlet_id.astype(str).str.zfill(4)
    df["checked_in"] = 1
    df = df[["order_id", "submitted_at", "rep_id", "outlet_code", "sku", "qty", "unit_price", "checked_in"]]

    orders = df.order_id.unique().tolist()
    pick = lambda k: set(rng.sample(orders, k))
    dup = df[df.order_id.isin(pick(40))]                                     # offline re-sync
    df.loc[df.order_id.isin(pick(25)), "outlet_code"] = "OUT9" + str(rng.randint(100, 999))  # typo'd code
    df.loc[df.order_id.isin(pick(30)), "checked_in"] = 0                     # no check-in
    fat = df.sample(n=15, random_state=seed).index
    df.loc[fat, "qty"] = df.loc[fat, "qty"] * 100                            # fat-finger
    clock = df.order_id.isin(pick(10))
    df.loc[clock, "submitted_at"] = df.loc[clock, "submitted_at"] + pd.Timedelta(days=400)  # device clock
    price = df.sample(n=40, random_state=seed + 1).index
    df.loc[price, "unit_price"] = df.loc[price, "unit_price"] * 1.2         # stale price list
    return pd.concat([df, dup]).sort_values("submitted_at").reset_index(drop=True)
