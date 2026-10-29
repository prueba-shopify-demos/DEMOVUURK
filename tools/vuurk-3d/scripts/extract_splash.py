"""Extrae la salpicadura naranja/amarilla del arte oficial para el fondo de la sección
Unzip en escritorio (assets/vuurk-splash.webp, con transparencia).

Uso: python3 tools/vuurk-3d/scripts/extract_splash.py [--install]
Fuente: config.json["art"]["source"] (no versionada). No redibuja ni recolorea:
la salpicadura está sobre film negro, así que el alfa sale de la luminancia y el
color se recupera dividiendo por el alfa (sobre fondo oscuro se ve igual que en el
envase). Solo se conservan tonos naranja/amarillo: quedan fuera los frutos, las
hojas, los textos y los brillos grises del film.
"""
import colorsys
import os
import shutil
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

# Zona de la salpicadura principal en la fuente de 1024×1536: por encima de los
# frutos (y > 1060) y por debajo de «Burn clean.» (y < 610), dentro del envase.
BOX = (92, 610, 900, 1060)
FEATHER = 220  # px de fundido suave en el borde inferior (corte sobre los frutos)
# Extremo izquierdo (el que queda junto al envase): el recorte del arte corta la
# salpicadura en vertical. En vez de fundir ese corte, el extremo se rehace en
# diagonal, en la dirección de la salpicadura (abajo-izquierda → arriba-derecha):
# la textura se deshace antes en sus zonas oscuras, sin contorno recto.
TIP_X = 60  # inicio del extremo en la base (px del recorte)
TIP_SLOPE = 0.45  # cuánto retrocede el extremo hacia arriba (px por px)
TIP_FADE = 200  # largo del extremo
HUE = (-0.03, 0.16)  # rojo (desde 349°) → naranja → amarillo (58°)

art = G.load_config()['art']
src = Image.open(os.path.join(G.ROOT, art['source'])).convert('RGB').crop(BOX)
w, h = src.size
out = Image.new('RGBA', (w, h))
sp, op = src.load(), out.load()
for y in range(h):
    t = min(1.0, (h - 1 - y) / FEATHER)
    edge_y = t * t * (3 - 2 * t)  # smoothstep: sin línea de corte visible
    for x in range(w):
        r, g, b = sp[x, y]
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if hh > 0.5:
            hh -= 1.0
        if not (HUE[0] <= hh <= HUE[1]) or s < 0.35:
            continue
        start = TIP_X + TIP_SLOPE * (h - 1 - y)
        u = min(1.0, max(0.0, (x - start) / TIP_FADE))
        edge_x = (u * u * (3 - 2 * u)) ** (1 + 1.5 * (1 - v))
        a = v * min(1.0, (s - 0.35) / 0.25) * edge_y * edge_x
        if a < 0.02:
            continue
        # Color sin el negro de fondo: sobre negro con este alfa da el píxel original.
        op[x, y] = (min(255, round(r / v)), min(255, round(g / v)), min(255, round(b / v)), round(a * 255))

dst = G.out_dir('splash')
path = os.path.join(dst, 'vuurk-splash.webp')
out.save(path, 'WEBP', quality=82, method=6)
print(f'VK_SPLASH {w}×{h} {os.path.getsize(path) / 1024:.0f} KB → {path}')

if '--install' in sys.argv:
    target = os.path.join(G.ROOT, '..', '..', 'assets', 'vuurk-splash.webp')
    shutil.copyfile(path, target)
    print(f'VK_SPLASH copiado a {os.path.normpath(target)}')
