"""Build the KingstonFeet interim static site from the 15 Oct 2026 crawl.

Run:  uv run --with beautifulsoup4 --with pillow python build/build.py
Reads the archive (never writes to it) and writes the site into docs/.
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup, NavigableString, Comment, Tag
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "docs"
ARCHIVE = ROOT.parent / "kingstonfeet-old-site" / "2026-10-15" / "site"
UPLOADS = ARCHIVE / "wp-content" / "uploads"
SITE = "https://kingstonfeet.com"
CLINIKO = "https://kingstonfeet-ltd.uk1.cliniko.com/bookings"
PHONE = "0208 546 9626"
TEL = "tel:+442085469626"
EMAIL = "office@kingstonfeet.com"

PAGES = [
    "/", "/about-us-jo-lea-podiatrist/", "/your-foot-problem/", "/book-now/",
    "/book-online/", "/contact-us/", "/find-us/", "/voluntary/", "/afterprocedure/",
    "/blog/", "/blog/toenail-trouble/", "/blog/foot-pain/", "/blog/embarrassing-feet/",
    "/blog/biomechanical-assessment/", "/blog/bunions-joint-problems/",
    "/blog/toenail-reconstructions/", "/blog/warm-wax-therapy/",
    "/blog/swift-microwave-therapy/", "/privacy-policy/", "/cookie-policy/",
]
# Outdated pages -> homepage; old non-sitemap blog URLs -> /blog/
FORWARDS = {
    "/covid-19-landing-page/": "/", "/lockdown-extra-safety-measures/": "/",
    "/hiring/": "/", "/november_2020_images/": "/",
    "/kingston-podiatry-chiropody-kingstonfeet-copy/": "/", "/physiomore/": "/",
    "/category/blog/": "/blog/", "/author/kfjoanna/": "/blog/", "/blog/page/2/": "/blog/",
}
NAV = [("/", "Home"), ("/about-us-jo-lea-podiatrist/", "About Us"), ("/book-now/", "Book now"),
       ("/your-foot-problem/", "My Foot Problem"), ("/contact-us/", "Contact Us"),
       ("/find-us/", "Find Us"), ("/voluntary/", "Voluntary")]
FOOTER_NAV = [("/", "Home"), ("/about-us-jo-lea-podiatrist/", "About Us"), ("/book-online/", "Book Online"),
              ("/your-foot-problem/", "My Foot Problem"), ("/blog/", "Blog"), ("/contact-us/", "Contact Us"),
              ("/find-us/", "Find Us"), ("/privacy-policy/", "Privacy Policy"), ("/cookie-policy/", "Cookie Policy")]

KEEP = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "a", "strong", "b", "em", "i",
        "br", "img", "blockquote", "table", "thead", "tbody", "tr", "td", "th", "hr", "u", "sup", "sub"}
BLOCK = {"h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "blockquote", "table", "hr", "div", "figure"}
ICON_LABELS = {"twitter": "Twitter", "facebook": "Facebook", "instagram": "Instagram", "linkedin": "LinkedIn",
               "google": "Google", "youtube": "YouTube"}

problems = []          # things we couldn't recover, reported at the end
images = {}            # archive path -> output relative path (from site root)


# ---------- helpers ----------

def page_file(path):
    return ARCHIVE / path.strip("/") / "index.html" if path != "/" else ARCHIVE / "index.html"


def rel(from_path, to_path):
    """Relative link from page directory from_path ('/blog/x/') to site path to_path."""
    frag = ""
    if "#" in to_path:
        to_path, frag = to_path.split("#", 1)
        frag = "#" + frag
    depth = len([p for p in from_path.split("/") if p])
    up = "../" * depth
    target = to_path.lstrip("/")
    out = (up + target) or "./"
    return out + frag


def internal_path(href):
    """Return site path for a kingstonfeet.com link, else None."""
    u = urlparse(href)
    if u.netloc and u.netloc.replace("www.", "") != "kingstonfeet.com":
        return None
    if not u.netloc and not href.startswith("/"):
        return None
    p = u.path or "/"
    if not p.endswith("/") and "." not in p.rsplit("/", 1)[-1]:
        p += "/"
    return p + (("#" + u.fragment) if u.fragment else "")


def find_original(url):
    """Map an uploads URL (sized/cached) to the largest local file we have."""
    path = unquote(urlparse(url).path)
    if "/wp-content/uploads/" not in path:
        return None
    sub = path.split("/wp-content/uploads/", 1)[1]
    f = UPLOADS / sub
    if sub.startswith("bb-plugin/cache/"):
        name = f.name
        stem = re.split(r"-(?:\d+x\d+-)?(?:panorama|square|landscape|portrait|circle)-", name)[0]
        stem = re.sub(r"-\d+x\d+$", "", stem)
        cands = [p for p in UPLOADS.glob("20*/*/*") if p.stem in (stem, stem + "-scaled")]
        if cands:
            return max(cands, key=lambda p: p.stat().st_size)
        return f if f.exists() else None
    base = re.sub(r"-\d+x\d+(\.\w+)$", r"\1", sub)
    for cand in [base, re.sub(r"(\.\w+)$", r"-scaled\1", base), sub]:
        if (UPLOADS / cand).exists():
            return UPLOADS / cand
    # sized variants on disk: take the biggest
    stem = Path(base).stem
    sized = list((UPLOADS / Path(base).parent).glob(stem + "-*x*" + Path(base).suffix))
    if sized:
        return max(sized, key=lambda p: p.stat().st_size)
    return None


def add_image(url):
    src = find_original(url)
    if not src:
        problems.append(f"image not in crawl: {url}")
        return None
    key = str(src)
    if key in images:
        return images[key]
    sub = src.relative_to(UPLOADS)
    if sub.parts[0] == "bb-plugin":
        sub = Path("cache") / re.sub(r"-[0-9a-f]{32}-[0-9a-z]*", "", src.name)
    ext = src.suffix.lower()
    out_ext = ".png" if ext == ".png" else ".jpg"
    out_rel = Path("images") / sub.with_suffix(out_ext)
    out_rel = Path(str(out_rel).replace("-scaled", ""))
    dest = OUT / out_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".heic":
        tmp = dest.with_suffix(".tmp.jpg")
        subprocess.run(["sips", "-s", "format", "jpeg", str(src), "--out", str(tmp)],
                       check=True, capture_output=True)
        src_open = tmp
    else:
        src_open = src
    im = Image.open(src_open)
    im = ImageOps.exif_transpose(im)
    im.thumbnail((1600, 1600))
    if out_ext == ".png":
        im.save(dest, optimize=True)        # no metadata carried over
    else:
        im.convert("RGB").save(dest, "JPEG", quality=78, optimize=True, progressive=True)
    if ext == ".heic":
        tmp.unlink()
    images[key] = "/" + str(out_rel)
    return images[key]


def best_src(img):
    for attr in ("data-lazy-src", "data-src", "data-litespeed-src", "src"):
        v = img.get(attr)
        if v and not v.startswith("data:") and "pixel.png" not in v:
            # prefer the largest srcset entry if present
            ss = img.get("data-srcset") or img.get("data-lazy-srcset") or img.get("srcset")
            if ss:
                best = max((s.strip().split(" ") for s in ss.split(",") if s.strip()),
                           key=lambda x: int(re.sub(r"\D", "", x[1]) or 0) if len(x) > 1 else 0)
                return best[0]
            return v
    return None


# ---------- conversion ----------

def visible_on_desktop(el):
    cls = [c for c in (el.get("class") or []) if c.startswith("fl-visible-")]
    return not cls or any(c in ("fl-visible-desktop", "fl-visible-large") for c in cls)


def clean(node, page):
    """Return clean HTML for the children of node."""
    out = []
    for ch in list(node.children):
        if isinstance(ch, Comment):
            continue
        if isinstance(ch, NavigableString):
            out.append(html.escape(str(ch), quote=False))
            continue
        if not isinstance(ch, Tag):
            continue
        name = ch.name
        if name in ("script", "style", "noscript", "meta", "link", "input", "button", "svg", "iframe", "label", "select", "textarea"):
            continue
        if name == "form":
            continue
        if not visible_on_desktop(ch):
            continue
        cls = ch.get("class") or []
        if "swiper-slide-duplicate" in cls or "fl-contact-error" in cls or "sr-only" in cls or "screen-reader-text" in cls:
            continue
        if name == "img":
            u = best_src(ch)
            if not u:
                continue
            local = add_image(u)
            if not local:
                continue
            alt = html.escape(ch.get("alt") or "", quote=True)
            w = ch.get("width") or ""
            size = f' style="width:{int(w)}px"' if w.isdigit() and int(w) < 700 else ""
            out.append(f'<img src="{rel(page, local)}" alt="{alt}" loading="lazy"{size}>')
            continue
        if name == "i":
            icon = " ".join(cls)
            if any(c.startswith(("fa", "fi-", "dashicons")) for c in cls):
                inner = clean(ch, page).strip()
                if inner:
                    out.append(inner)
                continue
        inner = clean(ch, page)
        if name == "a":
            href = (ch.get("href") or "").strip()
            label = re.sub(r"<[^>]+>", "", inner).strip()
            if not label and "<img" not in inner:
                for k, v in ICON_LABELS.items():
                    if k in str(ch):
                        inner = v
                        break
            if not href or href == "#" or "wp-admin" in href or "wp-login" in href:
                out.append(inner)
                continue
            if "/wp-content/uploads/" in href:   # image linked to its file: drop the link
                out.append(inner)
                continue
            ip = internal_path(href)
            if ip is not None:
                ipath = ip.split("#")[0]
                if ipath in FORWARDS:
                    ip = FORWARDS[ipath]
                # booking buttons/links in page content go straight to Cliniko (menus still list the pages)
                href = CLINIKO if ipath in ("/book-now/", "/book-online/") else rel(page, ip)
            if href.startswith("javascript"):
                out.append(inner)
                continue
            c = ' class="btn"' if "fl-button" in cls else ""
            ext = ' rel="noopener"' if href.startswith("http") else ""
            out.append(f'<a href="{html.escape(href, quote=True)}"{c}{ext}>{inner}</a>')
            continue
        if name in KEEP:
            if name in ("br", "hr"):
                out.append(f"<{name}>")
            elif name in ("td", "th") and ch.get("colspan"):
                out.append(f'<{name} colspan="{ch["colspan"]}">{inner}</{name}>')
            elif name in ("b",):
                out.append(f"<strong>{inner}</strong>")
            elif name == "i":
                out.append(f"<em>{inner}</em>")
            else:
                out.append(f"<{name}>{inner}</{name}>")
            continue
        # div/span/section/etc: unwrap; make a paragraph if a div holds only inline content
        if name in ("div", "section", "article", "figure", "header", "footer", "aside", "center"):
            text_only = not re.search(r"<(h\d|p|ul|ol|li|blockquote|table|div|hr|img)\b", inner)
            if text_only and re.sub(r"<[^>]+>|\s|&nbsp;", "", inner):
                out.append(f"<p>{inner.strip()}</p>")
            else:
                out.append(inner)
            continue
        out.append(inner)
    return "".join(out)


def tidy(h):
    h = h.replace("\xa0", " ")
    h = re.sub(r"<p>\s*(<br>\s*)*</p>", "", h)
    h = re.sub(r"<(strong|em|span|u)>\s*</\1>", "", h)
    h = re.sub(r"<p>\s*(<(h\d|ul|ol|p|blockquote)\b)", r"\1", h)
    h = re.sub(r"[ \t]{2,}", " ", h)
    h = re.sub(r"\n\s*\n+", "\n", h)
    return h.strip()


def row_backgrounds(soup):
    """node id -> background image URL, from the page's layout CSS."""
    css = "\n".join(s.get_text() for s in soup.find_all("style"))
    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        m = re.search(r"/wp-content/litespeed/css/([0-9a-f]+)\.css\?ver=(\w+)", href)
        if m:
            f = ARCHIVE / "wp-content" / "litespeed" / "css" / f"{m.group(1)}__ver={m.group(2)}.css"
            if f.exists():
                css += f.read_text(errors="ignore")
    widths = {}
    for m in re.finditer(r"\.fl-node-([a-z0-9]+)\s*\{\s*width:\s*([\d.]+)%", css):
        widths.setdefault(m.group(1), float(m.group(2)))
    bgs = {}
    for m in re.finditer(r"\.fl-node-([a-z0-9]+)\s*>\s*\.fl-row-content-wrap\s*\{[^}]*background-image:\s*url\(([^)]*)\)", css):
        bgs[m.group(1)] = m.group(2).strip("'\"")
    return bgs, widths


