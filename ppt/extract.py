"""Walks each demo page at 1280 px wide and records what PowerPoint needs to rebuild it:
text blocks (with runs and styles), solid boxes, and picture layers (photos, gradients, icons,
rotated groups) captured as transparent PNGs. Output: out/<page>/layout.json + PNGs.
usage: extract.py INDEX_HTML OUT_DIR"""
import json, os, sys
from playwright.sync_api import sync_playwright

SRC, OUT = sys.argv[1], sys.argv[2]
PAGES = [("home", "Home"), ("browse", "Businesses"), ("deals", "Deals"), ("biz-1", "Business page"),
         ("advertise", "Advertise"), ("about", "About"), ("help", "Help"), ("contact", "Contact & Price List")]

JS = r"""
() => {
  const out = {texts: [], boxes: [], shots: [], lines: []};
  let sid = 0, ord = 0;
  const sy = window.scrollY;
  const R = el => { const r = el.getBoundingClientRect(); return {x: r.left, y: r.top + sy, w: r.width, h: r.height}; };
  const vis = el => { if (el.closest('details:not([open])') && el.tagName !== 'DETAILS' && !el.closest('summary')) return false;
                      const c = getComputedStyle(el); if (c.display === 'none' || c.visibility === 'hidden' || +c.opacity === 0) return false;
                      const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const pseudo = el => ['::before', '::after'].some(p => { const c = getComputedStyle(el, p).content; return c && c !== 'none' && c !== 'normal'; });
  const rotated = el => { const t = getComputedStyle(el).transform; if (!t || t === 'none') return false;
                          const m = t.match(/matrix\(([^)]+)\)/); if (!m) return true; const v = m[1].split(',').map(Number); return Math.abs(v[1]) > 1e-3; };
  const clipText = el => getComputedStyle(el).webkitBackgroundClip === 'text' || getComputedStyle(el).backgroundClip === 'text';
  const INLINE = new Set(['B','STRONG','I','EM','SMALL','SPAN','A','LABEL','BR','U']);
  const hasBg = c => c.backgroundColor && c.backgroundColor !== 'rgba(0, 0, 0, 0)' && c.backgroundColor !== 'transparent';
  const done = new WeakSet();
  const mark = el => { el.setAttribute('data-shot', ++sid); return sid; };

  function shot(el, mode) { const id = mark(el); out.shots.push({id, mode, r: R(el), tag: el.tagName, o: ++ord}); }

  // inline child that should be merged into the parent's text runs
  const mergeable = el => { if (!INLINE.has(el.tagName)) return false; const c = getComputedStyle(el);
    return c.display === 'inline' && !hasBg(c) && c.backgroundImage === 'none' && !(parseFloat(c.borderTopWidth) > 0) && ![...el.querySelectorAll('svg')].some(v => !v.innerHTML.includes('lgV')); };

  function runs(el, acc) {
    for (const n of el.childNodes) {
      if (n.nodeType === 3) {
        const t = n.textContent.replace(/\s+/g, ' ');
        if (t.trim() === '' && t !== ' ') continue;
        const c = getComputedStyle(el);
        let color = c.color; if (clipText(el) || color === 'rgba(0, 0, 0, 0)') color = 'rgb(255, 194, 26)';
        acc.push({t: c.textTransform === 'uppercase' ? t.toUpperCase() : t, color, size: parseFloat(c.fontSize), weight: +c.fontWeight || 400,
                  italic: c.fontStyle === 'italic', family: c.fontFamily, ls: parseFloat(c.letterSpacing) || 0});
      } else if (n.nodeType === 1) {
        if (n.tagName === 'svg' && n.innerHTML.includes('lgV')) { done.add(n); const c = getComputedStyle(el);
          acc.push({t: 'V', color: 'rgb(42, 212, 107)', size: parseFloat(c.fontSize), weight: +c.fontWeight || 400, italic: false, family: c.fontFamily, ls: 0}); continue; }
        if (n.tagName === 'BR') acc.push({br: true});
        else if (mergeable(n) || (clipText(n) && getComputedStyle(n).display === 'inline')) { done.add(n); runs(n, acc); }
      }
    }
  }
  const directText = el => [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());

  function walk(el) {
    if (done.has(el) || !vis(el)) return;
    const tag = el.tagName, c = getComputedStyle(el);
    if (['SCRIPT','STYLE','TEMPLATE','OPTION'].includes(tag)) return;
    if (el.id === 'toast') return;
    if (tag === 'svg' || tag === 'IMG') { shot(el, 'whole'); return; }
    if (rotated(el)) { shot(el, 'whole'); return; }
    const bgImg = c.backgroundImage !== 'none' && !clipText(el);
    if (bgImg || pseudo(el) || c.webkitMaskImage !== 'none' && c.webkitMaskImage) {
      // decorative descendants (no text, no icons) are captured in the same picture
      const plain = d => { for (let a = d.parentElement; a && a !== el; a = a.parentElement) if (a.textContent.trim() || a.querySelector('svg')) return false; return true; };
      for (const d of el.querySelectorAll('*')) if (plain(d) && !d.textContent.trim() && !d.querySelector('svg') && d.tagName !== 'svg' && !['INPUT','SELECT','TEXTAREA','BUTTON'].includes(d.tagName) && !d.closest('svg')) { done.add(d); d.setAttribute('data-keep', '1'); }
      shot(el, 'bg');
    } else if (hasBg(c) || parseFloat(c.borderTopWidth) > 0 || parseFloat(c.borderLeftWidth) > 0 || parseFloat(c.borderBottomWidth) > 0 || parseFloat(c.borderRightWidth) > 0) {
      const bw = ['Top','Right','Bottom','Left'].map(s => parseFloat(c['border' + s + 'Width']) || 0);
      const bc = ['Top','Right','Bottom','Left'].map(s => c['border' + s + 'Color']);
      out.boxes.push({o: ++ord, r: R(el), bg: hasBg(c) ? c.backgroundColor : null, radius: parseFloat(c.borderTopLeftRadius) || 0, bw, bc});
    }
    if (['INPUT','TEXTAREA','SELECT'].includes(tag)) {
      const r = R(el), pl = parseFloat(c.paddingLeft), pt = parseFloat(c.paddingTop);
      let t = tag === 'SELECT' ? el.options[el.selectedIndex].text : (el.value || el.placeholder || '');
      const color = (tag !== 'SELECT' && !el.value) ? 'rgb(140, 150, 168)' : c.color;
      if (tag === 'SELECT') t += '   \u25BE';
      const fit = Math.floor((r.w - pl * 2) / (parseFloat(c.fontSize) * 0.52)); if (t.length > fit) t = t.slice(0, fit - 1).trimEnd() + '\u2026';
      if (t) out.texts.push({o: ++ord, r: {x: r.x + pl, y: r.y + pt, w: r.w - pl * 2, h: parseFloat(c.lineHeight) || parseFloat(c.fontSize) * 1.3},
        runs: [{t, color, size: parseFloat(c.fontSize), weight: +c.fontWeight || 400, italic: false, family: c.fontFamily, ls: 0}],
        align: 'left', lh: parseFloat(c.lineHeight) || parseFloat(c.fontSize) * 1.3, oneLine: true});
      return;
    }
    if (directText(el)) {
      const acc = []; runs(el, acc);
      while (acc.length && !acc[0].br && !acc[0].t.trim()) acc.shift();
      if (acc.length && !acc[0].br) acc[0].t = acc[0].t.replace(/^ /, '');
      while (acc.length && !acc[acc.length - 1].br && !acc[acc.length - 1].t.trim()) acc.pop();
      if (acc.length && !acc[acc.length - 1].br) acc[acc.length - 1].t = acc[acc.length - 1].t.replace(/ $/, '');
      // rect of the text itself (not the padded box)
      const rg = document.createRange(); let rr = null;
      for (const n of el.childNodes) {
        if (n.nodeType === 1 && !done.has(n) && n.tagName !== 'BR') continue;
        rg.selectNodeContents(n); const b = rg.getBoundingClientRect(); if (!b.width) continue;
        rr = rr ? {l: Math.min(rr.l, b.left), t: Math.min(rr.t, b.top), r: Math.max(rr.r, b.right), b: Math.max(rr.b, b.bottom)} : {l: b.left, t: b.top, r: b.right, b: b.bottom};
      }
      if (rr && acc.length) {
        let lh = parseFloat(c.lineHeight); if (isNaN(lh)) lh = parseFloat(c.fontSize) * 1.2;
        const lines = Math.round((rr.b - rr.t) / lh);
        const box = el.getBoundingClientRect(), pl = parseFloat(c.paddingLeft), pr = parseFloat(c.paddingRight);
        out.texts.push({o: ++ord, r: {x: rr.l, y: rr.t + sy, w: rr.r - rr.l, h: rr.b - rr.t}, box: {x: box.left + pl, w: box.width - pl - pr},
          runs: acc, align: c.textAlign, lh, oneLine: lines <= 1});
      }
    }
    for (const ch of el.children) walk(ch);
  }
  walk(document.body);
  return out;
}
"""

