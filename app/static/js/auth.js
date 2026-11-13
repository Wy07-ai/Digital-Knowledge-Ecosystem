/* DKE - auth.js
   Validasi inline untuk form Registrasi dan Login (Blueprint 5.5, UC-IS-01/02).
   Aturan dan teks pesan HARUS sama dengan app/infosys/validation.py; server tetap
   menjadi penentu akhir (form memakai novalidate supaya pesan kita yang tampil,
   bukan gelembung bawaan peramban).

   Perilaku:
   - Pesan muncul saat kolom ditinggalkan (blur), lalu diperbarui saat mengetik.
   - Saat kirim: bila ada yang salah, kirim dibatalkan dan fokus ke kolom salah pertama.
   - data-focus pada <form> (diisi server) menentukan kolom yang difokuskan saat dimuat,
     mis. kolom kata sandi setelah kredensial salah (UC-IS-02 alur 4a).
   - Tombol "Tampilkan/Sembunyikan" kata sandi. */
(function () {
  'use strict';

  var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  var MSG = {
    email: 'Email belum valid. Contoh: nama@email.com',
    passwordMin: 'Kata sandi minimal 8 karakter.',
    passwordMax: 'Kata sandi maksimal 128 karakter.',
    passwordRequired: 'Kata sandi wajib diisi.',
    confirm: 'Konfirmasi kata sandi belum sama. Ketik ulang kata sandi yang sama.',
    nameRequired: 'Nama lengkap wajib diisi.',
    nameMax: 'Nama lengkap maksimal 100 karakter.'
  };

  function val(form, name) {
    var el = form.querySelector('[data-field="' + name + '"]');
    return el ? el.value : '';
  }

  // Satu fungsi per kolom; mengembalikan pesan atau '' bila valid. `mode` = 'register' | 'login'.
  var RULES = {
    name: function (form) {
      var v = val(form, 'name').replace(/\s+/g, ' ').trim();
      if (!v) return MSG.nameRequired;
      if (v.length > 100) return MSG.nameMax;
      return '';
    },
    email: function (form) {
      var v = val(form, 'email').trim();
      return (v && v.length <= 254 && EMAIL_RE.test(v)) ? '' : MSG.email;
    },
    password: function (form, mode) {
      var v = val(form, 'password');
      if (mode === 'login') return v ? '' : MSG.passwordRequired;
      if (v.length < 8) return MSG.passwordMin;
      if (v.length > 128) return MSG.passwordMax;
      return '';
    },
    confirm: function (form) {
      return val(form, 'confirm') === val(form, 'password') ? '' : MSG.confirm;
    }
  };

  function fieldEl(form, name) { return form.querySelector('[data-field="' + name + '"]'); }

  function showError(form, name, message) {
    var input = fieldEl(form, name);
    var box = form.querySelector('[data-error-for="' + name + '"]');
    if (!input || !box) return;
    var text = box.querySelector('[data-error-text]');
    if (message) {
      text.textContent = message;
      box.hidden = false;
      input.setAttribute('aria-invalid', 'true');
      input.classList.add('border-red-600');
      input.classList.remove('border-line');
    } else {
      text.textContent = '';
      box.hidden = true;
      input.removeAttribute('aria-invalid');
      input.classList.remove('border-red-600');
      input.classList.add('border-line');
    }
  }

  function initForm(form) {
    var mode = form.dataset.authForm;                       // 'register' | 'login'
    var names = Array.prototype.map.call(form.querySelectorAll('[data-field]'),
      function (el) { return el.dataset.field; });
    var touched = {};

    function validate(name) {
      var message = RULES[name] ? RULES[name](form, mode) : '';
      showError(form, name, message);
      return message;
    }

    names.forEach(function (name) {
      var input = fieldEl(form, name);
      input.addEventListener('blur', function () {
        // Kolom kosong yang baru dilewati dengan Tab tidak langsung dimarahi,
        // kecuali sudah pernah diisi atau sudah ada pesan dari server.
        if (!input.value && !touched[name] && input.getAttribute('aria-invalid') !== 'true') return;
        touched[name] = true;
        validate(name);
        if (name === 'password' && touched.confirm) validate('confirm');
      });
      input.addEventListener('input', function () {
        // Perbarui pesan hanya untuk kolom yang sudah pernah ditinggalkan atau sedang salah,
        // supaya orang yang baru mulai mengetik tidak langsung dimarahi.
        if (touched[name] || input.getAttribute('aria-invalid') === 'true') validate(name);
        if (name === 'password' && touched.confirm) validate('confirm');
      });
    });

    form.addEventListener('submit', function (e) {
      var firstBad = null;
      names.forEach(function (name) {
        touched[name] = true;
        if (validate(name) && !firstBad) firstBad = name;
      });
      if (firstBad) {
        e.preventDefault();
        fieldEl(form, firstBad).focus();
        return;
      }
      var btn = form.querySelector('[data-submit]');       // cegah kirim ganda
      if (btn) { btn.disabled = true; btn.dataset.label = btn.textContent; btn.textContent = 'Memproses...'; }
    });

    // Peramban yang memulihkan halaman dari cache (tombol Kembali): aktifkan tombol lagi.
    window.addEventListener('pageshow', function () {
      var btn = form.querySelector('[data-submit]');
      if (btn && btn.dataset.label) { btn.disabled = false; btn.textContent = btn.dataset.label; }
    });

    // Bawa pilihan tema/tampilan Guest ke akun baru (hanya form registrasi).
    if (mode === 'register') {
      try {
        var t = localStorage.getItem('dke-theme'), v = localStorage.getItem('dke-view');
        var ft = form.querySelector('[name="pref_theme"]'), fv = form.querySelector('[name="pref_view"]');
        if (ft && t) ft.value = t;
        if (fv && v) fv.value = v;
      } catch (err) { /* mode privat: pakai nilai bawaan server */ }
    }

    // Fokus awal sesuai instruksi server.
    var focusName = form.dataset.focus;
    if (focusName && fieldEl(form, focusName)) {
      var target = fieldEl(form, focusName);
      target.focus();
      if (target.select && target.type !== 'password') target.select();
    }
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-toggle-password]');
    if (!btn) return;
    var input = document.getElementById(btn.dataset.togglePassword);
    if (!input) return;
    var show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    btn.textContent = show ? 'Sembunyikan' : 'Tampilkan';
    btn.setAttribute('aria-pressed', String(show));
    input.focus();
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-auth-form]'), initForm);
})();
