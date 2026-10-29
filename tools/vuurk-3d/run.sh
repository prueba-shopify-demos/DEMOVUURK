#!/usr/bin/env bash
# Ejecuta un script de tools/vuurk-3d/scripts en Blender sin interfaz.
# Uso: tools/vuurk-3d/run.sh <script.py> [blend] [-- args]
#   BLENDER y VK_BLENDER_LIBS se pueden sobrescribir por variable de entorno.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
BLENDER="${BLENDER:-$HOME/opt/blender-4.5.15-linux-x64/blender}"
VK_BLENDER_LIBS="${VK_BLENDER_LIBS:-$HOME/opt/blender-libs/usr/lib/x86_64-linux-gnu}"
export LD_LIBRARY_PATH="$VK_BLENDER_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

script="$1"; shift
blend=()
if [[ $# -gt 0 && "$1" == *.blend ]]; then blend=("$1"); shift; fi
exec "$BLENDER" -b "${blend[@]}" --factory-startup -noaudio --python-exit-code 1 \
  -P "$HERE/scripts/$script" "$@"
