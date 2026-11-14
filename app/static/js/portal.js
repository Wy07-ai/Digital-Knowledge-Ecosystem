/* DKE - portal.js
   Portal: bila gambar sampul gagal dimuat (mis. URL eksternal mati), ganti sekali dengan sampul bawaan
   agar kartu tidak menampilkan ikon gambar rusak. Halaman tetap berfungsi penuh tanpa JS. */
(function () {
  'use strict';
  function useFallback(img) {
    var fallback = img.getAttribute('data-fallback');
    if (!fallback || img.getAttribute('data-pt-failed') === '1') return;  // jangan berputar bila bawaan pun gagal
    img.setAttribute('data-pt-failed', '1');
    img.src = fallback;
  }

  var images = document.querySelectorAll('img[data-pt-img]');
  Array.prototype.forEach.call(images, function (img) {
    img.addEventListener('error', function () { useFallback(img); });
    // Gambar yang sudah gagal sebelum skrip berjalan.
    if (img.complete && img.naturalWidth === 0 && img.getAttribute('src')) useFallback(img);
  });
})();
