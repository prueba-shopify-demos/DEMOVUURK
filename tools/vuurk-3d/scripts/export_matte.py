"""Convierte las siluetas de render_matte.py a WebP (solo alfa) para el theme.

Uso: python3 tools/vuurk-3d/scripts/export_matte.py [--install]
Salida: out/<name>/matte/webp/vuurk-unzip-berry-matte-XX.webp, recortadas al
rectángulo común a los 24 estados. El origen del recorte (px del fotograma de
1200×640) se imprime y debe coincidir con MATTE_ORIGIN en vuurk-unzip-player.js.
--install las copia a assets/.
"""
import glob
import os
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

PAD = 2
cfg = G.load_config()
src = sorted(glob.glob(os.path.join(G.out_dir(cfg['name'], 'matte', 'png'), 'matte_*.png')))
assert len(src) == cfg['sequence']['frames'], f'faltan siluetas: {len(src)}'
alphas = [Image.open(p).getchannel('A') for p in src]
boxes = [a.getbbox() for a in alphas]
w, h = alphas[0].size
x0, y0 = max(0, min(b[0] for b in boxes) - PAD), max(0, min(b[1] for b in boxes) - PAD)
x1, y1 = min(w, max(b[2] for b in boxes) + PAD), min(h, max(b[3] for b in boxes) + PAD)

dst = G.out_dir(cfg['name'], 'matte', 'webp')
written = []
for i, a in enumerate(alphas, start=1):
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    img.putalpha(a)
    out = os.path.join(dst, f'vuurk-unzip-berry-matte-{i:02d}.webp')
    img.crop((x0, y0, x1, y1)).save(out, 'WEBP', lossless=True, quality=100, method=6)
    written.append(out)

sizes = [os.path.getsize(p) for p in written]
print(f'VK_MATTE origen=({x0}, {y0}) tamaño={x1 - x0}×{y1 - y0} '
      f'{len(written)} archivos, {sum(sizes) / 1024:.0f} KB, máx {max(sizes) / 1024:.1f} KB')

if '--install' in sys.argv:
    assets = os.path.join(G.ROOT, '..', '..', 'assets')
    for p in written:
        shutil.copyfile(p, os.path.join(assets, os.path.basename(p)))
    print(f'VK_MATTE copiados {len(written)} archivos a {os.path.normpath(assets)}')
