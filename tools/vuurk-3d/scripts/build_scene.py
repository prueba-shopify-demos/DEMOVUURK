"""Construye la escena del prototipo VUURK y guarda out/vuurk_pouch_<name>.blend.

Uso: tools/vuurk-3d/run.sh build_scene.py
Determinista: todo sale de config.json y de semillas fijas.
"""
import math
import os
import random
import sys

import bmesh
import bpy
from mathutils import Euler, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vk_geom as G  # noqa: E402

cfg = G.load_config()
P = G.Pouch(cfg)


# ---------- Utilidades ----------

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = 'VUURK_Proto'
    scene.unit_settings.system = 'METRIC'
    return scene


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def principled(name, color, roughness, **inputs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    for key, value in inputs.items():
        bsdf.inputs[key].default_value = value
    return mat


def film_material():
    """Film satinado neutro (sin arte): capa de barniz suave, microrrugosidad
    y estrías de sellado en las costuras laterales (|x| > semiancho interior)."""
    mat = principled('VK_Film_Exterior_Neutro', (0.22, 0.22, 0.22), 0.38,
                     **{'Coat Weight': 0.4, 'Coat Roughness': 0.18})
    nt = mat.node_tree
    n = nt.nodes
    coord = n.new('ShaderNodeTexCoord')
    xyz = n.new('ShaderNodeSeparateXYZ')
    nt.links.new(coord.outputs['Object'], xyz.inputs['Vector'])

    def math_node(op, a, b=None):
        m = n.new('ShaderNodeMath')
        m.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                nt.links.new(v, m.inputs[i])
        return m.outputs[0]

    seal = math_node('GREATER_THAN', math_node('ABSOLUTE', xyz.outputs['X']), P.a)
    stripes = math_node('SINE', math_node('MULTIPLY', xyz.outputs['Z'], math.tau / 0.0012))
    crimp = math_node('MULTIPLY', stripes, seal)

    noise = n.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 2500.0
    nt.links.new(coord.outputs['Object'], noise.inputs['Vector'])
    micro = n.new('ShaderNodeBump')
    micro.inputs['Strength'].default_value = 0.04
    nt.links.new(noise.outputs['Fac'], micro.inputs['Height'])
    seal_bump = n.new('ShaderNodeBump')
    seal_bump.inputs['Strength'].default_value = 0.35
    nt.links.new(crimp, seal_bump.inputs['Height'])
    nt.links.new(micro.outputs['Normal'], seal_bump.inputs['Normal'])
    nt.links.new(seal_bump.outputs['Normal'], n['Principled BSDF'].inputs['Normal'])
    return mat


def mesh_object(name, verts, faces, materials, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    for mat in materials:
        mesh.materials.append(mat)
    return link(bpy.data.objects.new(name, mesh))


def grid_z():
    p = cfg['pouch']
    body_top = P.Zz - P.pinch - 0.004
    zs = [body_top * i / p['grid_z_body'] for i in range(p['grid_z_body'])]
    n = p['grid_z_top']
    zs += [body_top + (P.H - body_top) * i / n for i in range(n + 1)]
    return zs


# ---------- Bolsa: frente, trasera y fuelle ----------

def build_pouch(mat_out, mat_in):
    nx = cfg['pouch']['grid_x']
    xs = [-P.W / 2 + P.W * i / (nx - 1) for i in range(nx)]
    zs = grid_z()
    verts, sides, faces = [], [], []

    def panel(side):
        base = len(verts)
        for z in zs:
            for x in xs:
                # Costuras: frente y trasera separadas por seal_gap (sin caras coincidentes).
                verts.append((x, P.panel_y(x, z, side), z))
                sides.append(side)
        for j in range(len(zs) - 1):
            for i in range(nx - 1):
                a = base + j * nx + i
                quad = (a, a + 1, a + nx + 1, a + nx)
                faces.append(quad if side < 0 else quad[::-1])  # normales hacia afuera

    panel(-1)
    panel(+1)

    # Fuelle inferior: lente entre el borde inferior del frente y el de la trasera,
    # con el pliegue hacia adentro (sube en el centro).
    ns = 24
    base = len(verts)
    for k in range(ns + 1):
        s = -1.0 + 2.0 * k / ns
        for x in xs:
            d = P.half_depth(x, 0.0)
            verts.append((x, s * d, P.rise * (1.0 - s * s) * P.gx(x)))
            sides.append(0)
    for k in range(ns):
        for i in range(nx - 1):
            a = base + k * nx + i
            faces.append((a, a + nx, a + nx + 1, a + 1))  # normal hacia abajo

    obj = mesh_object('VK_Pouch', verts, faces, [mat_out, mat_in])
    obj['vk_note'] = 'Prototipo geométrico. Medidas provisionales (config.json).'
    solid = obj.modifiers.new('VK_Film', 'SOLIDIFY')
    solid.thickness = P.thick
    solid.offset = -1.0          # hacia adentro: la cara exterior no se mueve
    solid.material_offset = 1    # cáscara interior = material oscuro
    solid.use_rim = True
    solid.material_offset_rim = 1
    return obj, verts, sides


# ---------- Zipper a presión: dos perfiles que acompañan a cada labio ----------

def build_zipper(mat):
    r = cfg['zipper']['track_radius']
    seg = cfg['zipper']['ring_segments']
    nx = cfg['pouch']['grid_x']
    x0, x1 = -P.a + 0.001, P.a - 0.001
    xs = [x0 + (x1 - x0) * i / (nx - 1) for i in range(nx)]
    verts, sides, faces = [], [], []
    for side in (-1, 1):
        base = len(verts)
        for x in xs:
            # Centro del perfil pegado a la cara interior del labio.
            yc = side * max(r * 0.6, P.half_depth(x, P.Zz) - P.thick - r)
            for k in range(seg):
                t = 2 * math.pi * k / seg
                verts.append((x, yc + r * math.cos(t), P.Zz + r * math.sin(t)))
                sides.append(side)
        for i in range(nx - 1):
            for k in range(seg):
                a = base + i * seg + k
                b = base + i * seg + (k + 1) % seg
                faces.append((a, b, b + seg, a + seg))
    obj = mesh_object('VK_Zipper', verts, faces, [mat])
    return obj, verts, sides


# ---------- Shape keys + drivers: vk_open controla la apertura ----------

def add_open_keys(obj, rest, sides, ctrl):
    keys = P.keys
    obj.shape_key_add(name='Basis', from_mix=False)
    for k in range(1, keys + 1):
        vk_open = k / keys
        sk = obj.shape_key_add(name=f'vk_open_{k:02d}', from_mix=False)
        flat = []
        for (x, y, z), side in zip(rest, sides):
            flat.extend(P.deform(x, y, z, side, vk_open))
        sk.data.foreach_set('co', flat)
        # Peso triangular: entre dos claves vecinas se interpola linealmente.
        drv = sk.driver_add('value').driver
        drv.type = 'SCRIPTED'
        var = drv.variables.new()
        var.name = 'v'
        var.type = 'SINGLE_PROP'
        var.targets[0].id_type = 'OBJECT'
        var.targets[0].id = ctrl
        var.targets[0].data_path = '["vk_open"]'
        drv.expression = f'max(0.0, 1.0 - abs(v * {keys}.0 - {k}.0))'
        assert drv.is_simple_expression, 'el driver debe ser una expresión simple (sin autoejecución de Python)'


def build_control(scene):
    ctrl = link(bpy.data.objects.new('VK_Control', None))
    ctrl.empty_display_type = 'ARROWS'
    ctrl.empty_display_size = 0.03
    ctrl.location = (-P.W / 2 - 0.03, 0.0, P.Zz)
    ctrl['vk_open'] = 0.0
    ui = ctrl.id_properties_ui('vk_open')
    ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, step=1,
              description='Apertura del zipper: 0 cerrado, 1 abierto (izquierda → derecha)')
    a = cfg['animation']
    ctrl['vk_open'] = 0.0
    ctrl.keyframe_insert('["vk_open"]', frame=a['frame_start'])
    ctrl['vk_open'] = 1.0
    ctrl.keyframe_insert('["vk_open"]', frame=a['frame_end'])
    for fc in ctrl.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    scene.frame_start, scene.frame_end = a['frame_start'], a['frame_end']
    return ctrl


# ---------- Gummies ----------

def build_gummies(mat):
    g = cfg['gummies']
    sx, sy, sz = (v / 2 for v in g['size'])
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
    for v in bm.verts:
        # Forma genérica de gummy: elipsoide algo aplanado en la base.
        z = v.co.z
        v.co = Vector((v.co.x * sx, v.co.y * sy, (z if z > 0 else z * 0.75) * sz))
    mesh = bpy.data.meshes.new('VK_Gummy_Mesh')
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    mesh.materials.append(mat)

    coll = bpy.data.collections.new('VK_Gummies')
    bpy.context.scene.collection.children.link(coll)
    rng = random.Random(g['seed'])
    r_max = max(sx, sy, sz) * 1.1
    z_top = P.Zz - g['zone_below_zipper'][0]
    z_low = P.Zz - g['zone_below_zipper'][1]
    # Candidatos válidos (dentro del film cerrado), ordenados de arriba hacia abajo:
    # se llena primero la capa superior, que es la que se ve por la boca.
    candidates = []
    for _ in range(g['attempts']):
        x = rng.uniform(-P.a, P.a)
        z = rng.uniform(z_low, z_top - r_max * 0.5)
        s = rng.uniform(0.9, 1.1)
        rr = r_max * s
        if abs(x) > P.a - rr - 0.004:
            continue
        inner = min(P.half_depth(x + dx, z + dz) for dx in (-rr, 0, rr) for dz in (-rr * 0.7, 0, rr * 0.7))
        inner -= P.thick + 0.0008
        y_lim = inner - sy * s * 1.15
        if y_lim <= 0:
            continue
        candidates.append((z, x, rng.uniform(-y_lim, y_lim), s, rr))
    candidates.sort(reverse=True)
    placed = []
    for z, x, y, s, rr in candidates:
        if len(placed) >= g['count']:
            break
        if any((Vector((x, y, z)) - c).length < (rr + cr) * 0.78 for c, cr in placed):
            continue
        placed.append((Vector((x, y, z)), rr))
        obj = bpy.data.objects.new(f'VK_Gummy_{len(placed):02d}', mesh)
        obj.location = (x, y, z)
        obj.rotation_euler = Euler((rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0, math.tau)))
        obj.scale = (s, s, s)
        coll.objects.link(obj)
    return len(placed)


