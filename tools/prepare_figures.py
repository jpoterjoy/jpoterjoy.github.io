"""Prepare research figures for the website from talk graphics.

Usage:
    python3 tools/prepare_figures.py /path/to/PRESENTATIONS [--only global,polar,...]

Reads figures from PRESENTATIONS/img, trims and resizes them, and writes
web-ready files to assets/img/research/. The two animations need ffmpeg and the
sea ice figure needs matplotlib. Steps: methods, global, mesoscale, hurricanes, polar.

Figures are shown about 480 CSS pixels wide on the research page and are saved at
about twice that, so every label and colorbar is redrawn to read at 11-13 px on screen.

Sources (talk slides that used each figure):
  global-hrly-lpf-*.png       AMS 2026, AMSC/UMBC/JPL/SIAM UQ 2026 (hourly global LPF)
  vort-KF-PF-250-20.png       AMS 2022/2023/2024 talks (250-mb EnKF vs. LPF members in HAFS)
  refl-frame-(zeros-)wmax*.png AMS 2025 ("DA using non-parametric likelihoods"; red contours
                              are wind speeds > 30 m/s near the level of maximum rear inflow)
  HAFS_domain_*.png           PSU 2023 / HFIP 2023 (video from Kenta Kurosawa)
  ISDA/FIGS/paper_scatter-3D-fullobs.png  Poterjoy (2022a, MWR) Fig. 12b (Rankine vortex manifold)
  AL13-14-PF-Var.png          NSSL 2023 (HAFS EnKF-Var vs. PF-Var, Laura and Marco 2020)
  SOCA-ice-pyx.png            JPL 2026 / CADRE 2025 (Wang et al., BAMS 2026)
"""
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
# The HAFS EnKF/LPF verification plot is unpublished and not shown on the site for now; set
# this to True to rebuild it (e.g., once the paper appears).
INCLUDE_UNPUBLISHED = False
OUT = os.path.join(HERE, "..", "assets", "img", "research")
INK = (38, 38, 38)            # MATLAB's axis and label colour


# ---------- small image helpers ----------

def trim(im, pad=6):
    """Remove white margins, keeping a small pad."""
    rgb = im.convert("RGB")
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, bg).point(lambda v: 255 if v > 12 else 0)
    box = diff.getbbox()
    if not box:
        return rgb
    l, t, r, b = box
    return rgb.crop((max(l - pad, 0), max(t - pad, 0),
                     min(r + pad, rgb.width), min(b + pad, rgb.height)))


def fit(im, width):
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    return im


def thumb(im, box, size=(640, 480)):
    """Crop a region and scale it to a 4:3 card thumbnail."""
    return im.convert("RGB").crop(box).resize(size, Image.LANCZOS)


def save(im, name, quality=86):
    path = os.path.join(OUT, name)
    im.save(path, "WEBP", quality=quality, method=6)
    print(f"  {name:32s} {im.width}x{im.height}  {os.path.getsize(path)/1024:.0f} KB")


# ---------- fonts and labels ----------

def _font(paths, size):
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:                                   # matplotlib ships DejaVu Sans
        import matplotlib
        return ImageFont.truetype(os.path.join(matplotlib.get_data_path(), "fonts", "ttf",
                                               "DejaVuSans.ttf"), size)
    except Exception:
        return ImageFont.load_default(size)


def regular_font(size):
    """A Helvetica-like font to match MATLAB's labels."""
    return _font(("/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                  "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
                  "C:/Windows/Fonts/arial.ttf"), size)


def bold_font(size):
    return _font(("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                  "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
                  "C:/Windows/Fonts/arialbd.ttf"), size)


def relabel(im, old_box, centre_x, top, text, size=34):
    """Replace a MATLAB panel title (e.g. "PF" -> "LPF") in a matching bold font."""
    d = ImageDraw.Draw(im)
    d.rectangle(old_box, fill="white")
    f = bold_font(size)
    l, t, r, _ = f.getbbox(text)
    d.text((centre_x - (r - l) / 2 - l, top - t), text, font=f, fill="black")
    return im


def rich_width(parts, size):
    """Width of text with superscripts; parts are (text, is_superscript) pairs."""
    f, s = regular_font(size), regular_font(round(size * 0.68))
    return sum((s if sup else f).getlength(t) for t, sup in parts)


