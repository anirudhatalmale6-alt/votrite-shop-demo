"""Builds ../index.html from template.html: inlines the icons and the photos (as data URIs) so the
demo is one self-contained file that also works when opened straight from a download."""
import base64, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
P = {  # 24x24 stroke icons (lucide style)
    'globe': '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/>',
    'user': '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    'users': '<circle cx="9" cy="8" r="3.5"/><path d="M2 20a7 7 0 0 1 14 0"/><circle cx="17" cy="9" r="2.6"/><path d="M17 14a5 5 0 0 1 5 5"/>',
    'menu': '<path d="M4 6h16M4 12h16M4 18h16"/>',
    'pin': '<path d="M12 22s7-6.4 7-12a7 7 0 0 0-14 0c0 5.6 7 12 7 12z"/><circle cx="12" cy="10" r="2.6"/>',
    'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'search': '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    'bag': '<path d="M5 8h14l-1 13H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    'tag': '<path d="M3 12V4h8l10 10-8 8z"/><circle cx="7.5" cy="8.5" r="1.4"/>',
    'store': '<path d="M3 9l2-5h14l2 5M4 9v11h16V9M3 9h18M9 20v-6h6v6"/>',
    'bars': '<path d="M5 20v-6M10 20V10M15 20V6M20 20V3"/>',
    'infinity': '<path d="M12 12c-2-2.5-4-4-6-4a4 4 0 0 0 0 8c2 0 4-1.5 6-4zm0 0c2 2.5 4 4 6 4a4 4 0 0 0 0-8c-2 0-4 1.5-6 4z"/>',
    'check': '<path d="M4 12.5l5 5L20 6.5"/>',
    'phone': '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>',
    'target': '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/>',
    'shield': '<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M8.5 12l2.5 2.5 4.5-5"/>',
    'alert': '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
    'star': '<path d="M12 2.5l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4 6.1 20.5l1.2-6.5L2.5 9.4l6.6-.9z"/>',
    'cup': '<path d="M4 8h13v6a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM17 10h1.5a2.5 2.5 0 0 1 0 5H17M8 2v3M12 2v3"/>',
    'cake': '<path d="M4 21V12h16v9M2 21h20M4 16c2 1.5 4 1.5 6 0s4-1.5 6 0 3 1 4 0M12 12V8M12 5.5a1.5 1.5 0 0 0 0-3"/>',
    'bed': '<path d="M2 18V6M2 14h20v4M22 14v-3a3 3 0 0 0-3-3h-8v6M6 11h.01"/>',
    'pool': '<path d="M2 18c2 1.5 4 1.5 6 0s4-1.5 6 0 4 1.5 6 0M8 15V5a2 2 0 0 1 4 0M16 15V5a2 2 0 0 0-4 0M8 9h8"/>',
    'shirt': '<path d="M8 3l-5 3 2 5 3-1v11h8V10l3 1 2-5-5-3a4 4 0 0 1-8 0z"/>',
    'pizza': '<path d="M12 22L3 6a14 14 0 0 1 18 0z"/><circle cx="10" cy="10" r="1.2"/><circle cx="14" cy="13" r="1.2"/>',
    'fork': '<path d="M7 2v8a2 2 0 0 0 4 0V2M9 10v12M17 2c-2 0-3 3-3 7h3v13"/>',
    'sofa': '<path d="M4 12V8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v4M2 12a2 2 0 0 1 4 0v2h12v-2a2 2 0 0 1 4 0v6H2zM5 18v2M19 18v2"/>',
    'leaf': '<path d="M5 21c0-9 5-15 16-17-1 11-7 16-16 17zM5 21l8-8"/>',
    'lamp': '<path d="M8 2h8l3 8H5zM12 10v10M8 22h8"/>',
    'sparkle': '<path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2zM19 3v4M17 5h4"/>',
    'scissors': '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.5 7.5L20 19M8.5 16.5L20 5"/>',
    'house': '<path d="M3 11l9-8 9 8M5 9.5V21h14V9.5M10 21v-6h4v6"/>',
    'plane': '<path d="M2 13l8-2 4-8h2l-2 8 6 1 2-2h1l-1 4 1 4h-1l-2-2-6 1 2 8h-2l-4-8-8-2z"/>',
    'wrench': '<path d="M14.5 6.5a4.5 4.5 0 0 0 5.8 5.8l-8.8 8.8a2.4 2.4 0 0 1-3.4-3.4l8.8-8.8A4.5 4.5 0 0 0 14.5 6.5zM14 3.5l3 3"/>',
    'grid': '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'facebook': '<path d="M15 3h-2.5A3.5 3.5 0 0 0 9 6.5V10H6v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h2z"/>',
    'instagram': '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>',
    'xlogo': '<path d="M4 4l16 16M20 4L4 20"/>',
    'youtube': '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="M10 9l5 3-5 3z"/>',
    'linkedin': '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 10v7M8 7h.01M12 17v-4a2 2 0 0 1 4 0v4M12 10v7"/>',
}
svg = lambda n: f'<svg class="i" viewBox="0 0 24 24">{P[n]}</svg>'

html = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
imgs = {}
for f in sorted(os.listdir(os.path.join(HERE, 'img'))):
    if f.endswith('.jpg'):
        imgs[f[:-4]] = 'data:image/jpeg;base64,' + base64.b64encode(open(os.path.join(HERE, 'img', f), 'rb').read()).decode()

html = html.replace('@@ICONJSON@@', json.dumps({k: svg(k) for k in P}))
html = html.replace('@@IMGJSON@@', json.dumps(imgs))
html = re.sub(r'@@IMG:(\w+)@@', lambda m: imgs[m.group(1)], html)
html = re.sub(r'@@(\w+)@@', lambda m: svg(m.group(1)), html)
assert '@@' not in html
open(os.path.join(HERE, '..', 'index.html'), 'w', encoding='utf-8').write(html)
print('index.html', len(html) // 1024, 'KB')
