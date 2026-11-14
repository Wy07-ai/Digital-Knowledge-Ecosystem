"""Katalog produk dan keranjang E-Commerce."""
import sqlite3
from datetime import datetime

from flask import abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from ..db import get_db
from ..utils import csrf_valid, login_required, log_activity, now_iso, notify, safe_next
from . import bp

MAX_CART_QTY = 99
PRODUCT_TYPES = (
    ("course", "Kursus digital"),
    ("ebook", "E-Book"),
    ("template", "Template & aset"),
)
SORT_OPTIONS = {
    "newest": ("Terbaru", "p.created_at DESC, p.id DESC"),
    "price_asc": ("Harga terendah", "p.price ASC, p.name COLLATE NOCASE ASC"),
    "price_desc": ("Harga tertinggi", "p.price DESC, p.name COLLATE NOCASE ASC"),
    "name": ("Nama A-Z", "p.name COLLATE NOCASE ASC"),
}
MSG_CSRF = "Formulir sudah kedaluwarsa. Muat ulang halaman, lalu coba lagi."
PAYMENT_METHODS = (
    ("transfer", "Transfer bank (simulasi)"),
    ("e-wallet", "E-Wallet (simulasi)"),
    ("kartu", "Kartu (simulasi)"),
)
SETTINGS_KEYS = {
    "address": "shipping_address",
    "payment": "preferred_payment_method",
}
MAX_ADDRESS_LENGTH = 1000


@bp.app_template_filter("rupiah")
def rupiah(value):
    """Format angka integer sebagai harga Rupiah, mis. Rp 150.000."""
    return f"Rp {int(value):,}".replace(",", ".")


@bp.app_context_processor
def ecommerce_template_context():
    count = 0
    if g.get("user") is not None and request.blueprint == "ecommerce":
        row = get_db().execute(
            "SELECT COALESCE(SUM(qty), 0) FROM cart_items WHERE user_id = ?",
            (g.user["id"],),
        ).fetchone()
        count = row[0]
    return {"cart_item_count": count}


def _price_value(raw):
    if not raw:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 1_000_000_000_000 else None


