#!/usr/bin/env python3
"""Render the Gaffer app icon with real transparency.

macOS ships no SVG rasteriser, and `qlmanage` flattens onto opaque white — which
is where the white square in the Dock came from. So the mark is drawn directly
here: same geometry as src/fpl/webapp/static/mark.svg, on a 96-unit grid,
supersampled 12x and downscaled for antialiasing.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

LIME = (200, 255, 61, 255)     # #C8FF3D
INK = (14, 17, 22, 255)        # #0E1116
U = 96                          # SVG viewBox units
SS = 12                         # supersample factor
OUT = 1024


def draw_mark(size: int = U * SS) -> Image.Image:
    s = size / U
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Tile: rounded square, corners genuinely transparent.
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=22 * s, fill=LIME)

    w = 9 * s                    # stroke-width 9
    r = w / 2                    # radius of a round cap

    def cap(x, y):
        d.ellipse([x * s - r, y * s - r, x * s + r, y * s + r], fill=INK)

    # Arc: circle centre (48,48) r=22. SVG sweeps the large arc from (62.6,32.1)
    # to (70,48); PIL draws clockwise, so that is 0deg -> 312.6deg.
    box = [(48 - 22) * s, (48 - 22) * s, (48 + 22) * s, (48 + 22) * s]
    d.arc(box, start=0, end=312.6, fill=INK, width=int(round(w)))
    cap(62.6, 32.1)
    cap(70, 48)

    # Bar: (70,48) -> (51.5,48)
    d.line([70 * s, 48 * s, 51.5 * s, 48 * s], fill=INK, width=int(round(w)))
    cap(51.5, 48)

    # Chevron: (62.2,39.6) -> (70.8,48.2) -> (62.2,56.8)
    d.line([62.2 * s, 39.6 * s, 70.8 * s, 48.2 * s], fill=INK, width=int(round(w)))
    d.line([70.8 * s, 48.2 * s, 62.2 * s, 56.8 * s], fill=INK, width=int(round(w)))
    cap(62.2, 39.6)
    cap(70.8, 48.2)
    cap(62.2, 56.8)

    return img.resize((OUT, OUT), Image.LANCZOS)


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gaffer.iconset")
    master = draw_mark()

    # Windows: a single .ico carrying every size the shell asks for.
    if target.suffix == ".ico":
        target.parent.mkdir(parents=True, exist_ok=True)
        sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256)]
        master.save(target, format="ICO", sizes=sizes)
        print(f"  wrote {target.name} with {len(sizes)} sizes, "
              f"corner alpha={master.getpixel((1, 1))[3]}")
        return 0

    iconset = target
    iconset.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            px = size * scale
            master.resize((px, px), Image.LANCZOS).save(
                iconset / f"icon_{size}x{size}{suffix}.png")
    corner = master.getpixel((1, 1))
    print(f"  drew {OUT}x{OUT}, corner alpha={corner[3]} "
          f"({'transparent' if corner[3] == 0 else 'OPAQUE - BUG'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
