# VUURK · Pipeline 3D (prototipo, Etapa 05 · v2)

> **v2 (actual):** solapa curva, film satinado con microrrugosidad, costuras con estrías de sellado, arrugas estáticas fuera de la zona del logotipo e iluminación de producto. Salidas en `out/v2/` y `out/vuurk_pouch_v2.blend`.
> **v1** está congelada en `v1/` (scripts y config) y sus salidas en `out/proto/` y `out/vuurk_pouch_proto.blend`. El primer intento descartado de v2 está en `out/v2-intento1/`.

Doypack paramétrico con zipper a presión que abre de izquierda a derecha, controlado por `vk_open` (0 cerrado → 1 abierto). **Prototipo:** material neutro, sin logotipo ni arte VUURK, con medidas provisionales (`config.json`). No es un modelo comercial definitivo.

## Requisitos

Blender 4.5 LTS portable en `~/opt/blender-4.5.15-linux-x64` y las librerías X11/GL extraídas en `~/opt/blender-libs`. `run.sh` las configura; se pueden sobrescribir con las variables `BLENDER` y `VK_BLENDER_LIBS`.

## Uso

```bash
cd tools/vuurk-3d
./run.sh build_scene.py                                         # escena → out/vuurk_pouch_proto.blend
./run.sh validate.py out/vuurk_pouch_proto.blend                # comprobaciones geométricas (sin render)
./run.sh render_states.py out/vuurk_pouch_proto.blend           # 5 estados → out/proto/*.png (≈ 1 min c/u en CPU)
./run.sh validate.py out/vuurk_pouch_proto.blend -- --images    # + comparación de píxeles y hoja de contacto
```

### Secuencia para el theme (24 fotogramas)

```bash
./run.sh build_scene.py
./run.sh render_sequence.py out/vuurk_pouch_v2.blend   # out/v2/seq/png + meta.json (posición del zipper)
python3 scripts/export_webp.py --install                # WebP 1200×640 (d) y 512×640 (m) → assets/vuurk-unzip-3d-*.webp
```

`render_sequence.py` renderiza completo el fotograma cerrado. En los demás solo renderiza la franja superior (boca y sombra de la solapa) y conserva el resto del fotograma 1, que es la misma geometría inmóvil. La versión móvil es un recorte central 4:5 del render de escritorio.

## Archivos

| Archivo | Función |
| --- | --- |
| `config.json` | Medidas provisionales, apertura, gummies, cámara, render y estados de prueba |
| `scripts/vk_geom.py` | Geometría pura (sin bpy): forma cerrada, apertura local y deformación |
| `scripts/build_scene.py` | Bolsa, zipper, shape keys con drivers, gummies, estudio y guardado del `.blend` |
| `scripts/render_states.py` | Render de los estados con Cycles en CPU |
| `scripts/validate.py` | Zona rígida inmóvil, avance de izquierda a derecha, cámara fija, visibilidad de las gummies y diferencias de píxeles |

## Mecanismo

- `VK_Control["vk_open"]` está animado de forma lineal entre el fotograma 0 (0) y el 100 (1).
- `VK_Pouch` y `VK_Zipper` tienen 20 shape keys (`vk_open_01…20`). Cada una la activa un driver de expresión simple con peso triangular, `max(0, 1 − |20·v − k|)`, así que entre claves vecinas se interpola linealmente.
- No hace falta habilitar la autoejecución de Python al abrir el `.blend`.
- Debajo de `z_hinge` (zona rígida, donde irá el arte) ningún vértice se mueve en ninguna clave.
