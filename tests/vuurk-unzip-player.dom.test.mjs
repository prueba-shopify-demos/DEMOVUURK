// Pruebas de interacción del reproductor VUURK Unzip con un DOM simulado:
// arrastre con mouse y con el dedo (pointer events), teclado y salida de gummies.
// Ejecutar: node --test tests/*.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const code = readFileSync(new URL('../assets/vuurk-unzip-player.js', import.meta.url), 'utf8');
const FRAMES = 24;
const STAGE_WIDTH = 1000;
const TRACK_WIDTH = 280; // pista sobre el zipper
const SPRITES = Array.from({ length: 6 }, (_, i) => `/gummy-${i + 1}.webp`);

class FakeElement {
  constructor(name) {
    this.name = name;
    this.listeners = {};
    this.attrs = {};
    this.hidden = false;
    this.textContent = '';
    this.classes = new Set();
    this.styleProps = {};
    this.classList = {
      add: (c) => this.classes.add(c),
      remove: (c) => this.classes.delete(c),
      contains: (c) => this.classes.has(c),
      toggle: (c, on) => (on ?? !this.classes.has(c)) ? this.classes.add(c) : this.classes.delete(c),
    };
    this.style = { setProperty: (k, v) => (this.styleProps[k] = v) };
    this.children = [];
    this.animations = [];
  }
  appendChild(child) { this.children.push(child); return child; }
  animate(keyframes, options) {
    const anim = { keyframes, options, cancelled: false, cancel() { this.cancelled = true; } };
    this.animations.push(anim);
    return anim;
  }
  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }
  dispatch(type, event = {}) {
    const ev = { target: { closest: () => null }, preventDefault() { this.defaultPrevented = true; }, ...event };
    (this.listeners[type] || []).forEach((fn) => fn(ev));
    return ev;
  }
  setAttribute(k, v) { this.attrs[k] = v; }
  getAttribute(k) { return this.attrs[k]; }
  getBoundingClientRect() { const width = this.width ?? STAGE_WIDTH; return { width, height: width * 8 / 15 }; }
  setPointerCapture(id) { this.captured = id; }
  focus() { this.focused = true; }
}

// queries: media queries activas, p. ej. ['(max-width: 749px)'].
// withMattes: la sección trae las siluetas desktop (como la secuencia BERRY FUSION).
function setup(queries = [], { withMattes = false } = {}) {
  const els = {};
  const sel = (s) => (els[s] ||= new FakeElement(s));
  const urls = Array.from({ length: FRAMES }, (_, i) => `/f-${i + 1}.webp`);
  const mattes = withMattes ? Array.from({ length: FRAMES }, (_, i) => `/matte-${i + 1}.webp`) : [];
  const mobileUrls = urls.map((u) => u.replace('/f-', '/m-'));
  sel('[data-vk-unzip2-frames]').textContent = JSON.stringify({ desktop: urls, mobile: mobileUrls, mattes, gummies: SPRITES });
  const track = new FakeElement('track');
  track.width = TRACK_WIDTH;
  sel('[data-vk-unzip2-handle]').parentElement = track;
  const canvas = sel('[data-vk-unzip2-canvas]');
  const draws = [];
  const ops = [];
  const ctx = {
    globalCompositeOperation: 'source-over',
    drawImage(bmp) {
      draws.push(bmp.index);
      ops.push({ op: this.globalCompositeOperation, img: bmp.url });
    },
    clearRect: (...rect) => ops.push({ op: 'clear', rect })
  };
  canvas.getContext = () => ctx;
  const fetched = [];
  const root = new FakeElement('root');
  root.querySelector = sel;

  let now = 0;
  const raf = [];
  const media = (q) => ({ matches: queries.includes(q), addEventListener() {}, removeEventListener() {} });
  const sandbox = {
    module: { exports: {} },
    window: { matchMedia: media, devicePixelRatio: 1 },
    // readyState 'loading': boot() solo registra eventos; la prueba crea el Player.
    document: { readyState: 'loading', addEventListener() {}, createElement: (tag) => new FakeElement(tag) },
    navigator: {},
    performance: { now: () => now },
    requestAnimationFrame: (fn) => raf.push(fn),
    cancelAnimationFrame: () => raf.splice(0),
    ResizeObserver: class { observe() {} disconnect() {} },
    IntersectionObserver: class {
      constructor(cb) { this.cb = cb; }
      observe() { this.cb([{ isIntersecting: true }]); }
      disconnect() {}
    },
    AbortController: class { constructor() { this.signal = {}; } abort() {} },
    fetch: async (url) => {
      fetched.push(url);
      return { ok: true, blob: async () => ({ size: 1000, url }) };
    },
    createImageBitmap: async (blob) => ({
      width: blob.url.includes('matte') ? 336 : 1200,
      height: blob.url.includes('matte') ? 526 : 640,
      index: Math.max(urls.indexOf(blob.url), mobileUrls.indexOf(blob.url)),
      url: blob.url,
      close() {}
    }),
  };
  vm.runInNewContext(code, sandbox);
  const player = new sandbox.module.exports.Player(root);

  const flushAsync = async () => {
    for (let i = 0; i < 50; i++) await new Promise((r) => setImmediate(r));
  };
  const flushAnimation = () => {
    for (let i = 0; i < 200 && raf.length; i++) {
      now += 50;
      raf.shift()(now);
    }
  };
  // Animaciones de gummies activas (no canceladas).
  const running = () => sel('[data-vk-unzip2-burst]').children.flatMap((img) => img.animations).filter((a) => !a.cancelled);
  return { root, player, sel, draws, ops, ctx, fetched, flushAsync, flushAnimation, running };
}

