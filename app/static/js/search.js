/* Pintasan keyboard untuk pencarian: tekan "/" untuk memindahkan fokus ke kolom pencarian di bilah atas.
   Hanya tambahan kenyamanan; pencarian tetap berfungsi tanpa berkas ini (formulir GET ke /cari). */
(function () {
  'use strict';
  var input = document.getElementById('topbar-search');
  if (!input) return;

  document.addEventListener('keydown', function (e) {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
    var t = e.target;
    var tag = t && t.tagName;
    // Jangan merebut karakter "/" saat pengguna sedang mengetik di kolom isian.
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable)) return;
    // Kolom tersembunyi (layar sempit atau Mobile View): biarkan tombol "/" bekerja seperti biasa.
    if (input.offsetParent === null) return;
    e.preventDefault();
    input.focus();
    input.select();
  });
})();