def _product(product_id):
    return get_db().execute(
        "SELECT id, name, slug, is_active FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()


def _cart_totals(user_id):
    row = get_db().execute(
        "SELECT COALESCE(SUM(ci.qty * p.price), 0) AS subtotal, "
        "COALESCE(SUM(ci.qty), 0) AS item_count "
        "FROM cart_items ci JOIN products p ON p.id = ci.product_id "
        "WHERE ci.user_id = ?",
        (user_id,),
    ).fetchone()
    return row["subtotal"], row["item_count"]


def _ecommerce_settings(user_id):
    rows = get_db().execute(
        "SELECT setting_key, setting_value FROM module_settings "
        "WHERE user_id = ? AND module_key = 'ecommerce' "
        "AND setting_key IN (?, ?)",
        (user_id, *SETTINGS_KEYS.values()),
    ).fetchall()
    values = {row["setting_key"]: row["setting_value"] or "" for row in rows}
    return {
        "address": values.get(SETTINGS_KEYS["address"], ""),
        "payment_method": values.get(SETTINGS_KEYS["payment"], ""),
    }


def _save_ecommerce_settings(user_id, address, payment_method):
    db = get_db()
    db.executemany(
        "INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) "
        "VALUES (?, 'ecommerce', ?, ?) "
        "ON CONFLICT(user_id, module_key, setting_key) "
        "DO UPDATE SET setting_value = excluded.setting_value",
        (
            (user_id, SETTINGS_KEYS["address"], address),
            (user_id, SETTINGS_KEYS["payment"], payment_method),
        ),
    )
    db.commit()


def _payment_label(value):
    return dict(PAYMENT_METHODS).get(value, "")


def _new_order_code(db, order_date):
    prefix = f"DKE-{order_date}-"
    row = db.execute(
        "SELECT COALESCE(MAX(CAST(substr(order_code, ?) AS INTEGER)), 0) "
        "FROM orders WHERE order_code LIKE ?",
        (len(prefix) + 1, prefix + "%"),
    ).fetchone()
    sequence = row[0] + 1
    if sequence > 9999:
        raise ValueError("Nomor pesanan hari ini sudah mencapai batas.")
    return f"{prefix}{sequence:04d}"


def _wants_json():
    return request.headers.get("X-Requested-With") == "XMLHttpRequest" or (
        request.accept_mimetypes.best == "application/json"
    )


def _csrf_failure():
    if _wants_json():
        return jsonify(success=False, message=MSG_CSRF), 400
    flash(MSG_CSRF, "error")
    return redirect(url_for("ecommerce.cart"))


def _invalid_cart_request(message, status=400):
    if _wants_json():
        return jsonify(success=False, message=message), status
    flash(message, "error")
    return redirect(url_for("ecommerce.cart"))


@bp.route("/")
def index():
    db = get_db()
    categories = db.execute(
        "SELECT id, name, slug FROM categories "
        "WHERE module_key = 'ecommerce' ORDER BY name COLLATE NOCASE"
    ).fetchall()
    category_slug = request.args.get("category", "").strip()
    selected_category = next((c for c in categories if c["slug"] == category_slug), None)

    product_type = request.args.get("type", "").strip()
    if product_type not in {value for value, _label in PRODUCT_TYPES}:
        product_type = ""
    search = request.args.get("q", "").strip()[:100]
    min_price = _price_value(request.args.get("min_price", "").strip())
    max_price = _price_value(request.args.get("max_price", "").strip())
    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price
    sort = request.args.get("sort", "newest")
    if sort not in SORT_OPTIONS:
        sort = "newest"

    clauses = ["p.is_active = 1"]
    params = []
    if selected_category:
        clauses.append("p.category_id = ?")
        params.append(selected_category["id"])
    if product_type:
        clauses.append("p.product_type = ?")
        params.append(product_type)
    if min_price is not None:
        clauses.append("p.price >= ?")
        params.append(min_price)
    if max_price is not None:
        clauses.append("p.price <= ?")
        params.append(max_price)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("(p.name LIKE ? ESCAPE '\\' OR p.description LIKE ? ESCAPE '\\')")
        params.extend((f"%{escaped}%", f"%{escaped}%"))

    products = db.execute(
        "SELECT p.id, p.name, p.slug, p.description, p.price, p.image_url, "
        "p.product_type, c.name AS category_name "
        "FROM products p LEFT JOIN categories c "
        "ON c.id = p.category_id AND c.module_key = 'ecommerce' "
        f"WHERE {' AND '.join(clauses)} ORDER BY {SORT_OPTIONS[sort][1]}",
        params,
    ).fetchall()
    return render_template(
        "ecommerce/index.html",
        page_title="Katalog",
        products=products,
        categories=categories,
        product_types=PRODUCT_TYPES,
        sort_options=SORT_OPTIONS,
        filters={
            "category": category_slug if selected_category else "",
            "type": product_type,
            "q": search,
            "min_price": min_price if min_price is not None else "",
            "max_price": max_price if max_price is not None else "",
            "sort": sort,
        },
    )


@bp.route("/produk/<slug>")
def product(slug):
    item = get_db().execute(
        "SELECT p.*, c.name AS category_name FROM products p "
        "LEFT JOIN categories c ON c.id = p.category_id AND c.module_key = 'ecommerce' "
        "WHERE p.slug = ? AND p.is_active = 1",
        (slug,),
    ).fetchone()
    if item is None:
        abort(404)
    return render_template("ecommerce/product.html", page_title=item["name"], product=item)


@bp.route("/keranjang")
@login_required
def cart():
    db = get_db()
    items = db.execute(
        "SELECT ci.id AS cart_item_id, ci.qty, p.id AS product_id, p.name, p.slug, "
        "p.price, p.image_url, p.product_type "
        "FROM cart_items ci JOIN products p ON p.id = ci.product_id "
        "WHERE ci.user_id = ? ORDER BY ci.added_at DESC, ci.id DESC",
        (g.user["id"],),
    ).fetchall()
    subtotal, item_count = _cart_totals(g.user["id"])
    return render_template(
        "ecommerce/cart.html",
        page_title="Keranjang",
        items=items,
        subtotal=subtotal,
        total=subtotal,
        item_count=item_count,
    )


@bp.post("/keranjang/tambah/<int:product_id>")
def add_to_cart(product_id):
    product = _product(product_id)
    if product is None or not product["is_active"]:
        abort(404)
    if g.get("user") is None:
        flash("Silakan masuk untuk menambahkan produk ke keranjang.", "warning")
        return redirect(url_for("infosys.login", next=url_for("ecommerce.product", slug=product["slug"])))
    if not csrf_valid():
        flash(MSG_CSRF, "error")
        return redirect(url_for("ecommerce.product", slug=product["slug"]))

    db = get_db()
    try:
        db.execute(
            "INSERT INTO cart_items (user_id, product_id, qty) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, product_id) DO UPDATE "
            "SET qty = MIN(cart_items.qty + 1, ?)",
            (g.user["id"], product_id, MAX_CART_QTY),
        )
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise

    flash("Produk ditambahkan ke keranjang.", "success")
    next_url = safe_next(request.form.get("next"))
    return redirect(next_url or url_for("ecommerce.product", slug=product["slug"]))


@bp.post("/keranjang/item/<int:item_id>/jumlah")
@login_required
def update_cart_quantity(item_id):
    if not csrf_valid():
        return _csrf_failure()
    try:
        quantity = int(request.form.get("qty", ""))
    except (TypeError, ValueError):
        return _invalid_cart_request("Masukkan jumlah produk yang valid.")
    if not 1 <= quantity <= MAX_CART_QTY:
        return _invalid_cart_request(f"Jumlah harus antara 1 dan {MAX_CART_QTY}.")

    db = get_db()
    result = db.execute(
        "UPDATE cart_items SET qty = ? WHERE id = ? AND user_id = ?",
        (quantity, item_id, g.user["id"]),
    )
    if result.rowcount == 0:
        if _wants_json():
            return jsonify(success=False, message="Item keranjang tidak ditemukan."), 404
        abort(404)
    db.commit()

    line_total = db.execute(
        "SELECT ci.qty * p.price FROM cart_items ci "
        "JOIN products p ON p.id = ci.product_id WHERE ci.id = ? AND ci.user_id = ?",
        (item_id, g.user["id"]),
    ).fetchone()[0]
    subtotal, item_count = _cart_totals(g.user["id"])
    if _wants_json():
        return jsonify(
            success=True,
            qty=quantity,
            line_total=line_total,
            subtotal=subtotal,
            total=subtotal,
            cart_count=item_count,
        )
    flash("Jumlah produk diperbarui.", "success")
    return redirect(url_for("ecommerce.cart"))


@bp.post("/keranjang/item/<int:item_id>/hapus")
@login_required
def remove_cart_item(item_id):
    if not csrf_valid():
        return _csrf_failure()
    db = get_db()
    result = db.execute(
        "DELETE FROM cart_items WHERE id = ? AND user_id = ?",
        (item_id, g.user["id"]),
    )
    if result.rowcount == 0:
        if _wants_json():
            return jsonify(success=False, message="Item keranjang tidak ditemukan."), 404
        abort(404)
    db.commit()

    subtotal, item_count = _cart_totals(g.user["id"])
    if _wants_json():
        return jsonify(
            success=True,
            subtotal=subtotal,
            total=subtotal,
            cart_count=item_count,
        )
    flash("Produk dihapus dari keranjang.", "success")
    return redirect(url_for("ecommerce.cart"))


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    db = get_db()
    user_id = g.user["id"]
    items = db.execute(
        "SELECT ci.qty, p.id AS product_id, p.name, p.price, p.product_type, "
        "p.course_id, p.is_active "
        "FROM cart_items ci JOIN products p ON p.id = ci.product_id "
        "WHERE ci.user_id = ? ORDER BY ci.added_at, ci.id",
        (user_id,),
    ).fetchall()
    if not items:
        flash("Keranjang masih kosong. Tambahkan produk sebelum checkout.", "warning")
        return redirect(url_for("ecommerce.cart"))

    subtotal = sum(item["price"] * item["qty"] for item in items)
    settings = _ecommerce_settings(user_id)
    address = request.form.get("address", settings["address"]).strip()
    payment_method = request.form.get(
        "payment_method", settings["payment_method"]
    ).strip()
    errors = {}
    if request.method == "POST":
        if not csrf_valid():
            flash(MSG_CSRF, "error")
            return redirect(url_for("ecommerce.checkout"))

        if not address:
            errors["address"] = "Alamat wajib diisi sebelum melakukan pembayaran."
        elif len(address) > MAX_ADDRESS_LENGTH:
            errors["address"] = f"Alamat maksimal {MAX_ADDRESS_LENGTH} karakter."
        if payment_method not in dict(PAYMENT_METHODS):
            errors["payment_method"] = "Pilih metode pembayaran simulasi."
        if errors:
            return render_template(
                "ecommerce/checkout.html",
                page_title="Checkout",
                items=items,
                subtotal=subtotal,
                total=subtotal,
                address=address,
                payment_method=payment_method,
                payment_methods=PAYMENT_METHODS,
                errors=errors,
            ), 400

        try:
            db.execute("BEGIN IMMEDIATE")
            items = db.execute(
                "SELECT ci.qty, p.id AS product_id, p.name, p.price, p.product_type, "
                "p.course_id, p.is_active "
                "FROM cart_items ci JOIN products p ON p.id = ci.product_id "
                "WHERE ci.user_id = ? ORDER BY ci.added_at, ci.id",
                (user_id,),
            ).fetchall()
            if not items:
                db.rollback()
                flash("Keranjang masih kosong. Tambahkan produk sebelum checkout.", "warning")
                return redirect(url_for("ecommerce.cart"))
            if any(not item["is_active"] for item in items):
                db.rollback()
                flash("Hapus produk yang sudah tidak tersedia sebelum checkout.", "error")
                return redirect(url_for("ecommerce.cart"))
            if any(
                item["product_type"] == "course" and item["course_id"] is None
                for item in items
            ):
                db.rollback()
                flash(
                    "Kursus di keranjang belum terhubung ke kelas. Hubungi administrator.",
                    "error",
                )
                return redirect(url_for("ecommerce.cart"))
            subtotal = sum(item["price"] * item["qty"] for item in items)
            order_date = datetime.now().strftime("%Y%m%d")
            order_code = _new_order_code(db, order_date)
            created_at = now_iso()
            cursor = db.execute(
                "INSERT INTO orders "
                "(order_code, user_id, total, status, payment_method, recipient_name, address, created_at) "
                "VALUES (?, ?, ?, 'paid', ?, ?, ?, ?)",
                (
                    order_code,
                    user_id,
                    subtotal,
                    payment_method,
                    g.user["full_name"],
                    address,
                    created_at,
                ),
            )
            order_id = cursor.lastrowid
            db.executemany(
                "INSERT INTO order_items (order_id, product_id, unit_price, qty) "
                "VALUES (?, ?, ?, ?)",
                (
                    (order_id, item["product_id"], item["price"], item["qty"])
                    for item in items
                ),
            )
            for item in items:
                if item["product_type"] == "course" and item["course_id"] is not None:
                    db.execute(
                        "INSERT OR IGNORE INTO enrollments "
                        "(user_id, course_id, source, order_id, enrolled_at) "
                        "VALUES (?, ?, 'order', ?, ?)",
                        (user_id, item["course_id"], order_id, created_at),
                    )
            db.execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))
            notify(
                user_id,
                "Pesanan berhasil dibuat",
                f"Pesanan {order_code} sebesar {rupiah(subtotal)}",
                link=url_for("ecommerce.order_detail", order_code=order_code),
                module="ecommerce",
                commit=False,
            )
            log_activity(
                "ecommerce",
                "checkout",
                f"Pesanan {order_code} dibuat ({rupiah(subtotal)})",
                user_id=user_id,
                commit=False,
            )
            db.commit()
        except Exception:
            db.rollback()
            current_app.logger.exception(
                "Checkout gagal untuk user_id=%s", user_id
            )
            flash(
                "Pembayaran simulasi gagal diproses. Keranjang Anda tetap tersimpan; silakan coba lagi.",
                "error",
            )
            return redirect(url_for("ecommerce.checkout"))

        flash(f"Pesanan {order_code} berhasil dibuat.", "success")
        return redirect(url_for("ecommerce.order_detail", order_code=order_code))

    return render_template(
        "ecommerce/checkout.html",
        page_title="Checkout",
        items=items,
        subtotal=subtotal,
        total=subtotal,
        address=address,
        payment_method=payment_method,
        payment_methods=PAYMENT_METHODS,
        errors=errors,
    )


