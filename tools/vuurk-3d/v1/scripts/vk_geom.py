"""Geometría paramétrica del doypack VUURK (prototipo).

Funciones puras, sin bpy: las usan build_scene.py y validate.py.
Ejes: X ancho (izquierda → derecha vista desde la cámara), Y profundidad
(frente en -Y, mirando a la cámara), Z alto (base en z = 0).
`side` = -1 frente, +1 trasera, 0 sin deformación (base).
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config():
    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as f:
        return json.load(f)


def out_dir(*parts):
    path = os.path.join(ROOT, 'out', *parts)
    os.makedirs(path, exist_ok=True)
    return path


def script_args():
    return sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def clamp(x, lo=0.0, hi=1.0):
    return min(hi, max(lo, x))


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3.0 - 2.0 * t)


class Pouch:
    def __init__(self, cfg):
        p = cfg['pouch']
        o = cfg['opening']
        self.W = p['width']
        self.H = p['height']
        self.half_gusset = p['gusset'] / 2.0
        self.rise = p['gusset_rise']
        self.a = self.W / 2.0 - p['side_seal']          # semiancho interior (sin costuras)
        self.Zz = self.H - p['zipper_from_top']           # altura del zipper
        self.z_hinge = self.Zz - p['hinge_below_zipper']  # por debajo: zona rígida
        self.hinge_blend = p['hinge_blend']
        self.pinch = p['pinch_length']
        self.lip_gap = p['lip_gap']
        self.seal_gap = p['seal_gap']
        self.ridge = p['zipper_ridge']
        self.thick = p['film_thickness']
        self.keys = o['keys']
        self.front_angle = math.radians(o['front_angle_deg'])
        self.back_angle = math.radians(o['back_angle_deg'])
        self.lens_power = o['lens_power']
        self.full_at = o['full_amplitude_at']

    # ---------- Forma en reposo (cerrada) ----------

    def gx(self, x):
        """Perfil horizontal: 1 en el centro, 0 en las costuras laterales."""
        q = 1.0 - (x / self.a) ** 2
        return q ** 0.4 if q > 0 else 0.0

    def half_depth(self, x, z):
        """Mitad del espesor de la bolsa llena (distancia del film al plano medio)."""
        t = clamp(z / self.H)
        body = self.half_gusset * (0.55 + 0.45 * (1.0 - t) ** 2)
        pinch = 1.0 - smoothstep(self.Zz - self.pinch, self.Zz, z)
        return self.seal_gap + self.gx(x) * max(body * pinch, self.lip_gap)

    def ridge_offset(self, x, z):
        """Relieve del zipper visible a través del film."""
        return self.ridge * self.gx(x) * math.exp(-((z - self.Zz) / 0.0018) ** 2)

    def panel_y(self, x, z, side):
        return side * (self.half_depth(x, z) + self.ridge_offset(x, z))

    # ---------- Apertura ----------

    def u(self, x):
        """Posición normalizada a lo largo del zipper: 0 izquierda, 1 derecha."""
        return clamp((x + self.a) / (2.0 * self.a))

    def opening(self, x, vk_open):
        """Apertura local 0..1. Ranura fijada en la costura izquierda y en el
        frente del cierre (u = vk_open): forma de lente que avanza a la derecha."""
        if vk_open <= 0.0:
            return 0.0
        u = self.u(x)
        if u <= 0.0 or u >= vk_open:
            return 0.0
        lens = math.sin(math.pi * u / vk_open) ** self.lens_power
        amplitude = clamp(vk_open / self.full_at) ** 0.7
        return lens * amplitude

    def deform(self, x, y, z, side, vk_open):
        """Posición deformada de un punto del film o del zipper.
        Solo afecta a z > z_hinge: la zona rígida (logotipo) nunca se mueve."""
        if side == 0 or z <= self.z_hinge:
            return x, y, z
        op = self.opening(x, vk_open)
        if op <= 0.0:
            return x, y, z
        # Forma abierta: el labio deja de converger hacia el cierre y queda como
        # una lámina recta que sale de la bisagra inclinada `angle` hacia afuera
        # (frente hacia la cámara, trasera hacia atrás). Se mezcla con la forma
        # cerrada según la apertura local y una rampa suave sobre la bisagra.
        angle = self.front_angle if side < 0 else self.back_angle
        h = z - self.z_hinge
        offset = y - self.panel_y(x, z, side)  # p. ej. perfiles del zipper, hacia adentro
        y_t = side * (self.half_depth(x, self.z_hinge) + h * math.sin(angle)) + offset
        z_t = self.z_hinge + h * math.cos(angle)
        w = op * smoothstep(self.z_hinge, self.z_hinge + self.hinge_blend, z)
        return x, y + (y_t - y) * w, z + (z_t - z) * w
