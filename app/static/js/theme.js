/* DKE - theme.js
   Tema (Light/Dark/Sistem) dan tampilan (Desktop/Mobile).
   - Guest : disimpan di localStorage (dke-theme, dke-view).
   - Member: disimpan lewat POST /api/settings/global (database menang saat halaman
             dimuat, lihat skrip anti-kedip di base.html). Bila gagal tersimpan,
             perubahan dibatalkan dan toast error ditampilkan.
   Klik manual pada pilihan tema memakai efek "circular reveal": warna tema baru tumbuh
   dari ikon tema (View Transitions API). Tanpa dukungan API itu, atau saat
   prefers-reduced-motion aktif, tema langsung berganti seperti biasa. Perubahan otomatis
   (mode Sistem mengikuti OS, sinkron antartab, pembatalan gagal simpan) tidak beranimasi.
   API: DKE.prefs.getTheme(), setTheme(t), getView(), setView(v), isDark() */
(function (global) {
  'use strict';

  var root = document.documentElement;
  var THEMES = ['light', 'dark', 'system'];
  var VIEWS = ['desktop', 'mobile'];
  var LS = { theme: 'dke-theme', view: 'dke-view' };
  var FIELD = { theme: 'theme', view: 'view_mode' };      // nama kolom user_settings
  var isMember = root.dataset.member === '1';
  var settingsUrl = root.dataset.settingsUrl || '/api/settings/global';
  var mq = global.matchMedia ? global.matchMedia('(prefers-color-scheme: dark)') : null;
  var REVEAL_MS = 550;                                   // durasi lingkaran membesar
  var animating = false;                                 // true selama transisi tema berjalan

  var state = {
    theme: THEMES.indexOf(root.dataset.theme) >= 0 ? root.dataset.theme : 'system',
    view: VIEWS.indexOf(root.dataset.view) >= 0 ? root.dataset.view : 'desktop'
  };

  function isDark() {
    return state.theme === 'dark' || (state.theme === 'system' && !!mq && mq.matches);
  }

  function apply() {
    root.classList.toggle('dark', isDark());
    root.dataset.theme = state.theme;
    root.dataset.view = state.view;
    syncUI();
    document.dispatchEvent(new CustomEvent('dke:prefschange', {
      detail: { theme: state.theme, view: state.view, dark: isDark() }
    }));
  }

  /* ---------- penyimpanan ---------- */
  function saveGuest(kind, value) {
    try { localStorage.setItem(LS[kind], value); } catch (e) { /* mode privat: abaikan */ }
  }

  function saveMember(kind, value, onFail) {
    var body = {};
    body[FIELD[kind]] = value;
    fetch(settingsUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (res) {
      if (res.ok) return;
      var err = new Error('HTTP ' + res.status);
      err.status = res.status;
      throw err;
    }).catch(function (err) {
      onFail(err && err.status === 401
        ? 'Sesi Anda berakhir. Masuk lagi untuk menyimpan pengaturan.'
        : 'Pengaturan belum tersimpan ke akun Anda. Periksa koneksi lalu coba lagi.');
    });
  }

  function set(kind, value, allowed, animate) {
    if (allowed.indexOf(value) < 0 || state[kind] === value) return;
    var previous = state[kind];
    var wasDark = isDark();
    state[kind] = value;

    if (kind === 'theme') {
      var change = function () { apply(); spin(); };
      // Efek hanya bila warna benar-benar berubah (mis. Terang -> Sistem di OS terang tidak).
      if (animate && isDark() !== wasDark) reveal(change); else change();
    } else {
      apply();
    }

    if (isMember) {
      saveMember(kind, value, function (message) {
        if (state[kind] === value) { state[kind] = previous; apply(); }   // batalkan
        if (global.toast) global.toast(message, 'error', 5000);
      });
    } else {
      saveGuest(kind, value);
    }
  }

  /* ---------- transisi lingkaran ---------- */
  function prefersReducedMotion() {
    return !!(global.matchMedia && global.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function setAnimating(on) {
    animating = on;
    if (on) root.setAttribute('data-theme-animating', '1');
    else root.removeAttribute('data-theme-animating');
  }

  // Titik pusat = tengah ikon tema; bila tidak ada/terlihat, tengah layar.
  function revealOrigin() {
    var el = document.querySelector('[data-theme-spin]');
    var r = el && el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    if (r && (r.width || r.height)) return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    return { x: global.innerWidth / 2, y: global.innerHeight / 2 };
  }

  function reveal(change) {
    if (typeof document.startViewTransition !== 'function' || prefersReducedMotion() || animating) {
      change();                                         // fallback: ganti tema langsung, tanpa galat
      return;
    }
    var o = revealOrigin();
    var radius = Math.hypot(Math.max(o.x, global.innerWidth - o.x),
                            Math.max(o.y, global.innerHeight - o.y));
    var at = ' at ' + o.x + 'px ' + o.y + 'px)';
    var noop = function () {};
    var transition;

    setAnimating(true);
    try {
      transition = document.startViewTransition(change);
    } catch (err) {
      setAnimating(false);
      change();
      return;
    }
    if (transition.updateCallbackDone) transition.updateCallbackDone.then(noop, noop);
    transition.ready.then(function () {
      root.animate(
        { clipPath: ['circle(0px' + at, 'circle(' + radius + 'px' + at] },
        { duration: REVEAL_MS, easing: 'ease-in-out', fill: 'both',
          pseudoElement: '::view-transition-new(root)' }
      );
    }).then(noop, noop);                                // transisi dilewati: tema tetap berganti
    transition.finished.then(function () { setAnimating(false); },
                             function () { setAnimating(false); });
  }

  /* ---------- UI ---------- */
  function spin() {
    var el = document.querySelector('[data-theme-spin]');
    if (!el) return;
    el.classList.remove('theme-spin');
    void el.offsetWidth;                       // mulai ulang animasi
    el.classList.add('theme-spin');
  }

  function syncUI() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-theme-option]'), function (b) {
      b.setAttribute('aria-checked', String(b.dataset.themeOption === state.theme));
    });
    Array.prototype.forEach.call(document.querySelectorAll('[data-view-toggle]'), function (b) {
      b.setAttribute('aria-pressed', String(state.view === 'mobile'));
    });
    // Pembacaan status untuk halaman uji: data-pref-readout="theme|dark|view|storage"
    var out = { theme: state.theme, dark: isDark() ? 'ya' : 'tidak', view: state.view,
                storage: isMember ? 'akun (POST /api/settings/global)' : 'localStorage (Guest)' };
    Array.prototype.forEach.call(document.querySelectorAll('[data-pref-readout]'), function (el) {
      el.textContent = out[el.dataset.prefReadout] || '';
    });
  }

  // Selama transisi tema berjalan, tombol tema dan pilihannya tidak bisa ditekan ganda.
  document.addEventListener('click', function (e) {
    if (animating && e.target.closest('[data-theme-toggle], [data-theme-option]')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  document.addEventListener('click', function (e) {
    var opt = e.target.closest('[data-theme-option]');
    if (opt) {
      set('theme', opt.dataset.themeOption, THEMES, true);
      if (global.DKE && global.DKE.switcher) global.DKE.switcher.closeAll(true);
      return;
    }
    if (e.target.closest('[data-view-toggle]')) {
      set('view', state.view === 'mobile' ? 'desktop' : 'mobile', VIEWS);
    }
  });

  // Mode "Sistem": ikuti perubahan preferensi OS secara langsung.
  if (mq) {
    var onSystemChange = function () { if (state.theme === 'system') apply(); };
    if (mq.addEventListener) mq.addEventListener('change', onSystemChange);
    else if (mq.addListener) mq.addListener(onSystemChange);
  }

  // Sinkron antartab untuk Guest.
  global.addEventListener('storage', function (e) {
    if (isMember) return;
    if (e.key === LS.theme && THEMES.indexOf(e.newValue) >= 0) { state.theme = e.newValue; apply(); }
    if (e.key === LS.view && VIEWS.indexOf(e.newValue) >= 0) { state.view = e.newValue; apply(); }
  });

  global.DKE = global.DKE || {};
  global.DKE.prefs = {
    getTheme: function () { return state.theme; },
    setTheme: function (t) { set('theme', t, THEMES); },
    getView: function () { return state.view; },
    setView: function (v) { set('view', v, VIEWS); },
    isDark: isDark
  };

  syncUI();
})(window);
