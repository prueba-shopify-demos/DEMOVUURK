"""Renderiza los estados de prueba de config.json["states"] (Cycles CPU).

Uso: tools/vuurk-3d/run.sh render_states.py out/vuurk_pouch_<name>.blend
Salida: out/<name>/vk_<name>_open_XXX.png y out/<name>/render_times.json.
Cada estado se obtiene moviendo la línea de tiempo: vk_open está animado
(fotograma 0 → 0, fotograma 100 → 1), así que el render usa la misma
cadena driver → shape keys que la animación.
"""
import json
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

cfg = G.load_config()
scene = bpy.context.scene
ctrl = bpy.data.objects['VK_Control']
out = G.out_dir(cfg['name'])
times = []
total = time.perf_counter()
for o in cfg['states']:
    frame = round(scene.frame_start + o * (scene.frame_end - scene.frame_start))
    scene.frame_set(frame)
    assert abs(ctrl['vk_open'] - o) < 1e-6, (o, ctrl['vk_open'])
    scene.render.filepath = os.path.join(out, f"vk_{cfg['name']}_open_{round(o * 100):03d}.png")
    t = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    dt = time.perf_counter() - t
    times.append({'state': o, 'frame': frame, 'seconds': round(dt, 2)})
    print(f'VK_RENDER state={o} frame={frame} seconds={dt:.2f}')
summary = {'states': times, 'total_seconds': round(time.perf_counter() - total, 2),
           'resolution': [scene.render.resolution_x, scene.render.resolution_y],
           'samples': scene.cycles.samples, 'device': scene.cycles.device,
           'denoiser': scene.cycles.denoiser if scene.cycles.use_denoising else None}
with open(os.path.join(out, 'render_times.json'), 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)
print('VK_RENDER total_seconds', summary['total_seconds'])