def convert_module(m, page):
    t = m.get("data-type") or next((c[10:] for c in m.get("class", []) if c.startswith("fl-module-") and c != "fl-module-content"), "")
    if t == "contact-form":
        return contact_block(page)
    if t == "map":
        return (f'<p><a class="btn btn-ghost" href="https://www.google.com/maps/search/?api=1&amp;query=kingstonfeet+196+Richmond+Road+Kingston+KT2+5HE" rel="noopener">'
                "View kingstonfeet on Google Maps</a></p>")
    if t == "html":
        frame = m.find("iframe")
        if frame and "cliniko" in (frame.get("data-litespeed-src") or frame.get("src") or ""):
            return (f'<p class="small">If the booking form does not load, <a href="{CLINIKO}" rel="noopener">open online booking</a>.</p>'
                    f'<iframe class="cliniko" src="{CLINIKO}?embedded=true" title="Book online with kingstonfeet"></iframe>')
        return tidy(clean(m, page))
    if t == "widget":
        if m.select_one(".widget_search"):
            return ""
    if t == "slideshow" and not m.find("img"):
        return ""
    if t == "testimonials":
        quotes = [tidy(clean(s, page)) for s in m.select(".fl-testimonial")]
        quotes = [q for q in quotes if q]
        if quotes:
            head = "".join(f"<h3>{html.escape(h.get_text().strip())}</h3>" for h in m.select(".fl-testimonials-heading"))
            return head + '<div class="testimonials">' + "".join(f"<blockquote>{q}</blockquote>" for q in quotes) + "</div>"
    body = tidy(clean(m, page))
    return f'<div class="m m-{t}">{body}</div>' if body else ""


