"""Convierte los sprites de render_gummies.py a WebP con transparencia para el theme.

Uso: python3 tools/vuurk-3d/scripts/export_gummies.py [--install]
Salida: out/gummies/webp/vuurk-gummy-NN.webp (160×160, gummy centrada).
--install los copia a assets/.
"""
import glob
import os
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

SIZE = 160  # el reproductor las muestra a ≤ 80 px CSS: nítidas en pantallas 2×
src = sorted(glob.glob(os.path.join(G.out_dir('gummies', 'png'), 'gummy_*.png')))
dst = G.out_dir('gummies', 'webp')
assert src, 'faltan sprites: correr render_gummies.py'

written = []
for i, path in enumerate(src, start=1):
    im = Image.open(path).convert('RGBA')
    # Recorte cuadrado centrado en la gummy: el centro de rotación queda en el centro.
    l, t, r, b = im.getbbox()
    side = max(r - l, b - t) + 8
    cx, cy = (l + r) // 2, (t + b) // 2
    box = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
    out = os.path.join(dst, f'vuurk-gummy-{i:02d}.webp')
    im.crop(box).resize((SIZE, SIZE), Image.LANCZOS).save(out, 'WEBP', quality=86, method=6)
    written.append(out)

sizes = [os.path.getsize(p) for p in written]
print(f'VK_WEBP gummies: {len(written)} archivos, {sum(sizes) / 1024:.0f} KB, máx {max(sizes) / 1024:.1f} KB')

if '--install' in sys.argv:
    assets = os.path.join(G.ROOT, '..', '..', 'assets')
    for p in written:
        shutil.copyfile(p, os.path.join(assets, os.path.basename(p)))
    print(f'VK_WEBP copiados {len(written)} archivos a {os.path.normpath(assets)}')
