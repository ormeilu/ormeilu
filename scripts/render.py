"""Render stitched profile widgets from a GitHub GraphQL dump.

The look is rolter's "Stitched Console": graphite surfaces, one bright thread
(#ff4017) and one folk-embroidery red (#b41d21), every mark a rounded square
on a grid, the way a cross-stitch sits on canvas. GitHub shows README images
through its camo proxy as plain <img>, so scripts never run there; the
"sewing" animation is CSS @keyframes, which does play.

Usage: python3 render.py user.json out/
(user.json is the GraphQL response that .github/workflows/widgets.yml fetches)
"""

import base64
import json
import sys
from datetime import date
from pathlib import Path

BG = "#111113"
PANEL = "#18181b"
LINE = "#27272a"
TEXT = "#fafafa"
MUTED = "#a1a1aa"
SUBTLE = "#93939e"
RED = "#ff4017"
FOLK = "#b41d21"
EMPTY = "#222226"
# contributionLevel -> thread colour, darkest folk red up to the bright thread
LEVELS = {
    "NONE": EMPTY,
    "FIRST_QUARTILE": "#4f1a1b",
    "SECOND_QUARTILE": "#7d1c1e",
    "THIRD_QUARTILE": FOLK,
    "FOURTH_QUARTILE": RED,
}
FONT = "Geist, ui-sans-serif, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

# rushnyk band from the llm-choice deck: R bright thread, F folk thread
RUSHNYK = [
    "F.F.F.F.",
    "........",
    "...R....",
    "..RFR...",
    ".RF.FR..",
    "RF.R.FRF",
    ".RF.FR..",
    "..RFR...",
    "...R....",
    "........",
    "F.F.F.F.",
]


def stitch(x, y, p, fill, extra=""):
    s = p * 0.84
    o = (p - s) / 2
    return (
        f'<rect x="{x + o:.2f}" y="{y + o:.2f}" width="{s:.2f}" height="{s:.2f}" '
        f'rx="{p * 0.16:.2f}" fill="{fill}"{extra}/>'
    )


def band(tile, p, max_width, y, canvas_w):
    """A divider of whole stitches, centred, that ends the way it starts.

    Repeating a tile n times leaves the next tile's lead-in hanging off the
    right end (the rushnyk's connecting thread, the dot rule's last dot cut
    in half), so the last column of the last tile is dropped: n * cols - 1
    columns. Every row must then read the same from both ends, which is
    checked here, so a tile edit that breaks the symmetry fails the render.
    """
    cols = len(tile[0])
    n = (max_width // p + 1) // cols
    rows = [(row * n)[: n * cols - 1] for row in tile]
    for row in rows:
        assert row == row[::-1], f"divider row is not symmetric: {row!r}"
    width = len(rows[0]) * p
    x0 = (canvas_w - width) / 2
    cells = "".join(
        stitch(x0 + k * p, y + r * p, p, RED if c == "R" else FOLK)
        for r, row in enumerate(rows)
        for k, c in enumerate(row)
        if c != "."
    )
    return cells, len(tile) * p


FONTS = Path(__file__).parent / "fonts"


def font_face():
    # GitHub's camo proxy serves the SVG as an <img>, which never fetches
    # external fonts, so Geist (ASCII subset, OFL) travels inside the file.
    rules = []
    for family, name in (("Geist", "geist"), ("Geist Mono", "geist-mono")):
        data = base64.b64encode((FONTS / f"{name}.woff2").read_bytes()).decode()
        rules.append(
            f"@font-face {{ font-family: '{family}'; font-weight: 100 900; "
            f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}"
        )
    return "<style>" + " ".join(rules) + "</style>"


def svg(w, h, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{label}">'
        f"<title>{label}</title>{font_face()}{body}</svg>\n"
    )


def header(user):
    w, h = 900, 230
    p = 5
    band_h = len(RUSHNYK) * p
    rushnyk, _ = band(RUSHNYK, p, w - 64, h - band_h - 22, w)
    # a big stitched diamond on the left, same geometry as the rolter mark
    diamond = []
    n, cell = 9, 9
    cx = n // 2
    for r in range(n):
        for c in range(n):
            d = abs(r - cx) + abs(c - cx)
            if d == cx:
                diamond.append(stitch(40 + c * cell, 22 + r * cell, cell, RED))
            elif d == cx - 1 or d == 1:
                diamond.append(stitch(40 + c * cell, 22 + r * cell, cell, FOLK))
            elif d == 0:
                diamond.append(stitch(40 + c * cell, 22 + r * cell, cell, RED))
    body = f"""
<style>
  .t {{ font-family: {FONT}; }}
  .m {{ font-family: {MONO}; }}
  .sew {{ animation: sew .35s ease-out backwards; }}
  @keyframes sew {{ from {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .sew {{ animation: none; }} }}
</style>
<rect width="{w}" height="{h}" rx="12" fill="{BG}"/>
<g>{''.join(diamond)}</g>
<text x="150" y="70" class="t" font-size="34" font-weight="600" fill="{TEXT}">{user['name']}</text>
<text x="151" y="98" class="m" font-size="15" fill="{MUTED}">@ormeilu</text>
<text x="151" y="124" class="t" font-size="15" fill="{SUBTLE}">LLM agents, Python, Rust, Mojo</text>
<g opacity=".85">{rushnyk}</g>
"""
    return svg(w, h, body, f"{user['name']} - GitHub profile header")


