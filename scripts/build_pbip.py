"""Generate a Power BI Project (PBIP) from the CSV headers and powerbi/measures.dax.

Output: powerbi/pbip/FMCG Sales.pbip, a TMDL semantic model (tables, types,
relationships, date table, measures with folders and formats) and a report
with five empty, named pages ready for visuals.

    python scripts/build_pbip.py
Open `powerbi/pbip/FMCG Sales.pbip` in Power BI Desktop (Feb 2024 or later),
then set the DataFolder parameter to your local data folder and Refresh.
"""

from __future__ import annotations

import csv
import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "powerbi" / "pbip"
NAME = "FMCG Sales"
NS = uuid.UUID("6f1c2a52-6b1e-4a43-9a52-0a6f2d0c9b11")


def tag(*parts: str) -> str:
    """Deterministic lineage tags so regenerating doesn't churn the files."""
    return str(uuid.uuid5(NS, "/".join(parts)))


# column -> (TMDL dataType, M type, formatString or None)
def col_type(table: str, col: str) -> tuple[str, str, str | None]:
    if col == "date" or col == "launch_date":
        return "dateTime", "type date", "yyyy-mm-dd"
    if col.endswith("_bdt"):
        return "decimal", "Currency.Type", "#,0"
    if col in ("year_month", "month", "quarter", "weekday", "sku") or not _is_numeric(table, col):
        return "string", "type text", None
    return "int64", "Int64.Type", "0"


_samples: dict[str, dict[str, str]] = {}


def _is_numeric(table: str, col: str) -> bool:
    if table not in _samples:
        with open(ROOT / "data" / f"{table}.csv", newline="") as f:
            _samples[table] = next(csv.DictReader(f))
    return bool(re.fullmatch(r"-?\d+", _samples[table][col] or ""))


def headers(table: str) -> list[str]:
    with open(ROOT / "data" / f"{table}.csv", newline="") as f:
        return next(csv.reader(f))


def parse_measures() -> list[dict]:
    text = (ROOT / "powerbi" / "measures.dax").read_text()
    measures, folder = [], "Measures"
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.strip().splitlines()]
        code = []
        for l in lines:
            m = re.match(r"//.*\(folder:\s*(.+?)\)", l)
            if m:
                folder = m.group(1)
            elif not l.strip().startswith("//"):
                code.append(l)
        if not code or "=" not in code[0]:
            continue
        name, first = code[0].split("=", 1)
        expr = "\n".join([first.strip()] + [c for c in code[1:]]).strip()
        measures.append({"name": name.strip(), "expr": expr, "folder": folder})
    return measures


def fmt_for(name: str) -> str | None:
    if "%" in name:
        return "0.0%"
    if name in ("Achievement Status", "YoY Arrow"):
        return None
    if "(M BDT)" in name:
        return "#,0.00"
    if name in ("Lines per Call",):
        return "0.00"
    return "#,0"


TABLES = ["dim_date", "dim_product", "dim_territory", "dim_distributor", "dim_sales_rep", "dim_outlet",
          "fact_sales", "fact_visits", "fact_targets"]
HIDE_COLS = {"date_key", "visit_id", "line_id", "territory_id", "rep_id", "outlet_id", "distributor_id"}
RELATIONSHIPS = [  # (from table.col, to table.col, active)
    ("fact_sales.date_key", "dim_date.date_key", True),
    ("fact_visits.date_key", "dim_date.date_key", True),
    ("fact_targets.date_key", "dim_date.date_key", True),
    ("fact_sales.sku", "dim_product.sku", True),
    ("fact_sales.outlet_id", "dim_outlet.outlet_id", True),
    ("fact_visits.outlet_id", "dim_outlet.outlet_id", True),
    ("fact_sales.rep_id", "dim_sales_rep.rep_id", True),
    ("fact_visits.rep_id", "dim_sales_rep.rep_id", True),
    ("fact_targets.rep_id", "dim_sales_rep.rep_id", True),
    ("fact_targets.territory_id", "dim_territory.territory_id", True),
    ("dim_outlet.territory_id", "dim_territory.territory_id", True),
    ("dim_distributor.territory_id", "dim_territory.territory_id", True),
    ("dim_sales_rep.territory_id", "dim_territory.territory_id", False),
]
PAGES = ["Executive overview", "Territory performance", "Field force", "Product & distribution", "Data quality"]


