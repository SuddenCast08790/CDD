#!/usr/bin/env python3
"""Generate C Decrease Decrease branding art with Pillow (no external assets needed).

Produces:
  docs/img/logo.png      - square logo: an axe chopping a semicolon
  docs/img/banner.png    - wide hero banner with slogan
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)
                      )
OUT = os.path.normpath(os.path.join(HERE, "img"))
os.makedirs(OUT, exist_ok=True)

INK = (248, 246, 240)        # paper
DARK = (26, 27, 38)          # near-black indigo
RED = (214, 69, 65)          # chop red
ORANGE = (240, 150, 60)
TEAL = (60, 170, 160)
GRAY = (120, 125, 140)


def font(size, mono=False):
    cands = []
    if mono:
        cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"]
    cands += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]
    for c in cands:
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


def S(w, h, scale=2):
    """Supersampled canvas."""
    img = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), scale


def down(img, scale):
    return img.resize((img.width // scale, img.height // scale),
                      Image.LANCZOS)


# ---------------------------------------------------------------- semicolon
def draw_semicolon(dr, cx, cy, s, color, broken=False):
    """Returns the waist point so the axe can bite there."""
    """A big comma-like semicolon glyph made of circles + tail."""
    r = 0.30 * s
    oy = -0.35 * s
    # head circle
    dr.ellipse([cx - r, cy + oy - r, cx + r, cy + oy + r], fill=color)
    # tail curve
    pts = []
    for t in range(0, 41):
        a = t / 40.0
        x = cx + r * 0.2 - s * 0.35 * (a ** 1.6)
        y = cy + oy + r * 0.6 + s * 0.85 * a
        pts.append((x, y))
    w = max(3, int(s * 0.16))
    dr.line(pts, fill=color, width=w, joint="curve")
    # dot at end of tail
    dr.ellipse([pts[-1][0] - w / 2, pts[-1][1] - w / 2,
                pts[-1][0] + w / 2, pts[-1][1] + w / 2], fill=color)
    return (cx, cy + oy + s * 0.45)  # "waist" of the glyph


# ---------------------------------------------------------------- axe
def draw_axe(dr, angle_deg, length, thick, head_at=(0, 0)):
    """Draw an axe pointing along +x from origin, rotated."""
    a = math.radians(angle_deg)

    def rot(x, y):
        return (head_at[0] + x * math.cos(a) - y * math.sin(a),
                head_at[1] + x * math.sin(a) + y * math.cos(a))

    # handle (grips the back of the blade, not the cutting edge)
    h0 = rot(-length * 0.95, -thick * 0.18)
    h1 = rot(length * 0.26, -thick * 0.18)
    dr.line([h0, h1], fill=(110, 74, 46), width=int(thick * 0.16),
            joint="curve")
    # metal collar
    c = rot(length * 0.28, 0)
    dr.ellipse([c[0] - thick * .12, c[1] - thick * .12,
                c[0] + thick * .12, c[1] + thick * .12], fill=DARK)
    # blade: wedge
    p_back_t = rot(length * 0.26, -thick * 0.45)
    p_back_b = rot(length * 0.26, thick * 0.55)
    p_edge_t = rot(length * 0.52, -thick * 0.70)
    p_edge_m = rot(length * 0.64, thick * 0.05)
    p_edge_b = rot(length * 0.52, thick * 0.80)
    dr.polygon([p_back_t, p_edge_t, p_edge_m, p_edge_b, p_back_b],
               fill=DARK, outline=DARK)
    # shining edge
    dr.line([p_edge_t, p_edge_m], fill=RED, width=max(2, int(thick*0.10)))
    dr.line([p_edge_m, p_edge_b], fill=RED, width=max(2, int(thick*0.10)))
    # pommel
    q = rot(-length * 0.95, -thick * 0.18)
    dr.ellipse([q[0] - thick * .10, q[1] - thick * .10,
                q[0] + thick * .10, q[1] + thick * .10],
               fill=(110, 74, 46))


# ---------------------------------------------------------------- logo
def make_logo():
    N = 512
    img, dr, sc = S(N, N)
    W, H = img.size
    # background rounded square
    pad = int(W * 0.04)
    dr.rounded_rectangle([pad, pad, W - pad, H - pad],
                         radius=int(W * 0.14), fill=INK)
    dr.rounded_rectangle([pad, pad, W - pad, H - pad],
                         radius=int(W * 0.14), outline=DARK,
                         width=int(W * 0.018))
    # faint code texture
    f = font(int(W * 0.030), mono=True)
    lines = ["let x is 41", "shout(\"{x}\\n\")", "if x is 42:",
             "back 0", "loop i from 0", "until i > 10"]
    for i, ln in enumerate(lines):
        dr.text((W * 0.09, H * 0.10 + i * H * 0.13), ln,
                font=f, fill=(200, 198, 190))
    # the victim: semicolon (kept small & centered)
    vx, vy = W * 0.50, H * 0.44
    s_semi = W * 0.28
    waist = draw_semicolon(dr, vx, vy, s_semi, DARK)
    # The axe edge midpoint sits exactly at the glyph waist; the blade is
    # sized so its cutting edge spans past the glyph and the wedge tip lands
    # on the waist line. No trig fudge needed: we place the head so that
    # rot(0.64L, ~0) == waist for the chosen tilt.
    import math as _m
    TILT = -24                      # degrees, blade points down-right-ish
    a = _m.radians(TILT)
    Lb = W * 0.46                   # blade length scale
    # solve head position h such that h + 0.64*Lb*(cos a, sin a) = waist
    tx, ty = waist
    hx = tx - 0.64 * Lb * _m.cos(a)
    hy = ty - 0.64 * Lb * _m.sin(a)
    draw_axe(dr, angle_deg=TILT, length=Lb, thick=Lb * 0.9, head_at=(hx, hy))
    # the cut: erase a thin notch perpendicular to the blade edge at the waist
    nx, ny = -_m.sin(a), _m.cos(a)  # unit normal to blade axis
    half = s_semi * 0.62            # notch reaches past glyph width
    g = W * 0.014                   # gap thickness along normal
    o = W * 0.004                   # blade-edge offset inside the gap
    ux, uy = _m.cos(a), _m.sin(a)   # along blade axis
    gap = [(tx - half * nx - o * ux, ty - half * ny - o * uy),
           (tx + half * nx - o * ux, ty + half * ny - o * uy),
           (tx + half * nx + (g - o) * ux, ty + half * ny + (g - o) * uy),
           (tx - half * nx + (g - o) * ux, ty - half * ny + (g - o) * uy)]
    dr.polygon(gap, fill=INK)
    # separate the halves slightly: nudge top part up-left, bottom down-right
    for (px, py, dx, dy) in [(vx, vy - s_semi * 0.35, -g * 0.9, -g * 0.4)]:
        pass  # (kept simple: the notch alone reads as the chop)
    # red splatter below the cut
    frag = RED
    for (dx, dy, fr) in [(-0.05, 0.10, 0.011), (0.03, 0.14, 0.008),
                          (0.09, 0.08, 0.006), (-0.10, 0.16, 0.005),
                          (0.00, 0.20, 0.007)]:
        dr.ellipse([vx+dx*W-fr*W, vy+dy*H-fr*W,
                    vx+dx*W+fr*W, vy+dy*H+fr*W], fill=frag)
    # wordmark bottom-left: C Decrease Decrease
    fw = font(int(W * 0.16))
    dr.text((W * 0.035, H * 0.68), "C Decrease\nDecrease", font=fw, fill=DARK)
    dmin = font(int(W * 0.030))
    dr.text((W * 0.10, H * 0.90), "chopped from gcc · v-4",
            font=dmin, fill=GRAY)
    down(img, sc).save(os.path.join(OUT, "logo.png"))
    print("logo.png ok")


# ---------------------------------------------------------------- banner
def make_banner():
    BW, BH = 1280, 400
    img, dr, sc = S(BW, BH)
    W, H = img.size
    # dark gradient-ish background bands
    steps = 24
    for i in range(steps):
        t = i / (steps - 1)
        col = tuple(int(DARK[j] + (32 - 8) * t) for j in range(3))
        y0 = int(H * i / steps)
        y1 = int(H * (i + 1) / steps) + 1
        dr.rectangle([0, y0, W, y1], fill=(26 + int(14*t), 27 + int(10*t),
                                           38 + int(20*t)))
    # left mini-logo disc
    r = int(H * 0.30)
    cx, cy = int(W * 0.13), int(H * 0.50)
    dr.ellipse([cx-r, cy-r, cx+r, cy+r], fill=INK, outline=RED,
               width=int(r*0.08))
    s_semi = r * 0.95
    waist = draw_semicolon(dr, cx - r*0.10, cy, s_semi, DARK)
    # blade edge midpoint lands exactly on the glyph waist (see make_logo)
    import math as _m3
    TILT = -24
    a3 = _m3.radians(TILT)
    Lb = r * 1.7
    hx = waist[0] - 0.64 * Lb * _m3.cos(a3)
    hy = waist[1] - 0.64 * Lb * _m3.sin(a3)
    draw_axe(dr, angle_deg=TILT, length=Lb, thick=Lb * 0.9,
             head_at=(hx, hy))
    # chop notch through the semicolon waist
    nx, ny = -_m3.sin(a3), _m3.cos(a3)
    ux, uy = _m3.cos(a3), _m3.sin(a3)
    tx, ty = waist
    half = s_semi * 0.62
    g = r * 0.10
    gap = [(tx - half * nx, ty - half * ny),
           (tx + half * nx, ty + half * ny),
           (tx + half * nx + g * ux, ty + half * ny + g * uy),
           (tx - half * nx + g * ux, ty - half * ny + g * uy)]
    dr.polygon(gap, fill=INK)
    # headline
    fh = font(int(H * 0.13))
    dr.text((int(W * 0.26), int(H * 0.16)), "C Decrease Decrease", font=fh, fill=INK)
    fs = font(int(H * 0.075))
    dr.text((int(W * 0.26), int(H * 0.46)),
            "Less is more. Chopping is love.", font=fs, fill=ORANGE)
    fl = font(int(H * 0.055), mono=True)
    dr.text((int(W * 0.26), int(H * 0.66)),
            'fork gcc -> chop ; chop for chop == -> "C Decrease Decrease"',
            font=fl, fill=(150, 160, 190))
    fl2 = font(int(H * 0.05), mono=True)
    dr.text((int(W * 0.26), int(H * 0.80)),
            '$ ccmm hello.ccm && ./hello   # no semicolons were spared',
            font=fl2, fill=TEAL)
    # right side: falling semicolons being chopped
    for (x, y, s2, br) in [(0.80, 0.25, 0.10, False), (0.88, 0.55, 0.08, True),
                           (0.76, 0.70, 0.07, True), (0.92, 0.20, 0.06, False)]:
        draw_semicolon(dr, W*x, H*y, H*s2, (90, 95, 115), broken=br)
    down(img, sc).save(os.path.join(OUT, "banner.png"))
    print("banner.png ok")


if __name__ == "__main__":
    make_logo()
    make_banner()
