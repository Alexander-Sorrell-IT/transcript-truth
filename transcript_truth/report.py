from __future__ import annotations
import html
from .types import Receipt

_GRADE_COLOR = {"A": "#2ea043", "B": "#3fb950", "C": "#d29922", "D": "#db6d28", "F": "#da3633"}
_SEV_COLOR = {"critical": "#da3633", "moderate": "#db6d28", "minor": "#6e7681"}


def to_html(receipt: Receipt, source: str = "") -> str:
    g = receipt.grade
    color = _GRADE_COLOR.get(g, "#666")
    if not receipt.flags:
        rows = '<div class="clean">&#10003; Clean against the deterministic rule-set — no violations.</div>'
    else:
        rows = ""
        for f in receipt.flags:
            rows += (
                f'<div class="flag"><div class="row"><span class="ln">L{f.line}</span>'
                f'<span class="sev" style="background:{_SEV_COLOR[f.severity]}">{f.severity}</span>'
                f'<span class="lab">{html.escape(f.label)}</span></div>'
                + (f'<div class="ev">{html.escape(f.evidence)}</div>' if f.evidence else "")
                + (f'<div class="fix">fix: {html.escape(f.fix)}</div>' if f.fix else "")
                + "</div>"
            )
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{font-family:-apple-system,Helvetica,Arial,sans-serif;margin:0;background:#0d1117;color:#e6edf3;}}
.card{{max-width:780px;margin:0 auto;padding:28px 32px;}}
.top{{display:flex;align-items:center;gap:22px;border-bottom:1px solid #21262d;padding-bottom:18px;}}
.grade{{font-size:58px;font-weight:800;color:{color};width:104px;height:104px;border:4px solid {color};
border-radius:18px;display:flex;align-items:center;justify-content:center;flex:none;}}
h1{{font-size:19px;margin:0 0 5px;}} .sub{{color:#8b949e;font-size:13px;margin:0;}}
.math{{color:#8b949e;font-size:12px;margin-top:7px;font-family:ui-monospace,SFMono-Regular,monospace;}}
.flags{{margin-top:16px;}}
.flag{{padding:9px 12px;border:1px solid #21262d;border-radius:9px;margin-bottom:7px;background:#161b22;}}
.row{{display:flex;align-items:center;gap:8px;}}
.ln{{font-family:ui-monospace,monospace;color:#8b949e;font-size:12px;}}
.sev{{font-size:10px;text-transform:uppercase;letter-spacing:.4px;color:#fff;padding:2px 7px;border-radius:5px;}}
.lab{{font-weight:600;font-size:13px;}}
.ev{{font-family:ui-monospace,monospace;font-size:12px;color:#c9d1d9;margin:6px 0 0 4px;}}
.fix{{font-size:12px;color:#7ee787;margin:3px 0 0 4px;}}
.clean{{padding:20px 4px;color:#7ee787;font-size:16px;font-weight:600;}}
.foot{{margin-top:18px;color:#6e7681;font-size:11px;border-top:1px solid #21262d;padding-top:12px;}}
</style></head><body><div class="card">
<div class="top"><div class="grade">{g}</div>
<div><h1>transcript-truth — guideline receipt</h1>
<p class="sub">{html.escape(source)} &middot; mode: {receipt.mode} &middot; {receipt.n_lines} lines</p>
<div class="math">{html.escape(receipt.math)}</div></div></div>
<div class="flags">{rows}</div>
<div class="foot">No model in the verdict path — every flag is a deterministic rule hit, cited at line.</div>
</div></body></html>"""
