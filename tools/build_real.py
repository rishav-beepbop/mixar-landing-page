#!/usr/bin/env python3
"""Generate the real-element page from the recovered Figma layers.

Nothing here is a screenshot: text is text, photographs and screenshots are
<img> at their original resolution, and flat shapes are elements. Geometry
comes from tools/layers.json (measured off the vector export) and type from
tools/text-spec.json (solved against the real Switzer metrics in a browser).

Everything is expressed against a 1728 x 11981 canvas, in percentages and
container units, so the page keeps the exact proportions of the design at any
viewport width — same layout, same spacing, same look.
"""
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DW, DH = 1728.0, 11981.0

layers_doc = json.loads((ROOT / "tools/layers.json").read_text())
spec_doc = json.loads((ROOT / "tools/text-spec.json").read_text())
METRICS, SPEC = spec_doc["metrics"], spec_doc["spec"]
IMAGES = layers_doc["images"]
LAYERS = layers_doc["layers"]

# ------------------------------------------------------------- gradients ---
raw = (ROOT / "public/assets/mixar-landing-updated.svg").read_text(errors="replace")
GRADS = {}
for m in re.finditer(
    r'<linearGradient id="([^"]+)"[^>]*x1="([-\d.e]+)" y1="([-\d.e]+)"'
    r' x2="([-\d.e]+)" y2="([-\d.e]+)"[^>]*>(.*?)</linearGradient>', raw, re.S):
    gid, x1, y1, x2, y2, body = m.groups()
    stops = re.findall(r'<stop(?: offset="([\d.]+)")?[^>]*stop-color="([^"]+)"', body)
    if not stops:
        continue
    import math
    ang = (math.degrees(math.atan2(float(y2) - float(y1), float(x2) - float(x1))) + 90) % 360
    parts = [f"{c} {float(o or 0) * 100:.1f}%" for o, c in stops]
    GRADS[gid] = f"linear-gradient({ang:.1f}deg, {', '.join(parts)})"


def paint(fill):
    """Return (css_value, is_gradient) for an SVG fill."""
    if not fill:
        return None, False
    g = re.match(r'url\(#(.+)\)', fill)
    if g:
        return GRADS.get(g.group(1), "#888"), True
    return fill, False


def pct(v, total):
    return f"{v / total * 100:.4f}%"


def cqw(px):
    """Design pixels as a share of canvas width, so type scales with layout."""
    return f"{px / DW * 100:.4f}cqw"


# ----------------------------------------------------------------- build ---
SKIP = re.compile(r'^(Rectangle|Group|Vector|Ellipse|Frame|Line|Union|Subtract'
                  r'|Arrow|Mask|Star|Polygon|Clip)')
spec_by_key = {(round(s["x"], 1), round(s["y"], 1)): s for s in SPEC}

nodes = []       # (z-order index, html)
used_text = set()

