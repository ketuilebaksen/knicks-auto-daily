#!/usr/bin/env python3
"""
thumbnail.py — channel-template thumbnail generator.

Base: assets/thumb_base.jpg (orange Knicks template, 1920x1080).
Replaces the bottom banner with a short punch word (BREAKING NEWS!, URGENT
UPDATE!, SCARY!, ...). Optionally composites a player cutout PNG on the right.

Usage:
  python3 scripts/thumbnail.py "URGENT UPDATE!" [player.png] [out.jpg]
Library use:
  from thumbnail import make_thumb
"""
import os, sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(BASE, "assets")
BAND_TOP = 878  # where the bottom banner starts on the 1920x1080 template


def _band(d, w, y0, y1):
    """Orange gradient banner like the template's bottom band."""
    top, bot = (255, 154, 46), (222, 98, 0)
    hgt = y1 - y0
    for i, y in enumerate(range(y0, y1)):
        f = i / hgt
        c = tuple(int(top[k] + (bot[k] - top[k]) * f) for k in range(3))
        d.line([(0, y), (w, y)], fill=c)


def _neon(img):
    """Team-color neon accents: glowing diagonal streaks + center glow + vignette."""
    from PIL import ImageChops
    W, H = img.size
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    BLUE, ORNG = (0, 150, 255), (255, 140, 30)
    # diagonal neon streaks following the stripe angle (45deg)
    for x0, col, wdt in ((-150, BLUE, 10), (60, ORNG, 7), (W - 460, ORNG, 9),
                         (W - 240, BLUE, 6)):
        g.line([(x0, H), (x0 + H, 0)], fill=col, width=wdt)
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    img = ImageChops.screen(img, glow)
    # soft radial glow behind the center logo
    halo = Image.new("RGB", (W, H), (0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse([W // 2 - 430, 150, W // 2 + 430, 900], fill=(90, 45, 0))
    hd.ellipse([W // 2 - 300, 240, W // 2 + 300, 810], fill=(140, 70, 10))
    halo = halo.filter(ImageFilter.GaussianBlur(120))
    img = ImageChops.screen(img, halo)
    # corner vignette for depth
    vig = Image.new("L", (W, H), 0)
    vd = ImageDraw.Draw(vig)
    vd.ellipse([-W // 3, -H // 3, W + W // 3, H + H // 3], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(img, black, vig.point(lambda v: 155 + v * 100 // 255))
    return img


def make_thumb(word, player_png=None, out=None):
    img = Image.open(os.path.join(A, "thumb_base.jpg")).convert("RGB")
    img = _neon(img)
    W, H = img.size
    d = ImageDraw.Draw(img)
    _band(d, W, BAND_TOP, H)

    # optional player cutout, right side, slight pop over the band
    if player_png and os.path.exists(player_png):
        p = Image.open(player_png).convert("RGBA")
        ph = int(H * 0.78)
        p = p.resize((int(p.width * ph / p.height), ph))
        # white outline glow
        halo = Image.new("RGBA", (p.width + 40, p.height + 40), (0, 0, 0, 0))
        mask = p.split()[3].point(lambda a: 255 if a > 40 else 0)
        white = Image.new("RGBA", p.size, (255, 255, 255, 255))
        for dx in (-8, 0, 8):
            for dy in (-8, 0, 8):
                halo.paste(white, (20 + dx, 20 + dy), mask)
        halo = halo.filter(ImageFilter.GaussianBlur(4))
        px = W - p.width - 60
        py = H - p.height - 10
        img.paste(halo, (px - 20, py - 20), halo)
        img.paste(p, (px, py), p)
        d = ImageDraw.Draw(img)

    # punch word, auto-sized to fit
    word = word.strip().upper()
    size = 210
    while size > 60:
        fnt = ImageFont.truetype(os.path.join(A, "ArchivoBlack.ttf"), size)
        if d.textlength(word, font=fnt) <= W - 140:
            break
        size -= 10
    tw = d.textlength(word, font=fnt)
    x, y = (W - tw) // 2, BAND_TOP + (H - BAND_TOP - size) // 2 - 20

    # soft black shadow (blurred layer) then crisp white text
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    ds.text((x + 10, y + 14), word, font=fnt, fill=(0, 0, 0, 230))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB")
    d = ImageDraw.Draw(img)
    d.text((x, y), word, font=fnt, fill=(255, 255, 255),
           stroke_width=3, stroke_fill=(20, 10, 0))

    out = out or os.path.join(BASE, "work", "thumbnail.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.resize((1280, 720)).save(out, quality=93)
    return out


if __name__ == "__main__":
    word = sys.argv[1] if len(sys.argv) > 1 else "BREAKING NEWS!"
    player = sys.argv[2] if len(sys.argv) > 2 else None
    out = sys.argv[3] if len(sys.argv) > 3 else None
    print(make_thumb(word, player, out))
