"""Renderiza sprites de gummies con fondo transparente para la capa animada del
reproductor Unzip (assets/vuurk-gummy-NN.webp). No toca el envase.

Uso: tools/vuurk-3d/run.sh render_gummies.py
Salida: out/gummies/png/gummy_NN.png (RGBA). Convertir con export_gummies.py.
Forma: la de build_gummies() en build_scene.py (superelipsoide con base más plana).
Material: la misma goma de frutos rojos, con el grano de azúcar resuelto para primer plano.
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
SIZE = 320  # px por sprite
# (variante de malla, rotación en grados): vistas distintas para que no se repitan.
VIEWS = [(0, (25, 10, 15)), (1, (-35, 20, 70)), (2, (60, -15, 30)),
         (0, (-70, 35, 120)), (1, (15, -55, 200)), (2, (-20, 75, 300))]


def gummy_mesh(rng, k):
    g = cfg['gummies']
    sx, sy, sz = (v / 2 for v in g['size'])
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=5, radius=1.0)
    ph = [rng.uniform(0, math.tau) for _ in range(3)]
    for v in bm.verts:
        d = v.co.normalized()
        pn = (abs(d.x) ** 3 + abs(d.y) ** 3 + abs(d.z) ** 3) ** (1 / 3)
        d = d / pn
        bump = 1.0 + 0.035 * math.sin(5 * d.x + ph[0]) * math.sin(4 * d.y + ph[1]) + 0.02 * math.sin(6 * d.z + ph[2])
        z = d.z if d.z > 0 else d.z * 0.7
        v.co = Vector((d.x * sx, d.y * sy, z * sz)) * bump
    mesh = bpy.data.meshes.new(f'VK_Gummy_Mesh_{k}')
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    return mesh


def gummy_material():
    # En primer plano el grano de azúcar tiene que leerse: cristales (Voronoi)
    # en relieve y una capa de barniz que brilla solo en sus caras.
    mat = bpy.data.materials.new('VK_Gummy')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.09, 0.004, 0.022, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.6
    for key, value in {'Subsurface Weight': 0.35, 'Subsurface Scale': 0.0008,
                       'Subsurface Radius': (1.0, 0.1, 0.18),
                       'Coat Weight': 0.5, 'Coat IOR': 1.55}.items():
        bsdf.inputs[key].default_value = value
    # Coordenadas del objeto (metros): la escala del grano es independiente del tamaño.
    coords = nt.nodes.new('ShaderNodeTexCoord')
    crystals = nt.nodes.new('ShaderNodeTexVoronoi')
    crystals.inputs['Scale'].default_value = 2600.0
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 900.0
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.45
    bump.inputs['Distance'].default_value = 0.0002
    fine = nt.nodes.new('ShaderNodeBump')
    fine.inputs['Strength'].default_value = 0.2
    nt.links.new(coords.outputs['Object'], crystals.inputs['Vector'])
    nt.links.new(coords.outputs['Object'], noise.inputs['Vector'])
    nt.links.new(crystals.outputs['Distance'], bump.inputs['Height'])
    nt.links.new(noise.outputs['Fac'], fine.inputs['Height'])
    nt.links.new(fine.outputs['Normal'], bump.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Coat Normal'])
    # Rugosidad del barniz variable por cristal: destellos dispersos.
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.55, (0.08, 0.08, 0.08, 1)
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.75, (0.45, 0.45, 0.45, 1)
    nt.links.new(crystals.outputs['Color'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Coat Roughness'])
    return mat


def light(name, loc, power, size, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.size, data.color = power, size, color
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.scene.collection.objects.link(obj)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    rng = random.Random(cfg['gummies']['seed'])
    mat = gummy_material()
    meshes = [gummy_mesh(rng, k) for k in range(3)]
    for m in meshes:
        m.materials.append(mat)

    cam_data = bpy.data.cameras.new('VK_Camera')
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = max(cfg['gummies']['size']) * 1.25
    cam = bpy.data.objects.new('VK_Camera', cam_data)
    cam.location = (0, -0.3, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    scene.collection.objects.link(cam)
    scene.camera = cam

    # Misma lógica de estudio que el envase: principal arriba a la izquierda,
    # relleno suave y contorno cálido para separarlas del fondo oscuro.
    light('VK_Key', (-0.12, -0.15, 0.14), 0.9, 0.08)
    light('VK_Fill', (0.15, -0.18, -0.02), 0.25, 0.2)
    light('VK_Rim', (0.06, 0.12, 0.1), 1.2, 0.05, (1.0, 0.62, 0.38))

    world = bpy.data.worlds.new('VK_World')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.02, 0.02, 0.022, 1)
    scene.world = world

    r = cfg['render']
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    # Sin denoiser: alisa el grano de azúcar. Con 256 muestras el ruido no se nota a 320 px.
    scene.cycles.samples = 256
    scene.cycles.seed = r['seed']
    scene.cycles.use_denoising = False
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = SIZE
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'

    out = G.out_dir('gummies', 'png')
    obj = bpy.data.objects.new('VK_Gummy', meshes[0])
    scene.collection.objects.link(obj)
    for i, (k, rot) in enumerate(VIEWS, start=1):
        obj.data = meshes[k]
        obj.rotation_euler = Euler([math.radians(a) for a in rot])
        scene.render.filepath = os.path.join(out, f'gummy_{i:02d}.png')
        bpy.ops.render.render(write_still=True)
        print(f'VK_GUMMY {scene.render.filepath}')


main()