# ---------- Estudio: cámara fija, luces, fondo ----------

def build_studio(scene):
    c = cfg['camera']
    target = Vector((0.0, 0.0, P.H * c['target_z_ratio']))
    dist = c['frame_height'] * c['lens_mm'] / c['sensor_height_mm']
    e = math.radians(c['elevation_deg'])
    cam_data = bpy.data.cameras.new('VK_Camera')
    cam_data.lens = c['lens_mm']
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.sensor_height = c['sensor_height_mm']
    cam_data.clip_start, cam_data.clip_end = 0.05, 20.0
    cam = link(bpy.data.objects.new('VK_Camera', cam_data))
    cam.location = target + Vector((0.0, -math.cos(e), math.sin(e))) * dist
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.lock_location = cam.lock_rotation = cam.lock_scale = (True, True, True)
    scene.camera = cam

    def area(name, loc, power, size, size_y=None, aim=None, spread=180):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.size = power, size
        data.spread = math.radians(spread)  # haz acotado: no ilumina el piso
        data.shape = 'RECTANGLE'
        data.size_y = size_y if size_y is not None else size * 0.6
        obj = link(bpy.data.objects.new(name, data))
        obj.location = loc
        obj.rotation_euler = ((aim or target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
        return obj

    # Esquema de producto: softbox principal, relleno suave, cenital para el
    # interior, dos tiras de contorno detrás y un halo neutro en el fondo.
    area('VK_Key', (-0.5, -0.6, 0.45), 9, 0.7)
    area('VK_Fill', (0.6, -0.7, 0.2), 2.5, 0.9)
    area('VK_Top', (0.0, -0.15, 0.7), 4, 0.5)
    area('VK_Strip_L', (-0.35, 0.22, 0.3), 5, 0.08, 0.6, aim=Vector((0.0, 0.0, 0.34)), spread=40)
    area('VK_Strip_R', (0.35, 0.22, 0.3), 5, 0.08, 0.6, aim=Vector((0.0, 0.0, 0.34)), spread=40)
    area('VK_Backglow', (0.0, 0.25, 0.08), 1.0, 0.4, aim=Vector((0.0, 0.8, 0.6)), spread=60)

    world = bpy.data.worlds.new('VK_World')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.012, 0.012, 0.013, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
    scene.world = world

    # Fondo continuo (piso + curva + pared) gris oscuro neutro.
    mat = principled('VK_Backdrop', (0.025, 0.025, 0.027), 0.85)
    verts, faces = [], []
    prof = [(-0.8, 0.0)]
    for k in range(13):
        t = k / 12 * (math.pi / 2)
        prof.append((0.3 + 0.5 * math.sin(t), 0.5 - 0.5 * math.cos(t)))
    prof.append((0.8, 1.6))
    for y, z in prof:
        verts += [(-2.0, y, z), (2.0, y, z)]
    for k in range(len(prof) - 1):
        a = 2 * k
        faces.append((a, a + 1, a + 3, a + 2))
    mesh_object('VK_Backdrop', verts, faces, [mat])


def setup_render(scene):
    r = cfg['render']
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = r['samples']
    scene.cycles.seed = r['seed']
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.render.resolution_x = r['width']
    scene.render.resolution_y = r['height']
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0.0


def main():
    scene = reset_scene()
    mat_out = film_material()
    mat_in = principled('VK_Film_Interior', (0.018, 0.018, 0.02), 0.55)
    mat_zip = principled('VK_Zipper', (0.035, 0.035, 0.038), 0.28)
    mat_gum = principled('VK_Gummy', (0.055, 0.006, 0.014), 0.45,
                         **{'Subsurface Weight': 0.2, 'Subsurface Scale': 0.004})
    nt = mat_gum.node_tree
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 900.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.12
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], nt.nodes['Principled BSDF'].inputs['Normal'])

    ctrl = build_control(scene)
    pouch, rest, sides = build_pouch(mat_out, mat_in)
    add_open_keys(pouch, rest, sides, ctrl)
    zipper, zrest, zsides = build_zipper(mat_zip)
    add_open_keys(zipper, zrest, zsides, ctrl)
    n_gum = build_gummies(mat_gum)
    build_studio(scene)
    setup_render(scene)
    scene.frame_set(scene.frame_start)

    path = os.path.join(G.out_dir(), f"vuurk_pouch_{cfg['name']}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print(f'VK_BUILD verts_pouch={len(rest)} verts_zipper={len(zrest)} gummies={n_gum} keys={P.keys}')
    print(f'VK_BUILD saved={path}')


main()
