/* DKE - app.js
   Inisialisasi umum:
   1. Menampilkan pesan flash() Flask sebagai toast (data dari <script id="flash-data">).
   2. Pemicu deklaratif toast untuk halaman uji dan modul:
        <button data-toast="Pesan" data-toast-type="success" data-toast-ms="3500">
        <button data-toast-all>   -> menampilkan keempat jenis berurutan */
(function (global) {
  'use strict';

  global.DKE = global.DKE || {};

  function showFlashMessages() {
    var el = document.getElementById('flash-data');
    if (!el || !global.toast) return;
    var items;
    try { items = JSON.parse(el.textContent); } catch (e) { return; }
    if (!Array.isArray(items)) return;
    items.forEach(function (pair, i) {
      // flask: get_flashed_messages(with_categories=true) -> [[kategori, pesan], ...]
      setTimeout(function () { global.toast(pair[1], pair[0]); }, i * 150);
    });
    el.remove();
  }

  var SAMPLE = [
    ['success', 'Produk ditambahkan ke keranjang.'],
    ['error',   'Email atau kata sandi salah. Periksa kembali dan coba lagi.'],
    ['info',    'Progres belajar tersimpan otomatis.'],
    ['warning', 'Koneksi lambat. Perubahan akan disimpan saat tersambung kembali.']
  ];

  document.addEventListener('click', function (e) {
    var one = e.target.closest('[data-toast]');
    if (one) {
      var ms = one.dataset.toastMs;
      global.toast(one.dataset.toast, one.dataset.toastType || 'info', ms === undefined ? undefined : Number(ms));
      return;
    }
    if (e.target.closest('[data-toast-all]')) {
      SAMPLE.forEach(function (s, i) { setTimeout(function () { global.toast(s[1], s[0]); }, i * 200); });
    }
    if (e.target.closest('[data-toast-clear]')) global.toast.dismissAll();
  });

  showFlashMessages();
})(window);
