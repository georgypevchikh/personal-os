#!/usr/bin/env python3
"""Render the README/docs illustrations as standalone SVG from metrics/snapshot.json.

Standard library only. Every SVG carries its own light/dark palette via
`prefers-color-scheme`, so it reads correctly in GitHub's light and dark themes.

    python3 site/charts.py      # writes docs/img/*.svg
"""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/img"
S = json.loads((ROOT / "metrics/snapshot.json").read_text(encoding="utf-8"))

STYLE = """<style>
  .bg{fill:#ffffff} .ink{fill:#16161a} .muted{fill:#5d5d66} .faint{fill:#8b8b94}
  .line{stroke:#e7e5df} .card{fill:#ffffff;stroke:#e7e5df} .hot{fill:#e8ecfb;stroke:#3b5bdb}
  .acc{fill:#3b5bdb} .accs{stroke:#3b5bdb} .soft{fill:#e8ecfb} .warn{fill:#c2410c} .warns{stroke:#c2410c}
  .warnsoft{fill:#fdf0e8} .zero{fill:#e7e5df} .edge{stroke:#8b8b94} .grey{fill:#8b8b94} .term{fill:#16161a}
  .tt{fill:#e9e9ee} .tg{fill:#7ee2a8} .ty{fill:#ffd479} .tr{fill:#ff8f8f} .tb{fill:#9db4ff}
  text{font-family:Inter,ui-sans-serif,-apple-system,"Segoe UI",system-ui,sans-serif}
  .mono{font-family:ui-monospace,"SF Mono",Menlo,monospace}
  @media (prefers-color-scheme: dark){
    .bg{fill:#0d1117} .ink{fill:#e6edf3} .muted{fill:#a2a2ad} .faint{fill:#7d8590}
    .line{stroke:#30363d} .card{fill:#161b22;stroke:#30363d} .hot{fill:#1d2340;stroke:#8ea4ff}
    .acc{fill:#8ea4ff} .accs{stroke:#8ea4ff} .soft{fill:#1d2340} .warn{fill:#fb923c} .warns{stroke:#fb923c}
    .warnsoft{fill:#2d1c10} .zero{fill:#30363d} .edge{stroke:#7d8590} .grey{fill:#7d8590} .term{fill:#010409}
  }
</style>"""


def svg(width: int, height: int, body: str, label: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{escape(label)}">{STYLE}'
        f'<rect class="bg" width="{width}" height="{height}" rx="14"/>{body}</svg>\n'
    )


def text(x, y, s, cls="ink", size=13, anchor="start", weight=400, extra=""):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" {extra}>{escape(str(s))}</text>'
    )


def title(x, y, eyebrow, heading):
    return text(x, y, eyebrow.upper(), "acc mono", 11, weight=600, extra='letter-spacing="1.2"') + text(
        x, y + 26, heading, "ink", 19, weight=700
    )


# 1. Weekly commits with the outage band ------------------------------------------------
def activity() -> str:
    weeks = list(S["git"]["weekly"].items())
    W, H, L, R, T, B = 960, 340, 56, 24, 92, 44
    peak = max(v for _, v in weeks)
    bw = (W - L - R) / len(weeks)
    y = lambda v: H - B - v / peak * (H - B - T)
    body = title(28, 36, "Activity", f"{S['git']['commits']} commits, {S['git']['first']} → {S['git']['last']}")
    run, start, gap = 0, None, None
    for i, (_, v) in enumerate(weeks):
        run = run + 1 if v == 0 else 0
        if run == 6 and start is None:
            start = i - 5
        if start is not None and gap is None and (i + 1 == len(weeks) or weeks[i + 1][1] > 0) and run >= 6:
            gap = (start, i)
    if gap:
        x0, x1 = L + gap[0] * bw, L + (gap[1] + 1) * bw
        body += f'<rect class="warnsoft" x="{x0:.1f}" y="{T - 6}" width="{x1 - x0:.1f}" height="{H - B - T + 6}" rx="8"/>'
        body += text((x0 + x1) / 2, T + 18, f"{S['git']['longest_gap_days']} days: backups silently blocked", "warn", 12.5, "middle", 600)
        body += text((x0 + x1) / 2, T + 36, "a guard rejected every auto-commit", "muted", 11.5, "middle")
    for v in (0, round(peak / 2), peak):
        body += f'<line class="line" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke-width="1"/>'
        body += text(L - 10, y(v) + 4, v, "faint mono", 11, "end")
    for i, (wk, v) in enumerate(weeks):
        h = max(2 if v else 1.5, H - B - y(v))
        x = L + i * bw + bw * 0.18
        body += f'<rect class="{"acc" if v else "zero"}" x="{x:.1f}" y="{H - B - h:.1f}" width="{bw * 0.64:.1f}" height="{h:.1f}" rx="2.5"><title>{wk}: {v}</title></rect>'
        if i % 4 == 0:
            body += text(x, H - B + 20, wk.replace("2026-", ""), "faint mono", 11)
    return svg(W, H, body, "Weekly commits to the private vault, with a 63-day gap caused by a silent backup outage")


