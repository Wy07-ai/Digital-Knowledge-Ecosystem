/* DKE - copy.js
   E-Tutorial (UC-ET-03): tombol "Salin" pada blok kode.
   Markup:  <button type="button" data-copy-target="kode-2"><span data-copy-label>Salin</span></button>
            <pre><code id="kode-2">...</code></pre>
   Yang disalin adalah textContent elemen target, yaitu kode mentah apa adanya (bukan HTML), jadi
   karakter seperti < > & tetap benar dan tidak ada markup yang dieksekusi.
   Berhasil -> toast "Kode disalin". Clipboard API hanya ada di HTTPS/localhost; di http:// biasa
   (mis. membuka server lokal dari ponsel lewat IP LAN) dipakai cadangan execCommand('copy'). */
(function () {
  'use strict';

  var MSG_OK = 'Kode disalin';
  var MSG_FAIL = 'Gagal menyalin kode. Pilih kode lalu salin secara manual.';
  var RESET_MS = 2000;

  function say(message, type) {
    if (window.toast) window.toast(message, type);
  }

  // Cadangan untuk konteks tidak aman atau peramban lama.
  function legacyCopy(text) {
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.setAttribute('aria-hidden', 'true');
    // Di luar layar, tapi tetap bisa difokus (iOS menolak elemen display:none). Ukuran font 16px
    // mencegah iOS memperbesar halaman saat textarea mendapat fokus.
    area.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0;font-size:16px;';
    var previous = document.activeElement;
    document.body.appendChild(area);
    area.focus();
    area.select();
    area.setSelectionRange(0, text.length);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(area);
    if (previous && previous.focus) previous.focus();
    return ok;
  }

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return legacyCopy(text); });
    }
    return Promise.resolve(legacyCopy(text));
  }

  function flash(button, label, text) {
    if (!label) return;
    var original = label.dataset.original || label.textContent;
    label.dataset.original = original;
    label.textContent = text;
    button.classList.toggle('is-copied', text !== original);
    clearTimeout(button._resetTimer);
    button._resetTimer = setTimeout(function () {
      label.textContent = original;
      button.classList.remove('is-copied');
    }, RESET_MS);
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-copy-target]');
    if (!button) return;
    var target = document.getElementById(button.getAttribute('data-copy-target'));
    if (!target) { say(MSG_FAIL, 'error'); return; }
    var label = button.querySelector('[data-copy-label]');

    copyText(target.textContent).then(function (ok) {
      if (ok) {
        say(MSG_OK, 'success');
        flash(button, label, 'Tersalin');
      } else {
        say(MSG_FAIL, 'error');
      }
    });
  });
})();