def child_blocks(el):
    """Direct builder children (modules / col-groups) of a column, in order."""
    for ch in el.children:
        if not isinstance(ch, Tag):
            continue
        cls = ch.get("class") or []
        if "fl-module" in cls or "fl-col-group" in cls:
            yield ch
        elif "fl-col-content" in cls or ch.name == "div" and not any(c.startswith("fl-module") for c in cls):
            yield from child_blocks(ch)


def convert_group(grp, page, widths):
    cols, fr = [], []
    for col in grp.find_all(class_="fl-col", recursive=False):
        if not visible_on_desktop(col):
            continue
        parts = []
        for b in child_blocks(col):
            if not visible_on_desktop(b):
                continue
            h = convert_group(b, page, widths) if "fl-col-group" in b.get("class", []) else convert_module(b, page)
            if h:
                parts.append(h)
        if parts:
            cols.append('<div class="col">' + "\n".join(parts) + "</div>")
            fr.append(widths.get(col.get("data-node", ""), 0))
    if not cols:
        return ""
    style = ""
    if len(cols) > 1 and all(fr):
        style = ' style="--cols:' + " ".join(f"{w:g}fr" for w in fr) + '"'
    return f'<div class="cols cols-{len(cols)}"{style}>' + "\n".join(cols) + "</div>"


