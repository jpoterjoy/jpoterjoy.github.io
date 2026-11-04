#!/usr/bin/env python3
"""Build poterjoy.com from the LaTeX CV and a few hand-written content files.

Usage:
    python3 build.py                      # reads ../CV-latex/CV.tex and CV.pdf
    python3 build.py --cv /path/to/CV.tex # use a different CV source

Output goes to docs/, which GitHub Pages serves as the website.
Only the Python standard library is required.
"""
import argparse
import datetime as dt
import html
import os
import re
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "docs")
DOMAIN = "poterjoy.com"
NAME = "Jonathan Poterjoy"
EMAIL = "poterjoy@umd.edu"
TODAY = dt.date.today()

# Scholarly profiles, linked from the profile card and footer and given to search engines.
SCHOLAR = "https://scholar.google.com/citations?user=hd_ZciIAAAAJ"
ORCID = "https://orcid.org/0000-0003-3927-4642"
GITHUB = "https://github.com/jpoterjoy"

# Old WordPress addresses that should forward to their new pages (path -> page).
REDIRECTS = {
    "publications/": "publications.html",
    "2022/03/10/the-journey-begins/": "",
}

# Third-party coverage, shown in an "In the news" section on the About page when this list is
# not empty: (date, outlet, headline, url). Left empty for now.
NEWS = []

NAV = [
    ("index.html", "Home"),
    ("about.html", "About"),
    ("research.html", "Research"),
    ("publications.html", "Publications"),
    ("software.html", "Software"),
    ("talks.html", "Talks"),
    ("group.html", "Group"),
    ("teaching.html", "Teaching"),
]

# Which research theme each article belongs to, by DOI (an article can sit under more than
# one). Articles not listed here are placed by THEME_KEYWORDS, matched against the title,
# so most new papers sort themselves; add a DOI here only to override that.
PAPER_THEMES = {
    "global": ["10.1175/MWR-D-21-0228.1", "10.1002/qj.4328", "10.1175/MWR-D-15-0163.1",
               "10.1175/MWR-D-15-0322.1"],
    "mesoscale": ["10.1175/MWR-D-16-0298.1", "10.1175/MWR-D-17-0344.1", "10.1175/MWR-D-22-0260.1",
                  "10.1175/WAF-D-24-0089.1", "10.1175/MWR-D-22-0281.1", "10.1175/MWR-D-21-0228.1"],
    "hurricanes": ["10.1175/MWR-D-25-0200.1", "10.1175/WAF-D-24-0147.1", "10.1175/WAF-D-23-0027.1",
                   "10.1175/WAF-D-20-0204.1", "10.1175/MWR-D-15-0116.1", "10.1175/MWR-D-14-00224.1",
                   "10.1175/MWR-D-13-00394.1", "10.1175/JAS-D-13-0291.1", "10.1175/MWR-D-13-00305.1",
                   "10.1175/MWR-D-12-00188.1", "10.1175/2011JAS3681.1"],
    "polar": ["10.5194/tc-19-5423-2025", "10.31223/X5SN37", "10.1175/BAMS-D-25-0098.1"],
    "methods": ["10.1175/MWR-D-24-0242.1", "10.1175/MWR-D-22-0298.1", "10.1175/MWR-D-22-0108.1",
                "10.1002/qj.4328", "10.1175/MWR-D-20-0368.1", "10.1175/MWR-D-19-0368.1",
                "10.1175/MWR-D-17-0344.1", "10.1002/qj.3256", "10.1175/MWR-D-15-0163.1",
                "10.1175/MWR-D-15-0322.1"],
    # listed here only so that the title keywords below do not place them under a theme
    "unlisted": ["10.1175/WAF-D-21-0069.1", "10.1175/WAF-D-21-0165.1"],
}
THEME_KEYWORDS = {
    "polar": r"sea ice|ice sheet|arctic|antarctic|polar|glacier",
    "hurricanes": r"hurricane|tropical cyclone|typhoon|HWRF|HAFS",
    "mesoscale": r"convect|mesonet|squall|storm-scale|radar|severe",
    "global": r"global",
    "methods": r"observation error|observation uncertainty|likelihood|measurement operator|particle filter|particle smoother",
}
PAPERS_PER_THEME = 4

# CV service entries left off the About page (they stay on the CV). Matched against the text.
ABOUT_SKIP = [
    r"Curriculum Committee",          # AOSC graduate and undergraduate curriculum committees
    r"Graduate Admissions Committee",
    r"AGU Bridge Program",
    r"Burgers Program",
    r"IWTC-8",
]

# CV entries shown as one combined item on the About page: (pattern, combined text). The
# dates of the matching entries are listed together.
ABOUT_MERGE = [
    (r"Program Committee Member, \d+th EnKF Data Assimilation Workshop",
     "Program Committee Member, 7th and 8th EnKF Data Assimilation Workshops, "
     "State College, PA, and Sainte-Adèle, QC, Canada"),
]

# One line per current Ph.D. student, shown on the Group page under their name. Keyed by the
# name as it appears in the CV; update when a topic changes (the build lists anyone missing).
STUDENT_TOPICS = {
    "Maria Nikolaitchik": "Comparing how particle filters and ensemble Kalman filters shape uncertainty in NOAA's "
                          "global model using singular vectors, and bringing data assimilation to machine "
                          "learning models of the atmosphere.",
    "Leah White": "Expanding small ensembles with statistically generated members so particle filters "
                  "stay accurate at low cost, starting with low-order models (with J. Chan, Ohio State "
                  "University).",
    "Quentin Simmons": "Developing data assimilation capabilities for estimating and monitoring carbon fluxes "
                       "in NASA's GEOS model, with carbon cycle scientists at Goddard's Global Modeling and "
                       "Assimilation Office.",
    "Dylan Major": "Testing hourly cycled Bayesian data assimilation with the local particle filter in "
                   "NOAA's global Unified Forecast System, toward more frequently updated forecasts and "
                   "reanalyses.",
    "Hee-Sung Jung": "Constraining atmospheric forcing errors for sea ice data assimilation, and developing "
                     "methods to assimilate far-infrared radiances from NASA's PREFIRE mission over Arctic "
                     "sea ice.",
    "Raelynn Wonnacott": "Learning likelihoods with generative machine learning, including marginalized "
                         "likelihoods that stabilize ensemble data assimilation when observations depend "
                         "on small-scale processes that small ensembles sample poorly.",
    "Alvin Cheung": "Predicting hurricane intensity forecast uncertainty in NOAA's HAFS with machine "
                    "learning, informed by rapid intensity changes and satellite precipitation structure "
                    "(with the Naval Research Laboratory).",
    "Gabrielle Linscott": "Quantifying how atmospheric rivers shape snowfall, snow depth, and mass balance on "
                          "Antarctic sea ice, how their role is changing, and the circulation patterns behind "
                          "their impacts.",
    "Sarah Loughran": "Retrieving winds in the atmospheres of Neptune and other planets in our solar system "
                      "with a multi-incremental 3DVar framework (with NASA Goddard's Planetary Systems "
                      "Laboratory).",
    "Henry Santer": "Developing fully non-parametric data assimilation with learned likelihoods, using "
                    "manifold learning and kernel embeddings to assimilate sea ice concentration "
                    "without explicit measurement operators.",
}

