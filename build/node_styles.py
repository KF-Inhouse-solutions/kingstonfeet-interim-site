"""Per-page CSS from the computed styles captured off the original site (build/styles/*.json).

capture: the 15 Oct 2026 crawl rendered with its own stylesheets, measured at 1280px and 375px wide.
Each builder row / column / module keeps its node id as a class (n-<id>) in our markup, so the
original's colours, sizes and spacing are re-applied to the matching parts of the new pages.
"""
import json
import re
from pathlib import Path

STYLES = Path(__file__).resolve().parent / "styles"
CLEAR = {"rgba(0, 0, 0, 0)", "transparent", "none", None, ""}
HEADS = "h1,h2,h3,h4,h5,h6".split(",")
HOVER = {}      # hover states per node, parsed from the original CSS by build.py
TEXT_ALL = {}   # rich-text modules whose editor colour applies to every element inside (set per page by build.py)


def slug(page):
    return page.strip("/").replace("/", "_") or "home"


def load(page, width):
    f = STYLES / f"{slug(page)}-{width}.json"
    return json.loads(f.read_text()) if f.exists() else None


def zero(v):
    return v in ("0px", "0", None, "")


def txt(d, keys=("color", "font-size", "font-family", "font-weight", "font-style", "line-height",
                 "text-align", "text-transform", "letter-spacing")):
    out = {}
    for k in keys:
        v = (d or {}).get(k)
        if v in CLEAR or v == "normal" and k in ("letter-spacing",):
            continue
        if k == "text-align" and v == "start":
            continue
        if k == "text-transform" and v == "none":
            continue
        out[k] = v
    return out


def overlay(d):
    o = d.get("overlay") or {}
    if (o.get("background-image") or "none") not in CLEAR and "gradient" in o["background-image"]:
        return o["background-image"]
    return o.get("background-color") if o.get("background-color") not in CLEAR else None


