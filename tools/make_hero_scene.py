#!/usr/bin/env python3
"""Rebuild the home-page banner and the scene data behind its animation.

Reads "Arctic Sky" (U.S. Coast Guard photo by Patrick Kelley from USCGC Healy, 19 August 2009,
public domain via USGS; kept in ../image-sources/) and writes

  assets/img/hero-arctic.webp   the banner (photo y 300-2300, scaled to 2400 x 1139, brightened
                                toward the right, with a colour lift)
  assets/img/og-banner.jpg      the picture shown when the site is shared (1200 x 630)
  tools/hero_scene.js           the SCENE object to paste into assets/js/site.js

The photo is taken from the ship's bridge with a 12 mm lens, looking level at the horizon, so
the sea surface is modelled as a flat plane seen by a pinhole camera (focal length 2180 px,
horizon at row 1402, camera 25 m up): row y lies at distance f h / (y - horizon). The
measurement is drawn NOT to scale, but as close to it as the photo allows: footprints sit on the
distant ice and water, 0.25-1.1 km from the ship (the visible horizon is ~18 km away, so a real
footprint of tens of km would cover everything in view), and every footprint is shrunk by the
same factor, 5 m on the picture per km of real footprint (1/200 of true size), so the two
SSMIS channels keep their true sizes and shapes relative to one another (19 GHz 74 x 45 km,
91 GHz 16 x 13 km; long axis toward the satellite), drawn in the photo's perspective. VIIRS
infrared pixels (375 m) are small enough to draw at true scale, 1-1.6 km out. Seen this far off,
a footprint is a long, flat ellipse.

Scene classes, from hand-drawn zones plus colour:
  sky        cloud fraction from how grey the sky is: 0 for deep blue (B - R > 120), 1 for grey
  far field  (rows 1402-1600) ice, except digitized open water: the lead in the foreground, the
             band of water with scattered floes beyond it (counted as 25% ice), and smaller
             patches; floes in the lead are ice. Ponds on the distant ice are too small to see
             and are taken as 15% of the ice, as on the nearby floes.
  near field melt ponds are dark (luma < 95), the rest is ice
For footprint centres every 80 photo pixels across and at a set of distances (0.25-1.1 km), and
each channel's footprint, the grid stores the ice concentration C (ponded ice counts as ice) and
the melt-pond fraction of the ice, plus the cloud fraction along the beam from that footprint
toward the satellite (53 deg incidence, 30 deg right of straight ahead), averaged over the sky it
crosses in the photo. A footprint is kept only if it is wide enough to see and not too wide for
the banner (SSMIS 220-840 photo px across, VIIRS 500-960) and not flattened to a line (SSMIS at
least 20 px tall); that limits footprints to within about a kilometre, the farthest a footprint
still reads as an ellipse.

Needs numpy and Pillow.  python3 tools/make_hero_scene.py
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "..", "image-sources", "Arctic_Sky_(4371010590).jpg")

F, CX, YH, HCAM = 2180.0, 2108.0, 1402.0, 25.0     # focal length (px), centre column, horizon row, height (m)
VIBRANCE = 1.2                                      # colour lift for the banner (0 = the photo as taken)
# extra saturation by hue: the gold of the low sun, the turquoise ponds and the blue sky are
# strengthened, and the violet cast of the shaded ice is eased so the ice stays near white
HUE_SAT = [(40, 45, 1.9), (185, 30, 1.7), (215, 25, 1.3), (262, 35, 0.8)]   # (centre deg, half-width, factor)
ICE_KEEP = 0.45     # share of that added colour kept on the bright, bluish ice below the horizon
KSCALE = 5.0                                        # schematic: picture metres per km of footprint
INC, AZ = np.radians(53.1), np.radians(30.0)        # incidence, azimuth of the satellite (from straight ahead)
# footprints, km (along x across the look), and how they are drawn (picture metres per km): the SSMIS
# 3-dB footprints at the schematic scale; VIIRS I5 (11.45 um, 375 m pixels) at true scale
FOOT = {"19": (74, 45, KSCALE), "91": (16, 13, KSCALE), "ir": (0.375, 0.375, 1000.0)}
SIZE = {"19": (220, 840, 20), "91": (220, 840, 20), "ir": (500, 960, 3)}   # width range, min height (photo px)
U = np.array([np.sin(INC) * np.sin(AZ), np.sin(INC) * np.cos(AZ), np.cos(INC)])   # toward the satellite
VP = (CX + F * U[0] / U[1], YH - F * U[2] / U[1])  # where every beam points in the photo


def to_ground(x, y):
    d = F * HCAM / (y - YH)
    return (x - CX) * d / F, d


def to_photo(X, D):
    return CX + F * X / D, YH + F * HCAM / D


def classes(im):
    rgb = im.astype(np.float32)
    luma = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    h, w = luma.shape
    yy, xx = np.mgrid[0:h, 0:w]
    sky = yy < YH
    cloud = np.clip((120 - (rgb[..., 2] - rgb[..., 0])) / 80, 0, 1) * sky
    def poly(*ps):
        m = Image.new("L", (w, h), 0)
        for p in ps:
            ImageDraw.Draw(m).polygon(p, fill=1)
        return np.asarray(m).astype(bool)
    lead = poly([(1850, 1590), (2100, 1560), (2450, 1548), (3050, 1548), (3350, 1556), (4216, 1556),
                 (4216, 1880), (3200, 1800), (2400, 1760), (1960, 1720), (1850, 1640)])
    floes = poly([(3420, 1572), (3700, 1572), (3720, 1598), (3440, 1600)],
                 [(3800, 1568), (4100, 1568), (4110, 1600), (3820, 1600)])
    band = poly([(2280, 1462), (2600, 1455), (3000, 1457), (3400, 1462), (3700, 1470), (3950, 1476),
                 (4216, 1474), (4216, 1502), (3900, 1506), (3600, 1508), (3200, 1512), (2900, 1506),
                 (2600, 1506), (2400, 1502), (2280, 1496)],
                [(3600, 1440), (4216, 1436), (4216, 1452), (3600, 1456)])
    patch = poly([(0, 1598), (220, 1600), (230, 1640), (0, 1645)])
    far = ~sky & (yy < 1600) & ~lead
    near = ~sky & (yy >= 1600) & ~lead
    ice = np.zeros_like(luma)
    pond = np.zeros_like(luma)
    ice[far] = 0.85                               # distant ice, 15% of it ponded
    pond[far] = 0.15
    ice[band] = 0.25 * 0.85
    pond[band] = 0.25 * 0.15
    ice[patch] = 0
    pond[patch] = 0
    ice[lead & floes] = 0.85
    pond[lead & floes] = 0.15
    ice[lead & ~floes] = 0
    pond[lead & ~floes] = 0
    pnd = near & (luma < 95)
    pond[pnd] = 1
    ice[near & ~pnd] = 1
    return cloud, ice, pond, sky


def hue_deg(c):
    """Hue in degrees of an RGB array (0-1)."""
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    mx, mn = c.max(-1), c.min(-1)
    d = mx - mn + 1e-6
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4))
    return h * 60


def footprint_poly(x, y, key):
    X0, D0 = to_ground(x, y)
    a, b = (FOOT[key][2] * v / 2 for v in FOOT[key][:2])
    ex = np.array([np.sin(AZ), np.cos(AZ)])            # long axis, toward the satellite
    ey = np.array([np.cos(AZ), -np.sin(AZ)])
    th = np.linspace(0, 2 * np.pi, 36, endpoint=False)
    pts = [(X0, D0) + a * np.cos(t) * ex + b * np.sin(t) * ey for t in th]
    return [to_photo(px, pd) for px, pd in pts]


def main():
    im = np.asarray(Image.open(SRC).convert("RGB"))
    h, w, _ = im.shape
    cloud, ice, pond, sky = classes(im)
    dist = np.array([250, 280, 320, 360, 410, 460, 520, 590, 670, 760, 860, 980, 1110, 1300, 1600, 2000, 2500, 3000])
    xs, ys = np.arange(0, w + 1, 80), YH + F * HCAM / dist
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    q = lambda v: digits[int(round(np.clip(v, 0, 1) * 35))]
    out = {k: {"C": "", "P": ""} for k in FOOT}
    beam = ""
    for y in ys:
        for x in xs:
            # cloud the beam passes in front of, in the sky part of the photo
            vx, vy = VP[0] - x, VP[1] - y
            n = np.hypot(vx, vy)
            ss = [(x + vx * s, y + vy * s) for s in np.linspace(0, 1, 400)]
            cs = [cloud[int(py), int(px)] for px, py in ss if 300 <= py < YH and 0 <= px < w]
            beam += q(np.mean(cs)) if cs else "0"
            for key in FOOT:
                poly = np.array(footprint_poly(x, y, key))
                size = np.ptp(poly, 0)
                lo, hi, mh = SIZE[key]
                if (poly[:, 1].min() < YH + 1 or poly[:, 0].min() < 0 or poly[:, 0].max() >= w or poly[:, 1].max() >= h
                        or not lo <= size[0] <= hi or size[1] < mh):
                    out[key]["C"] += "_"
                    out[key]["P"] += "_"
                    continue
                x0, y0 = np.floor(poly.min(0)).astype(int)
                x1, y1 = np.ceil(poly.max(0)).astype(int) + 1
                x1, y1 = min(x1, w), min(y1, h)
                m = Image.new("L", (x1 - x0, y1 - y0), 0)
                ImageDraw.Draw(m).polygon([tuple(p) for p in poly - [x0, y0]], fill=1)
                m = np.asarray(m).astype(bool)
                sl = (slice(y0, y1), slice(x0, x1))
                fi, fp = ice[sl][m].mean(), pond[sl][m].mean()
                C = fi + fp
                out[key]["C"] += q(C)
                out[key]["P"] += q(fp / C if C > 0 else 0)
    scene = dict(F=F, CX=CX, YH=YH, H=HCAM, K=KSCALE, AZ=round(float(AZ), 5), VP=[round(VP[0], 1), round(VP[1], 1)],
                 nx=len(xs), ny=len(ys), x0=0, dx=80, rows=[round(float(v), 1) for v in ys], beam=beam,
                 **{"C" + k: out[k]["C"] for k in FOOT}, **{"P" + k: out[k]["P"] for k in FOOT})
    with open(os.path.join(ROOT, "tools", "hero_scene.js"), "w") as f:
        f.write("  var SCENE = %s;\n" % json.dumps(scene))
    # the banner, brightened toward the right (gamma easing from 1 at 35% of the width to 0.75 at
    # 92%, a long ramp so the light changes gently), where the animation sits over the photo's
    # natural light
    crop = im[300:2300].astype(np.float32) / 255
    x = np.arange(w) / w
    wgt = np.clip((x - 0.35) / 0.57, 0, 1)
    wgt = wgt * wgt * (3 - 2 * wgt)
    G = np.array([0.299, 0.587, 0.114], np.float32)
    lum = np.clip(crop @ G, 1e-4, 1)
    crop = crop * (np.power(lum, 1 - 0.25 * wgt[None, :]) / lum)[..., None]   # brighten, keeping the colours
    # and a colour lift: vibrance (most for the muted greys of cloud and ice), then extra
    # saturation for the gold low sun, the turquoise ponds and the blue sky (HUE_SAT), with the
    # ice kept near white (ICE_KEEP)
    lum = crop @ G
    d = crop - lum[..., None]
    sat = np.abs(d).max(-1)
    crop = lum[..., None] + d * (1 + VIBRANCE * (1 - np.clip(sat / 0.35, 0, 1)) ** 0.7)[..., None]
    hue = hue_deg(np.clip(crop, 0, 1))
    k = np.ones_like(hue)
    for centre, width, factor in HUE_SAT:
        k += (factor - 1) * np.clip(1 - np.abs((hue - centre + 180) % 360 - 180) / width, 0, 1)
    lum = crop @ G
    crop = lum[..., None] + (crop - lum[..., None]) * k[..., None]
    # keep the ice near white: below the horizon, take back most of the colour from bright,
    # blue-to-violet pixels, leaving the dark turquoise ponds and the gold-lit water alone
    rows = np.arange(crop.shape[0])[:, None] + 300
    lum = crop @ G
    hue = hue_deg(np.clip(crop, 0, 1))
    def ease(v, a, b):
        t = np.clip((v - a) / (b - a), 0, 1)
        return t * t * (3 - 2 * t)
    def bump(c, width):
        return np.clip(1 - np.abs((hue - c + 180) % 360 - 180) / width, 0, 1)
    ice = ease(rows, YH + 10, YH + 60) * ease(lum, 0.45, 0.62) * np.clip(bump(235, 60) + bump(280, 40), 0, 1)
    crop = np.clip(lum[..., None] + (crop - lum[..., None]) * (1 - (1 - ICE_KEEP) * ice)[..., None], 0, 1)
    Image.fromarray((crop * 255 + 0.5).astype(np.uint8)).resize((2400, 1139), Image.LANCZOS).save(
        os.path.join(ROOT, "assets", "img", "hero-arctic.webp"), "WEBP", quality=72, method=6)
    # the picture shown when the site is shared (1200 x 630): the banner's view of the ice and cloud
    full = Image.fromarray((crop * 255 + 0.5).astype(np.uint8))
    x0, y0 = 1216, 300                        # photo rows 600-2175, the right three-quarters
    full.crop((x0, y0, x0 + 3000, y0 + 1575)).resize((1200, 630), Image.LANCZOS).save(
        os.path.join(ROOT, "assets", "img", "og-banner.jpg"), "JPEG", quality=84, optimize=True)
    print("vanishing point of the beams:", [round(v) for v in VP])
    print("wrote assets/img/hero-arctic.webp and tools/hero_scene.js")


if __name__ == "__main__":
    main()
