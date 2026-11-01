#!/usr/bin/env python3
"""Draws the 1200 x 630 share picture (static/og-image.png) used when a Gold Pulse link
is shared on WhatsApp, Facebook or X. It has no prices, so it never goes out of date.

  python tools/make_og_image.py      (needs Pillow and the Windows Georgia / Segoe UI fonts)
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "static" / "og-image.png"
FONTS = Path("C:/Windows/Fonts")
W, H = 1200, 630


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def gradient(size, stops):
    """Diagonal gradient through (position 0..1, (r, g, b)) stops."""
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    for x in range(w):
        for y in range(h):
            t = (x / w * 0.65 + y / h * 0.35)
            for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
                if p0 <= t <= p1:
                    f = (t - p0) / (p1 - p0)
                    px[x, y] = tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
                    break
    return img


DEEP_GOLD = [(0, (165, 120, 18)), (0.5, (140, 102, 21)), (1, (94, 68, 11))]
BRIGHT_GOLD = [(0, (255, 243, 176)), (0.3, (254, 208, 83)), (0.7, (212, 175, 55)), (1, (140, 102, 21))]


def gold_text(canvas, xy, text, fnt, stops):
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=fnt, fill=255)
    box = mask.getbbox()
    grad = gradient((box[2] - box[0], box[3] - box[1]), stops)
    canvas.paste(grad, box[:2], mask.crop(box))


def main():
    img = Image.new("RGB", (W, H), (250, 247, 242))
    d = ImageDraw.Draw(img)
    # soft warm glow top-right and a gold band at the top
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse((700, -300, 1500, 400), fill=60)
    img.paste((245, 225, 170), (0, 0), glow.resize((W, H)))
    img.paste(gradient((W, 10), BRIGHT_GOLD), (0, 0))

    # gold bar drawing on the right
    bar = Image.new("L", (W, H), 0)
    ImageDraw.Draw(bar).polygon([(860, 430), (930, 250), (1100, 250), (1170, 430)], fill=255)
    img.paste(gradient((W, H), BRIGHT_GOLD), (0, 0), bar)
    d.polygon([(930, 250), (1100, 250), (1112, 282), (918, 282)], fill=(255, 236, 170))
    d.rounded_rectangle((840, 430, 1190, 452), radius=10, fill=(226, 181, 79))

    gold_text(img, (70, 120), "GOLD PULSE", font("georgiab.ttf", 104), DEEP_GOLD)
    d.text((74, 270), "Today's gold & silver rates in India", font=font("segoeuib.ttf", 42), fill=(24, 26, 31))
    d.text((74, 335), "24K · 22K · 18K · Silver  ·  12 cities", font=font("segoeui.ttf", 32), fill=(75, 85, 101))
    d.text((74, 382), "Updated 3 times a day  ·  Free calculators & guides", font=font("segoeui.ttf", 32), fill=(75, 85, 101))
    d.rounded_rectangle((70, 500, 430, 566), radius=33, fill=(243, 238, 223), outline=(202, 158, 48), width=2)
    d.text((100, 510), "goldpulse.co.in", font=font("segoeuib.ttf", 34), fill=(133, 95, 15))

    img.save(OUT, optimize=True)
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