def draw_rich(draw, x, baseline, parts, size, fill=INK):
    """Draw text with superscripts (e.g. units like 10^-4 s^-1) from a baseline."""
    f, s = regular_font(size), regular_font(round(size * 0.68))
    for t, sup in parts:
        font = s if sup else f
        draw.text((x, baseline - (0.42 * size if sup else 0)), t, font=font, fill=fill, anchor="ls")
        x += font.getlength(t)


UNITS_VORT = [("\u00d710", False), ("\u22124", True), (" s", False), ("\u22121", True)]


def colorbar(strip, lo, hi, ticks, length, thick, size, horizontal=False, nearest=False):
    """A clean colorbar built from a MATLAB colorbar strip (highest value at the top).

    Returns the image and the (x, y) of the bar's top-left corner within it."""
    s = strip.convert("RGB")
    if horizontal:
        s = s.transpose(Image.ROTATE_270)                  # high values on the right
    s = s.resize((length, thick) if horizontal else (thick, length),
                 Image.NEAREST if nearest else Image.LANCZOS)
    font = regular_font(size)
    tick, gap = max(5, size // 5), max(4, size // 5)
    labels = [(v, f"{v:g}") for v in ticks]
    lw = max(font.getlength(t) for _, t in labels)
    if horizontal:
        pad = round(lw / 2) + 2
        im = Image.new("RGB", (length + 2 * pad, thick + tick + gap + round(size * 1.05)), "white")
        x0, y0 = pad, 1
    else:
        pad = round(size * 0.6)
        im = Image.new("RGB", (thick + tick + gap + round(lw) + 4, length + 2 * pad), "white")
        x0, y0 = 1, pad
    im.paste(s, (x0, y0))
    d = ImageDraw.Draw(im)
    w = max(2, size // 14)
    d.rectangle((x0 - 1, y0 - 1, x0 + s.width, y0 + s.height), outline=INK, width=w)
    for v, t in labels:
        f = (v - lo) / (hi - lo)
        if horizontal:
            x = x0 + f * s.width
            d.line((x, y0 + thick, x, y0 + thick + tick), fill=INK, width=w)
            d.text((x, y0 + thick + tick + gap), t, font=font, fill=INK, anchor="mt")
        else:
            y = y0 + (1 - f) * s.height
            d.line((x0 + thick, y, x0 + thick + tick, y), fill=INK, width=w)
            d.text((x0 + thick + tick + gap, y), t, font=font, fill=INK, anchor="lm")
    return im, (x0, y0)


# ---------- 1. Global: hourly LPF globe and the EnKF/LPF regional comparison ----------

def globe_frame(im):
    """One frame of the global LPF loop: the globe, with a legible colorbar beside it."""
    globe = im.crop((378, 325, 1176, 1123))
    strip = im.crop((1279, 394, 1319, 1004))              # 0 to 2 x 10^-4 s^-1
    cb, (_, by) = colorbar(strip, 0, 2, [0, 0.5, 1, 1.5, 2], length=470, thick=34, size=48)
    head = 56                                             # room for the units above the bar
    out = Image.new("RGB", (globe.width + 26 + cb.width + 16, globe.height), "white")
    out.paste(globe, (0, 0))
    top = (globe.height - cb.height + head) // 2
    out.paste(cb, (globe.width + 26, top))
    d = ImageDraw.Draw(out)
    units_w = rich_width(UNITS_VORT, 44)
    draw_rich(d, out.width - 16 - units_w, top + by - 24, UNITS_VORT, 44)
    return out


def _globe_png(job):
    src, dst = job
    globe_frame(Image.open(src).convert("RGB")).save(dst, compress_level=1)


def global_video(img):
    """The hourly loop (frames 01-427), with frames prepared in parallel."""
    if not shutil.which("ffmpeg"):
        print("  (ffmpeg not found; skipped global-lpf-loop.mp4)")
        return
    from multiprocessing import Pool
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [(os.path.join(img, f"global-hrly-lpf-{i:02d}.png"), os.path.join(tmp, f"f{i:03d}.png"))
                for i in range(1, 428)]
        with Pool() as pool:
            pool.map(_globe_png, jobs)
        mp4 = os.path.join(OUT, "global-lpf-loop.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-framerate", "20", "-start_number", "1",
            "-i", os.path.join(tmp, "f%03d.png"),
            "-vf", "scale=640:-2:flags=lanczos,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "28",
            "-movflags", "+faststart", "-an", mp4], check=True)
    print(f"  {'global-lpf-loop.mp4':32s} 427 frames  {os.path.getsize(mp4)/1024:.0f} KB")


def global_figs(img, video=True):
    # Hourly 500-hPa cyclonic vorticity (frames 01-427) from the global UFS LPF experiment
    g = Image.open(os.path.join(img, "global-hrly-lpf-01.png")).convert("RGB")
    save(fit(globe_frame(g), 640), "global-lpf-poster.webp", quality=84)
    save(thumb(g, (470, 410, 1090, 875)), "card-nongaussian.webp")
    if video:
        global_video(img)

    # Regional comparison: 250-mb relative vorticity in one EnKF and one LPF posterior member
    # from experimental HAFS, 18 UTC 19 Aug 2020, with an extratropical cyclone in the
    # northeast corner. The MATLAB title "PF" becomes "LPF", the date line is dropped, and
    # MATLAB's colorbar is redrawn with larger labels.
    v = Image.open(os.path.join(img, "vort-KF-PF-250-20.png")).convert("RGB")
    relabel(v, (790, 2, 862, 33), 825, 5, "LPF")
    maps = v.crop((45, 0, 1076, 541))
    cb, (_, by) = colorbar(v.crop((1085, 46, 1116, 533)), 0, 3, [0, 1, 2, 3],
                           length=455, thick=30, size=32)
    out = Image.new("RGB", (maps.width + 18 + cb.width + 44, maps.height), "white")
    out.paste(maps, (0, 0))
    top = maps.height - cb.height - 4
    out.paste(cb, (maps.width + 18, top))
    d = ImageDraw.Draw(out)
    units_w = rich_width(UNITS_VORT, 30)
    draw_rich(d, out.width - 12 - units_w, top + by - 15, UNITS_VORT, 30)
    save(out, "enkf-lpf-vorticity.webp", quality=88)


# ---------- 2. New methodology: Rankine vortex manifold ----------

def methods_figs(pres):
    # Members on and off the prior manifold, from Poterjoy (2022a, Fig. 12b, panel letter
    # removed), and a card cropped from it
    r = Image.open(os.path.join(pres, "ISDA", "FIGS", "paper_scatter-3D-fullobs.png")).convert("RGB")
    m = r.crop((989, 48, 1854, 582))
    ImageDraw.Draw(m).rectangle((114, 28, 151, 58), fill="white")
    save(m, "rankine-manifold.webp", quality=90)
    save(r.crop((1196, 52, 1756, 472)).resize((640, 480), Image.LANCZOS), "card-methods.webp")


# ---------- 3. Mesoscale: radar reflectivity with Gaussian vs. learned likelihoods ----------

def mesoscale_figs(img):
    # Each panel is cropped to its map frame (the small lat/lon labels are dropped); the
    # shared colorbar is redrawn once, horizontally, below the pair.
    for src, name in (("refl-frame-zeros-wmax37.png", "radar-gaussian.webp"),
                      ("refl-frame-wmax37.png", "radar-nonparametric.webp")):
        r = Image.open(os.path.join(img, src)).convert("RGB")
        save(r.crop((138, 49, 673, 584)), name, quality=88)
    strip = r.crop((692, 50, 722, 583))                   # 5 to 75 dBZ in 5-10 dBZ bands
    cb, (bx, by) = colorbar(strip, 5, 75, list(range(10, 71, 10)), length=600, thick=24,
                            size=25, horizontal=True, nearest=True)
    title = "Reflectivity (dBZ)"
    f = regular_font(25)
    tw = f.getlength(title)
    out = Image.new("RGB", (968, cb.height + 2), "white")
    x = round((out.width - (tw + 22 + cb.width)) / 2)
    ImageDraw.Draw(out).text((x, by + 13), title, font=f, fill=INK, anchor="lm")
    out.paste(cb, (round(x + tw + 22), 0))
    save(out, "radar-colorbar.webp", quality=90)
    r = Image.open(os.path.join(img, "refl-frame-wmax37.png"))
    save(thumb(r, (300, 150, 580, 360)), "card-observations.webp")


# ---------- 4. Hurricanes: simulated visible imagery from HAFS analyses (Aug 2020) ----------

def hurricane_figs(img, video=True):
    crop = (403, 95, 1983, 1136)
    h = Image.open(os.path.join(img, "HAFS_domain_030.png")).convert("RGB").crop(crop)
    save(fit(h, 1200), "hafs-poster.webp", quality=82)
    save(thumb(Image.open(os.path.join(img, "HAFS_domain_003.png")),
               (800, 330, 1600, 930)), "card-hurricanes.webp")
    frames = sorted(f for f in os.listdir(img) if f.startswith("HAFS_domain_") and f.endswith(".png"))
    if video and shutil.which("ffmpeg") and frames:
        with tempfile.TemporaryDirectory() as tmp:
            for i, f in enumerate(frames):
                Image.open(os.path.join(img, f)).convert("RGB").crop(crop).save(
                    os.path.join(tmp, f"f{i:03d}.png"))
            mp4 = os.path.join(OUT, "hafs-loop.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error", "-framerate", "4",
                "-i", os.path.join(tmp, "f%03d.png"),
                "-vf", "scale=1200:-2:flags=lanczos,format=yuv420p",
                "-c:v", "libx264", "-preset", "slow", "-crf", "27",
                "-movflags", "+faststart", "-an", mp4], check=True)
            print(f"  {'hafs-loop.mp4':32s} {len(frames)} frames  {os.path.getsize(mp4)/1024:.0f} KB")

    # Track and intensity errors and spread for EnKF-Var and PF-Var HAFS forecasts. The
    # legend's "PF-Var" becomes "LPF-Var" and the storm IDs become the storm names.
    if INCLUDE_UNPUBLISHED:
        a = Image.open(os.path.join(img, "AL13-14-PF-Var.png")).convert("RGB")
        d = ImageDraw.Draw(a)
        reg = regular_font(94)
        for x0, x1, txt in ((1977, 2640, "LPF-Var (RMSD)"), (3198, 3915, "LPF-Var (Spread)")):
            d.rectangle((x0 - 4, 192, x1 + 4, 296), fill="white")
            d.text((x0, 199), txt, font=reg, fill="black", anchor="lt")
        d.rectangle((540, 85, 1310, 200), fill="white")
        d.text((551, 101), "Laura and Marco", font=bold_font(104), fill="black", anchor="lt")
        a = a.crop((60, 30, 4392, 3320))
        save(fit(a, 1400), "hafs-lpf-verification.webp", quality=88)


