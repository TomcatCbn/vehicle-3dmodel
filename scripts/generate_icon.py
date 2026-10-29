#!/usr/bin/env python3
"""Generate the AXIS Vehicle Lab app icon.

Creates a cool, modern app icon featuring a stylised EV crossover silhouette
in the project's mint-green accent on a dark background, with an integrated
lightning bolt. Renders at 4× supersampling for anti-aliasing, then emits all
sizes required by Tauri (PNG / ICO / ICNS), Android, iOS, and a web favicon.
"""

from __future__ import annotations

import math
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFilter
import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DESIGN = 1024          # logical design canvas
SS = 4                 # supersampling factor → render at 4096
RENDER = DESIGN * SS   # actual pixel canvas for drawing

ICONS_DIR = os.path.join(os.path.dirname(__file__), "..", "src-tauri", "icons")
FAVICON_DIR = os.path.join(os.path.dirname(__file__), "..", "public")

# Colours (matching src/style.css)
BG_EDGE  = (12, 16, 19)       # #0c1013 — app background
BG_CTR   = (30, 40, 45)       # subtle spotlight centre
MINT     = (184, 235, 198)    # #b8ebc6 — accent
MINT_HI  = (210, 250, 220)    # brighter mint for bolt / highlights
MINT_LO  = (120, 168, 135)    # darker mint for depth
WINDOW   = (90, 150, 110)     # greenhouse glass
DARK     = (18, 24, 28)       # wheels / shadow
WHITE    = (238, 240, 241)    # #eef0f1

# Corner radius for the rounded-square background (~22.37 %, Apple-style)
CORNER_RATIO = 0.2237


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sc(*coords: float) -> tuple[float, ...]:
    """Scale design-space coordinates to render-space."""
    return tuple(c * SS for c in coords)


def sc_pts(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(x * SS, y * SS) for x, y in points]


def radial_gradient(size: int, centre, c_inner, c_outer) -> Image.Image:
    """Fast radial gradient via numpy."""
    cx, cy = centre
    yy, xx = np.ogrid[:size, :size]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    max_d = math.sqrt(size ** 2 / 2.5)
    t = np.clip(dist / max_d, 0, 1)
    t = t * t * (3 - 2 * t)                     # smoothstep
    r = c_inner[0] * (1 - t) + c_outer[0] * t
    g = c_inner[1] * (1 - t) + c_outer[1] * t
    b = c_inner[2] * (1 - t) + c_outer[2] * t
    arr = np.stack([r, g, b], axis=2).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def rounded_rect_mask(size: int, radius: int) -> Image.Image:
    """White rounded-rectangle mask on black background."""
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


# ---------------------------------------------------------------------------
# Vehicle silhouette (crossover / SUV side profile, front pointing right)
# ---------------------------------------------------------------------------

# Body outline — clockwise from front bumper bottom-left.
# Coordinates are in 1024 design space.
BODY = [
    (258, 706),   # 0  front bumper bottom-left
    (232, 660),   # 1  front lower lip
    (236, 610),   # 2  front fascia
    (248, 578),   # 3  hood leading edge
    (270, 548),   # 4  hood front (slight rise)
    (330, 520),   # 5  hood mid
    (392, 500),   # 6  cowl / windshield base
    (430, 472),   # 7  windshield lower
    (472, 438),   # 8  windshield mid (raked)
    (506, 412),   # 9  A-pillar top
    (544, 400),   # 10 roof front
    (664, 394),   # 11 roof (flat section)
    (738, 398),   # 12 roof rear
    (788, 412),   # 13 C-pillar top
    (828, 436),   # 14 rear window mid
    (858, 462),   # 15 rear deck
    (882, 486),   # 16 spoiler lip
    (898, 514),   # 17 rear upper
    (910, 560),   # 18 rear
    (918, 610),   # 19 rear mid
    (922, 660),   # 20 rear bumper
    (916, 706),   # 21 rear bumper bottom
]

# Bottom edge of body — we close the polygon with a straight line;
# wheel arches are punched out afterwards.
BODY_POLY = BODY + [(258, 706)]

