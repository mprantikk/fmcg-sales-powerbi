from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"


@pytest.fixture(scope="module")
def t():
    return {p.stem: pd.read_csv(p) for p in D.glob("*.csv")}


def test_primary_keys_unique(t):
    for table, key in [("dim_date", "date_key"), ("dim_product", "sku"), ("dim_outlet", "outlet_id"),
                       ("dim_sales_rep", "rep_id"), ("dim_territory", "territory_id"), ("fact_sales", "line_id"),
                       ("fact_visits", "visit_id")]:
        assert t[table][key].is_unique, table
    assert not t["fact_targets"].duplicated(["rep_id", "year_month"]).any()


def test_foreign_keys_resolve(t):
    for fact, col, dim, key in [("fact_sales", "sku", "dim_product", "sku"), ("fact_sales", "outlet_id", "dim_outlet", "outlet_id"),
                                ("fact_sales", "date_key", "dim_date", "date_key"), ("fact_sales", "visit_id", "fact_visits", "visit_id"),
                                ("fact_visits", "rep_id", "dim_sales_rep", "rep_id"), ("fact_targets", "date_key", "dim_date", "date_key"),
                                ("fact_targets", "territory_id", "dim_territory", "territory_id"),
                                ("dim_outlet", "territory_id", "dim_territory", "territory_id")]:
        assert t[fact][col].isin(t[dim][key]).all(), f"{fact}.{col}"


def test_sales_only_on_productive_visits(t):
    productive = set(t["fact_visits"].loc[t["fact_visits"].productive == 1, "visit_id"])
    assert t["fact_sales"].visit_id.isin(productive).all()


def test_amounts_are_consistent(t):
    s = t["fact_sales"]
    assert ((s.net_bdt - (s.gross_bdt - s.discount_bdt)).abs() < 0.01).all()
    assert (s.returned_qty <= s.qty).all() and (s.qty > 0).all()


def test_no_sales_before_launch(t):
    s = t["fact_sales"].merge(t["dim_product"], on="sku")
    assert (pd.to_datetime(s.date_key.astype(str)) >= pd.to_datetime(s.launch_date)).all()


def test_expected_kpis_file_is_current():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from expected_kpis import kpis

    text = (ROOT / "powerbi" / "EXPECTED_KPIS.md").read_text()
    k = kpis()
    assert f"| Net Sales (BDT) | {k['Net Sales (BDT)']:,} |" in text
    assert f"| Target Achievement % | {k['Target Achievement %']:,} |" in text


def test_pbip_is_generated_and_complete():
    import re
    import subprocess
    import sys

    subprocess.run([sys.executable, str(ROOT / "scripts" / "build_pbip.py")], check=True, capture_output=True)
    sm = ROOT / "powerbi" / "pbip" / "FMCG Sales.SemanticModel" / "definition"
    tables = {p.stem for p in (sm / "tables").glob("*.tmdl")}
    assert tables == {p.stem for p in D.glob("*.csv")}
    dax_measures = re.findall(r"^([A-Z][^=\n/]*?) =", (ROOT / "powerbi" / "measures.dax").read_text(), re.M)
    tmdl = (sm / "tables" / "fact_sales.tmdl").read_text()
    assert tmdl.count("\tmeasure ") == len(dax_measures)
    rels = (sm / "relationships.tmdl").read_text()
    assert rels.count("relationship ") == 13 and rels.count("isActive: false") == 1
    assert "dataCategory: Time" in (sm / "tables" / "dim_date.tmdl").read_text()