# ---------- 5. Sea ice: SIC analysis and conditional observation distributions ----------

def digitize_histograms(a):
    """Bin heights of the three histograms in panel (b) of SOCA-ice-pyx.png.

    The slide holds the panel only as a bitmap, so it is redrawn from the bars: x runs from
    0 to 1 between pixel columns 2422.5 and 3922.5 (the bars' edges show the bins are 0.01
    wide and centred on multiples of 0.01, about 2 px right of that scale), and p(y|x) = 15
    lies 15*31.93 px above each bottom axis. Returns bin centres and one height per bin."""
    a = a.astype(float)
    xs = np.arange(2428, 3920)
    x = (xs - 2422.5) / 1500.0 + 0.0015
    centres = np.round(np.arange(0, 1.0001, 0.01), 2)
    out = []
    for bottom, colour in ((869.5, (31, 119, 180)), (1464, (255, 127, 14)), (2060.5, (44, 160, 44))):
        c = np.array(colour, float)
        start = int(bottom) - 5                          # just above the blurred axis line
        heights = []
        for col in xs:
            y = start
            while y > 0 and np.linalg.norm(a[y, col] - c) < np.linalg.norm(a[y, col] - 255):
                y -= 1
            heights.append(0.0 if y == start else (bottom - y - 0.5) / 31.93)
        heights = np.array(heights)
        # the bin at 0 is mostly hidden under the y axis; use its few visible columns
        out.append(np.array([np.median(heights[(x < 0.0075) if m == 0 else (np.abs(x - m) < 0.0035)])
                             for m in centres]))
    return centres, out