for i, l in enumerate(LAYERS):
    x, y, w, h = l["x"], l["y"], l["w"], l["h"]
    if w <= 0 or h <= 0:
        continue
    key = (round(x, 1), round(y, 1))

    # --- real text -----------------------------------------------------
    s = spec_by_key.get(key)
    if s and l["tag"] == "path" and not SKIP.match(l["id"]) and key not in used_text:
        used_text.add(key)
        fm = METRICS[str(s["fw"])]
        size, lh = s["s"], s["lh"]
        # place by baseline: distance from block top down to the first baseline
        to_baseline = (lh * size - (fm["a"] + fm["d"]) * size) / 2 + fm["a"] * size
        top = s["base"] - to_baseline
        left = x + s["lsb"]
        colour, is_grad = paint(s["fill"])
        style = [
            f"left:{pct(left, DW)}", f"top:{pct(top, DH)}",
            f"font-size:{cqw(size)}", f"font-weight:{s['fw']}",
            f"line-height:{lh}",
        ]
        if "\n" in s["t"]:
            # the breaks are already authored - never let the box re-wrap them
            style.append("white-space:pre")
        elif s["box"]:
            # the measured width is ink only; add the side bearings back or the
            # last word on each line wraps early
            style.append(f"width:{pct(s['box'] + size * 0.4, DW)}")
        else:
            style.append("white-space:pre")
        if is_grad:
            style.append(f"background-image:{colour}")
            cls = "t g"
        else:
            style.append(f"color:{colour}")
            cls = "t"
        body = html.escape(s["t"]).replace("\n", "<br>")
        nodes.append(f'<p class="{cls}" style="{";".join(style)}">{body}</p>')
        continue

    # --- real image at native resolution --------------------------------
    if l["image"]:
        info = IMAGES.get(l["image"])
        if info:
            src = info["file"].replace("public/", "./public/")
            style = (f"left:{pct(x, DW)};top:{pct(y, DH)};"
                     f"width:{pct(w, DW)};height:{pct(h, DH)}")
            nodes.append(f'<img class="m" loading="lazy" decoding="async" '
                         f'src="{src}" alt="" style="{style}">')
        continue

    # --- vector art, kept as vector --------------------------------------
    if l["tag"] == "path" and l.get("d") and (l.get("stroke") or l["fill"]):
        x0, y0, x1, y1 = l["vb"]
        vw, vh = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        f_css, f_grad = paint(l["fill"])
        fill_attr = "none" if (not l["fill"] or l["fill"] == "none" or f_grad) else l["fill"]
        stroke = l.get("stroke") or "none"
        sw = l.get("sw") or "1"
        style = (f"left:{pct(x, DW)};top:{pct(y, DH)};"
                 f"width:{pct(w, DW)};height:{pct(h, DH)}")
        nodes.append(
            f'<svg class="v" style="{style}" viewBox="{x0} {y0} {vw} {vh}" '
            f'preserveAspectRatio="none" fill="none" aria-hidden="true">'
            f'<path d="{html.escape(l["d"])}" fill="{fill_attr}" stroke="{stroke}" '
            f'stroke-width="{sw}"/></svg>')
        continue

    # --- flat shape ------------------------------------------------------
    fill, is_grad = paint(l["fill"])
    if not fill or fill in ("none",):
        continue
    style = [f"left:{pct(x, DW)}", f"top:{pct(y, DH)}",
             f"width:{pct(w, DW)}", f"height:{pct(h, DH)}",
             f"background:{fill}"]
    if l["tag"] == "circle":
        style.append("border-radius:50%")
    if l["opacity"]:
        style.append(f"opacity:{l['opacity']}")
    nodes.append(f'<i class="s" style="{";".join(style)}"></i>')

FONTS = "".join(
    f"@font-face{{font-family:SW;src:url('./public/assets/fonts/Switzer-{f}.otf') "
    f"format('opentype');font-weight:{wgt};font-display:block}}"
    for f, wgt in (("Light", 300), ("Regular", 400), ("Medium", 500),
                   ("Semibold", 600), ("Bold", 700)))

CSS = FONTS + """
*{box-sizing:border-box}
html{background:#000}
body{margin:0;background:#000;-webkit-font-smoothing:antialiased}
.canvas{position:relative;container-type:inline-size;width:min(100%,1728px);
 margin-inline:auto;aspect-ratio:1728/11981;background:#000;overflow:hidden;
 font-family:SW,system-ui,sans-serif}
.canvas>*{position:absolute;margin:0}
.t{letter-spacing:0;text-rendering:geometricPrecision}
.g{-webkit-background-clip:text;background-clip:text;color:transparent}
.m{display:block;object-fit:fill}
.s{display:block}\n.v{display:block;overflow:visible}
"""

out = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
       "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
       "<title>Mixar \u2014 AI-native 3D creation</title>\n"
       f"<style>{CSS}</style>\n</head>\n<body>\n"
       f'<div class="canvas">\n' + "\n".join(nodes) + "\n</div>\n</body>\n</html>\n")
(ROOT / "real.html").write_text(out, encoding="utf-8")

print(f"gradients resolved : {len(GRADS)}")
print(f"text elements      : {sum(1 for n in nodes if n.startswith('<p'))}")
print(f"images (native res): {sum(1 for n in nodes if n.startswith('<img'))}")
print(f"shape elements     : {sum(1 for n in nodes if n.startswith('<i'))}")
print(f"vector art (svg)   : {sum(1 for n in nodes if n.startswith('<svg'))}")
print(f"wrote              : real.html  ({len(out)/1024:.0f} KB)")
