/* DKE - quiz.js
   Kuis E-Learning (UC-EL-05/06).
   Halaman pengerjaan: satu soal per layar, indikator nomor, jawaban sementara disimpan di localStorage
   (kunci per pengguna dan per kuis), dialog konfirmasi bila ada soal kosong.
   Yang dikirim ke server HANYA pilihan jawaban (q_<id> = a|b|c|d). Skor dihitung server.
   Tanpa JavaScript formulir tetap bisa dikumpulkan (semua soal tampil berurutan).
   Halaman hasil: membersihkan jawaban sementara setelah percobaan tersimpan di server. */
(function () {
  'use strict';

  // localStorage bisa tidak tersedia (mode privat, kuota, kebijakan): semua akses dibungkus try/catch.
  function readStore(key) {
    try { return JSON.parse(window.localStorage.getItem(key) || 'null'); } catch (e) { return null; }
  }
  function writeStore(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* abaikan */ }
  }
  function clearStore(key) {
    try { window.localStorage.removeItem(key); } catch (e) { /* abaikan */ }
  }

  // ---------- Halaman hasil ----------
  var result = document.querySelector('[data-quiz-result]');
  if (result) {
    clearStore(result.getAttribute('data-storage-key'));
    return;
  }

  // ---------- Halaman pengerjaan ----------
  var form = document.querySelector('[data-quiz]');
  if (!form) return;

  var storageKey = form.getAttribute('data-storage-key');
  var steps = Array.prototype.slice.call(form.querySelectorAll('[data-q]'));
  var dots = Array.prototype.slice.call(form.querySelectorAll('[data-goto]'));
  var nav = form.querySelector('[data-qnav]');
  var answeredText = form.querySelector('[data-answered-text]');
  var controls = form.querySelector('[data-controls]');
  var fallback = form.querySelector('[data-fallback]');
  var prevBtn = form.querySelector('[data-prev]');
  var nextBtn = form.querySelector('[data-next]');
  var finishBtn = form.querySelector('[data-finish]');
  var dialog = form.querySelector('[data-confirm]');
  var total = steps.length;
  var current = 0;
  var submitting = false;
  if (!total) return;

  function radiosOf(step) { return step.querySelectorAll('input[type="radio"]'); }
  function chosenOf(step) {
    var checked = step.querySelector('input[type="radio"]:checked');
    return checked ? checked.value : null;
  }
  function isAnswered(step) { return chosenOf(step) !== null; }
  function unansweredNumbers() {
    var out = [];
    steps.forEach(function (step, i) { if (!isAnswered(step)) out.push(i + 1); });
    return out;
  }

  // ---------- Simpan dan pulihkan jawaban sementara ----------
  function save() {
    var answers = {};
    steps.forEach(function (step) {
      var value = chosenOf(step);
      if (value) answers[step.getAttribute('data-qid')] = value;
    });
    writeStore(storageKey, { answers: answers, current: current });
  }

  function restore() {
    var saved = readStore(storageKey);
    if (!saved || typeof saved !== 'object') return;
    var answers = saved.answers && typeof saved.answers === 'object' ? saved.answers : {};
    steps.forEach(function (step) {
      var value = answers[step.getAttribute('data-qid')];
      if (typeof value !== 'string') return;
      // Hanya pulihkan nilai yang masih ada sebagai opsi (soal bisa berubah sejak disimpan).
      radiosOf(step).forEach(function (radio) { if (radio.value === value) radio.checked = true; });
    });
    var index = parseInt(saved.current, 10);
    if (index >= 0 && index < total) current = index;
  }

  // ---------- Tampilan ----------
  function paint() {
    steps.forEach(function (step, i) { step.hidden = i !== current; });
    dots.forEach(function (dot, i) {
      dot.classList.toggle('is-current', i === current);
      dot.classList.toggle('is-answered', isAnswered(steps[i]));
      if (i === current) dot.setAttribute('aria-current', 'step'); else dot.removeAttribute('aria-current');
      dot.setAttribute('aria-label', 'Soal ' + (i + 1) + (isAnswered(steps[i]) ? ', sudah dijawab' : ', belum dijawab'));
    });
    var answered = total - unansweredNumbers().length;
    if (answeredText) answeredText.textContent = 'Soal ' + (current + 1) + ' dari ' + total + ' · terjawab ' + answered + ' dari ' + total;
    var last = current === total - 1;
    if (prevBtn) prevBtn.disabled = current === 0;
    if (nextBtn) nextBtn.hidden = last;
    if (finishBtn) finishBtn.hidden = !last;
  }

  function go(index, focus) {
    current = Math.max(0, Math.min(total - 1, index));
    paint();
    save();
    if (focus) {
      steps[current].focus({ preventScroll: true });
      steps[current].scrollIntoView({ block: 'nearest' });
    }
  }

  // ---------- Kumpulkan ----------
  function reallySubmit() {
    if (submitting) return;
    submitting = true;
    [finishBtn, nextBtn, prevBtn].forEach(function (b) { if (b) b.disabled = true; });
    if (finishBtn) finishBtn.setAttribute('aria-busy', 'true');
    form.submit(); // tidak memicu event submit lagi
  }

  function requestSubmit() {
    var missing = unansweredNumbers();
    if (!missing.length) { reallySubmit(); return; }
    var text = missing.length === 1
      ? 'Soal nomor ' + missing[0] + ' belum dijawab.'
      : missing.length + ' soal belum dijawab: nomor ' + missing.join(', ') + '.';
    if (dialog && typeof dialog.showModal === 'function') {
      dialog.querySelector('[data-confirm-text]').textContent = text;
      dialog.showModal();
      dialog.querySelector('[data-confirm-back]').focus();
    } else if (window.confirm(text + ' Soal kosong dihitung salah. Kumpulkan sekarang?')) {
      reallySubmit();
    } else {
      go(missing[0] - 1, true);
    }
  }

  // ---------- Pasang perilaku ----------
  restore();
  form.classList.add('is-enhanced');
  [nav, answeredText, controls].forEach(function (el) { if (el) el.hidden = false; });
  if (fallback) fallback.hidden = true;
  paint();

  steps.forEach(function (step) {
    step.addEventListener('change', function () { paint(); save(); });
  });
  dots.forEach(function (dot) {
    dot.addEventListener('click', function () { go(parseInt(dot.getAttribute('data-goto'), 10), true); });
  });
  if (prevBtn) prevBtn.addEventListener('click', function () { go(current - 1, true); });
  if (nextBtn) nextBtn.addEventListener('click', function () { go(current + 1, true); });

  // Enter pada pilihan atau tombol Kumpulkan memicu submit: kita ambil alih agar dialog selalu diperiksa.
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    if (!submitting) requestSubmit();
  });

  if (dialog) {
    dialog.querySelector('[data-confirm-back]').addEventListener('click', function () {
      dialog.close();
      var missing = unansweredNumbers();
      if (missing.length) go(missing[0] - 1, true);
    });
    dialog.querySelector('[data-confirm-submit]').addEventListener('click', function () {
      dialog.close();
      reallySubmit();
    });
  }
})();
