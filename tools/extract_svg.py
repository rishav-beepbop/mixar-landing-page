#!/usr/bin/env python3
"""Recover the real layers from the Figma SVG export.

The export is not a flat picture: every text layer is a <path> whose id is the
literal string, and every photo/screenshot is an original-resolution bitmap in
<defs>, painted through a <pattern>. This pulls both out so the page can be
rebuilt from real elements instead of one flattened PNG.

Writes:
  public/assets/src/*            the 37 source bitmaps, native resolution
  tools/layers.json              every layer with text, geometry and fill
"""
import base64
import json
import pathlib
import re
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG = ROOT / "public/assets/mixar-landing-updated.svg"
IMG_OUT = ROOT / "public/assets/src"
MANIFEST = ROOT / "tools/layers.json"

# The export is authored at 1728x11981 but the viewBox is 591x4096.
DESIGN_W, DESIGN_H = 1728, 11981
VIEW_W, VIEW_H = 590.759, 4096.0
SX, SY = DESIGN_W / VIEW_W, DESIGN_H / VIEW_H

raw = SVG.read_text(errors="replace")

# ---------------------------------------------------------------- bitmaps ---
IMG_OUT.mkdir(parents=True, exist_ok=True)
images = {}
pattern = re.compile(
    r'<image id="(?P<id>[^"]+)"(?: data-name="(?P<name>[^"]*)")?'
    r'[^>]*width="(?P<w>[\d.]+)" height="(?P<h>[\d.]+)"'
    r'[^>]*xlink:href="data:image/(?P<fmt>[a-z]+);base64,(?P<data>[A-Za-z0-9+/=]+)"'
)
for m in pattern.finditer(raw):
    ident = m.group("id")
    blob = base64.b64decode(m.group("data"))
    path = IMG_OUT / f"{ident}.{m.group('fmt')}"
    path.write_bytes(blob)
    images[ident] = {
        "file": f"public/assets/src/{path.name}",
        "figma_name": m.group("name") or "",
        "pixels": [int(float(m.group("w"))), int(float(m.group("h")))],
        "bytes": len(blob),
    }

# pattern id -> image id, so a fill can be traced back to its bitmap
pattern_to_image = dict(
    re.findall(r'<pattern id="([^"]+)"[^>]*>\s*<use xlink:href="#([^"]+)"', raw)
)

# ----------------------------------------------------------------- layers ---
lean = re.sub(r'(base64,)[A-Za-z0-9+/=]+', r'\1', raw)
tree = ET.fromstring(lean)
NS = "{http://www.w3.org/2000/svg}"

num = re.compile(r'-?\d*\.?\d+(?:e-?\d+)?')


def parse_transform(text):
    """Return (a, d, e, f) of the matrix — only scale/translate are used here."""
    a = d = 1.0
    e = f = 0.0
    for kind, args in re.findall(r'(matrix|translate|scale)\(([^)]*)\)', text or ""):
        v = [float(x) for x in num.findall(args)]
        if kind == "matrix" and len(v) == 6:
            a, d, e, f = a * v[0], d * v[3], e + a * v[4], f + d * v[5]
        elif kind == "translate":
            e += a * v[0]
            f += d * (v[1] if len(v) > 1 else 0.0)
        elif kind == "scale":
            a *= v[0]
            d *= v[1] if len(v) > 1 else v[0]
    return a, d, e, f


ARGC = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}
TOKEN = re.compile(r'([MmLlHhVvCcSsQqTtAaZz])|(-?\d*\.?\d+(?:[eE]-?\d+)?)')