# hides everything except the element being captured (and, for 'bg', its decorative descendants)
HIDE = """([id, mode]) => {
  const st = document.createElement('style'); st.id = '__shot';
  st.textContent = mode === 'whole'
    ? `*{visibility:hidden!important} [data-shot="${id}"], [data-shot="${id}"] *{visibility:visible!important}`
    : `*{visibility:hidden!important} [data-shot="${id}"], [data-shot="${id}"] [data-keep]{visibility:visible!important} [data-shot="${id}"]{color:transparent!important;-webkit-text-fill-color:transparent!important}`;
  document.head.appendChild(st);
  document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent';
}"""
UNHIDE = """() => { document.getElementById('__shot').remove(); document.documentElement.style.background = ''; document.body.style.background = ''; }"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=2)
    for key, title in PAGES:
        d = os.path.join(OUT, key); os.makedirs(d, exist_ok=True)
        pg.goto("file://" + SRC + "#" + key); pg.wait_for_timeout(1500)
        pg.add_style_tag(content="header{position:relative!important} .toast{display:none!important} html{scroll-behavior:auto!important}")
        pg.wait_for_timeout(200)
        data = pg.evaluate(JS)
        data["height"] = pg.evaluate("document.documentElement.scrollHeight")
        data["title"] = title
        # cut points: tops of major blocks
        data["cuts"] = pg.evaluate("""() => [...document.querySelectorAll('.view.on > *, .view.on section, .view.on .sec-h, .view.on .panels, .view.on .grid, .view.on .deals, .view.on .cities, .view.on .cta, .view.on .plans, .view.on .why, .view.on .bpage, .view.on .card, .view.on details, .view.on .contact, .view.on .two, .view.on .vals, .view.on .biz, .view.on .plan, .view.on .rev, .view.on .val, .view.on .strip, .view.on .band, .discblk, footer, .reviews, .prods')]
            .filter(e => e.getBoundingClientRect().height > 0).map(e => Math.round(e.getBoundingClientRect().top + scrollY) - 16)""")
        for s in data["shots"]:
            r = s["r"]
            pg.evaluate(HIDE, [s["id"], s["mode"]])
            clip = {"x": max(r["x"], 0), "y": max(r["y"], 0), "width": min(r["w"], 1280 - max(r["x"], 0)), "height": r["h"]}
            if clip["width"] > 0.5 and clip["height"] > 0.5:
                pg.screenshot(path=os.path.join(d, f"s{s['id']}.png"), clip=clip, full_page=True, omit_background=True)
                s["r"] = {"x": clip["x"], "y": clip["y"], "w": clip["width"], "h": clip["height"]}
            else:
                s["skip"] = True
            pg.evaluate(UNHIDE)
        json.dump(data, open(os.path.join(d, "layout.json"), "w"))
        print(key, "texts", len(data["texts"]), "boxes", len(data["boxes"]), "shots", len(data["shots"]), "height", data["height"])
    b.close()