# Topics the group is known for, in the words people search with. Shown on the About page
# and given to search engines in the page metadata.
EXPERTISE = [
    "Data assimilation",
    "Ensemble data assimilation and ensemble Kalman filters",
    "Particle filters and non-Gaussian (Bayesian) data assimilation",
    "Hybrid ensemble-variational data assimilation (EnVar, 4DEnVar, 4DVar)",
    "Numerical weather prediction: global, regional, and convection-allowing models",
    "Hurricane and tropical cyclone data assimilation and prediction",
    "Radar and satellite radiance data assimilation",
    "Sea ice and polar data assimilation",
    "Uncertainty quantification and observation error estimation",
    "Machine learning for data assimilation: kernel methods and generative models",
    "Observing system simulation experiments (OSSEs) and observing system design",
    "NOAA Unified Forecast System (UFS), GFS, and HAFS; JEDI; NSF NCAR DART; WRF",
]


# --------------------------------------------------------------------------
# LaTeX helpers
# --------------------------------------------------------------------------

def strip_comments(tex):
    return re.sub(r"(?<!\\)%.*", "", tex)


def read_group(s, i):
    """Return (content, end_index) of the balanced {...} group starting at s[i]."""
    assert s[i] == "{", s[i:i + 30]
    depth = 0
    for j in range(i, len(s)):
        c = s[j]
        if c == "\\":
            continue
        if c == "{" and (j == 0 or s[j - 1] != "\\"):
            depth += 1
        elif c == "}" and s[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    raise ValueError("unbalanced braces near: " + s[i:i + 60])


def read_args(s, i, n):
    """Read n brace groups starting at index i (skipping whitespace)."""
    args = []
    for _ in range(n):
        while s[i].isspace():
            i += 1
        a, i = read_group(s, i)
        args.append(a)
    return args, i


def find_macro(s, name, n):
    """Yield (args, start, end) for every \\name{..}x n in s."""
    pat = re.compile(r"\\" + name + r"(?![A-Za-z])")
    pos = 0
    while True:
        m = pat.search(s, pos)
        if not m:
            return
        try:
            args, end = read_args(s, m.end(), n)
        except (AssertionError, IndexError):
            pos = m.end()
            continue
        yield args, m.start(), end
        pos = end


def sub_macro(s, name, n, fn):
    out, pos = [], 0
    for args, a, b in list(find_macro(s, name, n)):
        out.append(s[pos:a])
        out.append(fn(*args))
        pos = b
    out.append(s[pos:])
    return "".join(out)


ACCENTS = {
    r"\'{\i}": "í", r"\'\i": "í", r"\'{e}": "é", r"\'e": "é", r"\'{a}": "á", r"\'a": "á",
    r"\'{o}": "ó", r"\'o": "ó", r"\'{u}": "ú", r"\'u": "ú", r"\`{e}": "è", r"\`e": "è",
    r"\`{a}": "à", r"\`a": "à", r"\^{o}": "ô", r"\^o": "ô", r"\^{e}": "ê", r"\^e": "ê",
    r'\"{u}': "ü", r'\"u': "ü", r'\"{o}': "ö", r'\"o': "ö", r"\c{c}": "ç", r"\~{n}": "ñ",
    r"{\o}": "ø", r"\o{}": "ø", r"\o ": "ø", r"\ss{}": "ß",
}


def tex2html(s):
    s = strip_comments(s)
    s = s.replace("\\\\", " ")
    for k, v in ACCENTS.items():
        s = s.replace(k, v)
    s = re.sub(r"\\o(?![A-Za-z])", "ø", s)
    s = html.escape(s, quote=False)
    s = s.replace(r"\&amp;", "&amp;").replace(r"\%", "%").replace(r"\_", "_").replace(r"\$", "$")
    # links first so that their contents are left untouched
    s = sub_macro(s, "doi", 1, lambda d: '<a class="doi" href="https://doi.org/%s">doi</a>' % d.strip())
    s = sub_macro(s, "url", 1, lambda u: '<a href="%s">%s</a>' % (u, u))
    s = s.replace(r"\mefirst", '<span class="me">Poterjoy, J.</span>')
    s = re.sub(r"\\me(?![A-Za-z])", '<span class="me">J.&nbsp;Poterjoy</span>', s)
    s = sub_macro(s, "jrnl", 1, lambda x: "<em>%s</em>" % x)
    s = sub_macro(s, "vol", 1, lambda x: "<b>%s</b>" % x)
    for mac in ("textit", "emph"):
        s = sub_macro(s, mac, 1, lambda x: "<em>%s</em>" % x)
    s = sub_macro(s, "textbf", 1, lambda x: "<strong>%s</strong>" % x)
    s = sub_macro(s, "textsuperscript", 1, lambda x: "<sup>%s</sup>" % x)
    for mac in ("textmd", "mbox", "textrm", "textnormal"):
        s = sub_macro(s, mac, 1, lambda x: x)
    s = sub_macro(s, "coadv", 1, lambda x: " · co-advised with %s" % x)
    s = sub_macro(s, "advnote", 1, lambda x: " · %s" % x)
    s = s.replace(r"\present", "present").replace(r"\ ", " ")
    s = s.replace("---", "—").replace("--", "–")
    s = s.replace("``", "“").replace("''", "”").replace("`", "‘")
    s = re.sub(r"(?<=\w)'(?=\w)", "’", s)
    s = re.sub(r"(?<!:)~", "&nbsp;", s)
    s = re.sub(r"\\[A-Za-z]+\*?", "", s)          # drop any remaining macros
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def pub_html(raw):
    """Reference text with the DOI moved to a trailing link."""
    h = tex2html(raw)
    return re.sub(r',\s*(<a class="doi" [^>]*>)doi</a>\.?\s*$', r'. \1DOI&nbsp;↗</a>', h)


def block(tex, start_pat, end_pats=(r"\\subsection\{", r"\\section\{")):
    m = re.search(start_pat, tex)
    if not m:
        return ""
    rest = tex[m.end():]
    ends = [mm.start() for p in end_pats for mm in [re.search(p, rest)] if mm]
    return rest[:min(ends)] if ends else rest


def items(env_text, with_year=False):
    parts = re.split(r"\\item(?=[\s\[])", env_text)[1:]
    out = []
    for p in parts:
        p = re.sub(r"\\end\{[a-z]+\}.*", "", p, flags=re.S)
        if with_year:
            m = re.match(r"\s*\[([^\]]*)\]\s*(.*)", p, flags=re.S)
            out.append((m.group(1).strip(), m.group(2).strip()))
        else:
            out.append(p.strip())
    return out


# --------------------------------------------------------------------------
# Parse the CV
# --------------------------------------------------------------------------

def parse_cv(path):
    tex = strip_comments(open(path, encoding="utf-8").read())
    body = tex[tex.index(r"\begin{document}"):]
    cv = {}

    # Journal articles (reverse-chronological in the CV)
    jb = block(body, r"\\subsection\{Peer-Reviewed Journal Articles\}")
    arts = []
    for raw in items(jb):
        ym = re.search(r",\s*((?:19|20)\d\d)[a-z]?:", raw)
        arts.append(dict(paper_meta(raw), **{
            "html": pub_html(raw),
            "year": int(ym.group(1)) if ym else 0,
            "advisee": "*" in raw.lstrip().split(",")[0],
            "first": raw.lstrip().startswith(r"\mefirst"),
        }))
    cv["articles"] = arts
    cv["chapters"] = [pub_html(x) for x in items(block(body, r"\\subsection\{Invited Book Chapters\}"))]
    pre_raw = items(block(body, r"\\subsection\{Preprints\}"))
    cv["preprints"] = [pub_html(x) for x in pre_raw]
    cv["preprint_meta"] = [dict(paper_meta(x), preprint=True) for x in pre_raw]
    add_letters(cv["articles"] + cv["preprint_meta"])
    for p in cv["articles"]:          # show 2022a/2022b in the lists too, to match citations
        if p.get("letter"):
            p["html"] = re.sub(r",\s*%d:" % p["year"], ", %d%s:" % (p["year"], p["letter"]), p["html"], count=1)
    groups = {}                       # and list each "a" before its "b", in the slots they share
    for i, p in enumerate(arts):
        if p.get("letter"):
            groups.setdefault((p["cite"], p["yr"]), []).append(i)
    for idx in groups.values():
        for i, p in zip(idx, sorted((arts[i] for i in idx), key=lambda q: q["letter"])):
            arts[i] = p

    # Talks
    cv["talks"] = []
    for title in ("Conferences and Workshops", "Seminars and Lectures", "Summer Schools and Training Workshops"):
        b = block(body, r"\\subsection\{" + re.escape(title) + r"\}")
        cv["talks"].append((title, [(y, tex2html(t)) for y, t in items(b, with_year=True)]))

    # Grants
    gb = block(body, r"\\subsection\{Funded Grants\}")
    grants = []
    for (agency, role, dates, title, details), _, _ in find_macro(gb, "grant", 5):
        end = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", dates)
        end_date = dt.date(int(end[-1][2]), int(end[-1][0]), int(end[-1][1])) if end else None
        grants.append({"agency": tex2html(agency), "role": tex2html(role), "dates": dates,
                       "years": "–".join(sorted({e[2] for e in end})) if end else "",
                       "title": tex2html(title), "end": end_date})
    cv["grants"] = grants

    # Teaching
    tb = block(body, r"\\section\{Teaching\}", (r"\\section\{",))
    teach = []
    for (title, dates, rest), _, _ in find_macro(tb, "entry", 3):
        inst = rest.split(r"\begin{itemize}")[0]
        bullets = items(rest.split(r"\begin{itemize}")[1]) if r"\begin{itemize}" in rest else []
        teach.append({"title": tex2html(title), "dates": tex2html(dates),
                      "inst": tex2html(inst), "bullets": [tex2html(b) for b in bullets]})
    cv["teaching"] = teach

    # Advising
    adv = {}
    for sub in ("Postdoctoral Researchers", "Ph.D. Students", "M.S. Students", "Undergraduate Research"):
        b = block(body, r"\\subsection\{" + re.escape(sub) + r"\}")
        status, people = "Completed" if sub != "Postdoctoral Researchers" else "Postdoc", []
        tokens = re.finditer(r"\\sublabel\{(\w+)\}|\\advisee(?![A-Za-z])", b)
        for t in tokens:
            if t.group(1):
                status = t.group(1)
                continue
            args, _ = read_args(b, t.end(), 3)
            name_raw = args[0]
            note = ""
            for mac in ("coadv", "advnote"):
                for (x,), a, e in find_macro(name_raw, mac, 1):
                    note = ("co-advised with " + tex2html(x)) if mac == "coadv" else tex2html(x)
                name_raw = sub_macro(name_raw, mac, 1, lambda x: "")
            people.append({"name": tex2html(name_raw), "dates": tex2html(args[1]),
                           "thesis": tex2html(args[2]), "note": note, "status": status})
        adv[sub] = people
    cv["advising"] = adv

    # Honors, service, education and appointments (for the About page)
    def dated(pat):
        return [(tex2html(a), tex2html(b)) for (a, b), _, _ in find_macro(block(body, pat), "dated", 2)]
    def entries(pat):
        return [(tex2html(a), tex2html(b), tex2html(c)) for (a, b, c), _, _ in find_macro(block(body, pat), "entry", 3)]
    cv["honors"] = dated(r"\\section\{Honors and Awards\}")
    cv["advisee_awards"] = dated(r"\\subsection\{Awards Received by Advisees\}")
    cv["editorial"] = dated(r"\\subsection\{Editorial Service\}")
    cv["meetings"] = dated(r"\\subsection\{Meeting Organization\}")
    cv["committees"] = dated(r"\\subsection\{Committees, Boards, and Panels\}")
    cv["service"] = dated(r"\\section\{University and Department Service\}")
    cv["education"] = entries(r"\\section\{Education\}")
    cv["appointments"] = entries(r"\\section\{Appointments\}")
    return cv


def paper_meta(raw):
    """Short citation ("McCurry et al."), year, title, journal and DOI of a CV reference."""
    m = re.search(r",\s*((?:19|20)\d\d)[a-z]?:\s*", raw)
    if not m:
        return {"cite": "", "title": "", "journal": "", "doi": None}
    auth = raw[:m.start()].replace(r"\mefirst", "Poterjoy, J.").replace(r"\me", "J.~Poterjoy")
    auth = html.unescape(re.sub(r"<[^>]+>", "", tex2html(auth))).replace("*", "").replace("\xa0", " ")
    first, rest = auth.split(",", 1)
    rest = re.sub(r"^\s*(?:[A-Z][a-z]?\.[\s\-–]*)+", "", rest)          # the first author's initials
    others = [x for x in re.split(r",\s*(?:and\s+)?|\s*\band\s+", rest) if x.strip()]
    first = first.strip()
    cite = first if not others else (f"{first} and {others[0].strip().split(' ')[-1]}"
                                     if len(others) == 1 else f"{first} et al.")
    tail = raw[m.end():]
    tm = re.match(r"(.*?)\.\s*\\jrnl\{([^}]*)\}", tail, flags=re.S)
    dm = re.search(r"\\doi\{([^}]*)\}", raw)
    return {"cite": cite, "title": tex2html(tm.group(1)) if tm else "",
            "journal": tex2html(tm.group(2)) if tm else "", "doi": dm.group(1).strip() if dm else None,
            "yr": int(m.group(1))}


def add_letters(papers):
    """AMS-style 2022a/2022b for papers with the same authors and year (ordered by title)."""
    groups = {}
    for p in papers:
        groups.setdefault((p["cite"], p.get("yr")), []).append(p)
    for g in groups.values():
        for i, p in enumerate(sorted(g, key=lambda q: q["title"])):
            p["letter"] = "abcdefgh"[i] if len(g) > 1 else ""


def theme_papers(cv, theme):
    out = []
    for p in cv["articles"] + cv["preprint_meta"]:
        listed = [t for t, dois in PAPER_THEMES.items() if p["doi"] in dois]
        if listed:
            hit = theme in listed
        else:
            hit = bool(re.search(THEME_KEYWORDS[theme], p["title"], flags=re.I))
        if hit:
            out.append(p)
    return sorted(out, key=lambda p: -p["yr"])[:PAPERS_PER_THEME]


def papers_block(cv, theme):
    """One line of linked citations; the full title shows on hover."""
    links = []
    for p in theme_papers(cv, theme):
        label = f'{p["cite"]} {p["yr"]}{p["letter"]}'
        tip = html.escape(html.unescape(re.sub(r"<[^>]+>", "", p["title"])), quote=True)
        links.append(f'<a href="https://doi.org/{p["doi"]}" title="{tip}">{label}</a>' if p["doi"] else label)
    if not links:
        return ""
    return ('  <div class="papers"><h3>Recent papers</h3> '
            + ' <span aria-hidden="true">·</span> '.join(links) + '</div>')


# --------------------------------------------------------------------------
# Page templates
# --------------------------------------------------------------------------

def page(filename, title, body, description, head_extra=""):
    nav = "\n".join(
        '        <a href="%s"%s>%s</a>' % (href, ' aria-current="page"' if href == filename else "", label)
        for href, label in NAV)
    full_title = (f"{NAME} · Data Assimilation and Weather Prediction · University of Maryland"
                  if filename == "index.html" else "%s · %s" % (title, NAME))
    url = f"https://{DOMAIN}/{'' if filename == 'index.html' else filename}"
    if filename == "404.html":        # served at any missing address, so never indexed
        head_extra += '\n  <meta name="robots" content="noindex">'
    out = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{full_title}</title>
  <meta name="description" content="{html.escape(description)}">
  <meta property="og:title" content="{full_title}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="https://{DOMAIN}/assets/img/og-banner.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Melt-ponded sea ice and an open lead under cloud in the Canada Basin, Arctic Ocean">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="canonical" href="{url}">
  <link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
  <link rel="preload" href="assets/fonts/XCharter-Roman.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="assets/css/site.css">{head_extra}
</head>
<body>
  <a class="skip" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="wrap">
      <a class="brand" href="index.html">
        <span class="brand-name">{NAME}</span>
        <span class="brand-sub">Data Assimilation · University of Maryland</span>
      </a>
      <button class="menu-btn" aria-expanded="false" aria-controls="site-nav">Menu</button>
      <nav class="nav" id="site-nav" aria-label="Main">
{nav}
        <a class="nav-cv" href="cv.pdf">CV</a>
      </nav>
    </div>
  </header>
  <main id="main">
{body}
  </main>
  <footer class="site-footer">
    <div class="wrap">
      <div>
        <h2>{NAME}</h2>
        Department of Atmospheric and Oceanic Science<br>
        University of Maryland<br>
        4254 Stadium Drive, 3431 Atlantic Building<br>
        College Park, MD 20742
      </div>
      <div>
        <h2>Contact</h2>
        <a href="mailto:{EMAIL}">{EMAIL}</a><br>
        <a href="cv.pdf">Curriculum vitae (PDF)</a>
      </div>
      <div>
        <h2>Elsewhere</h2>
        <a href="{SCHOLAR}">Google Scholar</a> · <a href="{ORCID}">ORCID</a> · <a href="{GITHUB}">GitHub</a><br>
        <a href="https://aosc.umd.edu/">UMD Atmospheric &amp; Oceanic Science</a><br>
        <a href="https://ucadre.org/">CADRE data assimilation consortium</a><br>
        <span class="small">Updated {TODAY.strftime('%B %Y')}</span>
      </div>
    </div>
  </footer>
  <script src="assets/js/site.js" defer></script>
</body>
</html>
"""
    if filename == "404.html":
        # GitHub Pages shows this page at any missing address (e.g. /old/page/), so its links
        # must start from the site root; it also gets no canonical or og:url of its own.
        out = re.sub(r'\n  <(?:link rel="canonical"|meta property="og:url")[^>]*>', "", out)
        out = re.sub(r'(href|src)="(?!https?:|mailto:|#|/)', r'\1="/', out)
    return out


def page_head(title, intro=""):
    p = f"\n      <p>{intro}</p>" if intro else ""
    return f"""    <section class="page-head">
      <div class="wrap">
        <h1>{title}</h1>{p}
      </div>
    </section>"""


def content(name):
    txt = open(os.path.join(ROOT, "content", name), encoding="utf-8").read()
    return re.sub(r"<!--.*?-->\s*", "", txt, flags=re.S).strip()


def short_authors(h, keep=8):
    """For the home page: a long author list is cut after the last of the first few authors
    that includes J. Poterjoy, and the rest are counted (AMS lists up to eight in full)."""
    m = re.search(r",\s*(?:19|20)\d\d[a-z]?:", h)
    if not m:
        return h
    names = re.split(r",\s*(?:and\s+)?", h[:m.start()])
    names = [names[0] + ", " + names[1]] + names[2:]   # first author is "Last, F."
    if len(names) <= keep:
        return h
    me = next((i for i, x in enumerate(names) if 'class="me"' in x), 0)
    shown = names[:max(3, me + 1)]
    return ", ".join(shown) + f", and {len(names) - len(shown)} coauthors" + h[m.start():]


def pub_li(p, n, tag=True):
    kind = ["all"] + (["advisee"] if p["advisee"] else []) + (["first"] if p["first"] else [])
    tag = '<span class="tag">Advisee-led</span>' if p["advisee"] and tag else ""
    return f'<li data-n="{n}" data-kind="{" ".join(kind)}">{p["html"]}{tag}</li>'


THEMES = [
    ("methods", "research/card-methods.webp", "New data assimilation methodology",
     "The local particle filter, learned likelihood functions, and estimates of observation uncertainty."),
    ("global", "research/card-nongaussian.webp", "Particle filters for global prediction",
     "Testing the local particle filter in NOAA's global forecast system and bringing it into JEDI."),
    ("mesoscale", "research/card-observations.webp", "Mesoscale weather prediction",
     "Particle filters for thunderstorms, radar assimilation, and mesoscale ensembles and observing networks."),
    ("hurricanes", "research/card-hurricanes.webp", "Hurricanes and high-impact weather",
     "Cycling data assimilation, radiance bias correction, and particle filters for NOAA's hurricane models."),
    ("polar", "research/card-polar.webp", "Sea ice and polar prediction",
     "Learned likelihoods and particle filters for sea ice, PREFIRE radiances, and ice sheet observing experiments."),
]


def build_home(cv):
    recent = cv["articles"][:5]
    n_total = len(cv["articles"])
    n_students = sum(p["status"] == "Current" for p in cv["advising"]["Ph.D. Students"])
    # on the home page an advisee's paper is marked only by the asterisk on their name
    pubs = "\n".join(pub_li(dict(p, html=short_authors(p["html"])), n_total - i, tag=False) for i, p in enumerate(recent))
    cards = "\n".join(f"""          <a class="theme-card" href="research.html#{a}">
            <div class="art"><img src="assets/img/{img}" width="640" height="480" alt="" loading="lazy"></div>
            <div class="txt"><h3>{t}</h3><p>{d}</p></div>
          </a>""" for a, img, t, d in THEMES)
    body = f"""    <section class="hero">
      <canvas id="bayes" aria-hidden="true"></canvas>
      <div class="credit"><a href="research.html#polar"><span class="long">Animation: simulated SSMIS and VIIRS radiances updating forecasts of sea ice and cloud (not to scale)</span><span class="short">Animation: satellite radiances updating sea ice and cloud</span></a> · <a href="https://commons.wikimedia.org/wiki/File:Arctic_Sky_(4371010590).jpg" title="Taken from USCGC Healy during the 2009 U.S.–Canada extended continental shelf survey, 19 August 2009. Photo by Petty Officer 3rd Class Patrick Kelley, U.S. Coast Guard (public domain)."><span class="long">Photo: melt-ponded sea ice, Canada Basin, Aug. 2009 (U.S. Coast Guard)</span><span class="short">Photo: Canada Basin sea ice, Aug 2009 (USCG)</span></a></div>
      <div class="wrap">
        <div class="hero-text">
          <h1>Data assimilation for Earth system prediction</h1>
          <p>Our group develops Bayesian methods that combine models with observations to predict everything from thunderstorms and hurricanes to Arctic sea ice.</p>
          <div class="btns">
            <a class="btn btn-solid" href="research.html">Our research</a>
            <a class="btn btn-ghost" href="publications.html">Publications</a>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="wrap about">
        <div class="about-text">
          <h2>Who we are</h2>
          {content("home.html")}
          <p class="more"><a href="about.html">More about me →</a><a href="group.html">Meet our {n_students} Ph.D. students →</a></p>
        </div>
        <aside class="leader-card" aria-labelledby="leader-name">
          <div class="body">
          <div class="label">Group leader</div>
          <h3 id="leader-name"><a href="about.html">{NAME}</a></h3>
          <div class="role">Associate Professor and Graduate Program Director, Atmospheric and Oceanic Science</div>
          <ul class="contact">
            <li><span class="k">Email</span><a href="mailto:{EMAIL}">{EMAIL}</a></li>
            <li><span class="k">CV</span><a href="cv.pdf">Download PDF</a></li>
            <li><span class="k">Profiles</span><span><a href="{SCHOLAR}">Google Scholar</a> · <a href="{ORCID}">ORCID</a></span></li>
          </ul>
          </div>
        </aside>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>Current research themes</h2><a href="research.html">More about our research →</a></div>
        <div class="themes">
{cards}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>Recent publications</h2><a href="publications.html">All {n_total} articles →</a></div>
        <ol class="pubs pubs-home">
{pubs}
        </ol>
        <p class="note" style="margin-top:18px">* Graduate student or postdoctoral advisee</p>
      </div>
    </section>"""
    return page("index.html", "Home", body,
                f"{NAME}, Associate Professor at the University of Maryland, leads a research group in data assimilation, "
                "particle filters, and machine learning for numerical weather prediction, hurricanes, and sea ice.",
                head_extra=person_jsonld("index.html"))


def build_research(cv):
    active = [g for g in cv["grants"] if g["end"] and g["end"] >= TODAY]
    grants = "\n".join(f"""          <div class="card">
            <div class="label">{g['agency']}</div>
            <h3>{g['title']}</h3>
            <div class="meta">{g['role']} · {g['years']}</div>
          </div>""" for g in active)
    text = content("research.html")
    text = re.sub(r"\[\[papers:(\w+)\]\]", lambda m: papers_block(cv, m.group(1)), text)
    for sid, ym in re.findall(r'id="(\w+)" data-reviewed="(\d{4})-(\d{2})"', text) and \
            [(a, (int(b), int(c))) for a, b, c in re.findall(r'id="(\w+)" data-reviewed="(\d{4})-(\d{2})"', text)]:
        if (TODAY.year - ym[0]) * 12 + TODAY.month - ym[1] > 12:
            print(f"reminder: research theme '{sid}' was last reviewed {ym[0]}-{ym[1]:02d}; "
                  "check its 'Current work' paragraph")
    body = page_head("Research", "Methods for combining models and observations, and the applications that test them.") + f"""
    <section class="section">
      <div class="wrap">
{text}
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>Current support</h2></div>
        <div class="cards">
{grants}
        </div>
        <p class="note" style="margin-top:18px">We also gratefully acknowledge computing support from the NSF NCAR Computational and Information Systems Laboratory.</p>
      </div>
    </section>"""
    return page("research.html", "Research: data assimilation for weather, hurricane, and sea ice prediction", body,
                "Research by Jonathan Poterjoy's group: particle filters and ensemble data assimilation for global numerical weather prediction, convective storms, hurricanes, and sea ice, with NOAA, NASA, and NSF NCAR.")


def build_software():
    body = page_head("Software", "Open-source data assimilation code and teaching material from our group.") + f"""
    <section class="section">
      <div class="wrap">
        <h2 class="vh">Packages and tutorials</h2>
{content("software.html")}
        <p class="note" style="margin-top:18px">More code from the group is on <a href="{GITHUB}">GitHub</a>.</p>
      </div>
    </section>"""
    return page("software.html", "Software: local particle filter, DAPyr, and JEDI tutorials", body,
                f"Open-source data assimilation software from {NAME}'s group: the local particle filter "
                "in NSF NCAR DART, the DAPyr Python package for Lorenz-model experiments, and JEDI tutorials.",
                head_extra=software_jsonld())


def software_jsonld():
    """schema.org entries for the packages on the Software page."""
    import json
    me = {"@type": "Person", "name": NAME, "url": f"https://{DOMAIN}/"}
    items = [
        {"@type": "SoftwareSourceCode", "name": "Local particle filter (LPF) for DART",
         "description": "A localized particle filter for high-dimensional geophysical data assimilation, "
                        "distributed with the NSF NCAR Data Assimilation Research Testbed.",
         "codeRepository": "https://github.com/jpoterjoy/DART/tree/LPF", "programmingLanguage": "Fortran",
         "author": me, "citation": ["https://doi.org/10.1175/MWR-D-15-0163.1", "https://doi.org/10.1002/qj.4328"]},
        {"@type": "SoftwareSourceCode", "name": "DAPyr",
         "description": "A Python package for data assimilation experiments with Lorenz models.",
         "codeRepository": "https://github.com/nikolaitM/DAPyr", "programmingLanguage": "Python",
         "author": {"@type": "Person", "name": "Maria Nikolaitchik"}},
        {"@type": "SoftwareSourceCode", "name": "CADRE-JEDI-Edu",
         "description": "Tutorials introducing data assimilation methods in JEDI with a quasi-geostrophic model.",
         "codeRepository": "https://github.com/NicholasGasperoni/cadre-jedi-edu",
         "author": {"@type": "Organization", "name": "CADRE", "url": "https://ucadre.org/"}},
    ]
    data = {"@context": "https://schema.org", "@graph": items}
    return '\n  <script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


def build_publications(cv):
    arts = cv["articles"]
    n = len(arts)
    years = []
    for i, p in enumerate(arts):
        if not years or years[-1][0] != p["year"]:
            years.append((p["year"], []))
        years[-1][1].append(pub_li(p, n - i))
    blocks = "\n".join(f"""        <div class="year-block">
          <h3>{y}</h3>
          <ol class="pubs">
{chr(10).join('            ' + li for li in lis)}
          </ol>
        </div>""" for y, lis in years)
    n_adv = sum(p["advisee"] for p in arts)
    n_first = sum(p["first"] for p in arts)
    since = TODAY.year - 4
    n_recent = sum(p["year"] >= since for p in arts)
    chapters = "\n".join(f'            <li data-n="" data-kind="all">{c}</li>' for c in cv["chapters"])
    preprints = "\n".join(f'            <li data-n="" data-kind="all">{c}</li>' for c in cv["preprints"])
    body = page_head("Publications", "Peer-reviewed articles, book chapters, and preprints. "
                     "Names marked with * are graduate students or postdocs in our group.") + f"""
    <section class="section">
      <div class="wrap">
        <div class="pub-stats">
          <div><b>{n}</b><span>Journal articles</span></div>
          <div><b>{n_adv}</b><span>Led by advisees</span></div>
          <div><b>{n_first}</b><span>First-authored</span></div>
          <div><b>{n_recent}</b><span>Since {since}</span></div>
        </div>
        <h2 class="vh">Journal articles</h2>
        <div class="filter" role="group" aria-label="Filter publications">
          <button data-filter="all" aria-pressed="true">All articles</button>
          <button data-filter="advisee" aria-pressed="false">Advisee-led</button>
          <button data-filter="first" aria-pressed="false">First-authored</button>
        </div>
{blocks}
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>Book chapters</h2></div>
        <ul class="pubs">
{chapters}
        </ul>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>Preprints</h2></div>
        <ul class="pubs">
{preprints}
        </ul>
      </div>
    </section>"""
    return page("publications.html", "Publications", body,
                f"Publications by {NAME} on data assimilation and Earth system prediction.")


def split_event(t):
    """Talk text is 'Title, <em>Event</em>, Place' — de-emphasize the event part."""
    i = t.find("<em>")
    return t if i < 0 else t[:i] + '<span class="ev">' + t[i:] + "</span>"


def build_talks(cv):
    secs = []
    for title, lst in cv["talks"]:
        rows = "\n".join(f'          <li><span class="y">{y}</span><span>{split_event(t)}</span></li>' for y, t in lst)
        secs.append(f"""    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>{title.capitalize()}</h2><span class="note">{len(lst)} talks</span></div>
        <ol class="ylist">
{rows}
        </ol>
      </div>
    </section>""")
    body = page_head("Invited talks", "Invited presentations at conferences, workshops, universities, "
                     "research laboratories, and summer schools.") + "\n" + "\n\n".join(secs)
    return page("talks.html", "Talks", body, f"Invited talks and lectures by {NAME}.")


def program(name):
    m = re.search(r"\(([^)]*)\)", name)
    return (name[:m.start()].strip(), m.group(1)) if m else (name, "")


def build_group(cv):
    join = content("join.html")
    join_box = "" if not re.sub(r"<!--.*?-->", "", join, flags=re.S).strip() else f"""

    <section class="section">
      <div class="wrap">
        <div class="callout">
{join}
        </div>
      </div>
    </section>"""
    adv = cv["advising"]
    current = [p for p in adv["Ph.D. Students"] if p["status"] == "Current"]
    cards = []
    for p in current:
        nm, prog = program(p["name"])
        since = p["dates"].split("–")[0].strip()
        note = f"<br>{p['note'][0].upper() + p['note'][1:]}" if p["note"] else ""
        topic = STUDENT_TOPICS.get(nm, "")
        if not topic:
            print(f"note: no research line for current student {nm} (add one to STUDENT_TOPICS)")
        topic = f'\n            <p class="topic">{html.escape(topic, quote=False)}</p>' if topic else ""
        cards.append(f"""          <div class="person">
            <div class="name">{nm}</div>
            <div class="meta"><span class="badge">{prog}</span>Ph.D. student since {since}{note}</div>{topic}
          </div>""")

    def alumni(lst, degree):
        rows = []
        for p in lst:
            nm, prog = program(p["name"].split(",")[0])
            kind = p["name"].split(",", 1)[1].strip() if "," in p["name"] else degree
            th = f'<span class="thesis">{p["thesis"]}</span>' if p["thesis"] else ""
            extra = f' · {p["note"]}' if p.get("note") else ""
            rows.append(f'          <li><span><span class="name">{nm}</span><br><span class="note">{kind} · {prog}{extra}</span></span>{th}<span class="yr">{p["dates"]}</span></li>')
        return "\n".join(rows)

    phd_done = [p for p in adv["Ph.D. Students"] if p["status"] == "Completed"]
    ms_done = adv["M.S. Students"]
    postdocs = adv["Postdoctoral Researchers"]
    pd_rows = "\n".join(
        f'          <li><span><span class="name">{program(p["name"])[0]}</span><br><span class="note">Postdoctoral researcher · {program(p["name"])[1]}</span></span><span></span><span class="yr">{p["dates"]}</span></li>'
        for p in postdocs)
    body = page_head("Group", "Students and alumni working on data assimilation and prediction.") + f"""
    <section class="section">
      <div class="wrap">
{content("group.html")}
        <div class="section-title" style="margin-top:36px"><h2>Student members</h2><span class="note">{len(current)} Ph.D. students</span></div>
        <div class="people">
{chr(10).join(cards)}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>Alumni</h2></div>
        <div class="subhead">Ph.D.</div>
        <ul class="alumni">
{alumni(phd_done, "Ph.D.")}
        </ul>
        <div class="subhead">M.S.</div>
        <ul class="alumni">
{alumni(ms_done, "M.S.")}
        </ul>
        <div class="subhead">Postdoctoral researchers</div>
        <ul class="alumni">
{pd_rows}
        </ul>
        <div class="subhead">Undergraduate research</div>
        <ul class="alumni">
{alumni(adv["Undergraduate Research"], "Undergraduate")}
        </ul>
      </div>
    </section>
{join_box}"""
    return page("group.html", "Research group", body, f"Students and alumni of {NAME}'s research group at the University of Maryland.")


def build_teaching(cv):
    cards = []
    for t in cv["teaching"]:
        role, _, course = t["title"].partition(", ")
        bl = "".join(f"<p>{b}</p>" for b in t["bullets"])
        cards.append(f"""          <div class="card">
            <div class="label">{role}</div>
            <h3>{course}</h3>
            <div class="meta">{t['inst']} · {t['dates']}</div>
            <div style="margin-top:10px">{bl}</div>
          </div>""")
    workshops = cv["talks"][2][1]
    rows = "\n".join(f'          <li><span class="y">{y}</span><span>{split_event(t)}</span></li>' for y, t in workshops)
    body = page_head("Teaching", "Courses at the University of Maryland and lectures at data assimilation schools.") + f"""
    <section class="section">
      <div class="wrap">
        <h2 class="vh">Courses</h2>
        <div class="cards">
{chr(10).join(cards)}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>Summer schools and training workshops</h2></div>
        <p class="muted" style="margin:0 0 18px;max-width:70ch">Hands-on material from the CADRE training workshops, including the JEDI local particle filter tutorial, is available in the <a href="https://github.com/NicholasGasperoni/cadre-jedi-edu">CADRE-JEDI-Edu repository</a>. The <a href="software.html">Software page</a> also has DAPyr, a Python package for Lorenz-model experiments that is suited to teaching.</p>
        <ol class="ylist">
{rows}
        </ol>
      </div>
    </section>"""
    return page("teaching.html", "Teaching", body, f"Courses and lectures taught by {NAME}.")


def dated_list(rows):
    return "\n".join(f'          <li><span>{a}</span><span class="d">{b}</span></li>' for a, b in rows)


def build_about(cv):
    adv = cv["advising"]
    phd = adv["Ph.D. Students"]
    n_cur = sum(p["status"] == "Current" for p in phd)
    n_phd = sum(p["status"] == "Completed" for p in phd)
    n_ms = len(adv["M.S. Students"])
    n_pd = len(adv["Postdoctoral Researchers"])
    n_ug = len(adv["Undergraduate Research"])
    agencies = []
    for g in cv["grants"]:
        a = g["agency"].split()[0].split("/")[0]
        if a not in agencies:
            agencies.append(a)
    def sec(title, inner, note=""):
        n = f'<span class="note">{note}</span>' if note else ""
        return f"""    <section class="section">
      <div class="wrap">
        <div class="section-title"><h2>{title}</h2>{n}</div>
{inner}
      </div>
    </section>"""
    def group(title, rows):
        rows = [r for r in rows if not any(re.search(k, r[0]) for k in ABOUT_SKIP)]
        for pat, label in ABOUT_MERGE:
            hits = [i for i, r in enumerate(rows) if re.search(pat, r[0])]
            if len(hits) > 1:
                dates = ", ".join(sorted(rows[i][1] for i in hits))
                rows = [(label, dates) if i == hits[0] else r for i, r in enumerate(rows) if i == hits[0] or i not in hits]
        return f"""        <div class="cvgroup">
          <h3>{title}</h3>
          <ul class="dlist">
{dated_list(rows)}
          </ul>
        </div>"""
    blocks = {
        "expertise": '    <ul class="expertise">\n' + "\n".join(f"      <li>{e}</li>" for e in EXPERTISE) + "\n    </ul>",
        "cv:leadership": sec("Leadership and service", '        <div class="cvcols">\n' + "\n".join([
            group("Editorial service", cv["editorial"]),
            group("Boards, committees, and panels", cv["committees"]),
            group("Meeting organization", cv["meetings"]),
            group("University and department service", cv["service"])]) + "\n        </div>"),
        "cv:honors": sec("Honors and awards", '        <div class="cvcols">\n' + "\n".join([
            group("Awards", cv["honors"]),
            group("Awards received by advisees", cv["advisee_awards"])]) + "\n        </div>"),
        "cv:mentoring": sec("Mentoring", f"""        <ul class="stats">
          <li><b>{n_phd}</b> Ph.D. graduates</li>
          <li><b>{n_cur}</b> current Ph.D. students</li>
          <li><b>{n_ms}</b> M.S. graduates</li>
          <li><b>{n_pd}</b> postdoctoral researchers</li>
          <li><b>{n_ug}</b> undergraduate theses and internships</li>
        </ul>
        <p class="note">Current members, alumni, and thesis titles are on the <a href="group.html">Group page</a>.</p>"""),
        "cv:funding": sec("Research funding", '        <ul class="dlist">\n' + "\n".join(
            f'          <li><span><b>{g["agency"]}</b> · {g["title"]} · {g["role"]}</span><span class="d">{g["years"]}</span></li>'
            for g in cv["grants"]) + "\n        </ul>", note=f'{len(cv["grants"])} awards from ' + ", ".join(agencies[:-1]) + f", and {agencies[-1]}"),
        "cv:news": "" if not NEWS else sec("In the news", '        <ul class="news">\n' + "\n".join(
            f'          <li><a href="{u}">{h}</a><span class="src">{o}{", " + d if d else ""}</span></li>'
            for d, o, h, u in NEWS) + "\n        </ul>"),
        "cv:background": sec("Education and appointments", '        <div class="cvcols">\n' + "\n".join([
            group("Appointments", [(f"{t}, {pl}", d) for t, d, pl in cv["appointments"]]),
            group("Education", [(f"{t}, {pl}", d) for t, d, pl in cv["education"]])]) + "\n        </div>"),
    }
    text = content("about.html")
    intro, _, rest = text.partition("[[cv:news]]")
    intro = intro.replace("[[expertise]]", blocks["expertise"])
    rest = "[[cv:news]]" + rest
    for k, v in blocks.items():
        rest = rest.replace(f"[[{k}]]", v)
    body = page_head("About", "Biography, expertise, leadership, and service.") + f"""
    <section class="section">
      <div class="wrap">
{intro}
      </div>
    </section>
{rest}"""
    return page("about.html", "About", body,
                f"{NAME}: biography, areas of expertise in data assimilation and weather, hurricane, and sea ice prediction, leadership, service, and awards.",
                head_extra=person_jsonld("about.html"))


def person_jsonld(filename):
    """schema.org description of the person, so search engines can connect the site to him."""
    import json
    url = f"https://{DOMAIN}/"
    data = {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "url": url + ("" if filename == "index.html" else filename),
        "mainEntity": {
            "@type": "Person",
            "name": NAME,
            "url": url,
            "image": url + "assets/img/portrait.jpg",
            "email": "mailto:" + EMAIL,
            "jobTitle": "Associate Professor and Graduate Program Director",
            "worksFor": {"@type": "CollegeOrUniversity", "name": "University of Maryland, College Park",
                         "url": "https://umd.edu/"},
            "affiliation": {"@type": "Organization", "name": "Department of Atmospheric and Oceanic Science, University of Maryland",
                            "url": "https://aosc.umd.edu/"},
            "alumniOf": [{"@type": "CollegeOrUniversity", "name": "The Pennsylvania State University"},
                         {"@type": "CollegeOrUniversity", "name": "Millersville University of Pennsylvania"}],
            "knowsAbout": EXPERTISE,
            "award": ["National Science Foundation CAREER Award (2019)"],
            "sameAs": [SCHOLAR, ORCID, GITHUB],
        },
    }
    return '\n  <script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + "</script>"


def build_404():
    body = page_head("Page not found", 'The page you were looking for has moved. Try the <a href="index.html">home page</a>, '
                     '<a href="research.html">research</a>, or <a href="publications.html">publications</a>.')
    return page("404.html", "Not found", body, "Page not found")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", default=os.path.join(ROOT, "..", "CV-latex", "CV.tex"))
    ap.add_argument("--pdf", default=None)
    a = ap.parse_args()
    pdf = a.pdf or os.path.splitext(a.cv)[0] + ".pdf"
    cv = parse_cv(a.cv)

    # Files are overwritten in place, then anything left over from an earlier
    # build is removed, so docs/ always mirrors the current source.
    before = set()
    for d, _, fs in os.walk(OUT):
        before.update(os.path.join(d, x) for x in fs)
    os.makedirs(OUT, exist_ok=True)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"),
                    dirs_exist_ok=True)
    pages = {
        "index.html": build_home(cv),
        "about.html": build_about(cv),
        "research.html": build_research(cv),
        "publications.html": build_publications(cv),
        "talks.html": build_talks(cv),
        "group.html": build_group(cv),
        "teaching.html": build_teaching(cv),
        "software.html": build_software(),
        "404.html": build_404(),
    }
    for fn, txt in pages.items():
        with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
            f.write(txt)
    if os.path.exists(pdf):
        shutil.copy(pdf, os.path.join(OUT, "cv.pdf"))
        # keep the old WordPress CV link working
        legacy = os.path.join(OUT, "wp-content", "uploads", "2023", "06")
        os.makedirs(legacy, exist_ok=True)
        shutil.copy(pdf, os.path.join(legacy, "cv.pdf"))
    redirects = []
    for old, new in REDIRECTS.items():          # small forwarding pages for old addresses
        d = os.path.join(OUT, old)
        os.makedirs(d, exist_ok=True)
        target = f"https://{DOMAIN}/{new}"
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                    f'<title>Moved</title><meta name="robots" content="noindex">'
                    f'<link rel="canonical" href="{target}"><meta http-equiv="refresh" content="0; url=/{new}">'
                    f'</head><body><p>This page has moved to <a href="/{new}">{target}</a>.</p></body></html>\n')
        redirects.append(os.path.join(d, "index.html"))
    with open(os.path.join(OUT, "CNAME"), "w") as f:
        f.write(DOMAIN + "\n")
    with open(os.path.join(OUT, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "".join(f"  <url><loc>https://{DOMAIN}/{'' if fn == 'index.html' else fn}</loc>"
                          f"<lastmod>{TODAY.isoformat()}</lastmod></url>\n" for fn in pages if fn != "404.html")
                + "</urlset>\n")
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    after = set()
    for d, _, fs in os.walk(OUT):
        after.update(os.path.join(d, x) for x in fs)
    written = {os.path.join(OUT, fn) for fn in pages} | {
        os.path.join(OUT, "cv.pdf"), os.path.join(OUT, "CNAME"),
        os.path.join(OUT, "sitemap.xml"), os.path.join(OUT, "robots.txt"),
        os.path.join(OUT, ".nojekyll"),
        os.path.join(OUT, "wp-content", "uploads", "2023", "06", "cv.pdf")} | set(redirects)
    for d, _, fs in os.walk(os.path.join(ROOT, "assets")):
        rel = os.path.relpath(d, ROOT)
        written.update(os.path.join(OUT, rel, x) for x in fs)
    for stale in sorted((before | after) - written):
        try:
            os.remove(stale)
            print("removed old file", os.path.relpath(stale, OUT))
        except OSError:
            print("could not remove old file", os.path.relpath(stale, OUT))
    print(f"Built {len(pages)} pages, {len(cv['articles'])} articles, "
          f"{sum(len(x[1]) for x in cv['talks'])} talks -> {OUT}")


if __name__ == "__main__":
    main()