# 2. Anonymous block graph --------------------------------------------------------------
def block_graph() -> str:
    g = S["blocks"]["graph"]
    W, H = 960, 560
    cx, cy = 480, 300
    by_kind = {k: [n for n in g["nodes"] if n["kind"] == k] for k in ("system", "domain", "project")}
    pos = {}
    for n in by_kind["system"]:
        pos[n["id"]] = (cx, cy)
    for ring, kind, offset in ((150, "domain", -90), (235, "project", -45)):
        nodes = by_kind[kind]
        for i, n in enumerate(nodes):
            a = math.radians(offset + 360 * i / max(1, len(nodes)))
            pos[n["id"]] = (cx + ring * math.cos(a) * 1.55, cy + ring * math.sin(a) * 0.92)
    body = title(28, 36, "Block graph", f"{len(g['nodes'])} blocks · {len(g['edges'])} dependency edges, validated on every commit")
    for a, b in g["edges"]:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        mx, my = (x1 + x2) / 2 + (cy - (y1 + y2) / 2) * 0.12, (y1 + y2) / 2 + ((x1 + x2) / 2 - cx) * 0.06
        body += f'<path class="edge" d="M{x1:.1f},{y1:.1f} Q{mx:.1f},{my:.1f} {x2:.1f},{y2:.1f}" fill="none" stroke-width="1" opacity="0.35"/>'
    for n in g["nodes"]:
        x, y = pos[n["id"]]
        r = {"system": 34, "domain": 24, "project": 18}[n["kind"]]
        status = n["status"]
        cls = {"blocked": "warnsoft", "reserved": "card"}.get(status, "hot" if n["kind"] != "project" else "soft")
        stroke = "warns" if status == "blocked" else "accs"
        dash = ' stroke-dasharray="4 4"' if status in {"reserved", "developing"} else ""
        body += f'<circle class="{cls} {stroke}" cx="{x:.1f}" cy="{y:.1f}" r="{r}" stroke-width="1.6"{dash}/>'
        body += text(x, y + 4.5, n["id"], "ink mono", 12, "middle", 600)
    legend = [("hot accs", "", "system / domain"), ("soft accs", "", "project"), ("card accs", ' stroke-dasharray="4 4"', "reserved or developing"), ("warnsoft warns", "", "blocked")]
    for i, (cls, dash, label) in enumerate(legend):
        lx = 28 + i * 175
        body += f'<circle class="{cls}" cx="{lx + 8}" cy="{H - 26}" r="7" stroke-width="1.6"{dash}/>' + text(lx + 22, H - 22, label, "muted", 12)
    body += text(W - 28, 36, "ids anonymised: S system · D domain · P project", "faint", 11.5, "end")
    return svg(W, H, body, "Anonymised block dependency graph: one system block, eight domains, four projects")