def convert_builder(container, page, bgs, widths):
    out = []
    for row in container.select(".fl-row"):
        if row.find_parent(class_="fl-row"):
            continue
        if not visible_on_desktop(row):
            continue
        node = row.get("data-node", "")
        bg = bgs.get(node)
        style = ""
        cls = "row"
        if bg:
            local = add_image(bg)
            if local:
                style = f' style="background-image:url(\'{rel(page, local)}\')"'
                cls += " row-bg"
        if "fl-row-bg-color" in row.get("class", []) or "fl-row-bg-gradient" in row.get("class", []):
            cls += " row-tint"
        groups = [convert_group(g, page, widths) for g in row.select(".fl-col-group") if not g.find_parent(class_="fl-col-group")]
        groups = [g for g in groups if g]
        if groups:
            out.append(f'<section class="{cls}"{style}><div class="wrap">' + "\n".join(groups) + "</div></section>")
    return "\n".join(out)


def contact_block(page):
    return (
        '<div class="contact-card">'
        f'<p><strong>Phone:</strong> <a href="{TEL}">{PHONE}</a></p>'
        f'<p><strong>Email:</strong> <a href="mailto:{EMAIL}">{EMAIL}</a></p>'
        "<p><strong>Address:</strong> kingstonfeet, 196 Richmond Road, Kingston upon Thames, KT2 5HE</p>"
        f'<p><a class="btn" href="{CLINIKO}" rel="noopener">Book online</a></p>'
        "</div>"
    )