# Greenhouse / window glass — a polygon inset within the body.
GREENHOUSE = [
    (448, 468),   # windshield base (inside)
    (482, 438),   # windshield mid
    (512, 414),   # A-pillar
    (548, 404),   # roof front
    (660, 399),   # roof
    (730, 403),   # roof rear
    (776, 414),   # C-pillar
    (808, 436),   # rear window
    (786, 468),   # rear window base
    (500, 472),   # door window base
]

# Wheel positions (design space)
FRONT_WHEEL = (360, 706)
REAR_WHEEL  = (824, 706)
WHEEL_R     = 78       # outer tyre radius
RIM_R       = 52       # rim radius
HUB_R       = 16       # hub cap radius

# Lightning bolt — centred on the lower body, between the wheels.
# Polygon points (clockwise from top-left).  Bold enough to read at 32 px.
BOLT = [
    (554, 476),   # top-left
    (608, 476),   # top-right
    (574, 536),   # waist-right (kink in)
    (612, 536),   # hip-right (kink out)
    (536, 612),   # bottom point
    (578, 552),   # waist-left (kink in)
    (540, 552),   # hip-left (kink out)
]


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_icon() -> Image.Image:
    """Render the master icon at RENDER × RENDER pixels."""

    # 1. Background — radial gradient on rounded square
    grad = radial_gradient(
        RENDER,
        centre=(RENDER * 0.5, RENDER * 0.42),
        c_inner=BG_CTR,
        c_outer=BG_EDGE,
    )
    grad = grad.convert("RGBA")

    # Apply rounded-rectangle mask
    radius = int(DESIGN * CORNER_RATIO * SS)
    mask = rounded_rect_mask(RENDER, radius)
    bg = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    bg.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(bg, "RGBA")

    # 2. Subtle ground reflection / glow line
    glow_y = int(720 * SS)
    for i in range(40):
        alpha = int(30 * (1 - i / 40))
        draw.line(
            [(240 * SS, (glow_y + i * 2) * 1), (940 * SS, (glow_y + i * 2) * 1)],
            fill=(*MINT, alpha),
            width=max(1, SS),
        )

    # 3. Vehicle body — filled mint green
    body_pts = sc_pts(BODY_POLY)
    draw.polygon(body_pts, fill=(*MINT, 255))

    # 3a. Body shadow gradient (darker at bottom for depth)
    shadow = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    # Draw a semi-transparent dark overlay on the lower body area
    sd.polygon(
        sc_pts([
            (258, 640), (916, 640), (916, 706), (258, 706)
        ]),
        fill=(0, 0, 0, 50),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=12 * SS))
    bg = Image.alpha_composite(bg, shadow)
    draw = ImageDraw.Draw(bg, "RGBA")

    # 4. Punch out wheel arches (background-coloured semicircles)
    for wx, wy in (FRONT_WHEEL, REAR_WHEEL):
        draw.ellipse(
            [
                (wx - WHEEL_R - 6) * SS, (wy - WHEEL_R - 6) * SS,
                (wx + WHEEL_R + 6) * SS, (wy + WHEEL_R + 6) * SS,
            ],
            fill=(*BG_EDGE, 255),
        )

    # 5. Greenhouse (windows) — slightly darker / glassy
    gh_pts = sc_pts(GREENHOUSE)
    draw.polygon(gh_pts, fill=(*WINDOW, 230))

    # 5a. Window highlight (top edge brighter)
    draw.line(
        [sc_pts(GREENHOUSE)[0], sc_pts(GREENHOUSE)[1]],
        fill=(*MINT_HI, 180),
        width=max(2, SS * 2),
    )

    # 6. Wheels — dark tyre with mint rim and hub
    for wx, wy in (FRONT_WHEEL, REAR_WHEEL):
        cx, cy = wx * SS, wy * SS
        r_out = WHEEL_R * SS
        r_rim = RIM_R * SS
        r_hub = HUB_R * SS

        # Tyre (dark outer ring)
        draw.ellipse(
            [cx - r_out, cy - r_out, cx + r_out, cy + r_out],
            fill=(*DARK, 255),
        )
        # Rim (mint green)
        draw.ellipse(
            [cx - r_rim, cy - r_rim, cx + r_rim, cy + r_rim],
            fill=(*MINT, 255),
        )
        # Inner ring (slightly darker mint for depth)
        draw.ellipse(
            [cx - r_rim * 0.82, cy - r_rim * 0.82,
             cx + r_rim * 0.82, cy + r_rim * 0.82],
            fill=(*MINT_LO, 255),
        )
        # Hub cap (dark)
        draw.ellipse(
            [cx - r_hub, cy - r_hub, cx + r_hub, cy + r_hub],
            fill=(*DARK, 255),
        )
        # Spokes (5 simple lines from hub to rim)
        for deg in range(0, 360, 72):
            rad = math.radians(deg)
            x1 = cx + r_hub * math.cos(rad)
            y1 = cy + r_hub * math.sin(rad)
            x2 = cx + r_rim * 0.78 * math.cos(rad)
            y2 = cy + r_rim * 0.78 * math.sin(rad)
            draw.line([(x1, y1), (x2, y2)], fill=(*MINT_HI, 200), width=max(2, SS))

    # 7. Lightning bolt — bright white-mint, with glow
    # First draw a glow layer
    glow = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    bolt_pts = sc_pts(BOLT)
    for expand in range(8, 0, -2):
        gd.polygon(bolt_pts, fill=(*MINT_HI, 25))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=8 * SS))
    bg = Image.alpha_composite(bg, glow)
    draw = ImageDraw.Draw(bg, "RGBA")

    # Bolt body — white with mint tint
    draw.polygon(bolt_pts, fill=(*WHITE, 255))
    # Bolt outline — subtle mint glow
    draw.line(bolt_pts + [bolt_pts[0]], fill=(*MINT_HI, 255), width=max(1, SS))

    # 8. Overall vignette (darken corners slightly)
    vignette = Image.new("RGBA", (RENDER, RENDER), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    # Draw a subtle dark ring at the edges
    for i in range(60):
        alpha = int(40 * (i / 60))
        offset = i * SS
        vd.rounded_rectangle(
            (-offset, -offset, RENDER + offset, RENDER + offset),
            radius=radius + offset,
            outline=(0, 0, 0, 0),
            width=0,
        )
    # Simpler: just darken edges with a radial overlay
    vig_arr = np.zeros((RENDER, RENDER, 4), dtype=np.uint8)
    yy, xx = np.ogrid[:RENDER, :RENDER]
    cx_v, cy_v = RENDER / 2, RENDER / 2
    dist = np.sqrt((xx - cx_v) ** 2 + (yy - cy_v) ** 2)
    max_d = math.sqrt(2) * RENDER / 2
    t = np.clip((dist / max_d - 0.6) / 0.4, 0, 1)
    vig_arr[..., 3] = (t * 80).astype(np.uint8)
    vig_img = Image.fromarray(vig_arr, "RGBA")
    bg = Image.alpha_composite(bg, vig_img)

    # 9. Downscale to design size with high-quality LANCZOS
    final = bg.resize((DESIGN, DESIGN), Image.LANCZOS)

    # Re-apply rounded-rect mask at final size for crisp edges
    final_radius = int(DESIGN * CORNER_RATIO)
    final_mask = rounded_rect_mask(DESIGN, final_radius)
    final.putalpha(final_mask)

    return final


# ---------------------------------------------------------------------------
# Size generation
# ---------------------------------------------------------------------------

# All PNG sizes needed by Tauri + Android + iOS + Windows + favicon
PNG_SIZES = {
    # Tauri core
    "icon.png": 512,
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
    # Windows
    "Square30x30Logo.png": 30,
    "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png": 50,
    # Android (per-density)
}

ANDROID_DENSITIES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

IOS_SIZES = {
    "AppIcon-20x20@1x.png": 20,
    "AppIcon-20x20@2x.png": 40,
    "AppIcon-20x20@2x-1.png": 40,
    "AppIcon-20x20@3x.png": 60,
    "AppIcon-29x29@1x.png": 29,
    "AppIcon-29x29@2x.png": 58,
    "AppIcon-29x29@2x-1.png": 58,
    "AppIcon-29x29@3x.png": 87,
    "AppIcon-40x40@1x.png": 40,
    "AppIcon-40x40@2x.png": 80,
    "AppIcon-40x40@2x-1.png": 80,
    "AppIcon-40x40@3x.png": 120,
    "AppIcon-60x60@2x.png": 120,
    "AppIcon-60x60@3x.png": 180,
    "AppIcon-76x76@1x.png": 76,
    "AppIcon-76x76@2x.png": 152,
    "AppIcon-83.5x83.5@2x.png": 167,
    "AppIcon-512@2x.png": 1024,
}


def save_png(master: Image.Image, path: str, size: int):
    """Resize master to *size*×*size* and save."""
    img = master.resize((size, size), Image.LANCZOS)
    img.save(path, "PNG")
    print(f"  ✓ {os.path.relpath(path)} ({size}×{size})")


def create_ico(master: Image.Image, path: str):
    """Create a multi-resolution .ico file."""
    sizes = [16, 32, 48, 64, 128, 256]
    # Pillow resizes from the source for each entry in *sizes*.
    master.convert("RGBA").save(
        path, format="ICO",
        sizes=[(s, s) for s in sizes],
    )
    print(f"  ✓ {os.path.relpath(path)} (ICO, {len(sizes)} sizes)")


def create_icns(master: Image.Image, path: str):
    """Create an .icns file using iconutil."""
    import tempfile, shutil, subprocess

    tmp = tempfile.mkdtemp(prefix="icns_")
    iconset = os.path.join(tmp, "icon.iconset")
    os.makedirs(iconset)

    icns_entries = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for name, size in icns_entries:
        img = master.resize((size, size), Image.LANCZOS)
        img.save(os.path.join(iconset, name), "PNG")

    subprocess.run(
        ["iconutil", "-c", "icns", iconset, "-o", path],
        check=True, capture_output=True,
    )
    shutil.rmtree(tmp)
    print(f"  ✓ {os.path.relpath(path)} (ICNS, {len(icns_entries)} sizes)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Rendering master icon at {}×{} ({}× supersampling)…".format(
        RENDER, RENDER, SS))
    master = draw_icon()
    print("Master icon ready ({}×{}).".format(DESIGN, DESIGN))

    # Save a preview
    preview = os.path.join(os.path.dirname(__file__), "..", "output", "icon-preview.png")
    master.save(preview, "PNG")
    print(f"  ✓ {os.path.relpath(preview)} (preview)")

    os.makedirs(ICONS_DIR, exist_ok=True)
    os.makedirs(FAVICON_DIR, exist_ok=True)

    print("\nGenerating Tauri / Windows PNGs…")
    for name, size in PNG_SIZES.items():
        save_png(master, os.path.join(ICONS_DIR, name), size)

    print("\nGenerating Android PNGs…")
    for density, size in ANDROID_DENSITIES.items():
        d = os.path.join(ICONS_DIR, "android", density)
        os.makedirs(d, exist_ok=True)
        save_png(master, os.path.join(d, "ic_launcher.png"), size)
        save_png(master, os.path.join(d, "ic_launcher_round.png"), size)
        # Foreground (with padding for adaptive icon)
        fg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        m = master.resize((int(size * 0.62), int(size * 0.62)), Image.LANCZOS)
        offset = (size - m.width) // 2
        fg.paste(m, (offset, offset), m)
        fg.save(os.path.join(d, "ic_launcher_foreground.png"), "PNG")
        print(f"  ✓ android/{density}/ic_launcher_foreground.png ({size}×{size})")

    print("\nGenerating iOS PNGs…")
    ios_dir = os.path.join(ICONS_DIR, "ios")
    os.makedirs(ios_dir, exist_ok=True)
    for name, size in IOS_SIZES.items():
        save_png(master, os.path.join(ios_dir, name), size)

    print("\nGenerating ICO…")
    create_ico(master, os.path.join(ICONS_DIR, "icon.ico"))

    print("\nGenerating ICNS…")
    create_icns(master, os.path.join(ICONS_DIR, "icon.icns"))

    print("\nGenerating web favicon…")
    fav = master.resize((32, 32), Image.LANCZOS)
    fav.save(os.path.join(FAVICON_DIR, "favicon.png"), "PNG")
    print(f"  ✓ public/favicon.png (32×32)")

    fav180 = master.resize((180, 180), Image.LANCZOS)
    fav180.save(os.path.join(FAVICON_DIR, "apple-touch-icon.png"), "PNG")
    print(f"  ✓ public/apple-touch-icon.png (180×180)")

    print("\n✅ All icons generated.")


if __name__ == "__main__":
    main()
