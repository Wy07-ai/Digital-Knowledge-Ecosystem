/* DKE - switcher.js
   Perilaku popover Top-Bar: App Switcher (9 titik), menu tema, notifikasi, profil.
   Markup: <div data-popover> <button data-popover-toggle> <div data-popover-panel hidden>
   Keyboard: Esc menutup dan mengembalikan fokus; panah/Home/End berpindah antar
   [data-popover-item]; Tab keluar dari panel menutupnya. Hanya satu panel terbuka.
   Pemicu tambahan: tombol mana pun ber-[data-popover-open] + aria-controls=<id panel> (mis. menu Aplikasi di
   bilah navigasi bawah) membuka panel yang sama, tanpa menggandakan isinya. aria-expanded semua pemicu
   dijaga sama, dan Esc mengembalikan fokus ke pemicu yang dipakai. */
(function (global) {
  'use strict';

  var openPop = null;
  var closeTimers = new WeakMap();
  var openers = new WeakMap();   // popover -> pemicu tambahan yang membukanya (bila bukan tombol di bilah atas)

  function toggleOf(p) { return p.querySelector('[data-popover-toggle]'); }
  function panelOf(p) { return p.querySelector('[data-popover-panel]'); }
  function finishClose(panel) {
    panel.hidden = true;
    panel.inert = false;
    panel.removeAttribute('aria-hidden');
    panel.classList.remove('popover-exit');
  }
  function syncOpeners(p, expanded) {
    var panel = panelOf(p);
    if (!panel.id) return;
    Array.prototype.forEach.call(
      document.querySelectorAll('[data-popover-open][aria-controls="' + panel.id + '"]'),
      function (b) { b.setAttribute('aria-expanded', expanded ? 'true' : 'false'); });
  }
  function focusTargetOf(p) {
    var o = openers.get(p);
    return o && o.offsetParent !== null ? o : toggleOf(p);   // pemicu tambahan bisa tersembunyi bila layar berubah
  }
  function itemsOf(p) {
    return Array.prototype.filter.call(
      panelOf(p).querySelectorAll('[data-popover-item]'),
      function (el) { return !el.disabled; });
  }

  function close(p, returnFocus) {
    if (!p) return;
    var panel = panelOf(p);
    var timer = closeTimers.get(panel);
    if (timer) window.clearTimeout(timer);
    toggleOf(p).setAttribute('aria-expanded', 'false');
    syncOpeners(p, false);
    if (openPop === p) openPop = null;
    panel.setAttribute('aria-hidden', 'true');
    panel.inert = true;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      finishClose(panel);
    } else {
      panel.classList.add('popover-exit');
      closeTimers.set(panel, window.setTimeout(function () {
        finishClose(panel);
        closeTimers.delete(panel);
      }, 180));
    }
    if (returnFocus) focusTargetOf(p).focus();
  }

  function open(p, focusFirst) {
    if (openPop && openPop !== p) close(openPop);
    var panel = panelOf(p);
    var timer = closeTimers.get(panel);
    if (timer) window.clearTimeout(timer);
    closeTimers.delete(panel);
    panel.hidden = false;
    panel.inert = false;
    panel.removeAttribute('aria-hidden');
    panel.classList.remove('popover-exit');
    toggleOf(p).setAttribute('aria-expanded', 'true');
    syncOpeners(p, true);
    openPop = p;
    if (focusFirst) {
      var items = itemsOf(p);
      var checked = panelOf(p).querySelector('[aria-checked="true"], [aria-current="page"]');
      var target = checked || items[0];
      if (target) target.focus();
    }
  }

  document.addEventListener('click', function (e) {
    var opener = e.target.closest('[data-popover-open]');
    if (opener) {
      var target = document.getElementById(opener.getAttribute('aria-controls'));
      var op = target && target.closest('[data-popover]');
      if (!op) return;
      if (openPop === op) { close(op); return; }
      openers.set(op, opener);
      open(op, e.detail === 0);          // e.detail === 0: diaktifkan keyboard -> fokus masuk ke panel
      return;
    }
    var toggle = e.target.closest('[data-popover-toggle]');
    if (toggle) {
      var p = toggle.closest('[data-popover]');
      if (openPop === p) close(p); else { openers.delete(p); open(p); }
      return;
    }
    if (openPop && !openPop.contains(e.target)) close(openPop);
  });

  document.addEventListener('keydown', function (e) {
    var p = e.target.closest ? e.target.closest('[data-popover]') : null;

    if (e.key === 'Escape' && openPop) {
      e.preventDefault();
      close(openPop, true);
      return;
    }
    if (!p) return;

    var onToggle = e.target.closest('[data-popover-toggle]');
    if (onToggle && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
      e.preventDefault();
      open(p, true);
      return;
    }
    if (openPop !== p || onToggle) return;

    var items = itemsOf(p);
    if (!items.length) return;
    var i = items.indexOf(document.activeElement);
    var next = null;
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') next = items[(i + 1) % items.length];
    else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') next = items[(i - 1 + items.length) % items.length];
    else if (e.key === 'Home') next = items[0];
    else if (e.key === 'End') next = items[items.length - 1];
    if (next) { e.preventDefault(); next.focus(); }
  });

  // Tab keluar dari popover -> tutup.
  document.addEventListener('focusout', function (e) {
    if (!openPop || !e.relatedTarget) return;
    if (e.relatedTarget.closest && e.relatedTarget.closest('[data-popover-open]')) return;   // klik berikutnya yang menutup
    if (!openPop.contains(e.relatedTarget)) close(openPop);
  });

  global.DKE = global.DKE || {};
  global.DKE.switcher = {
    closeAll: function (returnFocus) { close(openPop, returnFocus); }
  };
})(window);
