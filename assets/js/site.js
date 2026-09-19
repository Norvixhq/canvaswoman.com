/* CANVAS WOMAN — site.js  (no dependencies; every feature degrades to plain links) */
(() => {
  'use strict';
  const d = document;
  const root = d.documentElement;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Header: hairline after scrolling; on the home page the wordmark appears once the masthead has gone */
  const header = d.querySelector('[data-header]');
  if (header) {
    const onScroll = () => header.classList.toggle('is-scrolled', window.scrollY > 4);
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    const mast = d.querySelector('[data-masthead]');
    if (mast && 'IntersectionObserver' in window) {
      new IntersectionObserver(([entry]) => header.classList.toggle('show-mark', !entry.isIntersecting),
        { rootMargin: '-90px 0px 0px 0px' }).observe(mast);
    } else {
      header.classList.add('show-mark');
    }
  }

  /* Mobile menu */
  const toggle = d.querySelector('[data-menu-toggle]');
  const menu = d.getElementById('site-menu');
  if (toggle && menu && header) {
    /* Everything the open menu covers is made inert, so a keyboard or screen-reader user
       cannot tab behind the overlay. The skip link belongs in here too: it sits outside
       main, so it stayed reachable and would have sent focus into the inert page. The
       header bar itself is deliberately left out — its icons stay visible above the open
       menu, so they are still genuinely usable. */
    const outside = () => [d.querySelector('main'), d.querySelector('.site-footer'),
      d.querySelector('.preview-note'), d.querySelector('.skip-link'),
      d.querySelector('.float-enquire')].filter(Boolean);
    const isOpen = () => toggle.getAttribute('aria-expanded') === 'true';
    let timer;
    const open = () => {
      clearTimeout(timer);
      const bar = header.querySelector('.site-header__bar').getBoundingClientRect();
      menu.style.setProperty('--menu-top', Math.max(0, Math.round(bar.bottom)) + 'px');
      menu.hidden = false;
      requestAnimationFrame(() => menu.classList.add('is-open'));
      toggle.setAttribute('aria-expanded', 'true');
      toggle.setAttribute('aria-label', 'Close menu');
      root.classList.add('menu-open');
      outside().forEach((el) => { el.inert = true; });
      const first = menu.querySelector('a');
      if (first) first.focus({ preventScroll: true });
    };
    const close = (restoreFocus) => {
      menu.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-label', 'Open menu');
      root.classList.remove('menu-open');
      outside().forEach((el) => { el.inert = false; });
      timer = setTimeout(() => { if (!isOpen()) menu.hidden = true; }, reduce ? 0 : 300);
      if (restoreFocus) toggle.focus();
    };
    toggle.addEventListener('click', () => (isOpen() ? close(true) : open()));
    d.addEventListener('keydown', (e) => { if (e.key === 'Escape' && isOpen()) close(true); });
    menu.addEventListener('click', (e) => { if (e.target.closest('a')) close(false); });
    window.matchMedia('(min-width: 1024px)').addEventListener('change', (e) => { if (e.matches && isOpen()) close(false); });
  }

  /* Unveil artworks that start below the fold */
  const reveals = d.querySelectorAll('[data-reveal]');
  if (!reduce && reveals.length && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add('is-in'); io.unobserve(entry.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    reveals.forEach((el) => {
      if (el.getBoundingClientRect().top < window.innerHeight) return;
      el.classList.add('will-reveal');
      io.observe(el);
    });
  }

  /* Reveal each photograph once it has fully decoded (see the CSS note). */
  const faders = d.querySelectorAll('picture[data-fade] > img');
  faders.forEach((im) => {
    const ready = () => im.classList.add('is-ready');
    if (im.complete && im.naturalWidth) { ready(); return; }
    im.addEventListener('load', ready, { once: true });
    im.addEventListener('error', ready, { once: true });
  });
  /* Safety net: an image restored from cache or laid out at a new breakpoint can finish
     without firing load, so sweep for finished images whenever the layout changes. No
     image may stay invisible because its reveal event was missed. */
  const sweep = () => faders.forEach((im) => {
    if (im.complete && !im.classList.contains('is-ready')) im.classList.add('is-ready');
  });
  addEventListener('resize', sweep, { passive: true });
  addEventListener('pageshow', sweep);
  addEventListener('load', sweep);

  /* Collection filters: each filter is a real category page; with JS it filters in place */
  const filterNav = d.querySelector('[data-filters]');
  const grid = d.querySelector('[data-grid]');
  if (filterNav && grid && window.history && history.pushState) {
    const links = Array.from(filterNav.querySelectorAll('a[data-filter]'));
    const cards = Array.from(grid.querySelectorAll('[data-category]'));
    const title = d.querySelector('[data-collection-title]');
    const intro = d.querySelector('[data-collection-intro]');
    const status = d.querySelector('[data-filter-status]');
    const empty = d.querySelector('[data-empty]');
    const apply = (link, push) => {
      const key = link.dataset.filter;
      let shown = 0;
      cards.forEach((card) => {
        const match = key === 'all' || card.dataset.category === key;
        card.hidden = !match;
        if (match) shown += 1;
      });
      links.forEach((a) => (a === link ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
      if (title) title.textContent = link.dataset.heading;
      if (intro) intro.textContent = link.dataset.intro;
      d.title = link.dataset.title;
      if (empty) empty.hidden = shown > 0;
      if (status) status.textContent = `Showing ${shown} ${shown === 1 ? 'painting' : 'paintings'}`;
      if (push) history.pushState({ filter: key }, '', link.href);
    };
    filterNav.addEventListener('click', (e) => {
      const link = e.target.closest('a[data-filter]');
      if (!link || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      if (link.getAttribute('aria-current') !== 'page') apply(link, true);
    });
    window.addEventListener('popstate', () => {
      const link = links.find((a) => new URL(a.href).pathname === location.pathname);
      if (link) apply(link, false);
    });
  }

  /* Painting gallery: swipe carousel on small screens */
  const gallery = d.querySelector('[data-gallery]');
  if (gallery) {
    const track = gallery.querySelector('[data-track]');
    const items = Array.from(track.children);
    const count = gallery.querySelector('[data-count]');
    const pad = () => parseFloat(getComputedStyle(track).paddingLeft) || 0;
    const scrollable = () => track.scrollWidth > track.clientWidth + 2;
    const currentIndex = () => {
      const base = track.getBoundingClientRect().left + pad();
      let best = 0; let dist = Infinity;
      items.forEach((it, i) => {
        const delta = Math.abs(it.getBoundingClientRect().left - base);
        if (delta < dist) { dist = delta; best = i; }
      });
      return best;
    };
    const go = (i) => {
      const target = items[Math.max(0, Math.min(items.length - 1, i))];
      const left = target.getBoundingClientRect().left - track.getBoundingClientRect().left - pad();
      track.scrollBy({ left, behavior: reduce ? 'auto' : 'smooth' });
    };
    const update = () => { if (count) count.textContent = `${currentIndex() + 1} / ${items.length}`; };
    track.addEventListener('scroll', () => requestAnimationFrame(update), { passive: true });
    const prev = gallery.querySelector('[data-prev]');
    const next = gallery.querySelector('[data-next]');
    if (prev) prev.addEventListener('click', () => go(currentIndex() - 1));
    if (next) next.addEventListener('click', () => go(currentIndex() + 1));
    track.addEventListener('keydown', (e) => {
      if (!scrollable()) return;
      if (e.key === 'ArrowRight') { e.preventDefault(); go(currentIndex() + 1); }
      if (e.key === 'ArrowLeft') { e.preventDefault(); go(currentIndex() - 1); }
    });
  }

  /* Lightbox */
  const box = d.querySelector('[data-lightbox]');
  const zooms = Array.from(d.querySelectorAll('[data-zoom]'));
  if (box && zooms.length && typeof box.showModal === 'function') {
    const img = box.querySelector('[data-lb-img]');
    const cap = box.querySelector('[data-lb-caption]');
    const prevBtn = box.querySelector('[data-lb-prev]');
    const nextBtn = box.querySelector('[data-lb-next]');
    let at = 0; let opener = null;
    const show = (i) => {
      if (typeof resetZoom === 'function') resetZoom();
      at = (i + zooms.length) % zooms.length;
      const z = zooms[at];
      img.src = z.dataset.zoom;
      img.alt = z.dataset.alt || '';
      cap.textContent = z.dataset.caption || '';
    };
    if (zooms.length < 2) { prevBtn.hidden = true; nextBtn.hidden = true; }
    zooms.forEach((z, i) => z.addEventListener('click', (e) => {
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      e.preventDefault();
      opener = z; show(i); box.showModal(); root.classList.add('menu-open');
    }));
    /* Zoom into the surface. Texture, impasto and brushwork are the product here, so the
       viewer can magnify to the photograph's own resolution and drag around the canvas. */
    const hint = box.querySelector('[data-lb-hint]');
    let zoom = 1, ox = 0, oy = 0, dragging = false, sx = 0, sy = 0, moved = false;
    const apply = () => { img.style.transform = `translate(${ox}px, ${oy}px) scale(${zoom})`; };
    const clampPan = () => {
      const limX = Math.max(0, (img.clientWidth * zoom - Math.min(img.clientWidth * zoom, window.innerWidth)) / 2);
      const limY = Math.max(0, (img.clientHeight * zoom - Math.min(img.clientHeight * zoom, window.innerHeight)) / 2);
      ox = Math.max(-limX, Math.min(limX, ox));
      oy = Math.max(-limY, Math.min(limY, oy));
    };
    const resetZoom = () => {
      zoom = 1; ox = 0; oy = 0; img.style.transform = '';
      box.classList.remove('is-zoomed');
      if (hint) hint.hidden = false;
    };
    img.addEventListener('click', (e) => {
      e.stopPropagation();
      if (moved) { moved = false; return; }
      if (zoom === 1) {
        const r = img.getBoundingClientRect();
        if (!r.width) return;
        zoom = Math.min(3.2, Math.max(1.9, img.naturalWidth / r.width));
        ox = -(e.clientX - (r.left + r.width / 2)) * (zoom - 1);
        oy = -(e.clientY - (r.top + r.height / 2)) * (zoom - 1);
        clampPan(); apply();
        box.classList.add('is-zoomed');
        if (hint) hint.hidden = true;
      } else resetZoom();
    });
    img.addEventListener('pointerdown', (e) => {
      if (zoom === 1) return;
      e.preventDefault();
      dragging = true; moved = false;
      sx = e.clientX - ox; sy = e.clientY - oy;
    });
    /* Tracked on the document, not the image: the pointer regularly leaves the artwork
       mid-drag, and the pan should keep following it. */
    d.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const nx = e.clientX - sx, ny = e.clientY - sy;
      if (Math.abs(nx - ox) + Math.abs(ny - oy) > 2) moved = true;
      ox = nx; oy = ny;
      clampPan(); apply();
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(
      (ev) => d.addEventListener(ev, () => { dragging = false; }));

    box.querySelector('[data-lb-close]').addEventListener('click', () => box.close());
    prevBtn.addEventListener('click', () => show(at - 1));
    nextBtn.addEventListener('click', () => show(at + 1));
    box.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') show(at - 1);
      if (e.key === 'ArrowRight') show(at + 1);
    });
    box.addEventListener('click', (e) => { if (e.target === box) box.close(); });
    box.addEventListener('close', () => {
      resetZoom();
      root.classList.remove('menu-open');
      if (opener) opener.focus({ preventScroll: true });
    });
  }

  /* Floating enquiry: only when no other WhatsApp call-to-action is on screen */
  const float = d.querySelector('[data-float]');
  if (float && 'IntersectionObserver' in window) {
    const onScreen = new Set();
    const sync = () => float.classList.toggle('is-visible', onScreen.size === 0 && window.scrollY > window.innerHeight * 0.6);
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => (en.isIntersecting ? onScreen.add(en.target) : onScreen.delete(en.target)));
      sync();
    });
    d.querySelectorAll('[data-float-hide], .site-footer').forEach((el) => io.observe(el));
    window.addEventListener('scroll', sync, { passive: true });
  }

  /* Conversion events. Every enquiry control carries data-event (and data-artwork where
     relevant). Forwarded to GA4 when a measurement ID is configured in site.toml; queued on
     dataLayer otherwise, so nothing is lost and nothing is required. */
  d.addEventListener('click', (e) => {
    const el = e.target.closest('[data-event]');
    if (!el) return;
    const params = el.dataset.artwork ? { artwork: el.dataset.artwork } : {};
    if (typeof window.gtag === 'function') window.gtag('event', el.dataset.event, params);
    else (window.dataLayer = window.dataLayer || []).push(Object.assign({ event: el.dataset.event }, params));
  }, true);

  /* Share a painting. Uses the device's own share sheet where it exists — the quickest
     route from "look at this" to a WhatsApp message — and copies the link otherwise.
     Hidden until this runs, so it never sits there as a control that does nothing. */
  const share = d.querySelector('[data-share]');
  if (share && (navigator.share || navigator.clipboard)) {
    share.hidden = false;
    const label = share.textContent;
    share.addEventListener('click', async () => {
      const data = { title: share.dataset.shareTitle, text: share.dataset.shareTitle, url: location.href };
      try {
        if (navigator.share) await navigator.share(data);
        else {
          await navigator.clipboard.writeText(location.href);
          share.textContent = 'Link copied';
          setTimeout(() => { share.textContent = label; }, 2400);
        }
      } catch (err) { /* the person dismissed the sheet — nothing to do */ }
    });
  }

  /* Contact: compose a WhatsApp message (nothing is sent from the site itself) */
  const form = d.querySelector('[data-wa-form]');
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const data = new FormData(form);
      const name = String(data.get('name') || '').trim();
      const interest = String(data.get('interest') || '').trim();
      const note = String(data.get('text') || '').trim();
      let text = form.dataset.greeting || 'Hi,';
      if (name) text += ` my name is ${name}.`;
      if (interest) text += ` I'm interested in ${interest}.`;
      if (!name && !interest && !note) text += ' I would like to know more about your work.';
      if (note) text += `\n\n${note}`;
      const url = `${form.action}?text=${encodeURIComponent(text)}`;
      const a = d.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener';
      d.body.appendChild(a);
      a.click();
      a.remove();
      /* Submitting opens WhatsApp in another tab, which is silent — nothing on this page
         changes, so a screen reader announces nothing and anyone whose pop-up blocker
         caught the tab is left guessing. This says what happened, and carries the link
         so the message is never lost. */
      const status = form.querySelector('[data-wa-status]');
      if (status) {
        status.textContent = 'Opening WhatsApp with your message. ';
        const link = d.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener';
        link.textContent = 'If nothing opened, continue in WhatsApp here.';
        status.appendChild(link);
      }
    });
  }
})();
