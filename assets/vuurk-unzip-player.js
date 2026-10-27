/* VUURK UNZIP PLAYER V2 (U1): reproductor de fotogramas en canvas controlado por arrastre.
   Las funciones puras se exportan para las pruebas (tests/vuurk-unzip-player.test.mjs). */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.VuurkUnzipPlayer = api;
  if (typeof document !== 'undefined') api.boot();
})(globalThis, function () {
  const OPEN_AT = 95; // a partir de este % el envase queda abierto
  const KEY_STEP = 5;
  const PAGE_STEP = 20;

  /* ---------- Funciones puras ---------- */

  const clamp = (value, min = 0, max = 100) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return min;
    return Math.min(max, Math.max(min, n));
  };

  const progressToFrame = (progress, count) => {
    if (count <= 1) return 0;
    return Math.round((clamp(progress) / 100) * (count - 1));
  };

  // Orden de descarga: extremos, luego 1 de cada `step`, luego el resto.
  // Permite arrastrar enseguida con baja resolución temporal.
  const loadOrder = (count, step = 4) => {
    const order = [];
    const seen = new Set();
    const push = (i) => {
      if (i >= 0 && i < count && !seen.has(i)) {
        seen.add(i);
        order.push(i);
      }
    };
    push(0);
    push(count - 1);
    for (let s = step; s >= 1; s = Math.floor(s / 2)) {
      for (let i = 0; i < count; i += s) push(i);
      if (s === 1) break;
    }
    return order;
  };

  // Fotogramas que conviene tener decodificados alrededor del actual.
  const decodeWindow = (index, count, radius) => {
    const from = Math.max(0, index - radius);
    const to = Math.min(count - 1, index + radius);
    const list = [];
    for (let i = from; i <= to; i++) list.push(i);
    return list;
  };

  // El fotograma disponible más cercano al pedido (el pedido si ya está).
  const nearestAvailable = (index, isAvailable, count) => {
    for (let d = 0; d < count; d++) {
      if (index - d >= 0 && isAvailable(index - d)) return index - d;
      if (index + d < count && isAvailable(index + d)) return index + d;
    }
    return -1;
  };

  // Progreso a partir del desplazamiento horizontal del arrastre.
  const dragToProgress = (startProgress, startX, currentX, trackWidth) => {
    if (!trackWidth) return clamp(startProgress);
    return clamp(startProgress + ((currentX - startX) / trackWidth) * 100);
  };

  const keyToProgress = (key, progress) => {
    switch (key) {
      case 'ArrowRight':
      case 'ArrowUp':
        return clamp(progress + KEY_STEP);
      case 'ArrowLeft':
      case 'ArrowDown':
        return clamp(progress - KEY_STEP);
      case 'PageUp':
        return clamp(progress + PAGE_STEP);
      case 'PageDown':
        return clamp(progress - PAGE_STEP);
      case 'Home':
        return 0;
      case 'End':
        return 100;
      default:
        return null;
    }
  };

  // Al soltar el arrastre: abierto si pasó el umbral, si no vuelve a cerrado.
  const releaseTarget = (progress) => (progress >= OPEN_AT ? 100 : 0);

  // Rectángulo para dibujar la imagen cubriendo el canvas (como object-fit: cover).
  const coverRect = (imgW, imgH, boxW, boxH) => {
    const scale = Math.max(boxW / imgW, boxH / imgH);
    const w = imgW * scale;
    const h = imgH * scale;
    return { x: (boxW - w) / 2, y: (boxH - h) / 2, w, h };
  };

  const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

  /* ---------- Reproductor ---------- */

  class Player {
    constructor(root) {
      this.root = root;
      this.player = root.querySelector('[data-vk-unzip2-player]');
      this.stage = root.querySelector('[data-vk-unzip2-stage]');
      this.canvas = root.querySelector('[data-vk-unzip2-canvas]');
      this.handle = root.querySelector('[data-vk-unzip2-handle]');
      this.fill = root.querySelector('[data-vk-unzip2-fill]');
      this.openBtn = root.querySelector('[data-vk-unzip2-open]');
      this.resetBtn = root.querySelector('[data-vk-unzip2-reset]');
      this.cta = root.querySelector('[data-vk-unzip2-cta]');
      this.status = root.querySelector('[data-vk-unzip2-status]');
      this.fallback = root.querySelector('[data-vk-unzip2-fallback]');
      this.ctx = this.canvas.getContext('2d');

      const data = JSON.parse(root.querySelector('[data-vk-unzip2-frames]').textContent);
      this.sets = data;
      this.mqMobile = window.matchMedia('(max-width: 749px)');
      this.mqReduce = window.matchMedia('(prefers-reduced-motion: reduce)');
      const conn = navigator.connection;
      this.saveData = Boolean(conn && conn.saveData);

      this.progress = 0;
      this.drawn = -1;
      this.anim = 0;
      this.drag = null;
      this.started = false;
      this.stats = { requested: 0, loaded: 0, bytes: 0, decoded: 0, maxDecoded: 0, draws: 0 };

      this.selectSet();
      this.bind();
      this.render();
      this.cta.hidden = true;
      this.player.hidden = false;
      if (this.fallback) this.fallback.hidden = true;
      this.root.classList.add('is-ready');
      this.root.vkUnzipPlayer = this;
    }

    // Modo binario: solo cerrado y abierto (movimiento reducido o ahorro de datos).
    get binary() {
      return this.mqReduce.matches || this.saveData;
    }

    selectSet() {
      const set = this.mqMobile.matches && this.sets.mobile && this.sets.mobile.length ? this.sets.mobile : this.sets.desktop;
      if (set === this.urls) return;
      this.cancelLoads();
      this.urls = set;
      this.count = set.length;
      this.blobs = new Array(this.count).fill(null);
      this.bitmaps = new Map();
      this.pending = new Set();
      this.queue = [];
      this.drawn = -1;
      // Fotogramas decodificados a la vez: limita la memoria en móvil.
      this.radius = this.mqMobile.matches ? 4 : 8;
      if (this.started) this.startLoading();
    }

    bind() {
      this.onPointerDown = this.onPointerDown.bind(this);
      this.onPointerMove = this.onPointerMove.bind(this);
      this.onPointerUp = this.onPointerUp.bind(this);
      this.stage.addEventListener('pointerdown', this.onPointerDown);
      this.stage.addEventListener('pointermove', this.onPointerMove);
      this.stage.addEventListener('pointerup', this.onPointerUp);
      this.stage.addEventListener('pointercancel', this.onPointerUp);
      this.stage.addEventListener('lostpointercapture', this.onPointerUp);

      this.handle.addEventListener('keydown', (event) => {
        const next = keyToProgress(event.key, this.progress);
        if (next === null) return;
        event.preventDefault();
        this.stopAnim();
        this.setProgress(this.binary ? (next >= 50 ? 100 : 0) : next);
      });
      this.openBtn.addEventListener('click', () => this.animateTo(100));
      this.resetBtn.addEventListener('click', () => {
        this.animateTo(0);
        this.handle.focus();
      });

      this.resizeObserver = new ResizeObserver(() => this.resize());
      this.resizeObserver.observe(this.stage);

      this.onMedia = () => {
        this.selectSet();
        this.render();
      };
      this.mqMobile.addEventListener('change', this.onMedia);
      this.mqReduce.addEventListener('change', this.onMedia);

      // La descarga empieza cuando la sección se acerca a la pantalla.
      this.io = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) {
            this.io.disconnect();
            this.started = true;
            this.startLoading();
          }
        },
        { rootMargin: '600px 0px' }
      );
      this.io.observe(this.root);
    }

    destroy() {
      this.cancelLoads();
      this.stopAnim();
      this.io.disconnect();
      this.resizeObserver.disconnect();
      this.mqMobile.removeEventListener('change', this.onMedia);
      this.mqReduce.removeEventListener('change', this.onMedia);
      this.bitmaps.forEach((bmp) => bmp.close && bmp.close());
      this.bitmaps.clear();
    }

    /* ----- Carga progresiva ----- */

    startLoading() {
      const all = loadOrder(this.count);
      this.queue = this.binary ? [0, this.count - 1] : all;
      for (let i = 0; i < 4; i++) this.next();
    }

    cancelLoads() {
      if (this.controller) this.controller.abort();
      this.controller = new AbortController();
    }

    next() {
      const index = this.queue.shift();
      if (index === undefined) return;
      if (this.blobs[index] || this.pending.has(index)) return this.next();
      this.pending.add(index);
      this.stats.requested++;
      const urls = this.urls;
      fetch(urls[index], { signal: this.controller.signal })
        .then((res) => {
          if (!res.ok) throw new Error(res.status);
          return res.blob();
        })
        .then((blob) => {
          if (urls !== this.urls) return;
          this.blobs[index] = blob;
          this.stats.loaded++;
          this.stats.bytes += blob.size;
          this.pending.delete(index);
          this.render();
          this.next();
        })
        .catch((error) => {
          this.pending.delete(index);
          if (error.name !== 'AbortError') this.next();
        });
    }

    /* ----- Memoria: solo se decodifica una ventana alrededor del fotograma actual ----- */

    ensureDecoded(index) {
      const keep = new Set(decodeWindow(index, this.count, this.radius));
      keep.add(0);
      keep.add(this.count - 1);
      this.bitmaps.forEach((bmp, i) => {
        if (!keep.has(i) && bmp !== 'pending') {
          if (bmp.close) bmp.close();
          this.bitmaps.delete(i);
        }
      });
      keep.forEach((i) => {
        if (!this.blobs[i] || this.bitmaps.has(i)) return;
        this.bitmaps.set(i, 'pending');
        createImageBitmap(this.blobs[i])
          .then((bmp) => {
            if (this.bitmaps.get(i) !== 'pending') return bmp.close();
            this.bitmaps.set(i, bmp);
            let decoded = 0;
            this.bitmaps.forEach((b) => b !== 'pending' && decoded++);
            this.stats.decoded = decoded;
            this.stats.maxDecoded = Math.max(this.stats.maxDecoded, decoded);
            this.render();
          })
          .catch(() => this.bitmaps.delete(i));
      });
    }

    /* ----- Dibujo ----- */

    resize() {
      const rect = this.stage.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.round(rect.width * dpr);
      const h = Math.round(rect.height * dpr);
      if (this.canvas.width !== w || this.canvas.height !== h) {
        this.canvas.width = w;
        this.canvas.height = h;
        this.drawn = -1;
      }
      this.render();
    }

    targetFrame() {
      if (this.binary) return this.progress >= OPEN_AT ? this.count - 1 : 0;
      return progressToFrame(this.progress, this.count);
    }

    render() {
      if (!this.count) return;
      const wanted = this.targetFrame();
      this.ensureDecoded(wanted);
      const ready = (i) => this.bitmaps.get(i) && this.bitmaps.get(i) !== 'pending';
      const index = nearestAvailable(wanted, ready, this.count);
      if (index >= 0 && index !== this.drawn) {
        const bmp = this.bitmaps.get(index);
        const r = coverRect(bmp.width, bmp.height, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(bmp, r.x, r.y, r.w, r.h);
        this.drawn = index;
        this.stats.draws++;
      }
      this.root.classList.toggle('is-loading', index < 0);
    }

    setProgress(value) {
      this.progress = clamp(value);
      const pct = Math.round(this.progress);
      this.root.style.setProperty('--vk-unzip2-progress', `${this.progress}%`);
      this.handle.setAttribute('aria-valuenow', String(pct));
      this.handle.setAttribute('aria-valuetext', `Apertura ${pct} %`);
      const open = this.progress >= OPEN_AT;
      if (open !== this.root.classList.contains('is-open')) {
        this.root.classList.toggle('is-open', open);
        this.cta.hidden = !open;
        this.status.textContent = open ? 'Envase abierto.' : 'Envase cerrado.';
      }
      this.openBtn.hidden = open;
      this.render();
    }

    stopAnim() {
      cancelAnimationFrame(this.anim);
      this.anim = 0;
    }

    animateTo(target) {
      this.stopAnim();
      const from = this.progress;
      if (this.binary || from === target) return this.setProgress(target);
      const duration = Math.max(250, Math.abs(target - from) * 12);
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / duration);
        this.setProgress(from + (target - from) * easeOutCubic(t));
        if (t < 1) this.anim = requestAnimationFrame(step);
      };
      this.anim = requestAnimationFrame(step);
    }

    /* ----- Arrastre (mouse, lápiz y dedo) ----- */

    onPointerDown(event) {
      if (event.button > 0) return;
      if (event.target.closest('a, button')) return;
      this.stopAnim();
      this.drag = {
        id: event.pointerId,
        startX: event.clientX,
        startProgress: this.progress,
        // El recorrido completo es el ancho de la pista sobre el zipper: el tirador sigue al dedo.
        width: (this.handle.parentElement && this.handle.parentElement.getBoundingClientRect().width) ||
          this.stage.getBoundingClientRect().width * 0.8
      };
      this.stage.setPointerCapture(event.pointerId);
      this.root.classList.add('is-dragging');
    }

    onPointerMove(event) {
      if (!this.drag || event.pointerId !== this.drag.id) return;
      this.setProgress(dragToProgress(this.drag.startProgress, this.drag.startX, event.clientX, this.drag.width));
    }

    onPointerUp(event) {
      if (!this.drag || event.pointerId !== this.drag.id) return;
      this.drag = null;
      this.root.classList.remove('is-dragging');
      this.animateTo(releaseTarget(this.progress));
    }
  }

  const boot = () => {
    const init = (scope = document) => {
      const nodes = [];
      if (scope.matches && scope.matches('[data-vk-unzip2]')) nodes.push(scope);
      nodes.push(...scope.querySelectorAll('[data-vk-unzip2]'));
      nodes.forEach((node) => {
        if (!node.vkUnzipPlayer) new Player(node);
      });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
    else init();
    document.addEventListener('shopify:section:load', (event) => init(event.target));
    document.addEventListener('shopify:section:unload', (event) => {
      event.target.querySelectorAll('[data-vk-unzip2]').forEach((node) => node.vkUnzipPlayer && node.vkUnzipPlayer.destroy());
    });
  };

  return {
    OPEN_AT,
    clamp,
    progressToFrame,
    loadOrder,
    decodeWindow,
    nearestAvailable,
    dragToProgress,
    keyToProgress,
    releaseTarget,
    coverRect,
    easeOutCubic,
    Player,
    boot
  };
});