@bp.route("/pengaturan", methods=["GET", "POST"])
@login_required
def settings():
    values = _ecommerce_settings(g.user["id"])
    errors = {}
    if request.method == "POST":
        if not csrf_valid():
            flash(MSG_CSRF, "error")
            return redirect(url_for("ecommerce.settings"))
        address = request.form.get("address", "").strip()
        payment_method = request.form.get("payment_method", "").strip()
        if len(address) > MAX_ADDRESS_LENGTH:
            errors["address"] = f"Alamat maksimal {MAX_ADDRESS_LENGTH} karakter."
        if payment_method not in dict(PAYMENT_METHODS):
            errors["payment_method"] = "Pilih metode pembayaran favorit."
        if errors:
            return render_template(
                "ecommerce/settings.html",
                page_title="Pengaturan",
                values={"address": address, "payment_method": payment_method},
                payment_methods=PAYMENT_METHODS,
                errors=errors,
            ), 400
        try:
            _save_ecommerce_settings(g.user["id"], address, payment_method)
        except sqlite3.Error:
            get_db().rollback()
            current_app.logger.exception(
                "Gagal menyimpan pengaturan E-Commerce untuk user_id=%s",
                g.user["id"],
            )
            flash("Pengaturan belum bisa disimpan. Coba lagi sebentar lagi.", "error")
            return redirect(url_for("ecommerce.settings"))
        flash("Pengaturan E-Commerce berhasil disimpan.", "success")
        return redirect(url_for("ecommerce.settings"))

    return render_template(
        "ecommerce/settings.html",
        page_title="Pengaturan",
        values=values,
        payment_methods=PAYMENT_METHODS,
        errors=errors,
    )