# ---------- template ----------

def layout(page, title, desc, body, extra_head=""):
    canon = SITE + page
    nav = "".join(
        f'<li><a href="{rel(page, p)}"{" aria-current=\"page\"" if p == page else ""}>{t}</a></li>' for p, t in NAV)
    fnav = "".join(f'<li><a href="{rel(page, p)}">{t}</a></li>' for p, t in FOOTER_NAV)
    d = f'<meta name="description" content="{html.escape(desc, quote=True)}">\n' if desc else ""
    css = rel(page, "/assets/site.css")
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
{d}<link rel="canonical" href="{canon}">
<link rel="icon" href="{rel(page, '/favicon.png')}" sizes="32x32">
<link rel="apple-touch-icon" href="{rel(page, '/apple-touch-icon.png')}">
<link rel="stylesheet" href="{css}">
{extra_head}</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="{rel(page, '/')}"><span class="logo-k">kingston</span><span class="logo-f">feet</span><span class="tagline">...because your footcare matters</span></a>
    <div class="header-actions">
      <a class="phone" href="{TEL}">{PHONE}</a>
      <a class="btn btn-small" href="{CLINIKO}" rel="noopener">Book now</a>
    </div>
    <div class="menu">
      <input type="checkbox" id="nav-toggle" class="nav-toggle"><label for="nav-toggle">Menu</label>
      <nav aria-label="Main"><ul>{nav}</ul></nav>
    </div>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p class="footer-contact"><a href="{TEL}">{PHONE}</a> · <a href="mailto:{EMAIL}">{EMAIL}</a> · 196 Richmond Road, Kingston upon Thames, KT2 5HE</p>
    <nav aria-label="Footer"><ul>{fnav}</ul></nav>
    <p class="copy">© 2026 kingstonfeet</p>
  </div>
</footer>
</body>
</html>
"""


def forward_page(page, target):
    url = rel(page, target)
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<title>kingstonfeet</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{SITE}{target}">
<meta http-equiv="refresh" content="0; url={url}">
</head>
<body>
<p>This page has moved. <a href="{url}">Continue to kingstonfeet</a>.</p>
</body>
</html>
"""


# ---------- build ----------