def calendar(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = cal["weeks"]
    p = 15
    left, top = 34, 52
    w = left + len(weeks) * p + 40
    h = top + 7 * p + 46
    cells, months = [], []
    last_month = None
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            fill = LEVELS[day["contributionLevel"]]
            x = left + wi * p
            y = top + day["weekday"] * p
            if day["contributionLevel"] == "NONE":
                cells.append(stitch(x, y, p, fill))
            else:
                # sewn column by column, left to right
                cells.append(
                    stitch(
                        x, y, p, fill,
                        f' class="sew" style="animation-delay:{wi * 0.045 + day["weekday"] * 0.01:.3f}s"',
                    )
                )
        first = date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != last_month and wi < len(weeks) - 2:
            months.append(
                f'<text x="{left + wi * p + 2}" y="{top - 10}" class="m" font-size="11" '
                f'fill="{SUBTLE}">{first.strftime("%b")}</text>'
            )
            last_month = first.month
    days = "".join(
        f'<text x="{left - 8}" y="{top + i * p + 11}" text-anchor="end" class="m" '
        f'font-size="10" fill="{SUBTLE}">{d}</text>'
        for i, d in ((1, "Mon"), (3, "Wed"), (5, "Fri"))
    )
    legend_x = w - 40 - 5 * p
    legend = "".join(
        stitch(legend_x + i * p, h - 30, p, c) for i, c in enumerate(LEVELS.values())
    )
    body = f"""
<style>
  .t {{ font-family: {FONT}; }}
  .m {{ font-family: {MONO}; }}
  .sew {{ animation: sew .4s ease-out backwards; }}
  @keyframes sew {{ from {{ opacity: 0; transform: scale(.4); }} }}
  .sew {{ transform-box: fill-box; transform-origin: center; }}
  @media (prefers-reduced-motion: reduce) {{ .sew {{ animation: none; }} }}
</style>
<rect width="{w}" height="{h}" rx="12" fill="{BG}"/>
<text x="{left}" y="22" class="t" font-size="14" font-weight="600" fill="{TEXT}">{cal['totalContributions']:,} contributions</text>
<text x="{left + 150}" y="22" class="t" font-size="13" fill="{SUBTLE}">in the last year</text>
{''.join(months)}{days}
<g>{''.join(cells)}</g>
<text x="{legend_x - 8}" y="{h - 19}" text-anchor="end" class="m" font-size="10" fill="{SUBTLE}">less</text>
{legend}
<text x="{legend_x + 5 * p + 4}" y="{h - 19}" class="m" font-size="10" fill="{SUBTLE}">more</text>
"""
    return svg(w, h, body, f"{cal['totalContributions']} contributions in the last year")


def stats(user):
    cc = user["contributionsCollection"]
    stars = sum(n["stargazerCount"] for n in user["repositories"]["nodes"])
    rows = [
        ("commits", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
        ("pull requests", cc["totalPullRequestContributions"]),
        ("reviews", cc["totalPullRequestReviewContributions"]),
        ("stars earned", stars),
    ]
    w, h = 900, 110
    col = w / len(rows)
    p = 5
    dots, _ = band(["F."], p, w - 64, h - 14, w)
    items = "".join(
        f'<text x="{col * i + col / 2:.0f}" y="54" text-anchor="middle" class="m" font-size="30" '
        f'font-weight="600" fill="{RED if i == 0 else TEXT}">{v:,}</text>'
        f'<text x="{col * i + col / 2:.0f}" y="80" text-anchor="middle" class="t" font-size="13" '
        f'fill="{SUBTLE}">{k}</text>'
        for i, (k, v) in enumerate(rows)
    )
    seps = "".join(
        f'<rect x="{col * i - 1:.0f}" y="26" width="2" height="60" fill="{LINE}"/>'
        for i in range(1, len(rows))
    )
    body = f"""
<style> .t {{ font-family: {FONT}; }} .m {{ font-family: {MONO}; }} </style>
<rect width="{w}" height="{h}" rx="12" fill="{BG}"/>
<g opacity=".7">{dots}</g>
{seps}{items}
"""
    return svg(w, h, body, "GitHub activity in the last year")


def main():
    data = json.loads(Path(sys.argv[1]).read_text())["data"]["user"]
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    (out / "header.svg").write_text(header(data))
    (out / "calendar.svg").write_text(calendar(data))
    (out / "stats.svg").write_text(stats(data))


if __name__ == "__main__":
    main()