# 3. Cold-start budget gauge ------------------------------------------------------------
def budget() -> str:
    o = S["orientation"]
    W, H, L, R = 960, 200, 28, 28
    scale = (W - L - R) / (o["max"] * 1.08)
    x = lambda v: L + v * scale
    body = title(28, 36, "Cold-start budget", f"~{o['tokens_estimate'] / 1000:.1f}K tokens to orient an agent, measured by pos budget")
    body += f'<rect class="zero" x="{L}" y="96" width="{x(o["max"] * 1.08) - L:.1f}" height="26" rx="13"/>'
    body += f'<rect class="soft" x="{L}" y="96" width="{x(o["target"]) - L:.1f}" height="26" rx="13"/>'
    body += f'<rect class="acc" x="{L}" y="96" width="{x(o["tokens_estimate"]) - L:.1f}" height="26" rx="13"/>'
    for v, label, cls in ((o["target"], "target", "accs"), (o["max"], "ceiling (fails CI)", "warns")):
        body += f'<line class="{cls}" x1="{x(v):.1f}" x2="{x(v):.1f}" y1="86" y2="132" stroke-width="2"/>'
        body += text(x(v), 152, f"{v // 1000}K {label}", "muted", 12, "middle")
    body += text(x(o["tokens_estimate"]) - 10, 114, f"{o['tokens_estimate']:,}", "bg", 12.5, "end", 700, 'style="fill:#fff"')
    body += text(L, 182, "Entry point · current context · block graph · sync contract · agent behaviour · today's log tail", "faint", 11.5)
    return svg(W, H, body, "Session orientation costs about 10 thousand tokens against a 20K target and 25K ceiling")


# 4. Evolution timeline -----------------------------------------------------------------
TIMELINE = [  # (label, MM-DD, description, kind, level: +up / -down)
    ("v0 → v2.3", "05-09", "5 releases in 12 days", "r", 1),
    ("no bot", "07-03", "chose not to build", "n", -1),
    ("sync", "07-14", "cloud sync broke git", "i", 2),
    ("v2.4", "07-16", "secret guard", "r", -2),
    ("v2.5", "07-22", "block registry", "r", 1),
    ("v2.5.1", "09-23", "fix after 63-day outage", "i", 1),
    ("pos 0.1", "11-11", "public CLI + kit", "r", 1),
]
MAY_DOTS = ["05-09", "05-12", "05-13", "05-18", "05-21"]


def timeline() -> str:
    from datetime import date

    W, H, L, R, Y = 960, 300, 60, 60, 170
    d0, d1 = date(2026, 5, 1), date(2026, 11, 20)
    x = lambda md: L + (date.fromisoformat(f"2026-{md}") - d0).days / (d1 - d0).days * (W - L - R)
    body = title(28, 36, "Evolution", "Every release had a trigger: a failure or a measured limit")
    body += f'<line class="line" x1="{L}" x2="{W - R}" y1="{Y}" y2="{Y}" stroke-width="2"/>'
    for m, label in ((5, "May"), (6, "Jun"), (7, "Jul"), (8, "Aug"), (9, "Sep"), (10, "Oct"), (11, "Nov")):
        mx = x(f"{m:02d}-01")
        body += f'<line class="line" x1="{mx:.1f}" x2="{mx:.1f}" y1="{Y - 5}" y2="{Y + 5}" stroke-width="1"/>' + text(mx, H - 14, label, "faint mono", 11, "middle")
    for md in MAY_DOTS:
        body += f'<circle class="hot accs" cx="{x(md):.1f}" cy="{Y}" r="5" stroke-width="2"/>'
    for v, md, desc, kind, level in TIMELINE:
        px = x(md)
        ty = Y - 34 - (abs(level) - 1) * 44 if level > 0 else Y + 34 + (abs(level) - 1) * 44
        cls = {"r": "hot accs", "n": "card", "i": "warnsoft warns"}[kind]
        if md not in MAY_DOTS:
            body += f'<circle class="{cls}" cx="{px:.1f}" cy="{Y}" r="6.5" stroke-width="2"/>'
        y_from, y_to = (Y - 8, ty + 6) if level > 0 else (Y + 8, ty - 14)
        body += f'<line class="line" x1="{px:.1f}" x2="{px:.1f}" y1="{y_from}" y2="{y_to}" stroke-width="1"/>'
        anchor = "start" if px < L + 40 else ("end" if px > W - R - 60 else "middle")
        tcls = "warn" if kind == "i" else ("muted" if kind == "n" else "ink")
        top = ty - 12 if level > 0 else ty
        body += text(px, top, v, f"{tcls} mono", 11.5, anchor, 700) + text(px, top + 15, desc, "muted", 10.5, anchor)
    return svg(W, H, body, "Timeline of releases from May to November 2026, with two incidents and one decision not to build")


