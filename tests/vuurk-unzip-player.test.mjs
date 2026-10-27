// Pruebas de las funciones puras del reproductor VUURK Unzip V2.
// Ejecutar: node --test tests/vuurk-unzip-player.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

// El asset es un script clásico del theme: se evalúa con un `module` simulado.
const code = readFileSync(new URL('../assets/vuurk-unzip-player.js', import.meta.url), 'utf8');
const sandbox = { module: { exports: {} } };
vm.runInNewContext(code, sandbox);
const P = sandbox.module.exports;
// Los arrays vienen de otro contexto: se copian para compararlos.
const arr = (list) => Array.from(list);

test('clamp limita a 0–100 y descarta valores no numéricos', () => {
  assert.equal(P.clamp(-5), 0);
  assert.equal(P.clamp(140), 100);
  assert.equal(P.clamp(42.5), 42.5);
  assert.equal(P.clamp('abc'), 0);
  assert.equal(P.clamp(NaN), 0);
});

test('progressToFrame recorre todos los fotogramas', () => {
  assert.equal(P.progressToFrame(0, 48), 0);
  assert.equal(P.progressToFrame(100, 48), 47);
  assert.equal(P.progressToFrame(50, 48), 24);
  assert.equal(P.progressToFrame(150, 48), 47);
  assert.equal(P.progressToFrame(50, 1), 0);
});

test('loadOrder empieza por los extremos, luego 1 de cada 4, y no repite', () => {
  const order = arr(P.loadOrder(48));
  assert.deepEqual(order.slice(0, 2), [0, 47]);
  assert.equal(order.length, 48);
  assert.equal(new Set(order).size, 48);
  const coarse = order.slice(2, 13);
  assert.ok(coarse.every((i) => i % 4 === 0), `orden grueso: ${coarse}`);
});

test('decodeWindow respeta los bordes', () => {
  assert.deepEqual(arr(P.decodeWindow(0, 48, 2)), [0, 1, 2]);
  assert.deepEqual(arr(P.decodeWindow(47, 48, 2)), [45, 46, 47]);
  assert.equal(P.decodeWindow(20, 48, 4).length, 9);
});

test('nearestAvailable elige el fotograma listo más cercano', () => {
  const ready = new Set([0, 10, 47]);
  const has = (i) => ready.has(i);
  assert.equal(P.nearestAvailable(10, has, 48), 10);
  assert.equal(P.nearestAvailable(8, has, 48), 10);
  assert.equal(P.nearestAvailable(3, has, 48), 0);
  assert.equal(P.nearestAvailable(40, has, 48), 47);
  assert.equal(P.nearestAvailable(5, () => false, 48), -1);
});

test('dragToProgress convierte píxeles en porcentaje de la pista', () => {
  assert.equal(P.dragToProgress(0, 100, 300, 400), 50);
  assert.equal(P.dragToProgress(50, 300, 100, 400), 0);
  assert.equal(P.dragToProgress(80, 0, 400, 400), 100);
  assert.equal(P.dragToProgress(30, 0, 50, 0), 30);
});

test('keyToProgress cubre flechas, página, inicio y fin', () => {
  assert.equal(P.keyToProgress('ArrowRight', 10), 15);
  assert.equal(P.keyToProgress('ArrowLeft', 3), 0);
  assert.equal(P.keyToProgress('ArrowUp', 98), 100);
  assert.equal(P.keyToProgress('PageUp', 10), 30);
  assert.equal(P.keyToProgress('PageDown', 10), 0);
  assert.equal(P.keyToProgress('Home', 60), 0);
  assert.equal(P.keyToProgress('End', 0), 100);
  assert.equal(P.keyToProgress('a', 10), null);
});

test('releaseTarget abre desde el umbral y si no vuelve a cerrado', () => {
  assert.equal(P.releaseTarget(P.OPEN_AT), 100);
  assert.equal(P.releaseTarget(94.9), 0);
  assert.equal(P.releaseTarget(0), 0);
});

test('coverRect cubre el canvas sin deformar', () => {
  const r = P.coverRect(1200, 640, 600, 600);
  assert.equal(r.h, 600);
  assert.equal(r.w, 1125);
  assert.equal(r.x, -262.5);
  assert.equal(r.y, 0);
  assert.equal(r.w / r.h, 1200 / 640);
});

test('easeOutCubic va de 0 a 1', () => {
  assert.equal(P.easeOutCubic(0), 0);
  assert.equal(P.easeOutCubic(1), 1);
  assert.ok(P.easeOutCubic(0.5) > 0.5);
});