def seaice_map(s):
    """Panel (a) without its panel letter and colorbar (redrawn later in matplotlib)."""
    s = s.copy()
    a = np.asarray(s).astype(int)
    # The old colorbar sits just outside the lower edge of the curved domain. Find that edge
    # (the first non-white pixel above the colorbar) and whiten everything below it.
    xs = np.arange(1340, 2090, 10)
    ys = []
    for x in xs:
        y = 1848
        while a[y, x].min() > 235:
            y -= 1
        ys.append(y)
    edge = np.poly1d(np.polyfit(xs, ys, 2))
    yy, xx = np.mgrid[1650:2130, 1210:2130]
    mask = yy > edge(xx) + 4
    a[1650:2130, 1210:2130][mask] = 255
    a[150:280, 120:300] = 255                             # panel letter "a)"
    return Image.fromarray(a.astype(np.uint8)).crop((180, 200, 2120, 2125))


def polar_figs(img):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.lines import Line2D

    src = Image.open(os.path.join(img, "SOCA-ice-pyx.png")).convert("RGB")
    a = np.asarray(src)
    x, hist = digitize_histograms(a)
    m = seaice_map(src)
    cmap = ListedColormap(a[1878, 1236:2084].astype(float) / 255)   # the SIC colorbar, 0 to 1
    marks = (("o", (1356, 835), 0.14), ("D", (1240, 975), 0.56), ("*", (916, 1254), 0.86))
    colours = ("#1f77b4", "#ff7f0e", "#2ca02c")

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.2, "axes.linewidth": 0.7,
                         "xtick.major.width": 0.7, "ytick.major.width": 0.7,
                         "xtick.major.size": 2.5, "ytick.major.size": 2.5,
                         "axes.edgecolor": "#262626", "text.color": "#262626",
                         "xtick.color": "#262626", "ytick.color": "#262626"})
    fig = plt.figure(figsize=(4.84, 2.85), dpi=100)
    ax = fig.add_axes((0.025, 0.0, 0.53, 1.0))
    ax.imshow(np.asarray(m), interpolation="lanczos")
    ax.set_axis_off()
    for mk, (px, py), _ in marks:
        ax.plot(px - 180, py - 200, mk, ms=7.5 if mk == "*" else 5.2, mfc="red", mec="white",
                mew=0.8)
    fig.text(0.0, 0.98, "a", fontweight="bold", fontsize=10, va="top")
    cax = ax.inset_axes((0.66, 0.16, 0.32, 0.04))
    cb = fig.colorbar(plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1)), cax=cax,
                      orientation="horizontal", ticks=[0, 0.5, 1])
    cb.ax.set_xticklabels(["0", "0.5", "1"])
    cb.outline.set_linewidth(0.6)
    cb.set_label("Analysis SIC, $x$", labelpad=1.5)

    left, width, bottom, top, gap = 0.67, 0.315, 0.15, 0.955, 0.05
    hgt = (top - bottom - 2 * gap) / 3
    axes = []
    for i, ((mk, _, val), h, c) in enumerate(zip(marks, hist, colours)):
        b = fig.add_axes((left, top - (i + 1) * hgt - i * gap, width, hgt))
        b.bar(x, h, width=0.01, color=c, linewidth=0)
        b.set_xlim(-0.012, 1.012)                         # keep the bins at 0 and 1 in view
        b.set_ylim(0, 15.5)
        b.set_yticks([0, 5, 10])
        b.set_xticks([0, 0.5, 1])
        b.set_xticklabels(["0", "0.5", "1"])
        b.tick_params(labelbottom=(i == 2), pad=1.5)
        b.legend(handles=[Line2D([], [], marker=mk, ls="none", mfc="red", mec="white", mew=0.6,
                                 ms=7 if mk == "*" else 5, label=f"$x = {val}$")],
                 loc="upper right", frameon=False, handletextpad=0.2, borderaxespad=0.1,
                 borderpad=0.2, handlelength=1.0)
        axes.append(b)
    axes[2].set_xlabel("Observed SIC, $y$", labelpad=1.5)
    axes[1].set_ylabel("$p(y\\,|\\,x)$", labelpad=2)
    fig.text(left - 0.09, 0.98, "b", fontweight="bold", fontsize=10, va="top")

    with tempfile.TemporaryDirectory() as tmp:
        png = os.path.join(tmp, "seaice.png")
        fig.savefig(png, dpi=200, facecolor="white")
        plt.close(fig)
        save(Image.open(png).convert("RGB"), "seaice-obs-distributions.webp", quality=90)
    s = src.crop((6, 4, src.width, src.height))       # drop the thin border on the slide export
    save(thumb(s, (800, 640, 1900, 1465)), "card-polar.webp")


STEPS = ("methods", "global", "mesoscale", "hurricanes", "polar")


def main(pres, only=STEPS, video=True):
    img = os.path.join(pres, "img")
    os.makedirs(OUT, exist_ok=True)
    if "methods" in only:
        methods_figs(pres)
    if "global" in only:
        global_figs(img, video)
    if "mesoscale" in only:
        mesoscale_figs(img)
    if "hurricanes" in only:
        hurricane_figs(img, video)
    if "polar" in only:
        polar_figs(img)


if __name__ == "__main__":
    args = sys.argv[1:]
    only, video = STEPS, True
    if "--no-video" in args:
        args.remove("--no-video")
        video = False
    if "--only" in args:
        i = args.index("--only")
        only = tuple(args[i + 1].split(","))
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], only, video)
