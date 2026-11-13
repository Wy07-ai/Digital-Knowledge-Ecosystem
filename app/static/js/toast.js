/* DKE - toast.js
   Pengganti alert() bawaan browser (Blueprint 5.5 dan 6.2).
   Pakai:  toast('Produk ditambahkan ke keranjang.', 'success');
           toast(pesan, tipe, ms)   tipe: success | error | info | warning
           ms = 0 -> tidak hilang otomatis (tutup lewat tombol x)
   Masuk dari kanan atas 200 ms, hilang otomatis 3,5 detik, berhenti saat
   disorot kursor atau difokus keyboard. Pesan dipasang lewat textContent (aman dari XSS). */
(function (global) {
  'use strict';

  var ICONS = {
    success: '<path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z"/><path d="m9 12 2 2 4-4"/>',
    error:   '<path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    info:    '<path d="M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    warning: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>'
  };
  // Warna dari Blueprint 6.2; semuanya putih di atasnya dengan kontras >= 4,5:1.
  var BG = {
    success: 'bg-emerald-700',
    error:   'bg-red-600',
    info:    'bg-indigo-600',
    warning: 'bg-amber-700'
  };
  var ALIAS = { danger: 'error', message: 'info', notice: 'info', warn: 'warning', ok: 'success' };
  var MAX_VISIBLE = 5;
  var DEFAULT_MS = 3500;

  function svg(paths, cls) {
    return '<svg class="' + cls + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + paths + '</svg>';
  }

  function normalizeType(type) {
    type = String(type || 'info').toLowerCase();
    type = ALIAS[type] || type;
    return BG[type] ? type : 'info';
  }

  function remove(el) {
    if (!el || el.dataset.closing) return;
    el.dataset.closing = '1';
    clearTimeout(el._timer);
    el.classList.remove('toast-in');
    el.classList.add('toast-out');
    // Pakai timer (bukan animationend) supaya tetap terhapus saat animasi dimatikan
    // oleh prefers-reduced-motion.
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 200);
  }

  function schedule(el, ms) {
    clearTimeout(el._timer);
    if (!ms) return;
    el._deadline = Date.now() + ms;
    el._timer = setTimeout(function () { remove(el); }, ms);
  }

  function toast(message, type, ms) {
    var root = document.getElementById('toast-root');
    if (!root || message == null || message === '') return null;
    type = normalizeType(type);
    ms = (ms === undefined || ms === null) ? DEFAULT_MS : ms;
    message = String(message);

    // Pesan yang sama dan masih tampil: cukup perpanjang waktunya, jangan menumpuk.
    var existing = root.children;
    for (var i = 0; i < existing.length; i++) {
      if (existing[i].dataset.key === type + '|' + message && !existing[i].dataset.closing) {
        existing[i]._ms = ms;
        schedule(existing[i], ms);
        return existing[i];
      }
    }
    while (root.children.length >= MAX_VISIBLE) {      // batasi tumpukan: buang yang tertua
      clearTimeout(root.children[0]._timer);
      root.removeChild(root.children[0]);
    }

    var el = document.createElement('div');
    el.className = 'toast-in flex items-start gap-3 rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ring-1 ring-white/10 ' + BG[type];
    el.setAttribute('role', type === 'error' ? 'alert' : 'status');
    el.dataset.key = type + '|' + message;
    el._ms = ms;

    var icon = document.createElement('span');
    icon.className = 'mt-0.5 flex-none';
    icon.innerHTML = svg(ICONS[type], 'h-5 w-5');

    var text = document.createElement('p');
    text.className = 'min-w-0 flex-1 break-words leading-snug';
    text.textContent = message;

    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'flex-none -m-1.5 flex h-8 w-8 items-center justify-center rounded-md transition hover:bg-white/20 active:scale-95';
    close.setAttribute('aria-label', 'Tutup notifikasi');
    close.innerHTML = svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', 'h-4 w-4');
    close.addEventListener('click', function () { remove(el); });

    el.appendChild(icon); el.appendChild(text); el.appendChild(close);

    // Jeda saat disorot/difokus; lanjutkan dengan sisa waktu (minimal 1,5 detik).
    function pause() { clearTimeout(el._timer); }
    function resume() {
      if (!el._ms) return;
      schedule(el, Math.max(1500, (el._deadline || 0) - Date.now()));
    }
    el.addEventListener('mouseenter', pause);
    el.addEventListener('mouseleave', resume);
    el.addEventListener('focusin', pause);
    el.addEventListener('focusout', resume);

    root.appendChild(el);
    schedule(el, ms);
    return el;
  }

  toast.dismissAll = function () {
    var root = document.getElementById('toast-root');
    if (root) Array.prototype.slice.call(root.children).forEach(remove);
  };

  global.toast = toast;
  (global.DKE = global.DKE || {}).toast = toast;
})(window);
