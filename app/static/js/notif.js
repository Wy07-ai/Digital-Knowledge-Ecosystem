/* DKE - notif.js
   Notifikasi Top-Bar (lonceng): tandai dibaca lewat POST /api/notifications/read
   (URL dari <html data-notif-url>), pola yang sama dengan theme.js dan launcher.js.
   Markup di _components/topbar.html:
     [data-notif-badge]       lencana jumlah belum dibaca di lonceng
     [data-notif-read-all]    tombol "Tandai semua dibaca"
     [data-notif-item]        satu notifikasi (<a> bila punya tautan asal, <button> bila tidak),
                              atribut data-notif-id dan data-unread="1|0"
   Klik pada notifikasi bertautan menandainya dibaca sambil tetap membuka halaman asal. */
(function () {
  'use strict';

  var root = document.documentElement;
  var url = root.dataset.notifUrl;
  if (!url || root.dataset.member !== '1') return;

  var bell = document.querySelector('[data-notif-bell]');
  var readAll = document.querySelector('[data-notif-read-all]');

  function notify(message, type) {
    if (window.toast) window.toast(message, type, type === 'error' ? 5000 : 3500);
  }

  function post(body) {
    // keepalive: permintaan tetap terkirim walau peramban langsung berpindah ke halaman asal.
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (res) {
      if (!res.ok) { var err = new Error('HTTP ' + res.status); err.status = res.status; throw err; }
      return res.json();
    });
  }

  function markItemRead(item) {
    item.dataset.unread = '0';
    var dot = item.querySelector('[data-notif-dot]');
    if (dot) { dot.classList.remove('bg-primary'); dot.classList.add('bg-transparent'); }
    var text = item.querySelector('[data-notif-text]');
    if (text) text.classList.remove('font-semibold');
  }

  function showUnread(count) {
    var badge = document.querySelector('[data-notif-badge]');
    if (badge) {
      if (count > 0) badge.textContent = count > 9 ? '9+' : String(count);
      else badge.remove();
    }
    if (bell) bell.setAttribute('aria-label', count > 0 ? 'Notifikasi, ' + count + ' belum dibaca' : 'Notifikasi');
    if (readAll) readAll.hidden = count <= 0;
  }

  document.addEventListener('click', function (e) {
    var all = e.target.closest('[data-notif-read-all]');
    if (all) {
      post({ all: true }).then(function (data) {
        document.querySelectorAll('[data-notif-item][data-unread="1"]').forEach(markItemRead);
        showUnread(data.unread);
        notify('Semua notifikasi ditandai sudah dibaca.', 'success');
      }).catch(function (err) {
        notify(err && err.status === 401
          ? 'Sesi Anda berakhir. Silakan masuk lagi.'
          : 'Notifikasi belum bisa diperbarui. Periksa koneksi lalu coba lagi.', 'error');
      });
      return;
    }

    var item = e.target.closest('[data-notif-item]');
    if (!item || item.dataset.unread !== '1') return;
    var id = Number(item.dataset.notifId);
    if (!id) return;
    var opensPage = item.tagName === 'A';
    post({ id: id }).then(function (data) {
      if (!opensPage) { markItemRead(item); showUnread(data.unread); }
    }).catch(function () {
      if (!opensPage) notify('Notifikasi belum bisa diperbarui. Periksa koneksi lalu coba lagi.', 'error');
    });
  });
})();
