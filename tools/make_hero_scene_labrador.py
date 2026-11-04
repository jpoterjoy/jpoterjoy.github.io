#!/usr/bin/env python3
"""Rebuild the home-page banner image and the scene data behind its animation.

Reads the astronaut photograph ISS070-E-86805 (NASA Earth Observatory, 5568 x 3712; kept in
../image-sources/) and writes

  assets/img/hero-labrador.webp   the banner (photo x 0-4400, y 1300-3300, scaled to 2000 x 909,
                                  softened under the headline to keep the file small)
  tools/hero_scene.js             the CAM and GRID objects to paste into assets/js/site.js

Steps:
 1. Camera: a pinhole camera 418 km up with the Nikon D5 / 135 mm focal length (20,938 px). Its
    pointing below the horizontal and its roll are fitted so the rays through the Earth's limb in
    the photo graze a sphere 10 km above the surface.
 2. Scene: hand-drawn zones (land, pack ice, loose ice, open ocean; 1392 x 928 working scale) plus
    brightness. In the ice zones bright is ice and dark is water; over the open ocean bright is
    cloud.
 3. For footprint centres every 100 photo pixels, the fraction of ice and of cloud inside each
    instrument's footprint (SSMIS 37 GHz: 45 x 28 km; PREFIRE: 34.8 x 11.8 km), projected through
    the camera onto the photo. Stored one character each (0-z = 0-1, "_" = land or off the photo).

Needs numpy, scipy and Pillow.  python3 tools/make_hero_scene.py
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.optimize import least_squares

Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "..", "image-sources", "ISS070-E-86805_lrg.jpg")

R, H_ISS = 6371.0, 418.0
W, HH = 5568, 3712
F = 135 / 35.9 * W                     # focal length in pixels (35.9 mm sensor width)
CX, CY = W / 2, HH / 2


def basis(dl, rho):
    d = np.array([np.cos(dl), 0, -np.sin(dl)])
    up0 = np.array([np.sin(dl), 0, np.cos(dl)])
    r0 = np.array([0, -1.0, 0])
    right = np.cos(rho) * r0 + np.sin(rho) * up0
    up = -np.sin(rho) * r0 + np.cos(rho) * up0
    return d, right, up


def rays(x, y, dl, rho):
    d, r, u = basis(dl, rho)
    v = F * d[None, :] + (np.asarray(x) - CX)[:, None] * r[None, :] - (np.asarray(y) - CY)[:, None] * u[None, :]
    return v / np.linalg.norm(v, axis=1)[:, None]


def ground(x, y, dl, rho, alt=0.0):
    v = rays(np.atleast_1d(x), np.atleast_1d(y), dl, rho)
    P = np.array([0, 0, R + H_ISS])
    b = v @ P
    disc = b * b - (P @ P - (R + alt) ** 2)
    t = -b - np.sqrt(np.where(disc > 0, disc, np.nan))
    return P[None, :] + t[:, None] * v


def project(G, dl, rho):
    d, r, u = basis(dl, rho)
    v = np.atleast_2d(G) - np.array([0, 0, R + H_ISS])
    z = v @ d
    return CX + F * (v @ r) / z, CY - F * (v @ u) / z


def fit_camera(im):
    pts = []
    for x in range(3400, W, 20):
        col = im[:, x, :]
        ys = np.where(col[:, 2] > 25)[0]
        if len(ys) == 0 or ys[0] < 15:
            continue
        red = col[ys[0]:, 0]
        ok = np.where(np.convolve((red > 35).astype(int), np.ones(5, int), "valid") == 5)[0]
        if len(ok):
            pts.append((x, ys[0] + ok[0]))
    pts = np.array(pts, float)

    def resid(p):
        v = rays(pts[:, 0], pts[:, 1], p[0], p[1])
        return np.hypot(v[:, 0], v[:, 1]) * (R + H_ISS) - (R + 10)
    s = least_squares(resid, [np.radians(25), np.radians(30)])
    print("camera: %.2f deg below horizontal, roll %.2f deg, limb rms %.2f km"
          % (np.degrees(s.x[0]), np.degrees(s.x[1]), np.sqrt(np.mean(s.fun ** 2))))
    return s.x


def scene_mask(im, dl, rho):
    sm = np.asarray(Image.fromarray(im).resize((1392, 928), Image.BOX)).astype(np.float32)
    luma = sm @ np.array([0.299, 0.587, 0.114], np.float32)
    h, w = luma.shape

    def poly(pts):
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).polygon(pts, fill=1)
        return np.asarray(m).astype(bool)
    land = poly([(0, 420), (450, 928), (0, 928)])
    b1 = [(330, 0), (350, 250), (420, 380), (560, 650), (545, 928)]          # pack ice | loose ice
    b2 = [(520, 0), (560, 250), (650, 330), (800, 420), (800, 540), (720, 600),
          (705, 650), (650, 760), (575, 928)]                                # loose ice | open ocean
    pack = poly([(0, 0)] + b1 + [(0, 928)]) & ~land
    miz = poly(b1 + b2[::-1]) & ~land & ~pack
    ocean = ~land & ~pack & ~miz
    yy, xx = np.mgrid[0:h, 0:w]
    space = np.isnan(ground(xx.ravel() * 4 + 2.0, yy.ravel() * 4 + 2.0, dl, rho, alt=15.0)[:, 0]).reshape(h, w)
    ice = np.zeros_like(luma)
    cld = np.zeros_like(luma)
    ice[pack] = np.clip((luma[pack] - 45) / 30, 0, 1)
    ice[miz] = np.clip((luma[miz] - 95) / 55, 0, 1)
    cld[ocean] = np.clip((luma[ocean] - 70) / 80, 0, 1)
    return ice, cld, land, space


def footprint_grid(dl, rho, ice, cld, land, space):
    d, r, u = basis(dl, rho)
    h4, w4 = ice.shape
    xs, ys = np.arange(0, 4401, 100), np.arange(1300, 3301, 100)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = {}
    for key, (a, b) in {"mw": (22.5, 14.0), "pf": (17.4, 5.9)}.items():
        cs, fs = "", ""
        for y in ys:
            for x in xs:
                G = ground(x, y, dl, rho)[0]
                up = G / np.linalg.norm(G)
                n = d - (d @ up) * up
                n /= np.linalg.norm(n)
                e = np.cross(n, up)
                th = np.linspace(0, 2 * np.pi, 36, endpoint=False)
                pts = G[None, :] + a * np.cos(th)[:, None] * n + b * np.sin(th)[:, None] * e
                pts *= R / np.linalg.norm(pts, axis=1)[:, None]
                q = np.stack(project(pts, dl, rho), 1) / 4.0
                stat = None
                if q.min() >= 0 and q[:, 0].max() < w4 and q[:, 1].max() < h4:
                    x0, y0 = np.floor(q.min(0)).astype(int)
                    x1, y1 = np.ceil(q.max(0)).astype(int) + 1
                    m = Image.new("L", (x1 - x0, y1 - y0), 0)
                    ImageDraw.Draw(m).polygon([tuple(p) for p in q - [x0, y0]], fill=1)
                    m = np.asarray(m).astype(bool)
                    sl = (slice(y0, y1), slice(x0, x1))
                    if m.sum() >= 4 and land[sl][m].mean() <= 0.03 and space[sl][m].mean() == 0:
                        stat = (ice[sl][m].mean(), cld[sl][m].mean())
                if stat is None:
                    cs += "_"
                    fs += "_"
                else:
                    cs += digits[int(round(np.clip(stat[0], 0, 1) * 35))]
                    fs += digits[int(round(np.clip(stat[1], 0, 1) * 35))]
        out[key + "C"], out[key + "F"] = cs, fs
    return dict(nx=len(xs), ny=len(ys), x0=0, y0=1300, step=100, **out)


def main():
    im = np.asarray(Image.open(SRC).convert("RGB"))
    dl, rho = fit_camera(im.astype(float))
    grid = footprint_grid(dl, rho, *scene_mask(im, dl, rho))
    d, r, u = basis(dl, rho)
    cam = dict(F=round(F, 2), CX=CX, CY=CY, R=R, H=H_ISS,
               d=[round(v, 6) for v in d], r=[round(v, 6) for v in r], u=[round(v, 6) for v in u])
    with open(os.path.join(ROOT, "tools", "hero_scene.js"), "w") as f:
        f.write("  var CAM = %s;\n  var GRID = %s;\n" % (json.dumps(cam), json.dumps(grid)))
    # the banner: softened under the headline, where the overlay hides the detail anyway
    a = Image.fromarray(im).crop((0, 1300, 4400, 3300)).resize((2000, 909), Image.LANCZOS)
    b = a.filter(ImageFilter.GaussianBlur(1.2))
    m = np.clip((np.arange(2000) / 2000 - 0.33) / 0.15, 0, 1)[None, :, None]
    Image.fromarray((np.asarray(b) * (1 - m) + np.asarray(a) * m).astype(np.uint8)).save(
        os.path.join(ROOT, "assets", "img", "hero-labrador.webp"), "WEBP", quality=62, method=6)
    print("wrote assets/img/hero-labrador.webp and tools/hero_scene.js")


if __name__ == "__main__":
    main()