const drag = (stage, pointerType, fromX, toX) => {
  stage.dispatch('pointerdown', { button: 0, pointerId: 7, clientX: fromX, pointerType });
  stage.dispatch('pointermove', { pointerId: 7, clientX: (fromX + toX) / 2, pointerType });
  stage.dispatch('pointermove', { pointerId: 7, clientX: toX, pointerType });
};

test('usa la secuencia de 24 fotogramas y dibuja el envase cerrado al cargar', async () => {
  const { player, draws, flushAsync } = setup();
  await flushAsync();
  assert.equal(player.count, FRAMES);
  assert.equal(player.drawn, 0);
  assert.ok(draws.includes(0));
});

test('mouse: el tirador sigue al cursor sobre la pista; al soltar a mitad vuelve a cerrado', async () => {
  const { root, player, sel, flushAsync, flushAnimation } = setup();
  await flushAsync();
  const stage = sel('[data-vk-unzip2-stage]');
  const handle = sel('[data-vk-unzip2-handle]');
  // Recorrer la mitad de la pista (140 de 280 px) abre el 50 %.
  drag(stage, 'mouse', 100, 100 + TRACK_WIDTH / 2);
  assert.equal(stage.captured, 7);
  assert.ok(root.classList.contains('is-dragging'));
  assert.equal(player.progress, 50);
  assert.equal(handle.getAttribute('aria-valuenow'), '50');
  assert.equal(player.targetFrame(), 12);
  await flushAsync();
  assert.equal(player.drawn, 12);
  stage.dispatch('pointerup', { pointerId: 7 });
  flushAnimation();
  assert.equal(player.progress, 0);
  assert.ok(!root.classList.contains('is-dragging'));
});

test('táctil: arrastre completo abre el envase, muestra la compra y anuncia el estado', async () => {
  const { root, player, sel, flushAsync, flushAnimation } = setup();
  await flushAsync();
  const stage = sel('[data-vk-unzip2-stage]');
  drag(stage, 'touch', 50, 950);
  stage.dispatch('pointerup', { pointerId: 7 });
  flushAnimation();
  await flushAsync();
  assert.equal(player.progress, 100);
  assert.equal(player.drawn, FRAMES - 1);
  assert.ok(root.classList.contains('is-open'));
  assert.equal(sel('[data-vk-unzip2-cta]').hidden, false);
  assert.equal(sel('[data-vk-unzip2-status]').textContent, 'Envase abierto.');
  // Arrastrar hacia la izquierda vuelve a cerrar.
  drag(stage, 'touch', 950, 50);
  stage.dispatch('pointerup', { pointerId: 7 });
  flushAnimation();
  assert.equal(player.progress, 0);
  assert.ok(!root.classList.contains('is-open'));
});

test('teclado: flechas, Inicio y Fin mueven la apertura', async () => {
  const { player, sel, flushAsync } = setup();
  await flushAsync();
  const handle = sel('[data-vk-unzip2-handle]');
  const ev = handle.dispatch('keydown', { key: 'ArrowRight' });
  assert.ok(ev.defaultPrevented);
  assert.equal(player.progress, 5);
  handle.dispatch('keydown', { key: 'End' });
  assert.equal(player.progress, 100);
  assert.equal(handle.getAttribute('aria-valuetext'), 'Apertura 100 %');
  handle.dispatch('keydown', { key: 'ArrowLeft' });
  assert.equal(player.progress, 95);
  handle.dispatch('keydown', { key: 'Home' });
  assert.equal(player.progress, 0);
  const ignored = handle.dispatch('keydown', { key: 'a' });
  assert.ok(!ignored.defaultPrevented);
});