def build_page(page):
    soup = BeautifulSoup(page_file(page).read_text(errors="ignore"), "html.parser")
    title = soup.title.get_text().strip() if soup.title else "kingstonfeet"
    md = soup.find("meta", attrs={"name": "description"})
    desc = md["content"].strip() if md and md.get("content") else ""
    bgs, widths = row_backgrounds(soup)
    main = soup.select_one(".fl-builder-content-primary")
    parts = []
    post = soup.select_one("article.fl-post")
    header = soup.select_one(".fl-post-header")
    if header and header.find("h1") and (not main or "type-post" in (post.get("class") or [])):
        parts.append(f'<section class="row page-title"><div class="wrap"><h1>{html.escape(header.find("h1").get_text().strip())}</h1></div></section>')
    if main:
        parts.append(convert_builder(main, page, bgs, widths))
    else:
        content = soup.select_one(".fl-post-content")
        parts.append(f'<section class="row"><div class="wrap prose">{tidy(clean(content, page))}</div></section>')
    body = "\n".join(p for p in parts if p)
    body = body.replace(' loading="lazy"', "", 2)   # first images load straight away
    extra = ""
    if "cliniko" in body and "<iframe" in body:
        # Cliniko's own resize snippet for its embedded booking form
        extra = ("<script>window.addEventListener('message',function(e){var f=document.querySelector('iframe.cliniko');"
                 "if(!f||typeof e.data!=='string')return;if(e.data.indexOf('cliniko-bookings-resize')>-1){"
                 "f.style.height=Number(e.data.split(':')[1])+'px'}if(e.data.indexOf('cliniko-bookings-page')>-1){f.scrollIntoView()}});</script>\n")
    out = OUT / page.strip("/") / "index.html" if page != "/" else OUT / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(layout(page, title, desc, body, extra))
    return title, desc


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "assets").mkdir()
    shutil.copy(HERE / "site.css", OUT / "assets" / "site.css")
    meta = {}
    for p in PAGES:
        meta[p] = build_page(p)
    for p, target in FORWARDS.items():
        f = OUT / p.strip("/") / "index.html"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(forward_page(p, target))
    # favicon from the old site's cropped favicon
    fav = UPLOADS / "2018" / "10"
    Image.open(fav / "cropped-favicon-1-32x32.png").save(OUT / "favicon.png", optimize=True)
    Image.open(fav / "cropped-favicon-1-180x180.png").save(OUT / "apple-touch-icon.png", optimize=True)
    Image.open(fav / "cropped-favicon-1-32x32.png").save(OUT / "favicon.ico", sizes=[(32, 32)])
    # 404: GitHub Pages serves it at any depth, so inline the CSS and point links at the live domain
    body404 = ('<section class="row"><div class="wrap prose"><h1>Page not found</h1>'
               f'<p>Sorry, we could not find that page.</p><p><a class="btn" href="{SITE}/">Go to the homepage</a> '
               f'<a class="btn btn-ghost" href="{CLINIKO}" rel="noopener">Book online</a></p>'
               f'<p>Or call us on <a href="{TEL}">{PHONE}</a>.</p></div></section>')
    page404 = layout("/", "Page not found - kingstonfeet", "", body404)
    page404 = page404.replace(f'<link rel="canonical" href="{SITE}/">', '<meta name="robots" content="noindex">')
    page404 = re.sub(r'<link rel="(icon|apple-touch-icon)"[^>]*>\n', "", page404)
    page404 = page404.replace('<link rel="stylesheet" href="assets/site.css">',
                              "<style>" + (HERE / "site.css").read_text() + "</style>")
    page404 = re.sub(r'href="(?!https?:|tel:|mailto:|#)\.?/?([^"]*)"', lambda m: f'href="{SITE}/{m.group(1)}"', page404)
    (OUT / "404.html").write_text(page404)
    # sitemap + robots
    urls = "".join(f"<url><loc>{SITE}{p}</loc></url>\n" for p in PAGES)
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    (OUT / ".nojekyll").write_text("")
    (OUT / "CNAME").write_text("kingstonfeet.com\n")
    (ROOT / "build" / "report.json").write_text(json.dumps(
        {"pages": {p: {"title": t, "description": d} for p, (t, d) in meta.items()},
         "forwards": FORWARDS, "images": sorted(images.values()), "problems": problems}, indent=1))
    print(f"{len(PAGES)} pages, {len(FORWARDS)} forwards, {len(images)} images")
    for pr in problems:
        print("PROBLEM:", pr)


if __name__ == "__main__":
    main()
