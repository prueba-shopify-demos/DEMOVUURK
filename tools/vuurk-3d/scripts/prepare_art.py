"""Prepara la textura frontal a partir de la imagen oficial del envase.

Uso: python3 tools/vuurk-3d/scripts/prepare_art.py
Recorta la imagen fuente (config.json["art"]["source"]) a la silueta del envase
(art.bbox_px) sin reescalar ni retocar: el recorte se mapea 1:1 sobre el panel
frontal (UV ortográfica). El original no se modifica.
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

art = G.load_config()['art']
src = os.path.join(G.ROOT, art['source'])
dst = os.path.join(G.ROOT, art['front'])
os.makedirs(os.path.dirname(dst), exist_ok=True)
im = Image.open(src).convert('RGBA')
x0, y0, x1, y1 = art['bbox_px']
crop = im.crop((x0, y0, x1, y1))
crop.save(dst)
print(f'VK_ART {src} {im.size} → {dst} {crop.size} (aspecto {crop.height / crop.width:.4f})')