def path_bbox(d_attr):
    """Bbox by walking the path properly — H/V take one value and Z none, so
    splitting the numbers into alternating pairs misreads every coordinate."""
    tokens = [(c, n) for c, n in TOKEN.findall(d_attr)]
    xs, ys = [], []
    cx = cy = sx = sy = 0.0
    i, cmd = 0, None
    while i < len(tokens):
        if tokens[i][0]:
            cmd = tokens[i][0]
            i += 1
            if cmd in "Zz":
                cx, cy = sx, sy
                continue
        if cmd is None:
            break
        upper = cmd.upper()
        need = ARGC[upper]
        if i + need > len(tokens):
            break
        args = [float(tokens[i + k][1]) for k in range(need)]
        i += need
        rel = cmd.islower()

        if upper == "H":
            cx = cx + args[0] if rel else args[0]
        elif upper == "V":
            cy = cy + args[0] if rel else args[0]
        elif upper == "A":
            cx = cx + args[5] if rel else args[5]
            cy = cy + args[6] if rel else args[6]
        else:
            # every remaining command ends on its final pair; intermediate
            # control points are included too, which only widens the box
            for k in range(0, need, 2):
                px = cx + args[k] if rel else args[k]
                py = cy + args[k + 1] if rel else args[k + 1]
                xs.append(px)
                ys.append(py)
            cx = cx + args[need - 2] if rel else args[need - 2]
            cy = cy + args[need - 1] if rel else args[need - 1]
            if upper == "M":
                sx, sy = cx, cy
        xs.append(cx)
        ys.append(cy)
        if upper == "M":
            cmd = "l" if rel else "L"

    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def repair(text):
    """Figma writes each UTF-8 byte as its own XML entity, so an em dash
    arrives as the three characters 0xE2,0x80,0x94. Put the bytes back."""
    if not text:
        return text
    try:
        fixed = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    # U+2028/2029 are Figma's explicit line breaks; keep them as newlines
    return fixed.replace("\u2028", "\n").replace("\u2029", "\n")


layers = []


# these subtrees define paint sources and clips - they are never drawn directly
NON_DRAWN = {"defs", "mask", "clipPath", "pattern", "filter", "linearGradient",
             "radialGradient", "symbol", "marker"}


def walk(node, ctm):
    if node.tag.replace(NS, "") in NON_DRAWN:
        return
    a, d, e, f = ctm
    ta, td, te, tf = parse_transform(node.get("transform"))
    ctm = (a * ta, d * td, e + a * te, f + d * tf)
    a, d, e, f = ctm

    tag = node.tag.replace(NS, "")
    ident = node.get("id")

    box = None
    if tag == "path" and node.get("d"):
        bb = path_bbox(node.get("d"))
        if bb:
            box = (bb[0] * a + e, bb[1] * d + f, bb[2] * a + e, bb[3] * d + f)
    elif tag in ("rect", "image"):
        x, y = float(node.get("x", 0)), float(node.get("y", 0))
        w, h = float(node.get("width", 0)), float(node.get("height", 0))
        box = (x * a + e, y * d + f, (x + w) * a + e, (y + h) * d + f)
    elif tag == "circle":
        cx, cy = float(node.get("cx", 0)), float(node.get("cy", 0))
        r = float(node.get("r", 0))
        box = ((cx - r) * a + e, (cy - r) * d + f, (cx + r) * a + e, (cy + r) * d + f)

    # Unnamed elements matter: Figma leaves section backgrounds and dividers
    # without a layer name, and dropping them loses whole page backdrops.
    if box and tag != "clipPath":
        ident = ident or f"_{tag}{len(layers)}"
        fill = node.get("fill", "")
        img = None
        pm = re.match(r'url\(#(.+)\)', fill or "")
        if pm:
            img = pattern_to_image.get(pm.group(1))
        # convert viewBox units to design pixels
        x0, y0, x1, y1 = box
        layers.append({
            "tag": tag,
            "id": repair(ident),
            "x": round(x0 * SX, 2),
            "y": round(y0 * SY, 2),
            "w": round((x1 - x0) * SX, 2),
            "h": round((y1 - y0) * SY, 2),
            "fill": fill,
            "opacity": node.get("opacity"),
            "image": img,
            "d": node.get("d") if tag == "path" else None,
            "vb": [round(v, 3) for v in box],
            "stroke": node.get("stroke"),
            "sw": node.get("stroke-width"),
        })

    for child in node:
        walk(child, ctm)


walk(tree, (1.0, 1.0, 0.0, 0.0))

MANIFEST.write_text(json.dumps({"images": images, "layers": layers}, indent=1))

texty = [l for l in layers if l["tag"] == "path" and re.search(r'[A-Za-z]{3}', l["id"])
         and not re.match(r'^(Rectangle|Group|Vector|Ellipse|Frame|Line|Union|Subtract)', l["id"])]
print(f"bitmaps extracted : {len(images)}  -> {IMG_OUT}")
print(f"layers mapped     : {len(layers)}")
print(f"  text layers     : {len(texty)}")
print(f"  image-filled    : {sum(1 for l in layers if l['image'])}")
print(f"manifest          : {MANIFEST}")