@bp.route("/pesanan")
@login_required
def orders():
    rows = get_db().execute(
        "SELECT id, order_code, total, status, payment_method, created_at "
        "FROM orders WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (g.user["id"],),
    ).fetchall()
    return render_template(
        "ecommerce/orders.html",
        page_title="Pesanan Saya",
        orders=rows,
        payment_label=_payment_label,
    )


@bp.route("/pesanan/<order_code>")
@login_required
def order_detail(order_code):
    db = get_db()
    order = db.execute(
        "SELECT * FROM orders WHERE order_code = ? AND user_id = ?",
        (order_code, g.user["id"]),
    ).fetchone()
    if order is None:
        abort(404)
    items = db.execute(
        "SELECT oi.unit_price, oi.qty, p.name, p.slug "
        "FROM order_items oi JOIN products p ON p.id = oi.product_id "
        "WHERE oi.order_id = ? ORDER BY oi.id",
        (order["id"],),
    ).fetchall()
    has_course = db.execute(
        "SELECT 1 FROM order_items oi JOIN products p ON p.id = oi.product_id "
        "WHERE oi.order_id = ? AND p.product_type = 'course' AND p.course_id IS NOT NULL LIMIT 1",
        (order["id"],),
    ).fetchone() is not None
    return render_template(
        "ecommerce/order_detail.html",
        page_title="Konfirmasi Pesanan",
        order=order,
        items=items,
        has_course=has_course,
        payment_label=_payment_label(order["payment_method"]),
    )