# 5. Architecture -----------------------------------------------------------------------
def architecture() -> str:
    W, H = 960, 420

    def box(x, y, w, h, label, rows, hot=False):
        out = text(x, y - 10, label.upper(), "faint mono", 10.5, weight=600, extra='letter-spacing="1"')
        out += f'<rect class="{"hot" if hot else "card"}" x="{x}" y="{y}" width="{w}" height="{h}" rx="12" stroke-width="1.2"/>'
        for i, (a, b) in enumerate(rows):
            out += text(x + 18, y + 30 + i * 25, a, "ink", 13) + (text(x + w * 0.5, y + 30 + i * 25, b, "muted", 11.5) if b else "")
        return out

    def arrow(d, dash=False):
        return f'<path class="edge" d="{d}" fill="none" stroke-width="1.4"{" stroke-dasharray=\"4 4\"" if dash else ""} marker-end="url(#a)"/>'

    body = '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="grey" d="M0,0 L10,5 L0,10 z"/></marker></defs>'
    body += title(28, 36, "Architecture", "Chat is where work happens. Files are where truth lives.")
    body += box(28, 92, 170, 140, "Runtimes", [("Claude Code", ""), ("Codex", ""), ("Cursor", ""), ("Mobile client", "")])
    body += box(250, 92, 270, 140, f"Orientation · ~{S['orientation']['tokens_estimate'] // 1000}K tokens", [("current-context", "what is true"), ("block-state", "generated graph"), ("block-sync", "contract"), ("agent-soul", "behaviour"), ("today's log tail", "")], hot=True)
    body += box(572, 92, 190, 140, "Owners · one per fact", [(f"{S['blocks']['by_kind'].get('domain', 0)} domains", ""), (f"{S['blocks']['by_kind'].get('project', 0)} projects", ""), (f"{S['blocks']['by_kind'].get('system', 0)} system block", ""), (f"{S['blocks']['dependency_edges']} edges", "")])
    body += box(812, 92, 120, 140, "Sync", [("git remote", ""), ("backup", ""), ("device sync", "")])
    body += box(250, 284, 270, 110, "Memory streams", [("session logs", "daily"), ("decision logs", "why it is so"), ("failure modes", "own mistakes")])
    body += box(572, 284, 360, 110, "Mechanisms", [("SessionStart hook", "injects orientation"), ("pre-commit hook", "stamp · validate · scan"), ("pos doctor · budget", "audit without memory")], hot=True)
    body += arrow("M198,162 H244") + arrow("M520,162 H566") + arrow("M762,162 H806")
    body += arrow("M113,232 V339 H244") + arrow("M520,339 H566", True) + arrow("M752,284 V238", True)
    return svg(W, H, body, "Architecture: runtimes load an orientation layer, read owners on demand, write memory streams; hooks and pos guard everything; git syncs")


# 6. Guard demo (real output from a fresh `pos init` vault) -----------------------------
def guard_demo() -> str:
    W, H = 960, 330
    lines = [
        ("tb", "$ pos init ~/my-os --owner \"Test User\""),
        ("tt", "created 25 files"),
        ("tb", "$ git commit -m init"),
        ("tt", "semantic propagation review: example-project, learning, meta, projects, self"),
        ("tg", "block graph valid: 5 local + 0 external blocks"),
        ("tg", "privacy scan clean: 25 file(s), 7 secret rules"),
        ("tb", "$ echo \"token: ghp_aaaa…\" > 30-projects/leak.md && git commit -am leak"),
        ("tr", "privacy scan BLOCK: 1 finding(s) in 1 file(s)"),
        ("tr", "  30-projects/leak.md:1: secret: github token: gh***a"),
        ("ty", "pre-commit BLOCK: move secrets to a password manager."),
    ]
    body = f'<rect class="term" x="0" y="0" width="{W}" height="{H}" rx="14"/>'
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        body += f'<circle cx="{26 + i * 20}" cy="24" r="6" fill="{c}"/>'
    body += text(W / 2, 28, "pos — starter kit, first commit, blocked leak", "tt mono", 12, "middle", extra='opacity="0.6"')
    for i, (cls, line) in enumerate(lines):
        body += text(28, 70 + i * 25, line, f"{cls} mono", 13.5)
    return svg(W, H, body, "Terminal: a new vault commits cleanly; a commit containing a token is blocked by the pre-commit hook")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in {
        "architecture": architecture, "activity": activity, "block-graph": block_graph,
        "budget": budget, "timeline": timeline, "guard-demo": guard_demo,
    }.items():
        (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
        print(f"wrote docs/img/{name}.svg")
