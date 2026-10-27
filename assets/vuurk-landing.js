/* VUURK landing: aparición al hacer scroll, inclinación del hero, visor de vistas y bloque de compra. */
(() => {
  if (window.vuurkLanding) return;
  window.vuurkLanding = true;

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initReveal(root) {
    const items = root.querySelectorAll('.vk-reveal:not(.is-in)');
    if (reduceMotion || !('IntersectionObserver' in window)) {
      items.forEach((el) => el.classList.add('is-in'));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-in');
          io.unobserve(entry.target);
        });
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.12 }
    );
    items.forEach((el) => io.observe(el));
  }

  function initTilt(root) {
    if (reduceMotion || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    root.querySelectorAll('[data-vk-tilt]').forEach((area) => {
      const target = area.querySelector('.vk-hero__tilt');
      if (!target) return;
      area.addEventListener('pointermove', (event) => {
        const rect = area.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        target.style.transform = `perspective(1600px) rotateY(${x * 4}deg) rotateX(${y * -3}deg)`;
      });
      area.addEventListener('pointerleave', () => {
        target.style.transform = '';
      });
    });
  }

  function initViewer(root) {
    root.querySelectorAll('[data-vk-viewer]').forEach((viewer) => {
      const tabs = [...viewer.querySelectorAll('[data-vk-view-tab]')];
      const views = [...viewer.querySelectorAll('[data-vk-view]')];
      const stage = viewer.querySelector('.vk-stage');
      if (!views.length || !stage) return;
      let index = Math.max(0, views.findIndex((v) => v.classList.contains('is-active')));

      const show = (next, direction = 1) => {
        index = (next + views.length) % views.length;
        views.forEach((view, i) => {
          view.style.setProperty('--vk-from', `${direction * 18}deg`);
          view.classList.toggle('is-active', i === index);
          view.setAttribute('aria-hidden', i === index ? 'false' : 'true');
        });
        tabs.forEach((tab, i) => tab.setAttribute('aria-selected', i === index ? 'true' : 'false'));
      };

      tabs.forEach((tab, i) => tab.addEventListener('click', () => show(i, i > index ? 1 : -1)));

      let startX = null;
      stage.addEventListener('pointerdown', (event) => {
        startX = event.clientX;
      });
      const end = (event) => {
        if (startX === null) return;
        const dx = event.clientX - startX;
        startX = null;
        if (Math.abs(dx) < 30) return;
        show(index + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1);
      };
      stage.addEventListener('pointerup', end);
      stage.addEventListener('pointercancel', () => {
        startX = null;
      });
      stage.addEventListener('keydown', (event) => {
        if (event.key === 'ArrowRight') show(index + 1, 1);
        if (event.key === 'ArrowLeft') show(index - 1, -1);
      });
    });
  }

  function initBuy(root) {
    root.querySelectorAll('[data-vk-buy]').forEach((buy) => {
      const input = buy.querySelector('[data-vk-qty-input]');
      buy.querySelectorAll('[data-vk-qty]').forEach((button) => {
        button.addEventListener('click', () => {
          if (!input) return;
          const step = Number(button.dataset.vkQty);
          const min = Number(input.min) || 1;
          const max = input.max ? Number(input.max) : Infinity;
          input.value = String(Math.min(max, Math.max(min, (Number(input.value) || min) + step)));
        });
      });

      const select = buy.querySelector('[data-vk-variant]');
      const dataEl = buy.querySelector('[data-vk-variants]');
      if (!select || !dataEl) return;
      let variants = [];
      try {
        variants = JSON.parse(dataEl.textContent);
      } catch (e) {
        return;
      }
      const price = buy.querySelector('[data-vk-price]');
      const compare = buy.querySelector('[data-vk-compare]');
      const stock = buy.querySelector('[data-vk-stock]');
      const submit = buy.querySelector('[data-vk-submit]');
      select.addEventListener('change', () => {
        const v = variants.find((item) => String(item.id) === select.value);
        if (!v) return;
        if (price) price.textContent = v.price;
        if (compare) {
          compare.textContent = v.compare || '';
          compare.hidden = !v.compare;
        }
        if (stock) {
          stock.textContent = v.available ? stock.dataset.inStock : stock.dataset.outStock;
          stock.classList.toggle('vk-buy__stock--out', !v.available);
        }
        if (submit) {
          submit.disabled = !v.available;
          submit.querySelector('span').textContent = v.available ? submit.dataset.label : submit.dataset.soldOut;
        }
      });
    });
  }

  function init(root = document) {
    initReveal(root);
    initTilt(root);
    initViewer(root);
    initBuy(root);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => init());
  } else {
    init();
  }
  document.addEventListener('shopify:section:load', (event) => init(event.target));
})();
