/* DKE - carousel.js
   Beranda: carousel hero lima aplikasi (markup: templates/_components/hero_carousel.html, gaya: custom.css bagian 8c).
   Berkas eksternal tanpa skrip inline dan tanpa atribut event, sehingga CSP tidak dilonggarkan.

   Perilaku:
   - Geser otomatis memakai jeda dari data-interval pada elemen carousel (tidak ada angka jeda di sini).
     Bila atribut hilang atau bukan angka positif, tidak ada geser otomatis.
   - Berhenti sementara saat mouseenter dan focusin; lanjut saat mouseleave dan focusout (hanya bila fokus
     sudah keluar dari carousel). Berhenti juga saat tab tersembunyi (visibilitychange).
   - Tombol Jeda/Putar adalah pilihan tetap pengguna (WCAG 2.2.2) dan tidak dibatalkan oleh mouseleave.
   - prefers-reduced-motion: reduce mematikan geser otomatis; perubahan pengaturan dipantau lewat matchMedia.
   - Keyboard pada kontrol: ArrowLeft/ArrowRight, Home, End. Geser sentuh (swipe) dengan ambang 40 px.
   - aria-live "off" saat geser otomatis, "polite" saat dijeda atau dipindah manual.
   - Tanpa JavaScript: slide pertama tampil dan kontrol tersembunyi; kelas .carousel-js memunculkan kontrol. */
(function () {
  'use strict';

  var root = document.querySelector('[data-carousel]');
  if (!root) return;

  var track = root.querySelector('[data-carousel-track]');
  var controls = root.querySelector('[data-carousel-controls]');
  var slides = Array.prototype.slice.call(root.querySelectorAll('[data-carousel-slide]'));
  var dots = Array.prototype.slice.call(root.querySelectorAll('[data-carousel-dot]'));
  var prevBtn = root.querySelector('[data-carousel-prev]');
  var nextBtn = root.querySelector('[data-carousel-next]');
  var toggleBtn = root.querySelector('[data-carousel-toggle]');
  if (!track || slides.length < 2) return;

  var SWIPE_PX = 40;
  var LABEL_PAUSE = 'Jeda geser otomatis';
  var LABEL_PLAY = 'Putar geser otomatis';

  var interval = parseInt(root.getAttribute('data-interval'), 10);
  var canAuto = interval > 0;                      // NaN > 0 bernilai false
  var reducedQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;

  var state = {
    index: 0,
    userPaused: false,                             // dipilih lewat tombol Jeda
    hover: false,
    focus: false,
    hidden: !!document.hidden,
    reduced: !!(reducedQuery && reducedQuery.matches),
    manual: false                                  // slide baru saja dipindah manual (untuk aria-live)
  };
  var timer = null;

  slides.forEach(function (slide, i) {
    if (slide.classList.contains('is-active')) state.index = i;
  });

  function shouldRun() {
    return canAuto && !state.userPaused && !state.hover && !state.focus && !state.hidden && !state.reduced;
  }

  function syncLive() {
    track.setAttribute('aria-live', shouldRun() && !state.manual ? 'off' : 'polite');
  }

  function syncToggle() {
    if (!toggleBtn) return;
    toggleBtn.hidden = !canAuto || state.reduced;  // tanpa geser otomatis, tombol Jeda tidak berguna
    toggleBtn.setAttribute('aria-label', state.userPaused ? LABEL_PLAY : LABEL_PAUSE);
    root.setAttribute('data-paused', state.userPaused ? 'true' : 'false');
    root.classList.toggle('is-reduced', state.reduced);
  }

  function show(index) {
    var count = slides.length;
    state.index = ((index % count) + count) % count;
    slides.forEach(function (slide, i) {
      slide.classList.toggle('is-active', i === state.index);
    });
    dots.forEach(function (dot, i) {
      var active = i === state.index;
      if (active) dot.setAttribute('aria-current', 'true'); else dot.removeAttribute('aria-current');
      dot.setAttribute('tabindex', active ? '0' : '-1');   // satu perhentian Tab; panah memindahkan slide
    });
  }

  function schedule() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (shouldRun()) {
      timer = setTimeout(function () {
        timer = null;
        state.manual = false;
        syncLive();                                // pastikan "off" sebelum isi slide berubah
        show(state.index + 1);
        schedule();
      }, interval);
    }
    syncLive();
    syncToggle();
  }

  function goTo(index, focusDot) {
    state.manual = true;
    track.setAttribute('aria-live', 'polite');     // pindah manual: umumkan slide baru
    show(index);
    if (focusDot && dots[state.index]) dots[state.index].focus();
    schedule();
  }

  // ---- kontrol ----
  root.addEventListener('click', function (e) {
    var dot = e.target.closest('[data-carousel-dot]');
    if (dot && root.contains(dot)) { goTo(parseInt(dot.getAttribute('data-carousel-dot'), 10), false); return; }
    if (e.target.closest('[data-carousel-prev]')) { goTo(state.index - 1, false); return; }
    if (e.target.closest('[data-carousel-next]')) { goTo(state.index + 1, false); return; }
    if (e.target.closest('[data-carousel-toggle]')) {
      state.userPaused = !state.userPaused;
      schedule();
    }
  });

  if (controls) {
    controls.addEventListener('keydown', function (e) {
      var target;
      if (e.key === 'ArrowRight') target = state.index + 1;
      else if (e.key === 'ArrowLeft') target = state.index - 1;
      else if (e.key === 'Home') target = 0;
      else if (e.key === 'End') target = slides.length - 1;
      else return;
      e.preventDefault();
      goTo(target, !!e.target.closest('[data-carousel-dot]'));
    });
  }

  // ---- jeda sementara: hover, fokus, tab tersembunyi ----
  root.addEventListener('mouseenter', function () { state.hover = true; schedule(); });
  root.addEventListener('mouseleave', function () { state.hover = false; schedule(); });
  root.addEventListener('focusin', function () { state.focus = true; schedule(); });
  root.addEventListener('focusout', function () {
    // Lanjut hanya bila fokus sudah keluar dari carousel (bukan berpindah antar kontrol di dalamnya).
    setTimeout(function () {
      state.focus = root.contains(document.activeElement);
      schedule();
    }, 0);
  });
  document.addEventListener('visibilitychange', function () {
    state.hidden = !!document.hidden;
    schedule();
  });

  // ---- prefers-reduced-motion: dipantau terus, bukan hanya saat muat ----
  if (reducedQuery) {
    var onReducedChange = function (e) {
      state.reduced = !!e.matches;
      schedule();
    };
    if (reducedQuery.addEventListener) reducedQuery.addEventListener('change', onReducedChange);
    else if (reducedQuery.addListener) reducedQuery.addListener(onReducedChange);
  }

  // ---- geser sentuh (swipe) ----
  var startX = null;
  var startY = null;
  track.addEventListener('touchstart', function (e) {
    var t = e.changedTouches[0];
    startX = t.clientX;
    startY = t.clientY;
  }, { passive: true });
  track.addEventListener('touchend', function (e) {
    if (startX === null) return;
    var t = e.changedTouches[0];
    var dx = t.clientX - startX;
    var dy = t.clientY - startY;
    startX = null;
    startY = null;
    if (Math.abs(dx) >= SWIPE_PX && Math.abs(dx) > Math.abs(dy) * 1.5) {
      goTo(dx < 0 ? state.index + 1 : state.index - 1, false);
    }
  }, { passive: true });

  // ---- mulai ----
  root.classList.add('carousel-js');               // memunculkan kontrol (tersembunyi tanpa JavaScript)
  show(state.index);
  schedule();
})();