test('gummies: listas al empezar la carga, salen una sola vez al completar la apertura', async () => {
  const { player, sel, flushAsync, running } = setup();
  await flushAsync();
  const layer = sel('[data-vk-unzip2-burst]');
  assert.equal(layer.children.length, 9);
  assert.deepEqual(layer.children.map((img) => img.src).slice(0, 6), SPRITES);
  assert.ok(layer.children.every((img) => img.alt === ''));
  const handle = sel('[data-vk-unzip2-handle]');
  // A mitad de camino no sale nada.
  handle.dispatch('keydown', { key: 'PageUp' });
  handle.dispatch('keydown', { key: 'PageUp' });
  assert.equal(running().length, 0);
  handle.dispatch('keydown', { key: 'End' });
  assert.equal(running().length, 9);
  const first = running()[0];
  assert.equal(first.keyframes[0].opacity, 0);
  assert.equal(first.keyframes.at(-1).opacity, 0);
  assert.equal(first.options.fill, 'both');
  // Sigue abierto: retroceder un paso y volver al final no repite la salida.
  handle.dispatch('keydown', { key: 'ArrowLeft' });
  handle.dispatch('keydown', { key: 'End' });
  assert.equal(player.bursts, 1);
  assert.equal(running().length, 9);
});

test('gummies: al cerrar se restablecen y vuelven a salir al reabrir (arrastre)', async () => {
  const { player, sel, flushAsync, flushAnimation, running } = setup();
  await flushAsync();
  const stage = sel('[data-vk-unzip2-stage]');
  drag(stage, 'touch', 50, 950);
  stage.dispatch('pointerup', { pointerId: 7 });
  flushAnimation();
  assert.equal(player.bursts, 1);
  const firstRun = running();
  drag(stage, 'touch', 950, 50);
  stage.dispatch('pointerup', { pointerId: 7 });
  flushAnimation();
  assert.equal(running().length, 0);
  assert.ok(firstRun.every((a) => a.cancelled));
  assert.ok(player.burstArmed);
  drag(stage, 'mouse', 50, 950);
  stage.dispatch('pointerup', { pointerId: 7 });
  flushAnimation();
  assert.equal(player.bursts, 2);
  assert.equal(running().length, 9);
});

test('gummies: en móvil salen menos y desde la boca del encuadre móvil', async () => {
  const { player, sel, flushAsync, running } = setup(['(max-width: 749px)']);
  await flushAsync();
  sel('[data-vk-unzip2-handle]').dispatch('keydown', { key: 'End' });
  assert.equal(running().length, 7);
  const box = sel('[data-vk-unzip2-stage]').getBoundingClientRect();
  const img = sel('[data-vk-unzip2-burst]').children[0];
  const size = parseFloat(img.style.width);
  const [x, y] = running()[0].keyframes[0].transform.match(/-?[\d.]+/g).map(Number);
  assert.ok(Math.abs((x + size / 2) / box.width - 0.512) <= 0.14 + 1e-6);
  assert.ok(Math.abs((y + size / 2) / box.height - 0.26) < 1e-3);
});

test('gummies: con movimiento reducido no hay animación pero el envase abre igual', async () => {
  const { root, player, sel, flushAsync, running } = setup(['(prefers-reduced-motion: reduce)']);
  await flushAsync();
  sel('[data-vk-unzip2-handle]').dispatch('keydown', { key: 'End' });
  assert.equal(player.progress, 100);
  assert.ok(root.classList.contains('is-open'));
  assert.equal(running().length, 0);
});

test('la primera interacción detiene la invitación del tirador', async () => {
  const { root, sel, flushAsync } = setup();
  await flushAsync();
  assert.ok(!root.classList.contains('is-touched'));
  sel('[data-vk-unzip2-handle]').dispatch('keydown', { key: 'ArrowRight' });
  assert.ok(root.classList.contains('is-touched'));
});

test('escritorio: cada fotograma se recorta con su silueta (sin el gris de estudio)', async () => {
  const { player, sel, ops, ctx, fetched, flushAsync } = setup([], { withMattes: true });
  await flushAsync();
  assert.equal(fetched.filter((u) => u.includes('/matte-')).length, FRAMES);
  assert.equal(player.drawn, 0);
  const cut = ops.filter((o) => o.op === 'destination-in');
  assert.equal(cut.at(-1).img, '/matte-1.webp');
  assert.ok(ops.filter((o) => o.op === 'clear').length >= 4);
  assert.equal(ctx.globalCompositeOperation, 'source-over');
  // Abrir: el último fotograma usa la última silueta.
  sel('[data-vk-unzip2-handle]').dispatch('keydown', { key: 'End' });
  await flushAsync();
  assert.equal(player.drawn, FRAMES - 1);
  assert.equal(ops.filter((o) => o.op === 'destination-in').at(-1).img, `/matte-${FRAMES}.webp`);
});

test('móvil: no descarga ni aplica siluetas', async () => {
  const { player, ops, fetched, flushAsync } = setup(['(max-width: 749px)'], { withMattes: true });
  await flushAsync();
  assert.equal(player.drawn, 0);
  assert.ok(fetched.length > 0);
  assert.ok(fetched.every((u) => !u.includes('matte')));
  assert.ok(
    ops.every((o) => o.op === 'source-over' || o.op === 'clear'),
    'En móvil solo se permite dibujo normal y limpieza del canvas'
  );
});
