"""Builds an editable PowerPoint from out/<page>/layout.json: one 16:9 slide per screen of each page
(1280 x 720 px = 13.333 x 7.5 in). Text stays text, solid shapes stay shapes, photos/gradients/icons
are pictures that can be replaced. usage: build_pptx.py OUT_DIR FILE.pptx"""
import io, json, os, re, sys
from PIL import Image
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn

OUT, DEST = sys.argv[1], sys.argv[2]
PAGES = ["home", "browse", "deals", "biz-1", "advertise", "about", "help", "contact"]
PX = 9525  # EMU per CSS px at 96 dpi
SLIDE_H = 720

def rgba(s):
    m = re.match(r"rgba?\(([^)]+)\)", s or "")
    if not m: return None
    v = [float(x) for x in m.group(1).replace("/", ",").split(",")]
    return (int(v[0]), int(v[1]), int(v[2]), v[3] if len(v) > 3 else 1.0)

def set_alpha(fill_fore, a):
    if a >= 0.999: return
    clr = fill_fore._xFill if hasattr(fill_fore, "_xFill") else None

def font_for(fam, weight):
    if "Caveat" in fam: return "Segoe Print", False
    return "Arial", weight >= 600

prs = Presentation()
prs.slide_width, prs.slide_height = Emu(1280 * PX), Emu(720 * PX)
blank = prs.slide_layouts[6]

def add_box(sl, b, y0, y1):
    r = b["r"]; top, bot = max(r["y"], y0), min(r["y"] + r["h"], y1)
    if bot - top < 0.5 or r["w"] < 0.5: return
    full = top == r["y"] and bot == r["y"] + r["h"]
    fill = rgba(b["bg"]) if b["bg"] else None
    bw, uniform = b["bw"], len(set(b["bw"])) == 1 and b["bw"][0] > 0
    if fill or uniform:
        shp = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if b["radius"] and full else MSO_SHAPE.RECTANGLE,
                                  Emu(int(r["x"] * PX)), Emu(int((top - y0) * PX)), Emu(int(r["w"] * PX)), Emu(int((bot - top) * PX)))
        if b["radius"] and full:
            shp.adjustments[0] = min(0.5, b["radius"] / max(1, min(r["w"], r["h"])))
        if fill and fill[3] > 0:
            shp.fill.solid(); shp.fill.fore_color.rgb = RGBColor(*fill[:3])
            if fill[3] < 0.999:
                sf = shp.fill._xPr.find(qn("a:solidFill"))[0]
                a = sf.makeelement(qn("a:alpha"), {"val": str(int(fill[3] * 100000))}); sf.append(a)
        else:
            shp.fill.background()
        if uniform:
            c = rgba(b["bc"][0]); shp.line.color.rgb = RGBColor(*c[:3]); shp.line.width = Emu(int(bw[0] * PX))
        else:
            shp.line.fill.background()
        shp.shadow.inherit = False
        shp.text_frame.text = ""
    if not uniform:   # one-sided borders become lines
        x, w = r["x"], r["w"]
        for i, (wd, col) in enumerate(zip(bw, b["bc"])):
            if wd <= 0: continue
            c = rgba(col)
            if not c or c[3] == 0: continue
            if i == 0 and r["y"] >= y0: seg = (x, r["y"] + wd / 2, x + w, r["y"] + wd / 2)
            elif i == 2 and r["y"] + r["h"] <= y1: seg = (x, r["y"] + r["h"] - wd / 2, x + w, r["y"] + r["h"] - wd / 2)
            elif i == 1: seg = (x + w - wd / 2, top, x + w - wd / 2, bot)
            elif i == 3: seg = (x + wd / 2, top, x + wd / 2, bot)
            else: continue
            ln = sl.shapes.add_connector(1, Emu(int(seg[0] * PX)), Emu(int((seg[1] - y0) * PX)), Emu(int(seg[2] * PX)), Emu(int((seg[3] - y0) * PX)))
            ln.line.color.rgb = RGBColor(*c[:3]); ln.line.width = Emu(int(wd * PX))

