/* DKE - elearning.js
   Ruang Belajar (UC-EL-03/04/07):
   1. Tombol "Tandai Selesai": POST JSON ke API progres, lalu perbarui tombol, centang bab di sidebar,
      dan semua progress bar TANPA memuat ulang halaman. Lebar progress bar bertransisi 300 ms (CSS).
   2. Daftar bab di layar sempit: buka/tutup lewat tombol.
   3. Kecepatan video dari Pengaturan: <video> langsung; YouTube/Vimeo lewat postMessage (upaya terbaik). */
(function () {
  'use strict';

  var room = document.querySelector('[data-room]');
  if (!room) return;

  function say(message, type, ms) {
    if (window.toast) window.toast(message, type, ms);
  }

  // ---------- 1. Tandai selesai ----------
  var btn = room.querySelector('[data-complete-btn]');
  var label = room.querySelector('[data-complete-label]');
  var next = room.querySelector('[data-next-btn]');
  var banner = room.querySelector('[data-complete-banner]');
  var pending = false;

  function isDone() { return btn.getAttribute('aria-pressed') === 'true'; }

  function paintButton(done) {
    btn.setAttribute('aria-pressed', done ? 'true' : 'false');
    btn.classList.toggle('is-done', done);
    if (label) label.textContent = done ? 'Selesai · Batalkan' : 'Tandai Selesai';
    // "Berikutnya" menjadi tombol utama setelah materi selesai.
    if (next) next.className = done ? 'el-btn' : 'btn btn-secondary';
  }

  function paintProgress(done, total, percent) {
    var text = done + ' dari ' + total + ' materi · ' + percent + '%';
    room.querySelectorAll('[data-progress-text]').forEach(function (el) { el.textContent = text; });
    room.querySelectorAll('[data-progress-bar]').forEach(function (el) { el.setAttribute('aria-valuenow', String(percent)); });
    room.querySelectorAll('[data-progress-fill]').forEach(function (el) {
      el.style.width = percent + '%';
      el.classList.toggle('is-complete', percent >= 100);
    });
    if (banner) banner.hidden = percent < 100;
  }

  function paintChapter(lessonId, done) {
    var item = room.querySelector('.el-chapter[data-lesson-id="' + lessonId + '"]');
    if (!item) return;
    item.classList.toggle('is-done', done);
    var sr = item.querySelector('[data-done-label]');
    if (sr) sr.textContent = done ? ' (selesai)' : '';
  }

  function setBusy(busy) {
    pending = busy;
    btn.disabled = busy;
    btn.setAttribute('aria-busy', busy ? 'true' : 'false');
  }

  async function toggleComplete() {
    if (pending) return;
    var want = !isDone();
    setBusy(true);
    try {
      var res = await fetch(room.dataset.api, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRF-Token': room.dataset.csrf
        },
        body: JSON.stringify({ completed: want })
      });
      var data = null;
      try { data = await res.json(); } catch (e) { data = null; }
      if (!res.ok || !data || !data.ok) {
        var msg = (data && data.error) || 'Progres belum bisa disimpan. Coba lagi sebentar lagi.';
        if (res.status === 401) msg = 'Sesi Anda berakhir. Silakan masuk lagi, lalu ulangi.';
        say(msg, 'error');
        return;
      }
      paintButton(data.completed);
      paintChapter(data.lesson_id, data.completed);
      paintProgress(data.done, data.total, data.progress_percent);
      if (data.completed) {
        say(data.course_completed ? 'Semua materi selesai. Kerja bagus!' : 'Materi ditandai selesai. Progres tersimpan.', 'success');
      } else {
        say('Tanda selesai dibatalkan.', 'info');
      }
    } catch (err) {
      say('Koneksi bermasalah. Progres belum tersimpan, coba lagi.', 'warning');
    } finally {
      setBusy(false);
      btn.focus({ preventScroll: true });
    }
  }
  if (btn) btn.addEventListener('click', toggleComplete);

  // ---------- 2. Daftar bab di layar sempit ----------
  var side = room.querySelector('[data-chapters]');
  var toggle = room.querySelector('[data-chapters-toggle]');
  if (side && toggle) {
    toggle.addEventListener('click', function () {
      var open = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', open ? 'false' : 'true');
      side.setAttribute('data-collapsed', open ? 'true' : 'false');
    });
  }
  // Bab aktif terlihat di daftar yang bisa digulir.
  var current = room.querySelector('.el-chapter.is-current');
  var list = room.querySelector('.el-chapter-list');
  if (current && list && list.scrollHeight > list.clientHeight) {
    list.scrollTop = Math.max(0, current.offsetTop - list.offsetTop - 8);
  }

  // ---------- 3. Kecepatan video ----------
  var speed = parseFloat(room.dataset.speed) || 1;

  var video = room.querySelector('video[data-player]');
  if (video) {
    var applySpeed = function () { video.playbackRate = speed; };
    applySpeed();
    video.addEventListener('loadedmetadata', applySpeed);
    video.addEventListener('play', applySpeed);
  }

  var frame = room.querySelector('iframe[data-player-frame]');
  if (frame) {
    var kind = frame.dataset.playerFrame;
    var origin = kind === 'youtube' ? 'https://www.youtube-nocookie.com' : 'https://player.vimeo.com';
    var send = function (payload) {
      try { frame.contentWindow.postMessage(JSON.stringify(payload), origin); } catch (e) { /* abaikan */ }
    };
    var push = function () {
      if (kind === 'youtube') send({ event: 'command', func: 'setPlaybackRate', args: [speed] });
      else send({ method: 'setPlaybackRate', value: speed });
    };
    frame.addEventListener('load', function () {
      if (kind === 'youtube') send({ event: 'listening', id: 1, channel: 'widget' });
      // Pemutar butuh waktu siap; kirim beberapa kali (tidak berbahaya bila diulang).
      [400, 1500, 3500].forEach(function (ms) { setTimeout(push, ms); });
    });
    window.addEventListener('message', function (e) {
      if (e.source !== frame.contentWindow || kind !== 'youtube') return;
      var d = e.data;
      if (typeof d === 'string') { try { d = JSON.parse(d); } catch (err) { return; } }
      if (d && (d.event === 'onReady' || d.event === 'initialDelivery')) push();
    });
  }
})();
