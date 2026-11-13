/* DKE - panel.js
   Perilaku Control Panel Information System (UC-IS-04..08):
   - Validasi inline form Profil dan Ganti kata sandi (Blueprint 5.5). Aturan dan teks pesan HARUS
     sama dengan app/infosys/validation.py; server tetap penentu akhir (form memakai novalidate).
   - Saat ada isian salah: kirim dibatalkan, toast error muncul, fokus ke kolom salah pertama.
   - Penghitung karakter bio, pratinjau avatar, tombol Tampilkan/Sembunyikan kata sandi.
   - Cadangan avatar: gambar gagal dimuat -> tampilkan inisial.
   - Filter log: pilihan modul langsung diterapkan (tombol Terapkan tetap ada tanpa JS). */
(function () {
  'use strict';

  var MSG = {
    nameRequired: 'Nama lengkap wajib diisi.',
    nameMax: 'Nama lengkap maksimal 100 karakter.',
    bioMax: 'Bio maksimal 300 karakter.',
    avatarInvalid: 'Tautan avatar belum valid. Gunakan alamat gambar yang diawali https://',
    avatarMax: 'Tautan avatar maksimal 500 karakter.',
    currentRequired: 'Kata sandi saat ini wajib diisi.',
    passwordMin: 'Kata sandi minimal 8 karakter.',
    passwordMax: 'Kata sandi maksimal 128 karakter.',
    newSame: 'Kata sandi baru harus berbeda dari kata sandi saat ini.',
    confirm: 'Konfirmasi kata sandi baru belum sama. Ketik ulang kata sandi yang sama.',
    formInvalid: 'Periksa kembali isian yang ditandai.'
  };

  function raw(form, name) {
    var el = form.querySelector('[data-field="' + name + '"]');
    return el ? el.value : '';
  }

  var RULES = {
    name: function (f) {
      var v = raw(f, 'name').replace(/\s+/g, ' ').trim();
      if (!v) return MSG.nameRequired;
      return v.length > 100 ? MSG.nameMax : '';
    },
    bio: function (f) {
      var v = raw(f, 'bio').replace(/\r\n?/g, '\n').trim().replace(/\n{3,}/g, '\n\n');
      return v.length > 300 ? MSG.bioMax : '';
    },
    avatar_url: function (f) { return avatarProblem(raw(f, 'avatar_url').trim()); },
    current_password: function (f) { return raw(f, 'current_password') ? '' : MSG.currentRequired; },
    new_password: function (f) {
      var v = raw(f, 'new_password'), cur = raw(f, 'current_password');
      if (v.length < 8) return MSG.passwordMin;
      if (v.length > 128) return MSG.passwordMax;
      if (cur && v === cur) return MSG.newSame;
      return '';
    },
    confirm_password: function (f) {
      return raw(f, 'confirm_password') === raw(f, 'new_password') ? '' : MSG.confirm;
    }
  };

  // Field yang harus divalidasi ulang saat field lain berubah.
  var DEPENDENTS = { new_password: ['confirm_password'], current_password: ['new_password'] };

  function avatarProblem(url) {
    if (!url) return '';
    if (url.length > 500) return MSG.avatarMax;
    if (/\s/.test(url) || !/^https?:\/\/[^\/\s?#]+/i.test(url)) return MSG.avatarInvalid;
    return '';
  }

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

  function notify(message, type) { if (window.toast) window.toast(message, type); }

  function initForm(form) {
    var names = Array.prototype.map.call(form.querySelectorAll('[data-field]'),
      function (el) { return el.dataset.field; });
    var touched = {};

    function validate(name) {
      var message = RULES[name] ? RULES[name](form) : '';
      showError(form, name, message);
      return message;
    }

    function revalidateDependents(name) {
      (DEPENDENTS[name] || []).forEach(function (dep) {
        if (names.indexOf(dep) >= 0 && touched[dep]) validate(dep);
      });
    }

    names.forEach(function (name) {
      var input = fieldEl(form, name);
      input.addEventListener('blur', function () {
        if (!input.value && !touched[name] && input.getAttribute('aria-invalid') !== 'true') return;
        touched[name] = true;
        validate(name);
        revalidateDependents(name);
      });
      input.addEventListener('input', function () {
        if (touched[name] || input.getAttribute('aria-invalid') === 'true') validate(name);
        revalidateDependents(name);
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
        notify(MSG.formInvalid, 'error');
        fieldEl(form, firstBad).focus();
        return;
      }
      var btn = form.querySelector('[data-submit]');   // cegah kirim ganda
      if (btn) { btn.disabled = true; btn.dataset.label = btn.textContent; btn.textContent = 'Menyimpan...'; }
    });

    window.addEventListener('pageshow', function () {
      var btn = form.querySelector('[data-submit]');
      if (btn && btn.dataset.label) { btn.disabled = false; btn.textContent = btn.dataset.label; }
    });

    var focusName = form.dataset.focus;
    if (focusName && fieldEl(form, focusName)) {
      var target = fieldEl(form, focusName);
      target.focus();
      if (target.select && target.type !== 'password' && target.tagName !== 'TEXTAREA') target.select();
    }
  }

  // ---- Penghitung karakter bio ----
  function initCounters() {
    Array.prototype.forEach.call(document.querySelectorAll('[data-counter-for]'), function (counter) {
      var input = document.querySelector('[data-field="' + counter.dataset.counterFor + '"]');
      var max = Number(counter.dataset.max);
      if (!input) return;
      function update() {
        var n = input.value.length;
        counter.textContent = n + '/' + max;
        counter.classList.toggle('text-red-600', n > max);
        counter.classList.toggle('text-muted', n <= max);
      }
      input.addEventListener('input', update);
      update();
    });
  }

  // ---- Avatar: pratinjau dan cadangan inisial ----
  function setAvatar(wrap, url) {
    var img = wrap.querySelector('img[data-avatar]');
    if (!img) return;
    if (url) { img.hidden = false; if (img.getAttribute('src') !== url) img.setAttribute('src', url); }
    else { img.hidden = true; img.removeAttribute('src'); }
  }

  function initialsOf(name) {
    var parts = name.replace(/\s+/g, ' ').trim().split(' ').filter(Boolean);
    if (!parts.length) return '?';
    return (parts[0].charAt(0) + (parts.length > 1 ? parts[parts.length - 1].charAt(0) : '')).toUpperCase();
  }

  function initAvatarPreview() {
    var box = document.querySelector('[data-avatar-preview]');
    if (!box) return;
    var form = box.closest('form');
    var wrap = box.querySelector('[data-avatar-wrap]');
    var timer;
    function refresh() {
      var url = raw(form, 'avatar_url').trim();
      setAvatar(wrap, avatarProblem(url) ? '' : url);
      var ini = wrap.querySelector('[data-avatar-initials]');
      if (ini) ini.textContent = initialsOf(raw(form, 'name'));
    }
    ['avatar_url', 'name'].forEach(function (n) {
      var el = fieldEl(form, n);
      if (el) el.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(refresh, 350); });
    });
  }

  document.addEventListener('error', function (e) {          // gambar gagal: kembali ke inisial
    var t = e.target;
    if (t && t.matches && t.matches('img[data-avatar]')) t.hidden = true;
  }, true);

  function fixBrokenAvatars() {                                // gagal sebelum skrip ini dimuat
    Array.prototype.forEach.call(document.querySelectorAll('img[data-avatar][src]'), function (img) {
      if (img.complete && img.naturalWidth === 0) img.hidden = true;
    });
  }

  // ---- Tampilkan/Sembunyikan kata sandi ----
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

  // ---- Filter log: terapkan saat pilihan berubah ----
  document.addEventListener('change', function (e) {
    var sel = e.target.closest('[data-autosubmit]');
    if (sel && sel.form) sel.form.submit();
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-panel-form]'), initForm);
  initCounters();
  initAvatarPreview();
  fixBrokenAvatars();
})();