def q(name: str) -> str:
    return f"'{name}'" if re.search(r"[^A-Za-z0-9_]", name) else name


def table_tmdl(t: str, measures: list[dict]) -> str:
    cols = headers(t)
    out = [f"table {t}", f"\tlineageTag: {tag(t)}"]
    if t == "dim_date":
        out.append("\tdataCategory: Time")
    out.append("")
    if t == "fact_sales":
        for m in measures:
            out.append(f"\tmeasure {q(m['name'])} =")
            for line in m["expr"].splitlines():
                out.append(f"\t\t\t{line.strip()}")
            f = fmt_for(m["name"])
            if f:
                out.append(f"\t\tformatString: {f}")
            out.append(f"\t\tdisplayFolder: {m['folder']}")
            out.append(f"\t\tlineageTag: {tag(t, 'm', m['name'])}")
            out.append("")
    m_types = []
    for c in cols:
        dtype, mtype, fmt = col_type(t, c)
        m_types.append(f'{{"{c}", {mtype}}}')
        out.append(f"\tcolumn {c}")
        out.append(f"\t\tdataType: {dtype}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        if t == "dim_date" and c == "date":
            out.append("\t\tisKey")
        hidden = c in HIDE_COLS or t.startswith("fact_")
        if hidden:
            out.append("\t\tisHidden")
        out.append(f"\t\tlineageTag: {tag(t, c)}")
        out.append("\t\tsummarizeBy: none")
        out.append(f"\t\tsourceColumn: {c}")
        if t == "dim_date" and c == "month":
            out.append("\t\tsortByColumn: month_no")
        out.append("")
    if t == "dim_territory":
        out += ["\thierarchy Geography", f"\t\tlineageTag: {tag(t, 'h')}", ""]
        for lvl in ("division", "region", "territory"):
            out += [f"\t\tlevel {lvl.title()}", f"\t\t\tlineageTag: {tag(t, 'h', lvl)}", f"\t\t\tcolumn: {lvl}", ""]
    types = ", ".join(m_types)
    out += [
        f"\tpartition {t} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(File.Contents(DataFolder & "{t}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "\t\t\t\t    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f"\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, \"en-US\")",
        "\t\t\t\tin",
        "\t\t\t\t    Typed",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    measures = parse_measures()
    sm = OUT / f"{NAME}.SemanticModel"
    rp = OUT / f"{NAME}.Report"
    (sm / "definition" / "tables").mkdir(parents=True, exist_ok=True)
    rp.mkdir(parents=True, exist_ok=True)

    (OUT / f"{NAME}.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}}, indent=2))
    (sm / "definition.pbism").write_text(json.dumps({"version": "4.0", "settings": {}}, indent=2))
    (sm / "definition" / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n")
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdiscourageImplicitMeasures", ""]
    model += [f"ref table {t}" for t in TABLES]
    (sm / "definition" / "model.tmdl").write_text("\n".join(model) + "\n")
    (sm / "definition" / "expressions.tmdl").write_text(
        'expression DataFolder = "C:\\fmcg-sales-powerbi\\data\\" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]\n'
        f"\tlineageTag: {tag('DataFolder')}\n")
    for t in TABLES:
        (sm / "definition" / "tables" / f"{t}.tmdl").write_text(table_tmdl(t, measures))
    rels = []
    for i, (a, b, active) in enumerate(RELATIONSHIPS, 1):
        rels += [f"relationship {tag('rel', a, b)}"]
        if not active:
            rels.append("\tisActive: false")
        rels += [f"\tfromColumn: {a}", f"\ttoColumn: {b}", ""]
    (sm / "definition" / "relationships.tmdl").write_text("\n".join(rels))

    (rp / "definition.pbir").write_text(json.dumps(
        {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2))
    sections = [{"name": tag("page", p).replace("-", "")[:20], "displayName": p, "displayOption": 1,
                 "width": 1280, "height": 720, "ordinal": i, "visualContainers": [], "config": "{}", "filters": "[]"}
                for i, p in enumerate(PAGES)]
    (rp / "report.json").write_text(json.dumps({
        "config": json.dumps({"version": "5.43", "activeSectionIndex": 0}),
        "layoutOptimization": 0, "resourcePackages": [], "sections": sections, "filters": "[]"}, indent=2))
    (OUT / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    print(f"PBIP written to {OUT}: {len(TABLES)} tables, {len(RELATIONSHIPS)} relationships, {len(measures)} measures")


if __name__ == "__main__":
    main()
