"""Validation rules for sales-app orders.

Each rule returns a boolean mask of failing rows. `blocking` rules stop the
row loading into the model; the rest are flagged for the sales-ops team.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Rule:
    name: str
    blocking: bool
    description: str
    check: Callable[[pd.DataFrame, dict], pd.Series]


def _ref() -> dict:
    outlets = pd.read_csv(ROOT / "data" / "dim_outlet.csv")
    products = pd.read_csv(ROOT / "data" / "dim_product.csv")
    sales = pd.read_csv(ROOT / "data" / "fact_sales.csv", usecols=["sku", "qty"])
    return {
        "outlet_codes": set("OUT" + outlets.outlet_id.astype(str).str.zfill(4)),
        "skus": set(products.sku),
        "price": products.set_index("sku").unit_price_bdt.to_dict(),
        "qty_cap": sales.groupby("sku").qty.quantile(0.999).mul(3).to_dict(),
        "max_date": pd.Timestamp("2025-12-31 23:59"),
    }


RULES = [
    Rule("duplicate_submission", True, "Same order line submitted more than once (offline re-sync)",
         lambda d, r: d.duplicated(["order_id", "sku", "qty", "submitted_at"], keep="first")),
    Rule("unknown_outlet", True, "Outlet code is not in the outlet master",
         lambda d, r: ~d.outlet_code.isin(r["outlet_codes"])),
    Rule("unknown_sku", True, "SKU is not in the product master",
         lambda d, r: ~d.sku.isin(r["skus"])),
    Rule("qty_outlier", True, "Quantity is non-positive or over 3x the 99.9th percentile for the SKU",
         lambda d, r: (d.qty <= 0) | (d.qty > d.sku.map(r["qty_cap"]))),
    Rule("future_timestamp", True, "Submitted after the reporting period (device clock wrong)",
         lambda d, r: d.submitted_at > r["max_date"]),
    Rule("no_check_in", False, "Order taken without a GPS check-in at the outlet",
         lambda d, r: d.checked_in.eq(0)),
    Rule("price_mismatch", False, "Unit price differs from the price list",
         lambda d, r: (d.unit_price - d.sku.map(r["price"])).abs() > 0.01),
]


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (summary, clean rows, rejected rows)."""
    ref = _ref()
    df = df.copy()
    df["submitted_at"] = pd.to_datetime(df.submitted_at)
    results, blocking_mask = [], pd.Series(False, index=df.index)
    for rule in RULES:
        mask = rule.check(df, ref).fillna(True)
        results.append({"rule": rule.name, "blocking": rule.blocking, "description": rule.description,
                        "failed_rows": int(mask.sum()), "failed_pct": round(100 * mask.mean(), 2)})
        if rule.blocking:
            blocking_mask |= mask
    return pd.DataFrame(results), df[~blocking_mask], df[blocking_mask]


def main() -> None:
    from .export import build_export

    raw = build_export()
    summary, clean, rejected = validate(raw)
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    summary.to_csv(out / "salesapp_quality.csv", index=False)
    rejected.to_csv(out / "salesapp_rejected.csv", index=False)
    print(summary[["rule", "blocking", "failed_rows", "failed_pct"]].to_string(index=False))
    print(f"\n{len(clean):,} of {len(raw):,} order lines load cleanly ({100 * len(clean) / len(raw):.1f}%); "
          f"{len(rejected):,} held back for correction.")


if __name__ == "__main__":
    main()
