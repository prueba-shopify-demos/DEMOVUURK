"""Convierte la secuencia PNG a WebP para el theme (Python del sistema + Pillow).

Uso: python3 tools/vuurk-3d/scripts/export_webp.py [--install]
Salida: out/<name>/seq/webp/<prefix>-d-XX.webp (escritorio, tamaño completo)
        out/<name>/seq/webp/<prefix>-m-XX.webp (móvil 4:5, recorte central)
--install copia los WebP a assets/ del theme (no borra ni pisa otros archivos).
"""
import glob
import os
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

cfg = G.load_config()
seq = cfg['sequence']
src = G.out_dir(cfg['name'], 'seq', 'png')
dst = G.out_dir(cfg['name'], 'seq', 'webp')
prefix = seq['theme_prefix']
mw, mh = seq['mobile_crop']
frames = sorted(glob.glob(os.path.join(src, 'frame_*.png')))
assert len(frames) == seq['frames'], f'faltan fotogramas: {len(frames)}/{seq["frames"]}'

written = []
for i, path in enumerate(frames, start=1):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    left = (w - mw) // 2
    for kind, img in (('d', im), ('m', im.crop((left, h - mh, left + mw, h)))):
        out = os.path.join(dst, f'{prefix}-{kind}-{i:02d}.webp')
        img.save(out, 'WEBP', quality=seq['webp_quality'], method=6)
        written.append(out)

for kind in ('d', 'm'):
    sizes = [os.path.getsize(p) for p in written if f'-{kind}-' in p]
    print(f'VK_WEBP {kind}: {len(sizes)} archivos, {sum(sizes) / 1024:.0f} KB, máx {max(sizes) / 1024:.0f} KB')

if '--install' in sys.argv:
    assets = os.path.join(G.ROOT, '..', '..', 'assets')
    for p in written:
        target = os.path.join(assets, os.path.basename(p))
        shutil.copyfile(p, target)
    print(f'VK_WEBP copiados {len(written)} archivos a {os.path.normpath(assets)}')
