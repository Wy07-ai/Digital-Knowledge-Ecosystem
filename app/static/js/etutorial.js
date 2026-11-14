/* DKE - etutorial.js
   E-Tutorial (halaman tutorial dan Pengaturan):
   1. Pengaturan: pratinjau ukuran font berubah langsung saat radio dipilih (nilai tersimpan tetap
      lewat tombol Simpan; formulir bekerja juga tanpa JS).
   2. Stepper: tombol panah kiri/kanan = Sebelumnya/Berikutnya (tidak aktif saat mengetik, saat
      fokus di blok kode, atau bila tombol Ctrl/Alt/Meta/Shift ditekan).
   3. Indikator langkah yang sempit digulir agar langkah aktif terlihat. */
(function () {
  'use strict';

  // ---------- 1. Pratinjau font ----------
  var form = document.querySelector('[data-et-font-form]');
  var preview = document.querySelector('[data-et-preview]');
  if (form && preview) {
    form.addEventListener('change', function (event) {
      var input = event.target;
      if (input && input.name === 'font_size' && ['sm', 'md', 'lg'].indexOf(input.value) >= 0) {
        preview.setAttribute('data-font', input.value);
      }
    });
  }

  // ---------- 2. Panah keyboard ----------
  var prev = document.querySelector('[data-et-prev]');
  var next = document.querySelector('[data-et-next]');
  if (prev || next) {
    document.addEventListener('keydown', function (event) {
      if (event.defaultPrevented || event.ctrlKey || event.altKey || event.metaKey || event.shiftKey) return;
      var el = event.target;
      var tag = el && el.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el && el.isContentEditable)) return;
      if (el && el.closest && el.closest('pre')) return;  // panah dipakai untuk menggulir kode
      var link = event.key === 'ArrowLeft' ? prev : event.key === 'ArrowRight' ? next : null;
      if (link) { event.preventDefault(); link.click(); }
    });
  }

  // ---------- 3. Indikator aktif terlihat ----------
  var dots = document.querySelector('[data-et-dots]');
  var current = dots && dots.querySelector('[aria-current="step"]');
  if (dots && current && dots.scrollWidth > dots.clientWidth) {
    dots.scrollLeft = current.offsetLeft - (dots.clientWidth - current.offsetWidth) / 2;
  }
})();
