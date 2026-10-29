"""Silueta del envase (solo alfa) para cada fotograma de la secuencia desktop.

Uso: tools/vuurk-3d/run.sh render_matte.py out/vuurk_pouch_<name>.blend
Salida: out/<name>/matte/png/matte_XX.png (escala de grises: 255 = envase).

No vuelve a renderizar el envase: misma escena, cámara y apertura que
render_sequence.py, pero con el fondo oculto, película transparente y un material
plano sin luz. Solo se guarda la cobertura (alfa) del envase, el zipper y las
gummies, que recorta los fotogramas existentes (assets/vuurk-unzip-berry-d-XX.webp).
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

cfg = G.load_config()
seq = cfg['sequence']
scene = bpy.context.scene
out = G.out_dir(cfg['name'], 'matte', 'png')
n = seq['frames']

scene.render.resolution_x, scene.render.resolution_y = seq['width'], seq['height']
scene.render.resolution_percentage = 100
scene.render.use_border = False
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.cycles.samples = 32  # suficiente para el antialiasing del borde
scene.cycles.use_adaptive_sampling = False
scene.cycles.use_denoising = False
scene.cycles.max_bounces = 0
scene.render.use_persistent_data = True

bpy.data.objects['VK_Backdrop'].hide_render = True
flat = bpy.data.materials.new('VK_Matte')
flat.use_nodes = True
flat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0, 0, 0, 1)
bpy.context.view_layer.material_override = flat

for i in range(n):
    vk_open = i / (n - 1)
    scene.frame_set(round(scene.frame_start + vk_open * (scene.frame_end - scene.frame_start)))
    path = os.path.join(out, f'matte_{i + 1:02d}.png')
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f'VK_MATTE frame={i + 1:02d} vk_open={vk_open:.4f}', flush=True)
