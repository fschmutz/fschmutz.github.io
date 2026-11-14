#!/usr/bin/env python3
"""Redraw the 1200x630 social card from projects.json.

The card is drawn as SVG — assets/og.svg, committed and diffable — and then
rasterised once to assets/og.png, which is what the meta tags point at because
no scraper renders SVG.

    python3 tools/make-og.py             # redraw both
    python3 tools/make-og.py --svg-only  # skip the raster step

Rasterising needs one of rsvg-convert, inkscape or Chrome/Chromium on PATH.
Only the person regenerating the card needs it: both files are committed, and
the site itself has no build step.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "projects.json"
SVG = ROOT / "assets" / "og.svg"
PNG = ROOT / "assets" / "og.png"

W, H = 1200, 630
COLUMNS = 3
ROWS = 2
COLUMN_X = (80, 456, 832)
TOP_Y = 316          # baseline of the first group heading
FIRST_ITEM = 34      # heading baseline to first item baseline
ITEM_STEP = 28
ROW_GAP = 46
FLOOR = H - 92       # the divider; nothing may be drawn below it
ACCENTS = ("#818cf8", "#22d3ee", "#f472b6", "#4ade80", "#fbbf24", "#fb923c")


def row_tops(groups: list[dict]) -> list[int]:
    """Where each row of groups starts. The second row waits for the tallest
    group in the first, so a group can grow without colliding with one below."""
    tops = [TOP_Y]
    for row in range(1, ROWS):
        above = groups[(row - 1) * COLUMNS : row * COLUMNS]
        tallest = max((len(group["items"]) for group in above), default=0)
        tops.append(tops[-1] + FIRST_ITEM + max(tallest - 1, 0) * ITEM_STEP + ROW_GAP)
    return tops


def draw(data: dict) -> str:
    groups = data["groups"]
    if len(groups) > COLUMNS * ROWS:
        raise SystemExit(f"the card has room for {COLUMNS * ROWS} groups, projects.json has {len(groups)}")
    tops = row_tops(groups)
    lowest = max(
        tops[index // COLUMNS] + FIRST_ITEM + (len(group["items"]) - 1) * ITEM_STEP
        for index, group in enumerate(groups)
    )
    if lowest > FLOOR - 10:
        raise SystemExit(
            f"the groups reach y={lowest} but the card's floor is {FLOOR}. "
            "Move a project to a shorter group, or give the first row fewer items."
        )

    count = sum(len(group["items"]) for group in groups)
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"'
        ' font-family="DejaVu Sans, Verdana, Helvetica, Arial, sans-serif">',
        "  <defs>",
        '    <linearGradient id="mark" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0" stop-color="#6366f1"/><stop offset="0.55" stop-color="#818cf8"/>'
        '<stop offset="1" stop-color="#22d3ee"/>',
        "    </linearGradient>",
        '    <radialGradient id="glow-indigo"><stop offset="0" stop-color="#6366f1" stop-opacity="0.22"/>'
        '<stop offset="1" stop-color="#6366f1" stop-opacity="0"/></radialGradient>',
        '    <radialGradient id="glow-pink"><stop offset="0" stop-color="#ec4899" stop-opacity="0.14"/>'
        '<stop offset="1" stop-color="#ec4899" stop-opacity="0"/></radialGradient>',
        '    <radialGradient id="glow-cyan"><stop offset="0" stop-color="#22d3ee" stop-opacity="0.12"/>'
        '<stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></radialGradient>',
        "  </defs>",
        f'  <rect width="{W}" height="{H}" fill="#0a0a0f"/>',
        '  <circle cx="150" cy="110" r="620" fill="url(#glow-indigo)"/>',
        '  <circle cx="1060" cy="90" r="560" fill="url(#glow-pink)"/>',
        f'  <circle cx="600" cy="{H - 10}" r="620" fill="url(#glow-cyan)"/>',
        # Monogram, the same shapes as assets/favicon.svg.
        '  <rect x="80" y="70" width="88" height="88" rx="20" fill="#0b1220" stroke="url(#mark)" stroke-width="4"/>',
        '  <g fill="url(#mark)">',
        '    <rect x="105" y="100" width="40" height="12" rx="3"/>',
        '    <rect x="105" y="100" width="12" height="46" rx="3"/>',
        '    <rect x="105" y="122" width="29" height="12" rx="3"/>',
        "  </g>",
        '  <rect x="138" y="138" width="12" height="12" rx="3" fill="#ec4899"/>',
        '  <text x="196" y="124" font-size="60" font-weight="700" fill="#e2e8f0">Falco Schmutz</text>',
        '  <text x="200" y="152" font-size="20" font-weight="700" letter-spacing="3.4" fill="#94a3b8">'
        "GAMES · LEARNING · SOUND · DEVELOPER TOOLS</text>",
        f'  <text x="80" y="226" font-size="34" fill="#cbd5e1">{count} free, open-source things for the browser.</text>',
        '  <text x="80" y="268" font-size="34" fill="#94a3b8">No account, no tracking, most of them work offline.</text>',
    ]

    for index, group in enumerate(groups):
        x = COLUMN_X[index % COLUMNS]
        y = tops[index // COLUMNS]
        accent = ACCENTS[index % len(ACCENTS)]
        parts.append(f'  <rect x="{x}" y="{y - 24}" width="34" height="4" rx="2" fill="{accent}"/>')
        parts.append(
            f'  <text x="{x}" y="{y}" font-size="19" font-weight="700" letter-spacing="2.6" '
            f'fill="{accent}">{escape(group["name"].upper())}</text>'
        )
        for row, item in enumerate(group["items"]):
            label = escape(item["name"])
            if item.get("lang"):
                label += f' <tspan fill="#7c8aa0">[{item["lang"].upper()}]</tspan>'
            parts.append(
                f'  <text x="{x}" y="{y + FIRST_ITEM + row * ITEM_STEP}" font-size="22" '
                f'fill="#e2e8f0">{label}</text>'
            )

    parts += [
        f'  <rect x="80" y="{FLOOR}" width="{W - 160}" height="1" fill="#1e293b"/>',
        f'  <text x="80" y="{H - 48}" font-size="27" font-weight="700" fill="#a5b4fc">fschmutz.github.io</text>',
        f'  <text x="{W - 80}" y="{H - 48}" font-size="23" text-anchor="end" fill="#64748b">'
        "github.com/fschmutz</text>",
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def rasterise(svg: Path, png: Path) -> None:
    if (tool := shutil.which("rsvg-convert")):
        subprocess.run([tool, "-w", str(W), "-h", str(H), "-o", str(png), str(svg)], check=True)
        return
    if (tool := shutil.which("inkscape")):
        subprocess.run([tool, str(svg), "-w", str(W), "-h", str(H), "-o", str(png)], check=True)
        return

    chrome = next((shutil.which(name) for name in ("google-chrome", "chromium", "chromium-browser") if shutil.which(name)), None)
    if not chrome:
        raise SystemExit("install rsvg-convert, inkscape or Chrome to rasterise, or pass --svg-only")

    # Chrome screenshots a document, so wrap the SVG in a page with no margin.
    # ignore_cleanup_errors: a headless Chrome that outstayed its welcome is
    # still writing into its profile while the directory goes away.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        page = Path(tmp) / "card.html"
        page.write_text(
            "<!doctype html><meta charset=utf-8>"
            "<style>html,body{margin:0;padding:0;background:#0a0a0f}svg{display:block}</style>"
            + svg.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        command = [
            chrome, "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
            "--hide-scrollbars", "--force-device-scale-factor=1", f"--window-size={W},{H}",
            f"--screenshot={png}", f"--user-data-dir={tmp}/profile", page.as_uri(),
        ]
        before = png.stat().st_mtime if png.exists() else 0
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            # Chrome writes the screenshot and then sometimes refuses to exit
            # on a machine with no D-Bus, so judge it by the file, not the
            # exit code, and do not leave the process behind either way.
            process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if not png.exists() or png.stat().st_mtime == before:
            raise SystemExit("Chrome did not write the screenshot")

    shrink(png)


def shrink(png: Path) -> None:
    """Chrome writes a 24-bit PNG; the card is three soft gradients and some
    text, so a dithered palette costs nothing visible and saves ~90%."""
    quiet = {"check": False, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if shutil.which("pngquant"):
        subprocess.run(
            ["pngquant", "64", "--force", "--skip-if-larger", "--quality", "50-92",
             "--speed", "1", "--output", str(png), str(png)],
            **quiet,
        )
    for lossless in (["oxipng", "-o", "4", "--strip", "safe", str(png)], ["optipng", "-quiet", "-o5", str(png)]):
        if shutil.which(lossless[0]):
            subprocess.run(lossless, **quiet)
            break


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--svg-only", action="store_true")
    args = parser.parse_args()

    SVG.write_text(draw(json.loads(DATA.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"wrote {SVG.relative_to(ROOT)} ({SVG.stat().st_size} bytes)")
    if args.svg_only:
        return 0
    rasterise(SVG, PNG)
    print(f"wrote {PNG.relative_to(ROOT)} ({PNG.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
