"""Generate the original illustrations used on the website.

Run once (requires numpy + matplotlib); outputs SVG files to assets/img/.
    python3 tools/make_graphics.py
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "img")
NAVY, BLUE, LIGHT, PALE, WARM = "#103468", "#1C6CA8", "#9DBBDD", "#E6EEF7", "#D9822B"
plt.rcParams.update({"svg.fonttype": "none", "svg.hashsalt": "poterjoy"})
rng = np.random.default_rng(7)


def canvas(w=4.0, h=3.0):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0.04, 0.06, 0.92, 0.88])
    ax.set_axis_off()
    return fig, ax


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, transparent=True)
    plt.close(fig)
    print(name, os.path.getsize(path), "bytes")


def gauss(x, m, s):
    return np.exp(-0.5 * ((x - m) / s) ** 2) / (s * np.sqrt(2 * np.pi))


# 1. Non-Gaussian Bayesian update with weighted particles -------------------
def nongaussian():
    x = np.linspace(-4, 4, 400)
    prior = 0.55 * gauss(x, -1.4, 0.6) + 0.45 * gauss(x, 1.5, 0.75)
    like = gauss(x, 1.0, 0.7)
    post = prior * like
    post /= np.trapezoid(post, x)
    fig, ax = canvas()
    ax.fill_between(x, prior, color=PALE, lw=0)
    ax.plot(x, prior, color=LIGHT, lw=2)
    ax.plot(x, like * 0.55, color=WARM, lw=2, ls=(0, (4, 3)))
    ax.fill_between(x, post * 0.62, color=BLUE, alpha=0.12, lw=0)
    ax.plot(x, post * 0.62, color=NAVY, lw=2.6)
    # particles drawn from the prior, sized by likelihood weight
    p = np.concatenate([rng.normal(-1.4, 0.6, 14), rng.normal(1.5, 0.75, 12)])
    w = gauss(p, 1.0, 0.7)
    w /= w.max()
    ax.scatter(p, np.full_like(p, -0.045), s=8 + 120 * w, color=NAVY,
               alpha=0.35 + 0.65 * w, lw=0, zorder=5)
    ax.axhline(-0.045, color=LIGHT, lw=0.8, zorder=1)
    ax.set_xlim(-4, 4)
    ax.set_ylim(-0.09, post.max() * 0.62 * 1.08)
    save(fig, "theme-nongaussian.svg")


# 2. Learning an unknown, noisy measurement relationship --------------------
def operators():
    n = 160
    xs = rng.uniform(0, 1, n)
    truth = lambda z: 0.15 + 0.75 / (1 + np.exp(-11 * (z - 0.52)))
    ys = truth(xs) + rng.normal(0, 0.03 + 0.07 * xs, n)
    xg = np.linspace(0, 1, 200)
    # Nadaraya-Watson kernel estimate of the mean and spread
    K = np.exp(-0.5 * ((xg[:, None] - xs[None, :]) / 0.06) ** 2)
    m = (K @ ys) / K.sum(1)
    v = (K @ (ys - np.interp(xs, xg, m)) ** 2) / K.sum(1)
    sd = np.sqrt(v)
    fig, ax = canvas()
    ax.fill_between(xg, m - 2 * sd, m + 2 * sd, color=PALE, lw=0)
    ax.scatter(xs, ys, s=10, color=LIGHT, lw=0, alpha=0.9)
    ax.plot(xg, m, color=NAVY, lw=2.6)
    sel = rng.choice(n, 7, replace=False)
    ax.scatter(xs[sel], ys[sel], s=26, color=WARM, lw=0, zorder=5)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.05, 1.12)
    save(fig, "theme-operators.svg")


# 3. Ensemble of tropical-cyclone track forecasts ---------------------------
def track(turn, speed, n=70, dt=1.0):
    """Integrate a track whose heading turns from WNW to NE (recurvature)."""
    x, y, h = [0.0], [0.0], np.deg2rad(160.0)
    for i in range(n):
        frac = i / n
        h -= np.deg2rad(turn) * (0.4 + 1.6 * frac)   # turning accelerates
        v = speed * (0.8 + 0.9 * frac)              # storm speeds up after recurving
        x.append(x[-1] + v * np.cos(h) * dt)
        y.append(y[-1] + v * np.sin(h) * dt)
    return np.array(x), np.array(y)


def tracks():
    fig, ax = canvas()
    xs, ys = [], []
    for k in range(26):
        x, y = track(1.25 + 0.22 * rng.normal(), 0.010 * (1 + 0.10 * rng.normal()), n=64)
        xs.append(x); ys.append(y)
        ax.plot(x, y, color=BLUE, lw=1.1, alpha=0.42, solid_capstyle="round")
        ax.scatter(x[8::12], y[8::12], s=5, color=BLUE, alpha=0.6, lw=0)
    xm, ym = track(1.25, 0.010, n=64)
    ax.plot(xm, ym, color=NAVY, lw=2.8, solid_capstyle="round")
    ax.scatter([0], [0], s=50, color=WARM, lw=0, zorder=5)
    th = np.linspace(0, 4 * np.pi, 200)
    r = 0.004 + 0.0022 * th
    ax.plot(r * np.cos(th), r * np.sin(th), color=WARM, lw=1.1, zorder=5)
    allx, ally = np.concatenate(xs), np.concatenate(ys)
    cx, cy = (allx.min() + allx.max()) / 2, (ally.min() + ally.max()) / 2
    half = max(allx.max() - allx.min(), (ally.max() - ally.min()) * 4 / 3) / 2 * 1.08
    ax.set_aspect("equal")
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half * 0.75, cy + half * 0.75)
    save(fig, "theme-tracks.svg")


# 4. Ensemble of sea-ice-edge estimates on a polar grid ---------------------
def seaice():
    fig, ax = canvas(4.0, 3.0)
    th = np.linspace(0, 2 * np.pi, 361)
    for r in (0.35, 0.7, 1.05):
        ax.plot(r * np.cos(th), r * np.sin(th), color=LIGHT, lw=0.6, alpha=0.6)
    for a in np.linspace(0, np.pi, 7)[:-1]:
        ax.plot([-1.1 * np.cos(a), 1.1 * np.cos(a)], [-1.1 * np.sin(a), 1.1 * np.sin(a)],
                color=LIGHT, lw=0.6, alpha=0.6)
    base = 0.62 + 0.10 * np.sin(3 * th + 0.4) + 0.06 * np.cos(5 * th - 1.0)
    ax.fill(base * np.cos(th), base * np.sin(th), color=PALE, lw=0)
    for k in range(16):
        pert = sum(rng.normal(0, 0.085 / (m ** 0.7)) * np.sin(m * th + rng.uniform(0, 6.3))
                   for m in range(2, 9))
        r = base + pert
        ax.plot(r * np.cos(th), r * np.sin(th), color=BLUE, lw=1.0, alpha=0.45)
    ax.plot(base * np.cos(th), base * np.sin(th), color=NAVY, lw=2.6)
    obs = rng.uniform(0, 2 * np.pi, 9)
    rb = 0.62 + 0.10 * np.sin(3 * obs + 0.4) + 0.06 * np.cos(5 * obs - 1.0)
    ax.scatter(rb * np.cos(obs), rb * np.sin(obs), s=24, color=WARM, lw=0, zorder=5)
    ax.set_aspect("equal")
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-1.12, 1.12)
    save(fig, "theme-seaice.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    nongaussian()
    operators()
    tracks()
    seaice()
