#!/usr/bin/env python3
"""Fold real.html into one self-contained page for hosting.

Images are resized to twice the size they are actually displayed at, so they
stay sharp when zoomed but the page fits the hosting ceiling. Switzer is
embedded so type renders correctly on any machine. Layout, spacing and colour
are untouched — only the pixel budget of the bitmaps changes.
"""
import base64
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORK = pathlib.Path("/private/tmp/claude-501/-Users-meh-Documents-Codex-2026-08-16-"
                    "figma-plugin-figma-openai-curated-remote/"
                    "23e9e5ab-6429-4f00-a12b-04d0ae01419d/scratchpad/realimg")
DW = 1728.0
RETINA = 1.6        # keep detail well past 100% zoom
CANVAS_MAX = 1728   # the page never renders wider than this

html_src = (ROOT / "real.html").read_text(encoding="utf-8")
layers = json.loads((ROOT / "tools/layers.json").read_text())

# widest on-page display width, in CSS px at full canvas, for each source file
display_px = {}
for l in layers["layers"]:
    if not l["image"]:
        continue
    info = layers["images"].get(l["image"])
    if not info:
        continue
    shown = l["w"] / DW * CANVAS_MAX
    name = pathlib.Path(info["file"]).name
    display_px[name] = max(display_px.get(name, 0), shown)

WORK.mkdir(parents=True, exist_ok=True)
saved_before = saved_after = 0
encoded = {}
for name, shown in display_px.items():
    src = ROOT / "public/assets/src" / name
    if not src.exists():
        continue
    native = layers["images"][src.stem]["pixels"][0]
    target = max(64, min(native, int(shown * RETINA)))
    # JPEG has no alpha, so anything with real transparency must stay PNG or it
    # gets composited onto white
    probe = subprocess.run(["sips", "-g", "hasAlpha", str(src)],
                           capture_output=True, text=True).stdout
    has_alpha = "hasAlpha: yes" in probe
    if has_alpha:
        out = WORK / (src.stem + ".png")
        subprocess.run(["sips", "-Z", str(target), str(src), "--out", str(out)],
                       check=True, capture_output=True)
        mime = "image/png"
    else:
        out = WORK / (src.stem + ".jpg")
        subprocess.run(["sips", "-Z", str(target), "-s", "format", "jpeg",
                        "-s", "formatOptions", "86", str(src), "--out", str(out)],
                       check=True, capture_output=True)
        mime = "image/jpeg"
    saved_before += src.stat().st_size
    saved_after += out.stat().st_size
    encoded[name] = (mime, out.read_bytes())

def data_uri(name):
    mime, blob = encoded[name]
    return f"data:{mime};base64,{base64.b64encode(blob).decode()}"

# swap image sources for their inline copies
def repl_img(m):
    name = pathlib.Path(m.group(1)).name
    return f'src="{data_uri(name)}"' if name in encoded else m.group(0)
page = re.sub(r'src="([^"]*public/assets/src/[^"]+)"', repl_img, html_src)

# embed only the weights the page actually uses
for face, weight in (("Regular", 400), ("Medium", 500)):
    blob = (ROOT / f"public/assets/fonts/Switzer-{face}.otf").read_bytes()
    uri = "data:font/otf;base64," + base64.b64encode(blob).decode()
    page = page.replace(f"url('./public/assets/fonts/Switzer-{face}.otf')", f"url('{uri}')")
# drop the weights we did not inline so nothing 404s
page = re.sub(r"@font-face\{font-family:SW;src:url\('\./public/assets/fonts/[^']+'\)[^}]*\}", "", page)

# the artifact host supplies <head>, so hand it body content with entities only
body = re.search(r'<body>(.*)</body>', page, re.S).group(1)
style = re.search(r'<style>(.*?)</style>', page, re.S).group(1)
title = "<title>Mixar &#8212; AI-native 3D creation</title>"
doc = title + "\n<style>" + style + "</style>\n" + body
doc = doc.encode("ascii", "xmlcharrefreplace").decode("ascii")

out_file = WORK.parent / "mixarweb-real.html"
out_file.write_text(doc, encoding="ascii")
print(f"images   : {len(encoded)}  {saved_before/1e6:.1f} MB -> {saved_after/1e6:.1f} MB")
print(f"page     : {out_file}  {len(doc)/1e6:.2f} MB")
