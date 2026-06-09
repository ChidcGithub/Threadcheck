from __future__ import annotations

import json
from html import escape
from typing import Any

from ..static.models import RaceWarning, Severity


def format_html(warnings: list[RaceWarning], title: str = "threadcheck Report") -> str:
    rows_html = "\n".join(_warning_row(w) for w in warnings)

    total = len(warnings)
    errors = sum(1 for w in warnings if w.severity == Severity.ERROR)
    warns = sum(1 for w in warnings if w.severity == Severity.WARNING)
    infos = sum(1 for w in warnings if w.severity == Severity.INFO)

    warnings_json = escape(
        json.dumps([w.to_dict() for w in warnings], indent=2, ensure_ascii=False),
        quote=False,
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
<style>
  :root {{
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --text-dim: #8b949e;
    --error: #f85149;
    --warning: #d29922;
    --info: #58a6ff;
    --high: #f85149;
    --medium: #d29922;
    --low: #8b949e;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji"; background: var(--bg); color: var(--text); padding: 24px; }}
  h1 {{ font-size: 24px; margin-bottom: 16px; }}
  .summary {{ display: flex; gap: 16px; margin-bottom: 24px; }}
  .summary-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 16px 24px; text-align: center; min-width: 100px; }}
  .summary-card .num {{ font-size: 28px; font-weight: 600; }}
  .summary-card .label {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; }}
  .summary-card.error .num {{ color: var(--error); }}
  .summary-card.warning .num {{ color: var(--warning); }}
  .summary-card.info .num {{ color: var(--info); }}
  .summary-card.total .num {{ color: var(--text); }}
  table {{ width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 14px; }}
  th {{ background: #21262d; font-weight: 600; color: var(--text-dim); text-transform: uppercase; font-size: 12px; letter-spacing: 0.05em; cursor: pointer; }}
  th:hover {{ color: var(--text); }}
  tr:hover td {{ background: #1c2128; }}
  .sev-error {{ color: var(--error); font-weight: 600; }}
  .sev-warning {{ color: var(--warning); font-weight: 600; }}
  .sev-info {{ color: var(--info); font-weight: 600; }}
  .tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }}
  .tag-high {{ background: var(--error); color: #fff; }}
  .tag-medium {{ background: var(--warning); color: #000; }}
  .tag-low {{ background: var(--low); color: #000; }}
  .suggestion {{ color: var(--text-dim); font-size: 12px; margin-top: 2px; }}
  .file-link {{ color: var(--info); text-decoration: none; }}
  .file-link:hover {{ text-decoration: underline; }}
  .footer {{ margin-top: 24px; color: var(--text-dim); font-size: 12px; text-align: center; }}
  .no-issues {{ text-align: center; padding: 48px; color: var(--text-dim); font-size: 16px; }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --bg: #ffffff;
      --surface: #f6f8fa;
      --border: #d0d7de;
      --text: #1f2328;
      --text-dim: #656d76;
      --error: #cf222e;
      --warning: #9a6700;
      --info: #0969da;
    }}
  }}
</style>
</head>
<body>
<h1>{escape(title)}</h1>

<div class="summary">
  <div class="summary-card total">
    <div class="num">{total}</div>
    <div class="label">Total</div>
  </div>
  <div class="summary-card error">
    <div class="num">{errors}</div>
    <div class="label">Errors</div>
  </div>
  <div class="summary-card warning">
    <div class="num">{warns}</div>
    <div class="label">Warnings</div>
  </div>
  <div class="summary-card info">
    <div class="num">{infos}</div>
    <div class="label">Info</div>
  </div>
</div>

{"<p class=\"no-issues\">No data-race issues detected.</p>" if not warnings else f'''<table id="results">
<thead>
<tr>
  <th onclick="sortTable(0)">File</th>
  <th onclick="sortTable(1)">Line</th>
  <th onclick="sortTable(2)">Severity</th>
  <th onclick="sortTable(3)">Category</th>
  <th onclick="sortTable(4)">Confidence</th>
  <th onclick="sortTable(5)">Message</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>

<script>
function sortTable(col) {{
  const table = document.getElementById("results");
  const tbody = table.tBodies[0];
  const rows = Array.from(tbody.rows);
  const ascending = tbody.getAttribute("data-sort-col") !== String(col) || tbody.getAttribute("data-sort-dir") !== "asc";
  tbody.setAttribute("data-sort-col", col);
  tbody.setAttribute("data-sort-dir", ascending ? "asc" : "desc");
  rows.sort((a, b) => {{
    let va = a.cells[col].textContent.trim();
    let vb = b.cells[col].textContent.trim();
    if (col === 1) {{ va = parseInt(va); vb = parseInt(vb); }}
    else {{ va = va.toLowerCase(); vb = vb.toLowerCase(); }}
    if (va < vb) return ascending ? -1 : 1;
    if (va > vb) return ascending ? 1 : -1;
    return 0;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
</script>'''}

<div class="footer">Generated by threadcheck</div>
</body>
</html>"""


def _sev_class(s: Severity) -> str:
    return {Severity.ERROR: "sev-error", Severity.WARNING: "sev-warning", Severity.INFO: "sev-info"}.get(s, "")


def _conf_tag(c: Any) -> str:
    return {"high": "tag-high", "medium": "tag-medium", "low": "tag-low"}.get(c.value if hasattr(c, "value") else str(c), "")


def _warning_row(w: RaceWarning) -> str:
    sev_cls = _sev_class(w.severity)
    conf_cls = _conf_tag(w.confidence)
    suggestion_html = f'<div class="suggestion">{escape(w.suggestion or "")}</div>' if w.suggestion else ""
    return f'''<tr>
  <td><a class="file-link" href="file:///{escape(str(w.file.resolve()))}">{escape(str(w.file))}</a></td>
  <td>{w.line}</td>
  <td class="{sev_cls}">{w.severity.value}</td>
  <td><code>{escape(w.category.value)}</code></td>
  <td><span class="tag {conf_cls}">{w.confidence.value.upper()}</span></td>
  <td>{escape(w.message)}{suggestion_html}</td>
</tr>'''
