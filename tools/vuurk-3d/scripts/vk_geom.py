"""Geometría paramétrica del doypack VUURK (prototipo v2).

Funciones puras, sin bpy: las usan build_scene.py y validate.py.
Ejes: X ancho (izquierda → derecha vista desde la cámara), Y profundidad
(frente en -Y, mirando a la cámara), Z alto (base en z = 0).
`side` = -1 frente, +1 trasera, 0 sin deformación (base).
La v1 congelada está en tools/vuurk-3d/v1/.
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
        self.pinch = p['pinch_length']
        self.base_round = p['base_round']
        self.lip_gap = p['lip_gap']
        self.seal_gap = p['seal_gap']
        self.ridge = p['zipper_ridge']
        self.thick = p['film_thickness']
        self.wrinkle = p['wrinkle']
        self.keys = o['keys']
        self.front_curl = math.radians(o['front_curl_deg'])
        self.back_curl = math.radians(o['back_curl_deg'])
        self.curl_power = o['curl_power']
        self.unpinch_at = o['unpinch_at']
        self.ripple = o['edge_ripple']
        self.lens_power = o['lens_power']
        self.seal_curl_min = o['seal_curl_min']
        self.seal_curl_falloff = o['seal_curl_falloff']
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
        body *= 0.72 + 0.28 * smoothstep(0.0, self.base_round, z)  # transición redondeada al fuelle
        pinch = 1.0 - smoothstep(self.Zz - self.pinch, self.Zz, z)
        return self.seal_gap + self.gx(x) * max(body * pinch, self.lip_gap)

    def ridge_offset(self, x, z):
        """Relieve del zipper visible a través del film."""
        return self.ridge * self.gx(x) * math.exp(-((z - self.Zz) / 0.0018) ** 2)

    def wrinkles(self, x, z):
        """Arrugas estáticas y suaves junto a las costuras y al fuelle.
        No tocan el centro del frente (zona del logotipo) y no cambian al abrir."""
        g = self.gx(x)
        if g <= 0.0:
            return 0.0
        edge = smoothstep(0.72 * self.a, 0.97 * self.a, abs(x))
        bottom = 1.0 - smoothstep(0.0, 0.045, z)
        diag = math.sin((z + 0.55 * abs(x)) * math.tau / 0.013 + 0.7 * math.sin(z * 90.0))
        horiz = math.sin(x * math.tau / 0.017 + 1.3) * math.sin(z * math.tau / 0.024)
        return self.wrinkle * math.sqrt(g) * (edge * diag + 0.6 * bottom * horiz)

    def panel_y(self, x, z, side):
        return side * (self.half_depth(x, z) + self.ridge_offset(x, z) + self.wrinkles(x, z))

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

    def curl(self, h, total, steps=14):
        """Lámina que se curva desde la bisagra: el ángulo crece con la distancia
        al pliegue (más curvatura arriba). Devuelve (salida, altura, ángulo)."""
        L = self.H - self.z_hinge
        ds = h / steps
        out = up = 0.0
        phi = 0.0
        for i in range(steps):
            phi = total * (((i + 0.5) * ds) / L) ** self.curl_power
            out += math.sin(phi) * ds
            up += math.cos(phi) * ds
        return out, up, total * (h / L) ** self.curl_power

    def deform(self, x, y, z, side, vk_open):
        """Posición deformada de un punto del film o del zipper.
        Solo afecta a z > z_hinge: la zona rígida (logotipo) nunca se mueve."""
        if side == 0 or z <= self.z_hinge:
            return x, y, z
        op = self.opening(x, vk_open)
        if op <= 0.0:
            return x, y, z
        h = z - self.z_hinge
        L = self.H - self.z_hinge
        total = (self.front_curl if side < 0 else self.back_curl) * op
        # Junto a las costuras la solapa se curva menos: evita esquinas retorcidas
        # que miran de costado hacia la luz principal.
        edge = min(self.u(x), 1.0 - self.u(x))
        total *= self.seal_curl_min + (1.0 - self.seal_curl_min) * smoothstep(0.0, self.seal_curl_falloff, edge)
        out, up, phi = self.curl(h, total)
        # Ondulación leve del borde abierto (el film no queda perfectamente recto).
        out += self.ripple * op * (h / L) ** 2 * math.sin(x * math.tau / 0.032 + 0.4)
        # Elementos pegados por dentro del labio (perfiles del zipper) giran con él.
        inset = -side * (y - self.panel_y(x, z, side))
        n_y, n_z = -side * math.cos(phi), math.sin(phi)
        y_t = side * (self.half_depth(x, self.z_hinge) + out) + inset * n_y
        z_t = self.z_hinge + up + inset * n_z
        # El labio primero deja de converger hacia el cierre y después se curva.
        w = smoothstep(0.0, self.unpinch_at, op)
        return x, y + (y_t - y) * w, z + (z_t - z) * w
