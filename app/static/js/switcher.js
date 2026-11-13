/* DKE - switcher.js
   Perilaku popover Top-Bar: App Switcher (9 titik), menu tema, notifikasi, profil.
   Markup: <div data-popover> <button data-popover-toggle> <div data-popover-panel hidden>
   Keyboard: Esc menutup dan mengembalikan fokus; panah/Home/End berpindah antar
   [data-popover-item]; Tab keluar dari panel menutupnya. Hanya satu panel terbuka. */
(function (global) {
  'use strict';

  var openPop = null;

  function toggleOf(p) { return p.querySelector('[data-popover-toggle]'); }
  function panelOf(p) { return p.querySelector('[data-popover-panel]'); }
  function itemsOf(p) {
    return Array.prototype.filter.call(
      panelOf(p).querySelectorAll('[data-popover-item]'),
      function (el) { return !el.disabled; });
  }

  function close(p, returnFocus) {
    if (!p) return;
    panelOf(p).hidden = true;
    toggleOf(p).setAttribute('aria-expanded', 'false');
    if (openPop === p) openPop = null;
    if (returnFocus) toggleOf(p).focus();
  }

  function open(p, focusFirst) {
    if (openPop && openPop !== p) close(openPop);
    panelOf(p).hidden = false;
    toggleOf(p).setAttribute('aria-expanded', 'true');
    openPop = p;
    if (focusFirst) {
      var items = itemsOf(p);
      var checked = panelOf(p).querySelector('[aria-checked="true"], [aria-current="page"]');
      var target = checked || items[0];
      if (target) target.focus();
    }
  }

  document.addEventListener('click', function (e) {
    var toggle = e.target.closest('[data-popover-toggle]');
    if (toggle) {
      var p = toggle.closest('[data-popover]');
      if (openPop === p) close(p); else open(p);
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
    if (!openPop.contains(e.relatedTarget)) close(openPop);
  });

  global.DKE = global.DKE || {};
  global.DKE.switcher = {
    closeAll: function (returnFocus) { close(openPop, returnFocus); }
  };
})(window);
