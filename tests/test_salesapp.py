from salesapp.checks import validate
from salesapp.export import build_export


def test_every_injected_defect_type_is_caught():
    summary, _, _ = validate(build_export(n_orders=1500, seed=3))
    s = summary.set_index("rule").failed_rows
    for rule in ["duplicate_submission", "unknown_outlet", "qty_outlier", "future_timestamp", "no_check_in", "price_mismatch"]:
        assert s[rule] > 0, rule
    assert s["unknown_sku"] == 0


def test_blocking_rules_split_rows():
    raw = build_export(n_orders=1500, seed=3)
    summary, clean, rejected = validate(raw)
    assert len(clean) + len(rejected) == len(raw)
    assert not clean.duplicated(["order_id", "sku", "qty", "submitted_at"]).any()
    assert len(rejected) / len(raw) < 0.05
