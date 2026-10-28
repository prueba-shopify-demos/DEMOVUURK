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

test('burstPlan es reproducible, alterna lados y respeta los rangos', () => {
  const a = P.burstPlan(9, 1);
  assert.equal(JSON.stringify(a), JSON.stringify(P.burstPlan(9, 1)));
  assert.notEqual(JSON.stringify(a), JSON.stringify(P.burstPlan(9, 2)));
  const [lo, hi] = P.MOUTH.desktop.lateral;
  a.forEach((g, i) => {
    assert.equal(Math.sign(g.dx), i % 2 ? 1 : -1);
    assert.ok(Math.abs(g.dx) >= lo && Math.abs(g.dx) <= hi);
    assert.ok(g.rise >= 0.09 && g.rise <= 0.17);
    assert.ok(g.depth >= 0 && g.depth < 1);
    assert.ok(g.delay + g.duration <= 2200, 'animación breve');
  });
  // En móvil caen más hacia los lados, por fuera del envase.
  P.burstPlan(7, 1, P.MOUTH.mobile.lateral).forEach((g) => assert.ok(Math.abs(g.dx) >= 0.3 && Math.abs(g.dx) <= 0.46));
});

test('burstKeyframes: sale de la boca, sube y cae hacia el lateral, aparece y se desvanece', () => {
  const box = { w: 1000, h: 533 };
  const mouth = P.MOUTH.desktop;
  const g = { offset: 0, dx: 0.2, rise: 0.12, apex: 0.36, spin: 180, size: 0.1, depth: 1 };
  const frames = P.burstKeyframes(g, mouth, box, 50);
  const pos = (f) => f.transform.match(/-?[\d.]+/g).slice(0, 2).map(Number);
  const half = (g.size * box.h) / 2;
  const [x0, y0] = pos(frames[0]);
  assert.ok(Math.abs(x0 + half - mouth.x * box.w) < 0.1);
  assert.ok(Math.abs(y0 + half - mouth.y * box.h) < 0.1);
  const ys = frames.map((f) => pos(f)[1]);
  const top = Math.min(...ys);
  assert.ok(Math.abs(y0 - top - g.rise * box.h) < 1, 'llega a la altura pedida');
  assert.equal(ys.indexOf(top), Math.round(g.apex * 50));
  const [x1] = pos(frames.at(-1));
  assert.ok(Math.abs(x1 - x0 - g.dx * box.w) < 0.1);
  assert.equal(frames[0].opacity, 0);
  assert.equal(frames.at(-1).opacity, 0);
  assert.ok(frames.every((f) => f.opacity >= 0 && f.opacity <= 1));
  assert.equal(frames.at(-1).offset, 1);
});

test('VIEW: el recorte de escritorio es 4:3 sobre el fotograma de 1200×640 y entra en él', () => {
  const v = P.VIEW.desktop;
  assert.ok(Math.abs((v.w * 1200) / (v.h * 640) - 4 / 3) < 0.001);
  assert.ok(v.x >= 0 && v.y >= 0 && v.x + v.w <= 1 && v.y + v.h <= 1);
  // Envase del render (x 0,363–0,678 · y 0,106–0,916): completo dentro del recorte.
  assert.ok(v.x < 0.363 && v.x + v.w > 0.678 && v.y < 0.106 && v.y + v.h > 0.916);
  assert.deepEqual({ ...P.VIEW.mobile }, { x: 0, y: 0, w: 1, h: 1 });
});

test('escritorio: las gummies no se recortan en el borde del escenario mientras son visibles', () => {
  // Escenario 4:3 al máximo (960 px) y al mínimo (560 px de alto).
  for (const [kind, box] of [['desktop', { w: 960, h: 720 }], ['desktop', { w: 746.7, h: 560 }]]) {
    const mouth = P.MOUTH[kind];
    for (let seed = 1; seed <= 40; seed++) {
      P.burstPlan(P.GUMMIES[kind], seed, mouth.lateral).forEach((g) => {
        const size = g.size * box.h;
        P.burstKeyframes(g, mouth, box, 40).forEach((f) => {
          if (f.opacity < 0.5) return; // apareciendo o ya desvaneciéndose
          const [x, y, , scale] = f.transform.match(/-?[\d.]+/g).map(Number);
          const r = (size * scale) / 2;
          const cx = x + size / 2;
          const cy = y + size / 2;
          assert.ok(cy - r >= 0, `${kind} ${seed}: sale por arriba`);
          assert.ok(cx - r >= 0 && cx + r <= box.w, `${kind} ${seed}: sale por un costado`);
        });
      });
    }
  }
});
