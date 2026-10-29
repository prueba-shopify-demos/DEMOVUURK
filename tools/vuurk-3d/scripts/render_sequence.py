"""Secuencia para el reproductor Shopify: N fotogramas, vk_open = i / (N - 1).

Uso: tools/vuurk-3d/run.sh render_sequence.py out/vuurk_pouch_<name>.blend
Salida: out/<name>/seq/png/frame_XX.png y out/<name>/seq/meta.json.

Optimización: el fotograma 1 (cerrado) se renderiza completo. En los demás
solo se renderiza la franja superior (boca + sombra de la solapa, hasta
`region_below_hinge` por debajo de la bisagra). El resto se toma del
fotograma 1, que es exactamente la misma geometría inmóvil; la unión se
suaviza en `feather_px` filas. No se mezclan fotografías distintas.
"""
import json
import os
import sys
import time

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

cfg = G.load_config()
P = G.Pouch(cfg)
seq = cfg['sequence']
scene = bpy.context.scene
cam = scene.camera
ctrl = bpy.data.objects['VK_Control']
out = G.out_dir(cfg['name'], 'seq', 'png')
n = seq['frames']
W, H = seq['width'], seq['height']

scene.render.resolution_x, scene.render.resolution_y = W, H
scene.cycles.samples = seq['samples']
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = seq['adaptive_threshold']
scene.render.use_persistent_data = True


def cam_uv(x, y, z):
    v = world_to_camera_view(scene, cam, Vector((x, y, z)))
    return v.x, v.y  # y desde abajo


def frame_for(vk_open):
    return round(scene.frame_start + vk_open * (scene.frame_end - scene.frame_start))


def pixels(path):
    img = bpy.data.images.load(path)
    px = np.empty(W * H * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(H, W, 4)  # fila 0 = abajo


def save(px, path):
    img = bpy.data.images.new('vk_seq', W, H, alpha=False)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


# Franja que cambia: desde la parte superior hasta debajo de la bisagra.
z_region = P.z_hinge - seq['region_below_hinge']
_, v_region = cam_uv(0.0, -P.half_depth(0.0, z_region), z_region)
row0 = max(0, int(v_region * H) - 2)            # primera fila (desde abajo) renderizada
feather = seq['feather_px']

times = []
t_all = time.perf_counter()
base_path = os.path.join(out, 'frame_01.png')
base = None
for i in range(n):
    vk_open = i / (n - 1)
    scene.frame_set(frame_for(vk_open))
    path = os.path.join(out, f'frame_{i + 1:02d}.png')
    t = time.perf_counter()
    if i == 0:
        scene.render.use_border = False
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        base = pixels(path)
    else:
        scene.render.use_border = True
        scene.render.use_crop_to_border = False
        scene.render.border_min_x, scene.render.border_max_x = 0.0, 1.0
        scene.render.border_min_y, scene.render.border_max_y = row0 / H, 1.0
        tmp = os.path.join(out, '_region.png')
        scene.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        region = pixels(tmp)
        os.remove(tmp)
        alpha = np.zeros((H, 1, 1), dtype=np.float32)
        ramp = np.clip((np.arange(H) - row0) / max(1, feather), 0.0, 1.0)
        alpha[:, 0, 0] = ramp
        comp = base * (1.0 - alpha) + region * alpha
        comp[..., 3] = 1.0
        save(comp, path)
    dt = time.perf_counter() - t
    times.append(round(dt, 2))
    print(f'VK_SEQ frame={i + 1:02d} vk_open={vk_open:.4f} seconds={dt:.1f}', flush=True)

# Posición del zipper en la imagen (para ubicar el control en el theme).
pts = [cam_uv(x, -P.half_depth(x, P.Zz), P.Zz) for x in (-P.a, 0.0, P.a)]
mw, mh = seq['mobile_crop']
ox = (W - mw) / 2
meta = {
    'frames': n,
    'size': [W, H],
    'region_from_row_top': H - row0,
    'zipper_desktop': {'left': pts[0][0], 'right': pts[2][0], 'top': 1.0 - pts[1][1]},
    'zipper_mobile_crop': {
        'left': (pts[0][0] * W - ox) / mw, 'right': (pts[2][0] * W - ox) / mw,
        'top': (1.0 - pts[1][1]) * H / mh},
    'seconds': times,
    'total_seconds': round(time.perf_counter() - t_all, 1),
}
with open(os.path.join(G.out_dir(cfg['name'], 'seq'), 'meta.json'), 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2)
print('VK_SEQ total_seconds', meta['total_seconds'])