def rules_for(data, img_url):
    """selector -> {prop: value} for one capture width."""
    R = {}

    def add(sel, props):
        if props:
            R.setdefault(sel, {}).update(props)

    for node, r in (data.get("rows") or {}).items():
        sel = f".n-{node}"
        p = {}
        if r.get("background-color") not in CLEAR:
            p["background-color"] = r["background-color"]
        m = re.search(r'url\("?([^")]+)"?\)', r.get("background-image") or "")
        if m:
            local = img_url(m.group(1))
            if local:
                p["background-image"] = f"url('{local}')"
                p["background-position"] = r.get("background-position", "center")
                p["background-size"] = r.get("background-size", "cover")
                p["background-repeat"] = "no-repeat"
        p["padding-top"] = r.get("padding-top", "0px")
        p["padding-bottom"] = r.get("padding-bottom", "0px")
        if r.get("color") not in CLEAR:
            p["color"] = r["color"]
        if not zero(r.get("min-height")) and r.get("min-height") != "auto":
            p["min-height"] = r["min-height"]
        add(sel, p)
        ov = overlay(r)
        if ov:
            add(sel, {"position": "relative"})
            add(f"{sel}::before", {"content": '""', "position": "absolute", "inset": "0", "background": ov})
            add(f"{sel} > .wrap", {"position": "relative"})
        pl, pr = r.get("padding-left", "20px"), r.get("padding-right", "20px")
        cw = r.get("contentWidth")
        w = {"padding-left": pl, "padding-right": pr}
        if cw:
            w["max-width"] = f"calc({round(cw)}px + {pl} + {pr})"
        add(f"{sel} > .wrap", w)

    for node, c in (data.get("cols") or {}).items():
        sel = f".n-{node}"
        p = {}
        if c.get("background-color") not in CLEAR:
            p["background-color"] = c["background-color"]
        m = re.search(r'url\("?([^")]+)"?\)', c.get("background-image") or "")
        if m and img_url(m.group(1)):
            p["background-image"] = f"url('{img_url(m.group(1))}')"
            p["background-size"] = c.get("background-size") or "cover"
            p["background-position"] = c.get("background-position") or "center"
            p["background-repeat"] = "no-repeat"
            if c.get("h"):
                p["min-height"] = f'{round(c["h"])}px'
        ov = overlay(c)
        if ov:
            p["position"] = "relative"
            add(f"{sel}::before", {"content": '""', "position": "absolute", "inset": "0", "background": ov,
                                   "border-radius": c.get("border-radius") or "0"})
            add(f"{sel} > *", {"position": "relative"})
        for k in ("padding-top", "padding-right", "padding-bottom", "padding-left"):
            if not zero(c.get(k)):
                p[k] = c[k]
        if c.get("border-radius") not in ("0px", None):
            p["border-radius"] = c["border-radius"]
        if c.get("color") not in CLEAR:
            p["color"] = c["color"]
        add(sel, p)

    for node, m in (data.get("mods") or {}).items():
        sel = f".n-{node}"
        box = m.get("box") or {}
        add(sel, {"margin": " ".join(box.get(k, "0px") for k in ("margin-top", "margin-right", "margin-bottom", "margin-left"))})
        t = m.get("t")
        if m.get("h"):
            h = txt(m["h"])
            if (m.get("ht") or {}).get("color") not in CLEAR:
                h["color"] = m["ht"]["color"]
            h["margin-top"] = m["h"].get("margin-top", "0px")
            h["margin-bottom"] = m["h"].get("margin-bottom", "0px")
            add(",".join(f"{sel} {x}" for x in HEADS), h)
            add(",".join(f"{sel} {x} a" for x in HEADS), {"color": "inherit", "text-decoration": "none"})
        if m.get("rt"):
            add(sel, txt(m["rt"]))
            if m.get("p"):
                pp = {"margin-top": m["p"].get("margin-top", "0px"), "margin-bottom": m["p"].get("margin-bottom", "10px")}
                if m["p"].get("color") not in CLEAR and m["p"].get("color") != m["rt"].get("color"):
                    pp["color"] = m["p"]["color"]
                add(f"{sel} p", pp)
            if m.get("a") and m["a"].get("color") not in CLEAR:
                add(f"{sel} a:not(.btn)", {"color": m["a"]["color"]})
            if node in TEXT_ALL:
                decl = dict(TEXT_ALL[node])
                if "color" in decl:
                    add(f"{sel} *:not(.btn)", {"color": decl.pop("color")})
                if decl:
                    add(f"{sel} *:not(.btn):not(b):not(strong)", decl)
        if m.get("btn"):
            b = m["btn"]
            bt = m.get("btnText") or {}
            p = {
                "background-color": b.get("background-color"),
                "background-image": b.get("background-image") if "gradient" in (b.get("background-image") or "") else None,
                "color": bt.get("color") or b.get("color"),
                "border": f'{b.get("border-top-width", "0px")} {b.get("border-top-style", "solid")} {b.get("border-top-color", "transparent")}',
                "border-radius": b.get("border-radius"),
                "font-size": bt.get("font-size") or b.get("font-size"),
                "font-family": bt.get("font-family") or b.get("font-family"),
                "font-weight": bt.get("font-weight") or b.get("font-weight"),
                "padding": " ".join(b.get(k, "0px") for k in ("padding-top", "padding-right", "padding-bottom", "padding-left")),
                "text-transform": (bt.get("text-transform") if bt.get("text-transform") not in (None, "none") else
                                   b.get("text-transform") if b.get("text-transform") not in (None, "none") else None),
            }
            bw = float(re.sub(r"[^\d.]", "", b.get("width") or "0") or 0)
            if m.get("btnFull") and bw >= (m.get("w") or 0) - 60:
                p.update({"display": "block", "width": "100%"})
            elif bw:
                p.update({"display": "inline-block", "min-width": f"{round(bw)}px"})
            add(f"{sel} .btn", {k: v for k, v in p.items() if v})
            if m.get("btnIcon") and m["btnIcon"].get("color") not in CLEAR:
                add(f"{sel} .btn .ico", {"color": m["btnIcon"]["color"]})
            al = (m.get("btnWrap") or {}).get("text-align")
            if t in ("button", "button-group") and al and al != "start":
                add(sel, {"text-align": al})
        if m.get("img") and t in ("photo", "callout", "rich-text", "cta"):
            i = m["img"]
            p = {"width": f'{i["w"]}px', "max-width": "100%"}
            if i.get("radius") not in ("0px", None):
                p["border-radius"] = i["radius"]
            p["margin-left"] = "0" if i.get("align") in ("left", "start") else "auto"
            p["margin-right"] = "auto" if i.get("align") in ("left", "start", "center") else "0"
            add(f"{sel} img", p)
        if t in ("photo", "callout", "cta", "icon", "testimonials") and (m.get("wrap") or {}).get("text-align") not in (None, "start"):
            add(sel, {"text-align": m["wrap"]["text-align"]})
    return R


def hover_rules():
    R = {}
    for node, kinds in HOVER.items():
        sel = f".n-{node}"
        if kinds.get("btn"):
            R[f"{sel} .btn:hover,{sel} .btn:focus"] = kinds["btn"]
        if kinds.get("btn_text") and kinds["btn_text"].get("color"):
            R[f"{sel} .btn:hover,{sel} .btn:focus,{sel} .btn:hover *"] = {"color": kinds["btn_text"]["color"]}
        if kinds.get("link"):
            R[f"{sel} a:not(.btn):hover,{sel} a:not(.btn):focus"] = kinds["link"]
    return R


def render(R, used, indent=""):
    out = []
    for sel, props in R.items():
        ids = re.findall(r"\.n-([a-z0-9]+)", sel)
        if ids and not all(i in used for i in ids):
            continue
        body = ";".join(f"{k}:{v}" for k, v in props.items())
        out.append(f"{indent}{sel}{{{body}}}")
    return "\n".join(out)


def page_css(page, used, img_url):
    desk, mob = load(page, 1280), load(page, 375)
    if not desk:
        return ""
    D = rules_for(desk, img_url)
    css = render(D, used) + "\n" + render(hover_rules(), used)
    if mob:
        M = rules_for(mob, img_url)
        diff = {}
        for sel, props in M.items():
            changed = {k: v for k, v in props.items() if D.get(sel, {}).get(k) != v}
            if changed:
                diff[sel] = changed
        mcss = render(diff, used, "  ")
        if mcss:
            css += "\n@media (max-width: 768px) {\n" + mcss + "\n}"
    return css


def page_meta(page):
    """Page-level styles of the original (post title etc.), at desktop width."""
    d = load(page, 1280)
    return (d or {}).get("page") or {}
