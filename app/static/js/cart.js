(function () {
  'use strict';

  var cart = document.querySelector('[data-cart-content]');
  if (!cart || typeof window.fetch !== 'function') return;

  var feedback = document.querySelector('[data-cart-feedback]');
  var formatter = new Intl.NumberFormat('id-ID');

  function formatRupiah(amount) {
    return 'Rp ' + formatter.format(amount);
  }

  function notify(message, type) {
    if (feedback) feedback.textContent = message;
    if (typeof window.toast === 'function') window.toast(message, type);
  }

  function updateHeaderCount(count) {
    var badge = document.querySelector('[data-cart-count]');
    var link = document.querySelector('[data-cart-link]');
    var label = document.querySelector('[data-cart-item-count-label]');
    if (badge) {
      badge.textContent = count > 99 ? '99+' : String(count);
    }
    if (link) link.setAttribute('aria-label', 'Keranjang belanja, ' + count + ' item');
    if (label) label.textContent = count + ' item di keranjang';
  }

  function updateSummary(data) {
    var subtotal = cart.querySelector('[data-subtotal]');
    var total = cart.querySelector('[data-total]');
    if (subtotal) subtotal.textContent = formatRupiah(data.subtotal);
    if (total) total.textContent = formatRupiah(data.total);
    updateHeaderCount(data.cart_count);
  }

  function showEmptyCart() {
    var items = cart.querySelector('[data-cart-items]');
    var summary = cart.querySelector('[data-cart-summary]');
    var empty = document.querySelector('[data-cart-empty]');
    cart.hidden = true;
    if (items) items.hidden = true;
    if (summary) summary.hidden = true;
    if (empty) empty.hidden = false;
  }

  function submitCartForm(form) {
    var submit = form.querySelector('button[type="submit"]');
    if (submit) submit.disabled = true;

    window.fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      }
    }).then(function (response) {
      if (response.redirected) {
        window.location.assign(response.url);
        return null;
      }
      return response.json().then(function (data) {
        if (!response.ok || !data.success) {
          throw new Error(data.message || 'Keranjang belum bisa diperbarui.');
        }
        return data;
      });
    }).then(function (data) {
      if (!data) return;
      updateSummary(data);
      if (form.matches('[data-cart-update]')) {
        var row = form.closest('[data-cart-item]');
        var quantity = form.querySelector('[name="qty"]').value;
        var lineTotal = row && row.querySelector('[data-line-total]');
        var quantityLabel = row && row.querySelector('[data-quantity-label]');
        if (lineTotal) {
          lineTotal.textContent = formatRupiah(data.line_total);
        }
        if (quantityLabel) quantityLabel.textContent = 'Jumlah: ' + quantity;
        notify('Jumlah produk diperbarui.', 'success');
      } else {
        var item = form.closest('[data-cart-item]');
        if (item) item.remove();
        if (data.cart_count === 0) showEmptyCart();
        notify('Produk dihapus dari keranjang.', 'success');
      }
    }).catch(function (error) {
      notify(error.message || 'Keranjang belum bisa diperbarui. Periksa koneksi lalu coba lagi.', 'error');
    }).finally(function () {
      if (submit && document.contains(submit)) submit.disabled = false;
    });
  }

  cart.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-cart-update], [data-cart-remove]');
    if (!form || !cart.contains(form)) return;
    event.preventDefault();
    submitCartForm(form);
  });
})();
