// Comprueba que la secuencia que usa la sección existe completa en assets/
// con las medidas de escritorio (1200×640) y móvil (512×640), que los sprites de
// gummies existen con transparencia y que la sección no tiene textos ni botones de más.
// Ejecutar: node --test tests/*.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const liquid = readFileSync(new URL('sections/vuurk-unzip-player.liquid', root), 'utf8');
const prefix = liquid.match(/assign test_prefix = '([^']+)'/)[1];
const count = Number(liquid.match(/assign test_prefix = '[^']+'\s+assign count = (\d+)/)[1]);

// Ancho y alto de un WebP (VP8, VP8L o VP8X).
function webpSize(buf) {
  assert.equal(buf.toString('ascii', 0, 4), 'RIFF');
  assert.equal(buf.toString('ascii', 8, 12), 'WEBP');
  const chunk = buf.toString('ascii', 12, 16);
  if (chunk === 'VP8 ') return [buf.readUInt16LE(26) & 0x3fff, buf.readUInt16LE(28) & 0x3fff];
  if (chunk === 'VP8L') {
    const b = buf.readUInt32LE(21);
    return [(b & 0x3fff) + 1, ((b >> 14) & 0x3fff) + 1];
  }
  if (chunk === 'VP8X') return [buf.readUIntLE(24, 3) + 1, buf.readUIntLE(27, 3) + 1];
  throw new Error(`formato WebP desconocido: ${chunk}`);
}

test('la sección usa 24 fotogramas', () => {
  assert.equal(count, 24);
});

for (const [kind, size] of [['d', [1200, 640]], ['m', [512, 640]]]) {
  test(`fotogramas ${kind === 'd' ? 'escritorio' : 'móvil'} completos y con la medida correcta`, () => {
    for (let i = 1; i <= count; i++) {
      const name = `assets/${prefix}-${kind}-${String(i).padStart(2, '0')}.webp`;
      const url = new URL(name, root);
      assert.ok(existsSync(url), `falta ${name}`);
      assert.deepEqual(webpSize(readFileSync(url)), size, name);
    }
  });
}

// VP8X: bit de canal alfa en el byte de opciones.
const webpHasAlpha = (buf) => buf.toString('ascii', 12, 16) === 'VP8X' && (buf[20] & 0x10) !== 0;

test('sprites de gummies: 6, 160×160 y con transparencia', () => {
  assert.match(liquid, /'vuurk-gummy-0' \| append: i/);
  assert.match(liquid, /for i in \(1\.\.6\)/);
  for (let i = 1; i <= 6; i++) {
    const name = `assets/vuurk-gummy-0${i}.webp`;
    const url = new URL(name, root);
    assert.ok(existsSync(url), `falta ${name}`);
    const buf = readFileSync(url);
    assert.deepEqual(webpSize(buf), [160, 160], name);
    assert.ok(webpHasAlpha(buf), `${name} sin transparencia`);
  }
});

test('sin textos explicativos ni botones Abrir/Reiniciar', () => {
  const home = readFileSync(new URL('templates/index.json', root), 'utf8');
  for (const gone of ['data-vk-unzip2-open', 'data-vk-unzip2-reset', 'vk-unzip2__notice', 'vk-unzip2__hint', 'Visualización 3D', 'Deslizá']) {
    assert.ok(!liquid.includes(gone), `la sección todavía tiene ${gone}`);
  }
  for (const gone of ['open_label', 'reset_label', '"hint"', 'Deslizá para abrir el envase']) {
    assert.ok(!home.includes(gone), `templates/index.json todavía tiene ${gone}`);
  }
});
