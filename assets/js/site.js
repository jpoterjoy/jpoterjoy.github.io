// poterjoy.com — small progressive enhancements (the site works without JS).
(function () {
  "use strict";

  // Mobile navigation toggle
  var btn = document.querySelector(".menu-btn");
  var nav = document.getElementById("site-nav");
  if (btn && nav) {
    btn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // Publication filter (All / Advisee-led)
  var filter = document.querySelector(".filter");
  if (filter) {
    filter.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      filter.querySelectorAll("button").forEach(function (x) {
        x.setAttribute("aria-pressed", x === b ? "true" : "false");
      });
      var mode = b.getAttribute("data-filter");
      document.querySelectorAll(".pubs li").forEach(function (li) {
        var show = mode === "all" || li.getAttribute("data-kind").indexOf(mode) !== -1;
        li.classList.toggle("hidden", !show);
      });
      document.querySelectorAll(".year-block").forEach(function (blk) {
        blk.classList.toggle("hidden", !blk.querySelector(".pubs li:not(.hidden)"));
      });
    });
  }

  // Research animations: play only while on screen, and never for reduced-motion users
  var loops = document.querySelectorAll("video.loop");
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (loops.length) {
    if (still || !("IntersectionObserver" in window)) {
      loops.forEach(function (v) { v.controls = true; });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) { var p = e.target.play(); if (p && p.catch) p.catch(function () { e.target.controls = true; }); }
          else { e.target.pause(); }
        });
      }, { threshold: 0.25 });
      loops.forEach(function (v) { io.observe(v); });
    }
  }

  // Hero: Bayesian updates of sea ice and cloud from satellite radiances, drawn over "Arctic Sky"
  // (U.S. Coast Guard photo by Patrick Kelley from USCGC Healy, Arctic Ocean, 19 August 2009; public
  // domain via USGS): melt-ponded ice, an open lead, and cloud thinning over the ice.
  //
  // Three sensors take turns, each sensitive to a different part of the column:
  //  * DMSP SSMIS 19 GHz (horizontal polarization; 3-dB footprint 74 x 45 km; Kunkee et al. 2008)
  //    mostly sees the surface, and updates the sea-ice concentration C.
  //  * SSMIS 91 GHz (16 x 13 km) is dominated by cloud liquid water, and updates the liquid water
  //    path (LWP); it can do so best over open water, whose low emissivity makes a bright cloud
  //    stand out, and only weakly over ice.
  //  * VIIRS 11 um (I5, 375 m pixels) sees the cloud top, or the surface where it is clear, and also
  //    updates LWP; a liquid cloud is opaque in the infrared once LWP passes ~0.02 kg m-2, so the
  //    infrared cannot say how much water a cloud holds; and over summer ice a low cloud's top is
  //    within a few kelvin of the surface, so it often cannot even tell cloud from clear sky: its
  //    likelihood is one-sided at best, and often nearly flat.
  // The radiation drawn for each starts where its signal comes from (see radiation()).
  //
  // Geometry. The photo is a level camera 25 m above a flat sea (12 mm lens); the horizon is only
  // ~18 km away, so a real microwave footprint (tens of km) would cover everything in view. The
  // microwave footprints are drawn NOT to scale but as close to it as the photo allows: on the
  // distant ice and water, 0.25-1.1 km from the ship, all shrunk by the same factor (to 1/200 of true
  // size), so they keep their sizes relative to one another. VIIRS pixels are small enough to draw at
  // true scale, 1-1.6 km out. Perspective flattens footprints this far off into long, thin ellipses.
  // Beams all head for the same point above the picture: the satellite, at 53 deg incidence, 30 deg
  // right of ahead.
  //
  // Microwave forward model: for each surface, Tb = T_up + t [e Ts + (1 - e)(T_dn + t T_cos)] in an
  // isothermal 268 K summer atmosphere whose clear-sky transmissivity (0.93 at 19 GHz, 0.72 at
  // 91 GHz) is lowered by cloud liquid water (mass absorption 0.072 and 1.3 per kg m-2 at nadir;
  // after Wentz and Meissner 2000). Emissivities at 53 deg, 19 / 91 GHz: open water at 272 K
  // 0.32 / 0.53, melt ponds (fresh, calm, 273 K) 0.30 / 0.50, wet summer ice at 273 K 0.88 / 0.84;
  // a melt pond looks like open water. Infrared: see tbIR().
  //
  // The scene comes from the photo (see tools/make_hero_scene.py): for footprint centres on a grid,
  // the ice concentration inside each sensor's footprint (ponded ice counts as ice), the pond
  // fraction of that ice, and the cloud the beam passes in front of on its way up (which sets its
  // LWP, up to 0.3 kg m-2). The cloud layer is drawn where the underside of the cloud deck is in
  // the picture.
  //
  // Each update starts from a non-Gaussian forecast of the variable. The likelihood comes from the
  // measured Tb through the forward model, integrated over what the forecast does not know (see
  // likelihood()), and the prior is tempered toward the posterior, p(x) L(x)^b with b from 0 to 1.
  // One update is on screen at a time.
  var canvas = document.getElementById("bayes");
  if (!canvas || !canvas.getContext) return;
  var hero = canvas.parentElement;
  var ctx = canvas.getContext("2d");
  var beamCanvas = document.createElement("canvas"), beamCtx = beamCanvas.getContext("2d");   // one beam's layer

  // the banner image: photo rows 300-2300 at full width, scaled to 2400 x 1139
  var IMG_W = 2400, IMG_H = 1139, CROP_Y = 300, CROP_S = IMG_W / 4216;
  var POS_X = 0, POS_Y = 0.78, POS_X_PHONE = 0.6;     // must match the CSS background-position
  var SCENE = {"F": 2180.0, "CX": 2108.0, "YH": 1402.0, "H": 25.0, "K": 5.0, "AZ": 0.5236, "VP": [3366.6, -488.0], "nx": 53, "ny": 18, "x0": 0, "dx": 80, "rows": [1620.0, 1596.6, 1572.3, 1553.4, 1534.9, 1520.5, 1506.8, 1494.4, 1483.3, 1473.7, 1465.4, 1457.6, 1451.1, 1443.9, 1436.1, 1429.2, 1423.8, 1420.2], "beam": "hhhghhhikkkjknmllmoopqrsstuwvwxxwxxwwwxxyyyyyyzzzzzzzhhhghhhijkkjjmnklmnopqqsstuvvwxxwxxwwwxxyyyyyyzzzzzzzhhhhhhhijkkkklnllmnopqqsttuvvwxxwxxwwwxxyyyyyyzzzzzzzhhhhghhhikkkjknmllnnopqrtttvwwxxwxxwwwxxyyyyyzzzzzzzzhhhhgghhijkkjjmnklmoopqrsttuwvxxwxxwwwxxyyyyyyzzzzzzzhhhhhhhhijkkjjlnklmoopqrsstuwvxxwxxwwwxxyyyyyzzzzzzzzhhhhhghhiikjkklnllmnopqrsstuwvxxwxxwwwxxyyyyyyzzzzzzzihhhhghhhikkkjknllmnopqqsstuwvxxwxxwwwxxyyyyyyzzzzzzzihhhhgghhikkkjknllmnopqqsstuwvwxwxxwwwxxyyyyyzzzzzzzzhhhhhghhhijkkjknmlmnooqqsttuwvwxwxxwwwxxyyyyyzzzzzzzzhhhhhhhhhijkkjkmnlmnooqqsttuvvwxwxxwwwxxyyyyyzzzzzzzzhhhhhhghhijkkjkmnklmoopqstttvvwxwxxwwwxxyyyyyzzzzzzzzhhhhhhghhijkkjjmnklmoopqrtttvvwxwxxwwwxxyyyyyzzzzzzzzhihhhhghhhjkkkklnklmoopqrtttvvwxxxxwwwxxyyyyyzzzzzzzzhhhhhhgghhikkkklnklmoopqrtttvvwxxwxwwwxxyyyyyzzzzzzzzhihhhhgghhikkkkknllmoopqrtttvwwxxwxwwwxxyyyyyzzzzzzzzhhhhhhgghhikjkkknllmnopqrtttvvwxxwxwwwxxyyyyyzzzzzzzzhhhhhhghhhikkkjknllmnopqrsttvvwxxwxwwwxxyyyyyzzzzzzzz", "C19": "________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________fcaaa999_____________________________________zyvsplieb9999999999abde_________________________zzzzzzzxurnjfb999aabbcegiknpr________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________", "C91": "________zzzzzzzzzzzzxupje83000000000000000001222___________zzzzzzzzzzzzzzzwrle82000000000000002479bded_________zzzzzzzzzzzzzzzzzzuoha510000000000015afffhij_________zzzzzzzzzzzzzzzzzzzzxsnjfca988889aceghijjkllk_______zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________", "Cir": "____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________zzzzzzzzzzzzywusqomkjjjjklnp___________________zzzzzzzzzzzzzzzzzzzzzyxwvuuuuvwxyzywvtrq____________zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzyvsolif__________zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzyxwvus________zzzz______________________________________zzzz_____________________________________________________________________________________________________________", "P19": "________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________55555555_____________________________________55555555555555555555555_________________________55555555555555555555555555555________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________", "P91": "________2222221111233344320000000000000000555555___________4333333333333455666830000000000000555555555_________55555555555555555555555550000000000555555555_________555555555555555555555555555555555555555555555_______5555555555555555555555555555555555555555555555____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________", "Pir": "____________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________________5555555555555555555555555555___________________5555555555555555555555555555555555555555____________555555555555555555555555555555555555555555__________55555555555555555555555555555555555555555555________5555______________________________________5555_____________________________________________________________________________________________________________"};
  var DEG = Math.PI / 180, COSI = Math.cos(53.1 * DEG);
  // the sensors, what each estimates (v), its footprint (km) and how that is drawn (k, picture metres
  // per km: the microwave footprints shrunk alike, VIIRS at true scale), and which lines of the
  // radiation start in the cloud rather than at the surface (from)
  var CH = {
    "19": { name: "SSMIS 19 GHz", v: "ice", km: [74, 45], k: SCENE.K, tc: 0.93, kap: 0.072, ew: 0.32, ep: 0.30, ei: 0.88,
            sig: 3, lo: 110, hi: 245, lam: 30, from: [0, 0, 0] },
    "91": { name: "SSMIS 91 GHz", v: "lwp", km: [16, 13], k: SCENE.K, tc: 0.72, kap: 1.3, ew: 0.53, ep: 0.50, ei: 0.84,
            sig: 4, lo: 200, hi: 265, lam: 12, from: [1, 0, 1] },
    "ir": { name: "VIIRS 11 \u00b5m", v: "lwp", km: [0.375, 0.375], k: 1000, ir: true,
            sig: 0.4, lo: 262, hi: 274, lam: 7, from: [1, 1, 1] }
  };
  var ORDER = ["19", "91", "ir"];
  var CLOUD_ROW = 1200;                       // the underside of the cloud deck in the photo
  var VAR = {
    ice: { max: 1, ticks: ["0", "50", "100"], title: "sea-ice concentration (%)" },
    lwp: { max: 0.5, ticks: ["0", "0.25", "0.5"], title: "cloud liquid water (kg m\u207b\u00b2)" }
  };
  function lwpOf(cloud) { return 0.3 * Math.min(1, Math.max(0, (cloud - 0.4) / 0.6)); }   // along the beam
  var NC = 201, CG = [];
  for (var ic = 0; ic < NC; ic++) CG.push(ic / (NC - 1));
  var DC = 1 / (NC - 1);
  var LIFE = 12.5, DONE = 9.6, FADE = 2;      // seconds: each update lives LIFE, fading over its last FADE,
  var every = LIFE, lifeSpan = LIFE;         // and the next one starts as it goes
  var GLOW = "255,170,110", RED = "255,72,58", LINE = "255,214,180";
  // the graphs: near-black and burnt orange with a white halo where they sit over the photo's
  // natural light (wide screens); white and amber with a dark halo over the darkened stacked layout
  // (phones and small tablets)
  var INK, ACC, HALO;
  var FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";

  function npdf(x, m, sd) { var z = (x - m) / sd; return Math.exp(-0.5 * z * z) / (sd * 2.5066283); }
  function randn() { var u = 1 - Math.random(), v = Math.random(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(6.2832 * v); }
  function normalize(f) {
    var z = 0; for (var i = 1; i < f.length; i++) z += 0.5 * (f[i] + f[i - 1]) * DC;
    return f.map(function (v) { return v / z; });
  }
  function tempered(prior, like, b) { return normalize(prior.map(function (v, i) { return v * Math.pow(like[i], b); })); }
  function ymaxOf(prior, like) {
    // the tallest the density gets at any stage of the update (it can peak part way), so the graph's
    // scale leaves room for all of it
    var m = 0;
    for (var b = 0; b <= 1.0001; b += 0.05) { var f = tempered(prior, like, b); m = Math.max(m, f[argmax(f)]); }
    return m;
  }
  function argmax(f) { var k = 0; for (var i = 1; i < f.length; i++) if (f[i] > f[k]) k = i; return k; }
  function ease(u) { u = Math.min(1, Math.max(0, u)); return u * u * (3 - 2 * u); }

  // --- geometry: photo pixels <-> the sea surface (a plane seen from 25 m) ----------------------
  function toGround(x, y) { var d = SCENE.F * SCENE.H / (y - SCENE.YH); return [(x - SCENE.CX) * d / SCENE.F, d]; }
  function toPhoto(X, D) { return [SCENE.CX + SCENE.F * X / D, SCENE.YH + SCENE.F * SCENE.H / D]; }
  function toScreen(P) { return { X: L.ox + P[0] * CROP_S * L.sc, Y: L.oy + (P[1] - CROP_Y) * CROP_S * L.sc }; }
  // in 3-D: X across, D ahead, Z up (m), the camera at (0, 0, H); U points to the satellite
  var U3 = [Math.sin(53.1 * DEG) * Math.sin(SCENE.AZ), Math.sin(53.1 * DEG) * Math.cos(SCENE.AZ), Math.cos(53.1 * DEG)];
  function proj3(X, D, Z) { return toScreen([SCENE.CX + SCENE.F * X / D, SCENE.YH - SCENE.F * (Z - SCENE.H) / D]); }
  function lift(G, z) { var t = z / U3[2]; return proj3(G[0] + t * U3[0], G[1] + t * U3[1], z); }   // up the beam to height z
  function footprint(P, ch, grow) {
    // the footprint on the sea surface (ground points), long axis toward the satellite, drawn at
    // ch.k picture metres per km (times L.m; grow enlarges it, for the glow around it)
    var s = (grow || 1) * ch.k * L.m, g = toGround(P[0], P[1]), a = s * ch.km[0] / 2, b = s * ch.km[1] / 2;
    var ex = [Math.sin(SCENE.AZ), Math.cos(SCENE.AZ)], ey = [Math.cos(SCENE.AZ), -Math.sin(SCENE.AZ)], pts = [];
    for (var k = 0; k < 48; k++) {
      var th = k / 48 * 6.2832, ca = a * Math.cos(th), sb = b * Math.sin(th);
      pts.push([g[0] + ca * ex[0] + sb * ey[0], g[1] + ca * ex[1] + sb * ey[1]]);
    }
    return pts;
  }
  function cell(i, j, key) {
    var k = j * SCENE.nx + i, c = SCENE["C" + key].charAt(k);
    if (c === "_") return null;
    return { C: parseInt(c, 36) / 35, p: parseInt(SCENE["P" + key].charAt(k), 36) / 35,
             lwp: lwpOf(parseInt(SCENE.beam.charAt(k), 36) / 35) };
  }

  // --- forward model and Bayes ---------------------------------------------------------------------
  function tb(ch, C, p, lwp) {
    var t = ch.tc * Math.exp(-ch.kap * lwp / COSI), up = (1 - t) * 268, dn = up + t * 2.7;
    var s = function (e, T) { return up + t * (e * T + (1 - e) * dn); };
    return C * ((1 - p) * s(ch.ei, 273) + p * s(ch.ep, 273)) + (1 - C) * s(ch.ew, 272);
  }
  // what the forecast does not know when estimating sea ice: cloud water (clear 30% of the time,
  // otherwise exponential with mean 0.1 kg m-2) and the pond fraction (uniform, 0-50%)
  var ALTS = [];
  (function () {
    var lw = [[0.3, 0]];
    for (var m = 1; m <= 20; m++) { var v = m * 0.025; lw.push([0.7 * Math.exp(-v / 0.1) * 0.025 / 0.1, v]); }
    lw.forEach(function (l) { for (var q = 0; q <= 10; q++) ALTS.push([l[0] / 11, l[1], q * 0.05]); });
  })();
  function tbIR(lwp, Tc) {
    // 11 um window: a liquid cloud at Tc over a 271.5 K clear-sky scene (surface near melting, a
    // little water vapour), emissivity 1 - exp(-130 LWP / mu) (absorption 0.13 m2 g-1). Summer
    // Arctic stratus sits in the lowest kilometre, its top within a few kelvin of the melting
    // surface and, under an inversion, sometimes warmer: Tc is 266-273 K, so cloud and surface
    // differ by 0-5 K, or not at all, at 11 um
    var e = 1 - Math.exp(-130 * lwp / COSI);
    return (1 - e) * 271.5 + e * Tc;
  }
  function likelihood(ch, T, s) {
    // p(T_b | x) for the variable the sensor estimates, integrated over what the forecast does not
    // know: for sea ice, the cloud water and ponds; for cloud water seen at 91 GHz, the ponds and
    // the ice (the forecast knows it to within ~15%); for cloud water seen in the infrared, the
    // cloud's temperature (266-273 K)
    var like;
    if (ch.v === "ice") {
      like = CG.map(function (C) {
        return ALTS.reduce(function (z, a) { return z + a[0] * npdf(T, tb(ch, C, a[2], a[1]), ch.sig); }, 0);
      });
    } else if (ch.ir) {
      like = CG.map(function (u) {
        var z = 0; for (var Tc = 266; Tc <= 273; Tc += 0.5) z += npdf(T, tbIR(VAR.lwp.max * u, Tc), ch.sig); return z;
      });
    } else {
      like = CG.map(function (u) {
        var z = 0;
        for (var d = -0.3; d <= 0.301; d += 0.1) {
          var C = Math.min(1, Math.max(0, s.C + d)), w = Math.exp(-0.5 * d * d / 0.0225);
          for (var q = 0; q <= 5; q++) z += w * npdf(T, tb(ch, C, q * 0.1, VAR.lwp.max * u), ch.sig);
        }
        return z;
      });
    }
    var mx = like[argmax(like)];
    return like.map(function (v) { return v / mx; });
  }
  function centre(like) {
    // where the leader lands: the middle of the likelihood's peak (or of its plateau)
    var n = 0, m = 0;
    like.forEach(function (v, i) { if (v > 0.7) { n++; m += CG[i]; } });
    return m / n;
  }
  function makePrior(like) {
    // a forecast that is never quite right: one to three bumps of varying width; nudged if it
    // flatly rules out what the radiance says. Each bump stays well inside the axis (its width is
    // capped by its distance from either end), so no large part of a density runs off the graph
    var n = Math.random() < 0.45 ? 3 : (Math.random() < 0.7 ? 2 : 1), comps = [];
    function fit(c) { c[1] = Math.min(0.95, Math.max(0.05, c[1])); c[2] = Math.max(0.025, Math.min(c[2], Math.min(c[1], 1 - c[1]) / 1.6)); }
    for (var k = 0; k < n; k++) {
      var sd = Math.random() < 0.35 ? 0.12 + Math.random() * 0.1 : 0.035 + Math.random() * 0.06;
      comps.push([0.25 + Math.random(), 0.05 + Math.random() * 0.9, sd]); fit(comps[k]);
    }
    function build() {
      return normalize(CG.map(function (x) { return comps.reduce(function (a, c) { return a + c[0] * npdf(x, c[1], c[2]); }, 0); }));
    }
    var f = build(), km = argmax(like);
    if (f[km] < 0.06 * f[argmax(f)]) {
      var near = 0;
      comps.forEach(function (c, k) { if (Math.abs(c[1] - CG[km]) < Math.abs(comps[near][1] - CG[km])) near = k; });
      comps[near][1] = CG[km] + (Math.random() - 0.5) * 0.2; fit(comps[near]);
      f = build();
    }
    return f;
  }

  // --- layout ---------------------------------------------------------------------------------
  var W = 0, H = 0, wide = true, L = null, eps = [], now = 0, nextSpawn = 0, count = 0, sweep = 0, lastGroup = -1;
  var last = 0, running = false, reduce = still, recent = [];

  function layout() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = hero.clientWidth; H = hero.clientHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    beamCanvas.width = canvas.width; beamCanvas.height = canvas.height;
    // side by side (the footprint, beam and graph beside the text) only where there is room for
    // them; below 1000 px the graph goes under the text. Must match the CSS breakpoint
    wide = window.matchMedia ? !window.matchMedia("(max-width: 999px)").matches : W >= 1000;
    INK = wide ? "12,22,38" : "240,246,255"; ACC = wide ? "186,78,14" : "242,184,126"; HALO = wide ? "255,255,255" : "5,16,36";
    var hr = hero.getBoundingClientRect();
    var tr = hero.querySelector(".hero-text").getBoundingClientRect();
    var cr = hero.querySelector(".credit").getBoundingClientRect();
    var sc = Math.max(W / IMG_W, H / IMG_H);
    L = { sc: sc, dpr: dpr, m: 1, ox: (W - IMG_W * sc) * (wide ? POS_X : POS_X_PHONE), oy: (H - IMG_H * sc) * POS_Y };
    L.hz = toScreen([0, SCENE.YH]).Y;                       // the horizon on screen
    L.vp = toScreen(SCENE.VP);                               // where the beams point
    if (wide) {
      L.R0 = tr.right - hr.left + 48; L.R1 = W - 40;
      L.pw = Math.min(300, Math.max(220, (L.R1 - L.R0) * 0.46));
      L.ph = Math.min(96, Math.max(76, H * 0.17));
      L.credit = [cr.left - hr.left - 12, cr.top - hr.top - 8, cr.right - hr.left + 6, H];   // the caption
      // footprints (and so beams) at full size where there is room beside the text, and down to half
      // that on narrower screens (tablets), so the graph can still sit clear of the beam
      L.m = Math.min(1, Math.max(0.5, (L.R1 - L.R0 - 220) / 250));
    } else {
      L.fixed = { x0: 34, x1: Math.min(W - 34, 634), base: H - 84, top: H - 184 };
    }
  }

  function exitLen(X, Y, ux, uy) {
    // distance from (X, Y) along (ux, uy) to where it leaves the banner
    var t = Infinity;
    if (uy < 0) t = Math.min(t, -Y / uy);
    if (uy > 0) t = Math.min(t, (H - Y) / uy);
    if (ux > 0) t = Math.min(t, (W - X) / ux);
    if (ux < 0) t = Math.min(t, -X / ux);
    return t + 20;
  }
  function observation(key, i, j) {
    // everything an update needs to draw its footprint and beam, in 3-D. The beam is the cylinder of
    // lines through the footprint parallel to the view direction U; in the picture all of them run
    // to the same vanishing point (where the satellite is), so the beam narrows as it rises, and its
    // edges are the two tangents from that point to the footprint ellipse
    var s = cell(i, j, key);
    if (!s) return null;
    var ch = CH[key], P = [SCENE.x0 + i * SCENE.dx, SCENE.rows[j]], S = toScreen(P), G0 = toGround(P[0], P[1]);
    var gp = footprint(P, ch), fp = gp.map(function (g) { return proj3(g[0], g[1], 0); }), n = fp.length, vp = L.vp;
    var ang = fp.map(function (p) { return Math.atan2(p.Y - vp.Y, p.X - vp.X); });
    var kL = 0, kR = 0;
    ang.forEach(function (v, k) { if (v < ang[kL]) kL = k; if (v > ang[kR]) kR = k; });
    // the near (lower) arc between the tangent points: the beam's base, in front of the rest
    var arcA = [], arcB = [];
    for (var k = kL; ; k = (k + 1) % n) { arcA.push(fp[k]); if (k === kR) break; }
    for (var k2 = kR; ; k2 = (k2 + 1) % n) { arcB.push(fp[k2]); if (k2 === kL) break; }
    var dist = function (arc) { return arc.reduce(function (z, p) { return z + Math.hypot(p.X - vp.X, p.Y - vp.Y); }, 0) / arc.length; };
    var near = dist(arcA) > dist(arcB) ? arcA : arcB.slice().reverse(), far = near === arcA ? arcB : arcA.slice().reverse();
    var Rb = near.reduce(function (z, p) { return Math.max(z, Math.hypot(p.X - vp.X, p.Y - vp.Y)); }, 0);
    // the cloud layer: the height where the beam's axis reaches the underside of the cloud deck in the
    // picture (photo row CLOUD_ROW); low stratus, a hundred metres or so up
    var r = CLOUD_ROW, ud = U3[1], uz = U3[2];
    var zc = ((SCENE.YH - r) * G0[1] + SCENE.F * SCENE.H) / (SCENE.F * uz - (SCENE.YH - r) * ud) * uz;
    var ring = gp.map(function (g) { return lift(g, zc); });
    // the lines of radiation: three ground points across the footprint (along its short axis)
    var b = ch.k * L.m * ch.km[1] / 2, ey = [Math.cos(SCENE.AZ), -Math.sin(SCENE.AZ)];
    var feet = [-0.55, 0, 0.55].map(function (f) {
      var g = [G0[0] + f * b * ey[0], G0[1] + f * b * ey[1]];
      return { base: proj3(g[0], g[1], 0), cloud: lift(g, zc) };
    });
    var ux = vp.X - S.X, uy = vp.Y - S.Y, ul = Math.hypot(ux, uy); ux /= ul; uy /= ul;
    var px = -uy, py = ux, lo = Infinity, hi = -Infinity, bottom = -Infinity, top = Infinity;
    fp.forEach(function (p) {
      var w = (p.X - S.X) * px + (p.Y - S.Y) * py; lo = Math.min(lo, w); hi = Math.max(hi, w);
      bottom = Math.max(bottom, p.Y); top = Math.min(top, p.Y);
    });
    return { key: key, ch: ch, X: S.X, Y: S.Y, s: s, P: P, fp: fp, near: near, far: far, angL: ang[kL], angR: ang[kR], Rb: Rb,
             ring: ring, feet: feet, bottom: bottom, top: top, ux: ux, uy: uy, w0: lo, w1: hi, len: exitLen(S.X, S.Y, ux, uy) };
  }
  function targets(key) {
    // footprint centres on screen, right of the text, clear of the caption, on the sea; and the
    // whole footprint too, which on a narrow screen can be wider than the space beside the text
    var out = [];
    for (var j = 0; j < SCENE.ny; j++) {
      for (var i = 0; i < SCENE.nx; i++) {
        if (!cell(i, j, key)) continue;
        var P = [SCENE.x0 + i * SCENE.dx, SCENE.rows[j]], S = toScreen(P);
        if (S.X > L.credit[0] - 70 && S.Y > L.credit[1] - 62) continue;        // room for the label above the caption
        if (!(S.X > L.R0 + 30 && S.X < W - 60 && S.Y > L.hz + 2 && S.Y < H - 62)) continue;
        var b = [Infinity, Infinity, -Infinity, -Infinity];
        footprint(P, CH[key]).forEach(function (g) {
          var p = proj3(g[0], g[1], 0);
          b[0] = Math.min(b[0], p.X); b[1] = Math.min(b[1], p.Y); b[2] = Math.max(b[2], p.X); b[3] = Math.max(b[3], p.Y);
        });
        if (b[0] < L.R0 - 24 || b[2] > W - 12 || overlap([b[0] - 8, b[1] - 8, b[2] + 8, b[3] + 8], L.credit)) continue;
        out.push({ i: i, j: j, X: S.X, Y: S.Y });
      }
    }
    return out;
  }
  function box(g) { return [g.x0 - 18, g.top - 12, g.x1 + 18, g.base + 40]; }
  function tagBox(o) { return o ? [o.X - 58, o.bottom + 4, o.X + 58, o.bottom + 40] : [0, 0, 0, 0]; }
  function fpBox(o) {
    var b = [Infinity, Infinity, -Infinity, -Infinity];
    o.fp.forEach(function (p) { b[0] = Math.min(b[0], p.X); b[1] = Math.min(b[1], p.Y); b[2] = Math.max(b[2], p.X); b[3] = Math.max(b[3], p.Y); });
    return [b[0] - 6, b[1] - 6, b[2] + 6, b[3] + 6];
  }
  function overlap(a, b) {
    var w = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), h = Math.min(a[3], b[3]) - Math.max(a[1], b[1]);
    return w > 0 && h > 0 ? w * h : 0;
  }
  function beamHits(b, o) {
    // how much of a beam (centre line every 10 px, padded by half its width there, which narrows
    // toward the vanishing point) falls in box b
    var n = 0, r0 = 0.5 * (o.w1 - o.w0), R = Math.hypot(L.vp.X - o.X, L.vp.Y - o.Y);
    for (var d = 0; d < o.len; d += 10) {
      var x = o.X + o.ux * d, y = o.Y + o.uy * d, r = r0 * Math.max(0, 1 - d / R);
      if (x > b[0] - r && x < b[2] + r && y > b[1] - r && y < b[3] + r) n++;
    }
    return n;
  }
  function slots() {
    var pw = L.pw, ph = L.ph, all = [];
    for (var x0 = L.R0; x0 <= L.R1 - pw; x0 += 20) {
      for (var base = ph + 30; base <= H - 48; base += 12) all.push({ x0: x0, x1: x0 + pw, base: base, top: base - ph });
    }
    return all;
  }

  function spawn(at) {
    // the channels take turns, and the scenes cycle through open water, loose ice and pack ice
    // (every pairing comes round every nine updates, where the channel's footprint fits there)
    var key = ORDER[count % 3], want = ["water", "edge", "ice"][(count + Math.floor(count / 3)) % 3], ob = null, g = null;
    if (wide) {
      var c = targets(key);
      if (c.length) {
        // the footprint keeps moving: candidates are split into a few groups from left to right,
        // and successive observations visit the groups in a fixed cycle that skips a group each
        // time (0, 2, 4, 1, 3, ...), so a new footprint is never next to the last one
        c.sort(function (p, q) { return p.X - q.X; });
        var K = Math.max(1, Math.min(5, Math.floor(c.length / 6))), order = [];
        for (var q0 = 0; q0 < K; q0 += 2) order.push(q0);
        for (var q1 = 1; q1 < K; q1 += 2) order.push(q1);
        var groupOf = function (k) { return c.slice(Math.floor(k * c.length / K), Math.floor((k + 1) * c.length / K)); };
        // try footprints from the scheduled group with every graph position, and keep the pairing
        // whose graph sits in the sky, clear of the beam, the footprint and its label, fairly near
        var all = slots(), best = null, bestScore = Infinity;
        var consider = function (t, extra, step) {
          var o = observation(key, t.i, t.j);
          if (!o) return;
          var tbx = tagBox(o), fpb = fpBox(o), base0 = extra;
          var kind = o.s.C < 0.15 ? "water" : (o.s.C < 0.85 ? "edge" : "ice");
          if (kind !== want) base0 += 150000;                                 // worth one group further
          if (tbx[3] > H - 6) base0 += 50000;
          base0 += 300 * overlap(tbx, L.credit);
          recent.forEach(function (r) {                                       // not where the last few were
            base0 += 250000 * Math.max(0, 1 - Math.hypot(o.X - r.X, o.Y - r.Y) / 240);
          });
          all.forEach(function (gg) {
            var bb = box(gg), sc = base0;
            sc += 20000 * beamHits(bb, o) + 40 * overlap(bb, tbx) + 60 * overlap(bb, fpb);
            sc += 30 * Math.max(0, bb[3] - L.hz) * (bb[2] - bb[0]);         // keep the graph in the sky
            sc += 300 * overlap(bb, L.credit);
            var dc = Math.hypot(0.5 * (bb[0] + bb[2]) - o.X, 0.5 * (bb[1] + bb[3]) - o.Y);
            sc += 30 * Math.max(0, dc - 260);                                 // keep the leader short
            sc += Math.random() * 400;
            if (sc < bestScore) { bestScore = sc; best = { o: o, g: gg, step: step }; }
          });
        };
        // the scheduled group is preferred; a later one in the cycle is used only when the
        // scheduled spot would crowd the graph, and the cycle resumes from it
        for (var st = 0; st < K; st++) {
          var gk = order[(sweep + st) % K];
          if (K > 2 && gk === lastGroup) continue;
          groupOf(gk).forEach(function (t) { consider(t, 120000 * st, st); });
        }
        if (best) {
          lastGroup = order[(sweep + best.step) % K]; sweep += best.step + 1;
          ob = best.o; g = best.g;
          recent = recent.concat([{ X: ob.X, Y: ob.Y }]).slice(-3);
        }
      }
    }
    // the truth in the footprint, or (stacked layout) a representative scene
    var s = ob ? ob.s : [{ C: 1, p: 0.3, lwp: 0.2 }, { C: 0, p: 0, lwp: 0.1 }, { C: 0.6, p: 0.1, lwp: 0.25 }, { C: 1, p: 0.05, lwp: 0.05 }][count % 4];
    var ch = CH[key], Tobs = ch.ir ? tbIR(s.lwp, 266 + 7 * Math.random()) + 0.2 * randn() : tb(ch, s.C, s.p, s.lwp) + 0.5 * randn();
    if (!g) g = wide ? { x0: L.R1 - L.pw, x1: L.R1, base: 30 + L.ph, top: 30 } : L.fixed;
    var like = likelihood(ch, Tobs, s), prior = makePrior(like), post = tempered(prior, like, 1);
    eps.push({ start: at, key: key, ch: ch, ob: ob, g: g, T: Tobs, prior: prior, like: like, mode: centre(like),
               ymax: ymaxOf(prior, like), cache: { b: -1 } });
    count++;
  }

  // --- drawing ----------------------------------------------------------------------------
  function sxOf(g) { return function (v) { return g.x0 + v * (g.x1 - g.x0); }; }
  function path(g, f, scale) {
    var sx = sxOf(g);
    ctx.beginPath();
    for (var i = 0; i < NC; i++) { var X = sx(CG[i]), Y = g.base - f[i] * scale; if (i === 0) ctx.moveTo(X, Y); else ctx.lineTo(X, Y); }
  }
  function curve(g, f, scale, col, a, fill, dash, width) {
    // a crisp line with a thin halo under it (no blur), so it reads over cloud, ice and water
    if (a <= 0.005) return;
    if (fill) {
      var sx = sxOf(g); path(g, f, scale);
      ctx.lineTo(sx(1), g.base); ctx.lineTo(sx(0), g.base); ctx.closePath();
      ctx.fillStyle = fill; ctx.fill();
    }
    path(g, f, scale);
    ctx.setLineDash(dash || []); ctx.lineJoin = "round"; ctx.lineCap = dash ? "butt" : "round";
    ctx.lineWidth = width + 3; ctx.strokeStyle = "rgba(" + HALO + "," + (0.7 * a) + ")"; ctx.stroke();
    ctx.lineWidth = width; ctx.strokeStyle = "rgba(" + col + "," + a + ")"; ctx.stroke(); ctx.setLineDash([]);
  }
  function text(str, x, y, col, a) {
    // text with a thin halo around each letter
    if (a <= 0.005) return;
    ctx.lineJoin = "round"; ctx.lineWidth = 3; ctx.strokeStyle = "rgba(" + HALO + "," + (0.75 * a) + ")";
    ctx.strokeText(str, x, y);
    ctx.fillStyle = "rgba(" + col + "," + a + ")"; ctx.fillText(str, x, y);
  }
  function tbLabel(T, X, Y, a, align, size) {
    // "T_b = 231 K" with a real subscript
    if (a <= 0.01) return;
    var big = "700 " + size + "px " + FONT, sub = "700 " + Math.round(size * 0.72) + "px " + FONT;
    var rest = " = " + Math.round(T) + " K";
    ctx.font = big; var wT = ctx.measureText("T").width, wR = ctx.measureText(rest).width;
    ctx.font = sub; var wb = ctx.measureText("b").width;
    var tot = wT + wb + wR, x = align === "right" ? X - tot : (align === "center" ? X - tot / 2 : X);
    ctx.textAlign = "left";
    ctx.font = big; text("T", x, Y, ACC, a);
    ctx.font = sub; text("b", x + wT, Y + 3, ACC, a);
    ctx.font = big; text(rest, x + wT + wb, Y, ACC, a);
  }
  function bright(e) { return Math.min(1, Math.max(0.08, (e.T - e.ch.lo) / (e.ch.hi - e.ch.lo))); }

  function path3(pts, close) {
    ctx.beginPath();
    pts.forEach(function (p, k) { if (k === 0) ctx.moveTo(p.X, p.Y); else ctx.lineTo(p.X, p.Y); });
    if (close) ctx.closePath();
  }
  function beam(o, A) {
    // the beam as a glowing translucent cylinder: brightest along its middle, where a sight line
    // crosses the most of it, and fading to nothing at its edges (as the path length through a
    // cylinder does); dimming as it rises. Drawn on its own layer: the across-the-beam profile is a
    // conic gradient about the vanishing point, and the along-the-beam fade a radial one
    var vp = L.vp, bc = beamCanvas, bx = beamCtx;
    bx.setTransform(1, 0, 0, 1, 0, 0); bx.clearRect(0, 0, bc.width, bc.height); bx.setTransform(L.dpr, 0, 0, L.dpr, 0, 0);
    var span = o.angR - o.angL, g;
    if (bx.createConicGradient) {
      g = bx.createConicGradient(o.angL, vp.X, vp.Y);
      for (var k = 0; k <= 16; k++) {
        var u = k / 16, x = 2 * u - 1;
        g.addColorStop(u * span / 6.2832, "rgba(" + GLOW + "," + (A * Math.pow(Math.max(0, 1 - x * x), 0.7)) + ")");
      }
      g.addColorStop(Math.min(1, span / 6.2832 + 1e-4), "rgba(" + GLOW + ",0)");
    } else {
      var p0 = o.near[0], p1 = o.near[o.near.length - 1];
      g = bx.createLinearGradient(p0.X, p0.Y, p1.X, p1.Y);
      g.addColorStop(0, "rgba(" + GLOW + ",0)"); g.addColorStop(0.5, "rgba(" + GLOW + "," + A + ")"); g.addColorStop(1, "rgba(" + GLOW + ",0)");
    }
    bx.fillStyle = g;
    bx.beginPath();
    o.near.forEach(function (p, k) { if (k === 0) bx.moveTo(p.X, p.Y); else bx.lineTo(p.X, p.Y); });
    bx.lineTo(vp.X, vp.Y); bx.closePath(); bx.fill();
    var Lc = exitLen(o.X, o.Y, o.ux, o.uy), f0 = Math.max(0, (o.Rb - Lc) / o.Rb);
    var rg = bx.createRadialGradient(vp.X, vp.Y, 0, vp.X, vp.Y, o.Rb);
    rg.addColorStop(0, "rgba(0,0,0,0)"); rg.addColorStop(f0, "rgba(0,0,0,0.5)"); rg.addColorStop(1, "rgba(0,0,0,1)");
    bx.globalCompositeOperation = "destination-in"; bx.fillStyle = rg; bx.fillRect(0, 0, W, H);
    bx.globalCompositeOperation = "source-over";
    ctx.drawImage(bc, 0, 0, W, H);
  }

  function measurement(e, T, dim, life) {
    // the footprint and its beam; brightness follows the measured T_b
    var o = e.ob, on = ease((T - 1.1) / 0.6);
    var a = (T < 2.6 ? 1 : 0.3 + 0.7 * (1 - ease((T - 2.6) / 2.4))) * life * dim;
    var af = ease((T - 0.3) / 0.5) * a, bv = bright(e);
    ctx.save();
    ctx.shadowBlur = 0; ctx.lineJoin = "round"; ctx.lineCap = "round";
    // light spilling onto the surface around the footprint
    var pool = footprint(o.P, o.ch, 2.4).map(function (g) { return proj3(g[0], g[1], 0); });
    var bb = [Infinity, Infinity, -Infinity, -Infinity];
    pool.forEach(function (p) { bb[0] = Math.min(bb[0], p.X); bb[1] = Math.min(bb[1], p.Y); bb[2] = Math.max(bb[2], p.X); bb[3] = Math.max(bb[3], p.Y); });
    var rw = (bb[2] - bb[0]) / 2, rh = Math.max(2, (bb[3] - bb[1]) / 2);
    ctx.save();
    ctx.translate((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2); ctx.scale(1, rh / rw);
    var pg = ctx.createRadialGradient(0, 0, 0, 0, 0, rw);
    pg.addColorStop(0, "rgba(" + GLOW + "," + (0.28 * af * bv) + ")"); pg.addColorStop(1, "rgba(" + GLOW + ",0)");
    ctx.fillStyle = pg; ctx.fillRect(-rw, -rw, 2 * rw, 2 * rw);
    ctx.restore();
    // the far rim of the footprint, seen through the beam
    path3(o.far, false);
    ctx.lineWidth = 1.2; ctx.strokeStyle = "rgba(" + LINE + "," + (0.5 * af) + ")"; ctx.stroke();
    // the beam
    if (on > 0) beam(o, 0.85 * on * a * (0.6 + 0.4 * bv));
    // the footprint: lit from within, with its near rim in front of the beam
    path3(o.fp, true);
    ctx.fillStyle = "rgba(" + GLOW + "," + (0.3 * af * bv) + ")"; ctx.fill();
    path3(o.near, false);
    ctx.shadowColor = "rgba(255,120,60," + (0.9 * af) + ")"; ctx.shadowBlur = 10;
    ctx.lineWidth = 2.2; ctx.strokeStyle = "rgba(" + LINE + "," + (0.95 * af) + ")"; ctx.stroke();
    ctx.restore();
  }

  function radiation(e, T, dim) {
    // radiance travelling up the beam (emitted by the surface and the air, not sent down to them),
    // drawn the textbook way: wavy red lines whose crests move up toward the satellite, as bright as
    // the measured radiance. Each line starts where that part of the signal comes from: at the
    // surface for 19 GHz; at the cloud for the infrared (an opaque cloud hides the surface); both
    // for 91 GHz, where cloud water dominates but the surface still shows through. Like the beam,
    // the lines run to the vanishing point, and their waves shrink with distance. The waves are
    // longest at 19 GHz and shortest in the infrared (none to scale). Drawn over everything else but
    // semi-transparent; they show while the measurement is taken and are gone well before the next
    // one starts (and stay put in the reduced-motion still)
    var on = ease((T - 1.1) / 0.6);
    if (on <= 0) return;
    var life = 1 - ease((T - (lifeSpan - FADE)) / FADE);
    var aw = reduce ? 0.8 * on * life : on * (1 - ease((T - 3.4) / 2)) * life * dim;
    if (aw < 0.01) return;
    var o = e.ob, vp = L.vp, cloudy = o.s.lwp > 0.02;
    var lam = e.ch.lam, kw = 6.2832 / lam, amp = Math.min(4, Math.max(2, 0.12 * lam)), om = reduce ? 0 : 55 * kw;
    var al = 0.75 * aw * (0.5 + 0.5 * bright(e));
    ctx.save();
    ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.lineWidth = 1.7;
    ctx.shadowColor = "rgba(255,50,40," + (0.35 * aw) + ")"; ctx.shadowBlur = 5;
    var fromCloud = cloudy && e.ch.from.some(function (f) { return f; });
    o.feet.forEach(function (ft, j) {
      var b0 = ft.base, dx = vp.X - b0.X, dy = vp.Y - b0.Y, Dv = Math.hypot(dx, dy);
      dx /= Dv; dy /= Dv;
      var nx = -dy, ny = dx, len = 0.9 * exitLen(b0.X, b0.Y, dx, dy);
      var d0 = cloudy && e.ch.from[j] ? Math.hypot(ft.cloud.X - b0.X, ft.cloud.Y - b0.Y) : 0;
      var lg = ctx.createLinearGradient(b0.X + dx * d0, b0.Y + dy * d0, b0.X + dx * len, b0.Y + dy * len);
      lg.addColorStop(0, "rgba(" + RED + ",0)"); lg.addColorStop(0.06, "rgba(" + RED + "," + al + ")");
      lg.addColorStop(0.65, "rgba(" + RED + "," + al + ")"); lg.addColorStop(1, "rgba(" + RED + ",0)");
      ctx.strokeStyle = lg; ctx.beginPath();
      for (var d = d0; d <= len; d += 2) {
        var w = amp * (1 - d / Dv) * Math.sin(kw * d - om * (T - 1.1) - 2.1 * j);
        var x = b0.X + dx * d + nx * w, y = b0.Y + dy * d + ny * w;
        if (d === d0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    });
    // where the beam meets the cloud: a faint ring around it, its cross-section at that height
    if (fromCloud) {
      ctx.shadowBlur = 8; ctx.shadowColor = "rgba(255,120,60," + (0.8 * aw) + ")";
      path3(o.ring, true);
      ctx.setLineDash([4, 3]); ctx.lineWidth = 1.6; ctx.strokeStyle = "rgba(" + LINE + "," + (0.9 * aw) + ")"; ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.restore();
  }

  function drawEpisode(e, T, dim, nw) {
    // T: seconds since this update started
    var g = e.g, sx = sxOf(g);
    var life = 1 - ease((T - (lifeSpan - FADE)) / FADE);
    var a = ease(T / 1.0) * life * dim;          // overall opacity
    var aObs = ease((T - 1.8) / 0.5) * life * dim, travel = ease((T - 2.1) / 1.0);
    var aLike = ease((T - 3.0) / 0.9) * life * dim;
    var b = ease((T - 4.2) / 5.0);
    var h = (g.base - g.top) * 0.92, scale = h / e.ymax, fs = 13;

    if (e.ob) measurement(e, T, dim, life);

    // axis
    ctx.lineCap = "butt";
    ctx.beginPath(); ctx.moveTo(sx(0), g.base); ctx.lineTo(sx(1), g.base);
    [0, 0.5, 1].forEach(function (k) { ctx.moveTo(sx(k), g.base); ctx.lineTo(sx(k), g.base + 5); });
    ctx.lineWidth = 4.2; ctx.strokeStyle = "rgba(" + HALO + "," + (0.7 * a) + ")"; ctx.stroke();
    ctx.lineWidth = 1.4; ctx.strokeStyle = "rgba(" + INK + "," + (0.9 * a) + ")"; ctx.stroke();
    ctx.font = "600 13px " + FONT; ctx.textAlign = "center";
    var va = VAR[e.ch.v];
    [0, 0.5, 1].forEach(function (k, n) { text(va.ticks[n], sx(k), g.base + 20, INK, a); });
    if (nw > 0.01) text(va.title, (sx(0) + sx(1)) / 2, g.base + 36, INK, a * nw);

    // the measurement: channel and T_b under the footprint, carried to the likelihood
    if (aObs > 0 && e.ob) {
      var X = e.ob.X, Y = e.ob.bottom + 18;
      ctx.font = "600 " + (fs - 1) + "px " + FONT; ctx.textAlign = "center";
      text(e.ch.name, X, Y, INK, aObs);
      tbLabel(e.T, X, Y + 16, aObs, "center", fs);
      var ox = sx(e.mode), sxp = X, syp = Y + 22, cx = (sxp + ox) / 2, cy = Math.max(syp, g.base) + 30;
      if (g.base < Y) { syp = e.ob.top - 4; cy = (syp + g.base) / 2; }
      ctx.beginPath();
      var steps = 40, n = Math.round(steps * travel);
      for (var k = 0; k <= n; k++) {
        var u = k / steps, qx = (1 - u) * (1 - u) * sxp + 2 * u * (1 - u) * cx + u * u * ox;
        var qy = (1 - u) * (1 - u) * syp + 2 * u * (1 - u) * cy + u * u * (g.base + 2);
        if (k === 0) ctx.moveTo(qx, qy); else ctx.lineTo(qx, qy);
      }
      ctx.setLineDash([3, 4]);
      ctx.lineWidth = 3.4; ctx.strokeStyle = "rgba(" + HALO + "," + (0.5 * aObs) + ")"; ctx.stroke();
      ctx.lineWidth = 1.3; ctx.strokeStyle = "rgba(" + ACC + "," + (0.9 * aObs) + ")"; ctx.stroke();
      ctx.setLineDash([]);
    } else if (aObs > 0 && !wide) {
      // the stacked layout shows no footprint: name the channel above the graph instead
      ctx.font = "600 " + (fs - 1) + "px " + FONT; ctx.textAlign = "left";
      text(e.ch.name, g.x0, g.top - 8, INK, 0.9 * aObs);
    }

    // likelihood
    if (aLike > 0) curve(g, e.like, h * 0.8, ACC, aLike, null, [7, 4], 2);

    // prior (ghost once the update starts) and the tempered density
    if (b > 0) curve(g, e.prior, scale, INK, 0.5 * a, null, [2, 4], 1.4);
    var f;
    if (b <= 0) f = e.prior;
    else if (Math.abs(b - e.cache.b) < 1e-4) f = e.cache.f;
    else { f = tempered(e.prior, e.like, b); e.cache = { b: b, f: f }; }
    curve(g, f, scale, INK, a, "rgba(" + HALO + "," + (0.22 * a) + ")", null, 2.4);
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    // no panel behind the graph: every line and label carries its own thin halo instead
    for (var i = 0; i < eps.length; i++) drawEpisode(eps[i], now - eps[i].start, 1, 1);
    ctx.restore();
    // the radiation goes on top
    for (var j = 0; j < eps.length; j++) if (eps[j].ob) radiation(eps[j], now - eps[j].start, 1);
  }

  function frame(ts) {
    if (!running) return;
    var d = last ? Math.min(0.05, (ts - last) / 1000) : 0; last = ts;
    now += d;
    if (now >= nextSpawn) { spawn(nextSpawn); nextSpawn += every; }
    eps = eps.filter(function (e) { return now - e.start < lifeSpan; });
    draw();
    window.requestAnimationFrame(frame);
  }
  function start() { if (!running && !reduce) { running = true; last = 0; window.requestAnimationFrame(frame); } }
  function stop() { running = false; }

  function reset() {
    layout(); eps = []; count = 0; sweep = Math.floor(5 * Math.random()); lastGroup = -1; recent = [];
    if (reduce) {
      // a still picture: one update at its posterior, with its beam
      now = DONE + 0.1; spawn(0);
    } else { now = 0; nextSpawn = 0; }
    draw();
  }

  reset();
  if (!reduce) {
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { es[0].isIntersecting ? start() : stop(); }).observe(hero);
    } else start();
  }
  var rt;
  window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(reset, 150); });
})();
