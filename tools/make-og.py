#!/usr/bin/env python3
"""Redraw assets/og.png, the 1200x630 social card.

Build-time only: the site itself ships the finished PNG and needs no tooling.

    pip install Pillow && python3 tools/make-og.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
BG = (10, 10, 15)
CARD = (15, 23, 42)
BORDER = (30, 41, 59)
INK = (226, 232, 240)
MUTED = (148, 163, 184)
INDIGO = (99, 102, 241)
INDIGO_LIGHT = (129, 140, 248)
CYAN = (34, 211, 238)
PINK = (236, 72, 153)

ROOT = Path(__file__).resolve().parent.parent
FONTS = Path("/usr/share/fonts/truetype")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for candidate in FONTS.rglob(name):
        return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size)


def glow(image: Image.Image, cx: int, cy: int, radius: int, rgb: tuple[int, int, int], peak: float) -> None:
    """Radial gradient, same three accent glows as the page background."""
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = layer.load()
    step = 3
    for y in range(max(0, cy - radius), min(image.height, cy + radius), step):
        for x in range(max(0, cx - radius), min(image.width, cx + radius), step):
            d = math.hypot(x - cx, y - cy)
            if d >= radius:
                continue
            alpha = int(255 * peak * (1 - d / radius) ** 2)
            if alpha <= 0:
                continue
            for dy in range(step):
                for dx in range(step):
                    if y + dy < image.height and x + dx < image.width:
                        pixels[x + dx, y + dy] = (*rgb, alpha)
    image.alpha_composite(layer)


def main() -> None:
    image = Image.new("RGBA", (W, H), (*BG, 255))
    glow(image, 150, 110, 620, INDIGO, 0.22)
    glow(image, 1060, 90, 560, PINK, 0.16)
    glow(image, 600, 620, 620, CYAN, 0.16)

    draw = ImageDraw.Draw(image)

    # Monogram tile, same shapes as assets/favicon.svg.
    draw.rounded_rectangle((80, 80, 168, 168), radius=20, fill=(11, 18, 32), outline=INDIGO_LIGHT, width=4)
    draw.rounded_rectangle((105, 102, 145, 113), radius=3, fill=INDIGO_LIGHT)
    draw.rounded_rectangle((105, 102, 116, 148), radius=3, fill=INDIGO_LIGHT)
    draw.rounded_rectangle((105, 122, 134, 133), radius=3, fill=INDIGO_LIGHT)
    draw.rounded_rectangle((139, 139, 151, 151), radius=3, fill=PINK)

    draw.text((196, 84), "Falco Schmutz", font=font("DejaVuSans-Bold.ttf", 62), fill=INK)
    draw.text((199, 158), "GAMES · TRAINERS · DEVELOPER TOOLS", font=font("DejaVuSans-Bold.ttf", 22), fill=MUTED)

    draw.text(
        (80, 252),
        "Small, fast things for the browser.\nThey load in a second and the code is public.",
        font=font("DejaVuSans.ttf", 34),
        fill=MUTED,
        spacing=16,
    )

    # Seven cards, one per curated project, laid out 4 + 3 like the grid.
    labels = [
        ("Arcade", INDIGO_LIGHT),
        ("Calcul Flash", CYAN),
        ("Shortcut Flash", (250, 204, 21)),
        ("Vocal Range", PINK),
        ("Déonto Flash", INDIGO_LIGHT),
        ("Claude Usage", (34, 197, 94)),
        ("Agent Orchestrator", CYAN),
    ]
    card_w, card_h, gap = 258, 84, 20
    text_room = card_w - 56
    for index, (label, accent) in enumerate(labels):
        row, column = divmod(index, 4)
        x = 80 + column * (card_w + gap)
        y = 356 + row * (card_h + gap)
        draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=14, fill=CARD, outline=BORDER, width=2)
        draw.rounded_rectangle((x + 20, y + 25, x + 26, y + 58), radius=3, fill=accent)
        label_font = next(
            f for size in (20, 19, 18, 17, 16, 15)
            for f in [font("DejaVuSans-Bold.ttf", size)]
            if draw.textlength(label, font=f) <= text_room or size == 15
        )
        draw.text((x + 40, y + 31), label, font=label_font, fill=INK)

    draw.text((80, H - 74), "fschmutz.github.io", font=font("DejaVuSans-Bold.ttf", 28), fill=INDIGO_LIGHT)

    out = ROOT / "assets" / "og.png"
    image.convert("RGB").save(out, optimize=True)
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
