"""Validación del prototipo en los estados de config.json["states"].

Uso: tools/vuurk-3d/run.sh validate.py out/vuurk_pouch_<name>.blend [-- --images]
Sin --images solo hace comprobaciones geométricas (no renderiza nada).
Con --images compara además los PNG de out/proto/ (generados por render_states.py).
Escribe out/proto/validation.json.
"""
import json
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

cfg = G.load_config()
P = G.Pouch(cfg)
scene = bpy.context.scene
cam = scene.camera
ctrl = bpy.data.objects['VK_Control']
pouch = bpy.data.objects['VK_Pouch']
states = cfg['states']
frame_of = lambda o: round(scene.frame_start + o * (scene.frame_end - scene.frame_start))  # noqa: E731


def evaluated_coords(obj):
    """Malla evaluada por Blender (drivers + shape keys). El Solidify está
    desactivado en viewport durante la validación: se mide la cara exterior."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    mesh = ev.to_mesh()
    co = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get('co', co)
    ev.to_mesh_clear()
    return co.reshape(-1, 3)


def opening_profile(co, rest):
    """Separación frente-trasera en el borde superior, por posición x."""
    top = rest[:, 2] >= P.H - 1e-9
    front = top & (rest[:, 1] < 0)
    back = top & (rest[:, 1] > 0)
    xs = rest[front, 0]
    order = np.argsort(xs)
    xs = xs[order]
    gap_y = co[back][np.argsort(rest[back, 0]), 1] - co[front][order, 1]
    return xs, gap_y


def camera_rays_hits(nx=160, ny=90):
    dg = bpy.context.evaluated_depsgraph_get()
    frame = [cam.matrix_world @ v for v in cam.data.view_frame(scene=scene)]
    # view_frame: 0 arriba-der, 1 abajo-der, 2 abajo-izq, 3 arriba-izq
    tr, br, bl, tl = frame
    origin = cam.matrix_world.translation
    hits = 0
    for j in range(ny):
        fy = (j + 0.5) / ny
        left = tl.lerp(bl, fy)
        right = tr.lerp(br, fy)
        for i in range(nx):
            p = left.lerp(right, (i + 0.5) / nx)
            ok, _, _, _, obj, _ = scene.ray_cast(dg, origin, (p - origin).normalized())
            if ok and obj.name.startswith('VK_Gummy'):
                hits += 1
    return hits, nx * ny


def main():
    images = '--images' in G.script_args()
    pouch.modifiers['VK_Film'].show_viewport = False  # no se guarda el .blend
    rest =np.array([v.co[:] for v in pouch.data.vertices])
    rigid = rest[:, 2] < P.z_hinge
    report = {'z_hinge_m': P.z_hinge, 'zipper_z_m': P.Zz, 'states': []}
    cam_mat0 = None
    base_co = None
    for o in states:
        scene.frame_set(frame_of(o))
        vk = ctrl['vk_open']
        co = evaluated_coords(pouch)
        if base_co is None:
            base_co = co
        xs, gap = opening_profile(co, rest)
        if o == states[0]:
            gap0 = gap
        open_x = xs[gap - gap0 > 0.003]  # abierto: 3 mm más de separación que cerrado
        hits, total = camera_rays_hits()
        cm = [list(r) for r in cam.matrix_world]
        if cam_mat0 is None:
            cam_mat0 = cm
        state = {
            'state': o,
            'frame': scene.frame_current,
            'vk_open': round(vk, 4),
            'rigid_zone_max_disp_m': float(np.abs(co[rigid] - base_co[rigid]).max()),
            'max_gap_mm': round(float(gap.max()) * 1000, 2),
            'open_from_x_mm': round(float(open_x.min()) * 1000, 1) if len(open_x) else None,
            'open_to_x_mm': round(float(open_x.max()) * 1000, 1) if len(open_x) else None,
            'gummy_pixels_pct': round(100.0 * hits / total, 2),
            'camera_unchanged': cm == cam_mat0,
        }
        report['states'].append(state)
        print('VK_STATE', json.dumps(state))

    if images:
        out = G.out_dir(cfg['name'])
        imgs = []
        for o in states:
            img = bpy.data.images.load(os.path.join(out, f"vk_{cfg['name']}_open_{round(o * 100):03d}.png"))
            w, h = img.size
            px = np.array(img.pixels[:]).reshape(h, w, 4)[::-1, :, :3]  # fila 0 = arriba
            imgs.append(px)
        # Fila de la imagen que corresponde a la bisagra (borde de la zona rígida).
        scene.frame_set(frame_of(0))
        hinge = world_to_camera_view(scene, cam, Vector((0.0, P.panel_y(0.0, P.z_hinge, -1), P.z_hinge)))
        row = int((1.0 - hinge.y) * h) + 4
        report['rigid_zone_from_row'] = row
        for o, px in zip(states, imgs):
            d = np.abs(px[row:] - imgs[0][row:]) * 255.0
            for s in report['states']:
                if s['state'] == o:
                    s['rigid_zone_px_mean_diff_8bit'] = round(float(d.mean()), 3)
                    s['rigid_zone_px_p99_diff_8bit'] = round(float(np.percentile(d, 99)), 2)
        # Hoja de contacto vertical con los cinco estados.
        sheet = np.concatenate(imgs, axis=0)
        sh = bpy.data.images.new('vk_contact', w, sheet.shape[0], alpha=False)
        rgba = np.concatenate([sheet, np.ones(sheet.shape[:2] + (1,))], axis=2)[::-1]
        sh.pixels.foreach_set(rgba.astype(np.float32).ravel())
        sh.filepath_raw = os.path.join(out, f"vk_{cfg['name']}_contact.png")
        sh.file_format = 'PNG'
        sh.save()

    path = os.path.join(G.out_dir(cfg['name']), 'validation.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print('VK_VALIDATION', path)


main()
