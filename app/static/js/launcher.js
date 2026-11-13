/* DKE - launcher.js
   Beranda: pilihan landing_mode (launcher | last_module) untuk Member.
   Disimpan lewat POST /api/settings/global (URL dari <html data-settings-url>), pola yang sama
   dengan theme.js: tampilan diubah dulu (optimis), dibatalkan dengan toast error bila gagal.
   Markup: <button data-landing-option="launcher|last_module" aria-pressed="true|false"> */
(function () {
  'use strict';

  var root = document.documentElement;
  var section = document.querySelector('[data-landing-section]');
  if (!section || root.dataset.member !== '1') return;

  var buttons = Array.prototype.slice.call(section.querySelectorAll('[data-landing-option]'));
  var busy = false;

  function current() {
    var on = buttons.filter(function (b) { return b.getAttribute('aria-pressed') === 'true'; })[0];
    return on ? on.dataset.landingOption : 'launcher';
  }

  function show(value) {
    buttons.forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.landingOption === value));
    });
  }

  function notify(message, type) {
    if (window.toast) window.toast(message, type, type === 'error' ? 5000 : 3500);
  }

  section.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-landing-option]');
    if (!btn || busy) return;
    var next = btn.dataset.landingOption;
    var previous = current();
    if (next === previous) return;

    busy = true;
    show(next);
    fetch(root.dataset.settingsUrl || '/api/settings/global', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ landing_mode: next })
    }).then(function (res) {
      if (!res.ok) { var err = new Error('HTTP ' + res.status); err.status = res.status; throw err; }
      notify(next === 'last_module'
        ? 'Berikutnya DKE akan membuka modul terakhir Anda.'
        : 'Berikutnya DKE akan membuka Beranda.', 'success');
    }).catch(function (err) {
      show(previous);
      notify(err && err.status === 401
        ? 'Sesi Anda berakhir. Silakan masuk lagi untuk menyimpan pengaturan.'
        : 'Pengaturan belum tersimpan. Periksa koneksi lalu coba lagi.', 'error');
    }).then(function () { busy = false; });
  });
})();