def add_shot(sl, s, d, y0, y1):
    if s.get("skip"): return
    f = os.path.join(d, f"s{s['id']}.png")
    if not os.path.exists(f): return
    r = s["r"]; top, bot = max(r["y"], y0), min(r["y"] + r["h"], y1)
    if bot - top < 0.5: return
    im = Image.open(f)
    sc = im.height / r["h"]
    if top != r["y"] or bot != r["y"] + r["h"]:
        im = im.crop((0, int((top - r["y"]) * sc), im.width, int((bot - r["y"]) * sc)))
    if im.getbbox() is None: return   # fully transparent
    if im.width * im.height > 250000:   # large layers: 1.25x the screen size is plenty
        k = 0.625; im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
    buf = io.BytesIO()
    if im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 255 and im.width * im.height > 40000:
        im.convert("RGB").save(buf, "JPEG", quality=86)   # opaque photos: much smaller file
    else:
        im.save(buf, "PNG")
    buf.seek(0)
    sl.shapes.add_picture(buf, Emu(int(r["x"] * PX)), Emu(int((top - y0) * PX)), Emu(int(r["w"] * PX)), Emu(int((bot - top) * PX)))

def add_text(sl, t, y0):
    r, runs = t["r"], t["runs"]
    sz = max(x["size"] for x in runs if "size" in x)
    if t["oneLine"]:
        w = r["w"] * 1.12 + 8
        x = r["x"] if t["align"] in ("left", "start", "justify") else (r["x"] + r["w"] / 2 - w / 2 if t["align"] == "center" else r["x"] + r["w"] - w)
    else:
        x, w = t["box"]["x"], t["box"]["w"] * 1.02
    tb = sl.shapes.add_textbox(Emu(int(x * PX)), Emu(int((r["y"] - y0) * PX)), Emu(int(w * PX)), Emu(int(max(r["h"], sz) * PX)))
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT, "end": PP_ALIGN.RIGHT}.get(t["align"], PP_ALIGN.LEFT)
    if not t["oneLine"]: p.line_spacing = Pt(t["lh"] * 0.75)
    for rn in runs:
        if rn.get("br"): p.add_line_break(); continue
        run = p.add_run(); run.text = rn["t"]
        fnt = run.font; name, bold = font_for(rn["family"], rn["weight"])
        fnt.name, fnt.bold, fnt.italic, fnt.size = name, bold, rn["italic"], Pt(round(rn["size"] * 0.75 * 2) / 2)
        c = rgba(rn["color"]); fnt.color.rgb = RGBColor(*c[:3])
        if rn["ls"]: run._r.get_or_add_rPr().set("spc", str(int(rn["ls"] * 75)))

for key in PAGES:
    d = os.path.join(OUT, key); L = json.load(open(os.path.join(d, "layout.json")))
    H, cuts = L["height"], sorted(set(L["cuts"]))
    y, slices = 0, []
    while y < H - 20:
        cand = [c for c in cuts if y + 260 < c <= y + SLIDE_H]
        nxt = max(cand) if cand else y + SLIDE_H
        slices.append((y, min(nxt, H))); y = nxt
    for i, (y0, y1) in enumerate(slices):
        sl = prs.slides.add_slide(blank)
        sl.background.fill.solid(); sl.background.fill.fore_color.rgb = RGBColor(0xF3, 0xF6, 0xFB)
        items = [("b", b) for b in L["boxes"]] + [("s", s) for s in L["shots"]] + [("t", t) for t in L["texts"]]
        for kind, it in sorted(items, key=lambda k: k[1]["o"]):
            r = it["r"]
            if kind == "t":
                if y0 - 2 <= r["y"] < y1 - 2: add_text(sl, it, y0)
            elif kind == "b" and r["w"] >= 1279 and r["h"] >= H - 2:
                continue   # the page body itself: the slide background already has its colour
            elif r["y"] < y1 and r["y"] + r["h"] > y0:
                (add_box if kind == "b" else lambda a, b_, c, e: add_shot(a, b_, d, c, e))(sl, it, y0, y1)
        sl.notes_slide.notes_text_frame.text = f"{L['title']} page, part {i + 1} of {len(slices)} (shopvotritemobil.com)"
    print(key, len(slices), "slides")

prs.core_properties.title = "Votrite Mobil Shop - website pages"
prs.save(DEST)
print("saved", DEST, len(prs.slides), "slides")
