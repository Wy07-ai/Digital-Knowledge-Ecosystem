/* DKE - forum.js
   Penyempurnaan progresif untuk Forum. Semua halaman tetap berfungsi penuh tanpa JavaScript:
   server selalu memvalidasi ulang, dan tautan "Balas" punya cadangan ?balas=<id>#form-balas.

   1. Validasi inline pada formulir [data-fm-form]: pesan di bawah field (aria-invalid + teks), penghitung karakter.
   2. Form balas [id=form-balas]: pindah ke bawah balasan yang dituju dengan animasi slide-up (250 ms).
   3. Draf teks disimpan sementara di sessionStorage (tidak hilang bila halaman tertutup tak sengaja).
   4. Tombol kirim dikunci setelah ditekan (cegah kirim ganda) dan dibuka lagi bila halaman dimuat dari cache.

   Teks pengguna (nama penulis, kutipan balasan) dipasang HANYA lewat textContent; tidak ada HTML yang dibangun. */
(function () {
  'use strict';

  var doc = document;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function all(root, selector) { return Array.prototype.slice.call(root.querySelectorAll(selector)); }

  function storage() {
    try { return window.sessionStorage; } catch (e) { return null; }
  }

  // ---------------------------------------------------------------- validasi
  function normalized(el) {
    var v = String(el.value || '').replace(/\r\n/g, '\n').trim();
    return el.tagName === 'INPUT' ? v.replace(/\s+/g, ' ') : v;   // judul satu baris: spasi beruntun jadi satu
  }

  function messageFor(el) {
    var label = el.getAttribute('data-label') || 'Isian';
    var value = normalized(el);
    var min = parseInt(el.getAttribute('data-min'), 10) || 0;
    var max = parseInt(el.getAttribute('data-max'), 10) || 0;
    if (!value) return el.getAttribute('data-empty') || (label + ' belum diisi.');
    if (min && value.length < min) return label + ' terlalu pendek. Tulis minimal ' + min + ' karakter.';
    if (max && value.length > max) return label + ' terlalu panjang. Maksimal ' + max + ' karakter (sekarang ' + value.length + ').';
    return '';
  }

  function wrapOf(el) { return el.closest('[data-fm-field]') || el.parentNode; }

  function setError(el, message) {
    var box = wrapOf(el).querySelector('[data-error-for]');
    if (box) {
      var text = box.querySelector('[data-error-text]');
      if (text) text.textContent = message;
      box.hidden = !message;
    }
    if (message) el.setAttribute('aria-invalid', 'true'); else el.removeAttribute('aria-invalid');
  }

  function updateCounter(el) {
    var max = parseInt(el.getAttribute('data-max'), 10) || 0;
    var counter = wrapOf(el).querySelector('[data-counter-for]');
    if (!counter || !max) return;
    var n = normalized(el).length;
    counter.textContent = n + ' / ' + max;
    counter.classList.toggle('is-over', n > max);
  }

  // ---------------------------------------------------------------- draf
  function draftKey(form) {
    var key = form.getAttribute('data-draft-key');
    return key ? 'dke-fm-draft:' + key : null;
  }

  function restoreDraft(form) {
    var key = draftKey(form), store = storage(), area = form.querySelector('[data-draft]');
    if (!key || !store || !area || area.value) return;     // isian dari server (mis. setelah galat) selalu menang
    try {
      var saved = store.getItem(key);
      if (saved) { area.value = saved; updateCounter(area); }
    } catch (e) { /* abaikan */ }
  }

  function saveDraft(form, area) {
    var key = draftKey(form), store = storage();
    if (!key || !store) return;
    try {
      if (area.value) store.setItem(key, area.value); else store.removeItem(key);
    } catch (e) { /* penyimpanan penuh atau diblokir: abaikan */ }
  }

  function clearDraft(form) {
    var key = draftKey(form), store = storage();
    if (!key || !store) return;
    try { store.removeItem(key); } catch (e) { /* abaikan */ }
  }

  // ---------------------------------------------------------------- formulir
  function initForm(form) {
    var fields = all(form, '[data-validate]');

    fields.forEach(function (field) {
      updateCounter(field);
      field.addEventListener('input', function () {
        updateCounter(field);
        if (field.getAttribute('data-touched')) setError(field, messageFor(field));
        if (field.hasAttribute('data-draft')) saveDraft(form, field);
      });
      field.addEventListener('change', function () {
        field.setAttribute('data-touched', '1');
        setError(field, messageFor(field));
      });
      field.addEventListener('blur', function () {
        field.setAttribute('data-touched', '1');
        setError(field, messageFor(field));
      });
    });
    restoreDraft(form);

    form.addEventListener('submit', function (event) {
      var first = null;
      fields.forEach(function (field) {
        field.setAttribute('data-touched', '1');
        var message = messageFor(field);
        setError(field, message);
        if (message && !first) first = field;
      });
      if (first) {
        event.preventDefault();
        first.focus();
        if (window.toast) window.toast('Periksa kembali isian yang ditandai.', 'error');
        return;
      }
      var button = form.querySelector('[type="submit"]');
      if (button && !button.disabled) {
        button.setAttribute('data-label-before', button.textContent);
        button.setAttribute('aria-busy', 'true');
        if (button.getAttribute('data-busy')) button.textContent = button.getAttribute('data-busy');
        // Dikunci setelah event submit selesai, supaya nilai tombol tetap ikut terkirim.
        setTimeout(function () { button.disabled = true; }, 0);
      }
      clearDraft(form);
    });
  }

  // Halaman dimuat dari cache peramban (tombol Kembali): buka kunci tombol kirim.
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) return;
    all(doc, '[data-fm-form] [type="submit"][aria-busy]').forEach(function (button) {
      button.disabled = false;
      button.removeAttribute('aria-busy');
      var before = button.getAttribute('data-label-before');
      if (before) button.textContent = before;
    });
  });

  // ---------------------------------------------------------------- form balas
  function initReply() {
    var box = doc.getElementById('form-balas');
    var home = doc.getElementById('fm-reply-home');
    if (!box || !home) return;     // Guest atau halaman lain: tidak ada form
    var form = box.querySelector('form');
    var parentInput = form.querySelector('[name="parent_post_id"]');
    var area = form.querySelector('textarea');
    var ctxDefault = box.querySelector('[data-fm-ctx-default]');
    var ctxParent = box.querySelector('[data-fm-ctx-parent]');
    var ctxName = box.querySelector('[data-fm-ctx-name]');
    var ctxExcerpt = box.querySelector('[data-fm-ctx-excerpt]');
    var cancel = box.querySelector('[data-fm-cancel]');
    var buttons = all(doc, '[data-fm-reply]');

    function setContext(author, excerpt) {
      var has = !!author;
      ctxDefault.hidden = has;
      ctxParent.hidden = !has;
      ctxName.textContent = has ? author : '';
      ctxExcerpt.textContent = has ? excerpt : '';
      cancel.hidden = !has;
    }

    function setExpanded(active) {
      buttons.forEach(function (b) { b.setAttribute('aria-expanded', b === active ? 'true' : 'false'); });
    }

    function slideUp() {
      box.classList.remove('fm-form-in');
      void box.offsetWidth;                 // mulai ulang animasi
      box.classList.add('fm-form-in');
    }

    function reveal() {
      slideUp();
      area.focus({ preventScroll: true });
      box.scrollIntoView({ block: 'center', behavior: reduceMotion ? 'auto' : 'smooth' });
    }

    function openFor(button) {
      var item = button.closest('.fm-post');
      if (!item) return;
      item.appendChild(box);                // form tampil tepat di bawah balasan yang dituju
      parentInput.value = button.getAttribute('data-post-id') || '';
      setContext(button.getAttribute('data-author'), button.getAttribute('data-excerpt'));
      setExpanded(button);
      reveal();
    }

    function closeToHome(focus) {
      home.appendChild(box);
      parentInput.value = '';
      setContext(null, '');
      setExpanded(null);
      if (focus) reveal();
    }

    buttons.forEach(function (button) {
      button.addEventListener('click', function (event) {
        event.preventDefault();
        openFor(button);
      });
    });
    cancel.addEventListener('click', function (event) {
      event.preventDefault();
      closeToHome(true);
    });
    all(doc, '[data-fm-reply-top]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        event.preventDefault();
        closeToHome(true);
      });
    });
    // Tekan Esc di kotak balasan yang sedang dipindah: kembali ke posisi bawah.
    area.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && parentInput.value) { event.preventDefault(); closeToHome(true); }
    });
  }

  all(doc, '[data-fm-form]').forEach(initForm);
  initReply();
})();
