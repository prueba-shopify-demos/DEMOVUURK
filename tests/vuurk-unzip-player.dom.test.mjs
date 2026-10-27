// Pruebas de interacción del reproductor VUURK Unzip con un DOM simulado:
// arrastre con mouse y con el dedo (pointer events), teclado y botones.
// Ejecutar: node --test tests/*.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const code = readFileSync(new URL('../assets/vuurk-unzip-player.js', import.meta.url), 'utf8');
const FRAMES = 24;
const STAGE_WIDTH = 1000;
const TRACK_WIDTH = 280; // pista sobre el zipper

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

function setup() {
  const els = {};
  const sel = (s) => (els[s] ||= new FakeElement(s));
  const urls = Array.from({ length: FRAMES }, (_, i) => `/f-${i + 1}.webp`);
  sel('[data-vk-unzip2-frames]').textContent = JSON.stringify({ desktop: urls, mobile: urls });
  const track = new FakeElement('track');
  track.width = TRACK_WIDTH;
  sel('[data-vk-unzip2-handle]').parentElement = track;
  const canvas = sel('[data-vk-unzip2-canvas]');
  const draws = [];
  canvas.getContext = () => ({ drawImage: (bmp) => draws.push(bmp.index) });
  const root = new FakeElement('root');
  root.querySelector = sel;

  let now = 0;
  const raf = [];
  const media = { matches: false, addEventListener() {}, removeEventListener() {} };
  const sandbox = {
    module: { exports: {} },
    window: { matchMedia: () => media, devicePixelRatio: 1 },
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
    fetch: async (url) => ({ ok: true, blob: async () => ({ size: 1000, url }) }),
    createImageBitmap: async (blob) => ({ width: 1200, height: 640, index: urls.indexOf(blob.url), close() {} }),
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
  return { root, player, sel, draws, flushAsync, flushAnimation };
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

test('botones Abrir y Reiniciar', async () => {
  const { player, sel, flushAsync, flushAnimation } = setup();
  await flushAsync();
  sel('[data-vk-unzip2-open]').dispatch('click');
  flushAnimation();
  assert.equal(player.progress, 100);
  sel('[data-vk-unzip2-reset]').dispatch('click');
  flushAnimation();
  assert.equal(player.progress, 0);
  assert.ok(sel('[data-vk-unzip2-handle]').focused);
});
