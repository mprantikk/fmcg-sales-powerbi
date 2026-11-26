"""Quick matplotlib previews of the main report views (until the Power BI screenshots are added)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data"
BLUE, ORANGE, GREY, INK, INK2 = "#257de0", "#f47230", "#c2c2c2", "#191919", "#666666"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GREY,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": "#ececec",
                     "axes.axisbelow": True, "figure.dpi": 150})


def main():
    s = pd.read_csv(D / "fact_sales.csv")
    s["net"] = s.net_bdt - s.returned_bdt
    s["ym"] = s.date_key.astype(str).str[:6]
    t = pd.read_csv(D / "fact_targets.csv")
    t["ym"] = t.date_key.astype(str).str[:6]
    m = s.groupby("ym").net.sum().to_frame().join(t.groupby("ym").target_bdt.sum())
    fig, ax = plt.subplots(figsize=(8, 3.8))
    x = range(len(m))
    ax.bar(x, m.net / 1e6, color=BLUE, width=0.62, label="Net sales")
    ax.plot(x, m.target_bdt / 1e6, color=ORANGE, lw=2, marker="o", ms=3, label="Target")
    ax.set_xticks(list(x)[::3], [f"{i[:4]}-{i[4:]}" for i in m.index[::3]])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1f}M")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, loc="upper left")
    ax.set_title("Net sales vs target by month (BDT)", loc="left", fontweight="bold", color=INK)
    fig.savefig(ROOT / "docs" / "preview_sales_vs_target.png", bbox_inches="tight")
    plt.close(fig)

    o = pd.read_csv(D / "dim_outlet.csv").merge(pd.read_csv(D / "dim_territory.csv"), on="territory_id")
    s25 = s[s.date_key >= 20250101].merge(o[["outlet_id", "division"]], on="outlet_id")
    t25 = t[t.date_key >= 20250101].merge(pd.read_csv(D / "dim_territory.csv"), on="territory_id")
    a = (s25.groupby("division").net.sum() / t25.groupby("division").target_bdt.sum() * 100).sort_values()
    fig, ax = plt.subplots(figsize=(8, 3.6))
    colors = [BLUE if v >= 100 else ORANGE if v >= 90 else "#dc3c3d" for v in a]
    bars = ax.barh(a.index, a.values, color=colors, height=0.6)
    ax.axvline(100, color=INK2, lw=1, ls="--")
    for b, v in zip(bars, a.values):
        ax.text(v + 0.5, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", fontsize=9, color=INK)
    ax.set_xlim(min(80, a.min() - 5), max(110, a.max() + 6))
    ax.grid(axis="y", visible=False)
    ax.set_title("Target achievement by division, 2025", loc="left", fontweight="bold", color=INK)
    fig.savefig(ROOT / "docs" / "preview_division_achievement.png", bbox_inches="tight")
    plt.close(fig)
    print(a.round(1).to_string())


if __name__ == "__main__":
    main()
