"""Pencarian terpadu DKE: kelas, produk, tutorial, artikel, dan topik Forum (halaman /cari).

Hanya data publik yang dicari: judul, deskripsi, ringkasan, kutipan, dan isi topik. Tidak ada
email atau data akun. Aturan keamanan:

  * Semua nilai dari pengguna masuk lewat parameter (`?`), tidak pernah digabung ke teks SQL.
    Nama tabel dan kolom di bawah adalah konstanta kode.
  * Karakter `%`, `_`, dan `\\` pada kata kunci di-escape (`like_pattern`), jadi dicari sebagai teks
    biasa, bukan wildcard. Pola yang sama dengan katalog E-Commerce (app/ecommerce/routes.py).
  * Cuplikan dikembalikan sebagai potongan teks biasa (`highlight_parts`), bukan HTML. Template
    mencetaknya lewat autoescape Jinja dan membungkus potongan yang cocok dengan <mark>.

Penyaring status (lihat schema.sql): kelas hanya `is_published = 1`, produk hanya `is_active = 1`.
Tabel `tutorials`, `articles`, dan `threads` tidak punya kolom status terbit, jadi semua barisnya
publik. Bila kolom status ditambahkan nanti, cukup ubah `where` pada fungsi pencarian aplikasinya.
"""
import re

from flask import url_for

from . import MODULE_BY_KEY

MIN_QUERY_CHARS = 2
MAX_QUERY_CHARS = 100
LIMIT_PER_KIND = 5        # hasil per jenis pada tampilan semua jenis
LIMIT_SINGLE_KIND = 20    # hasil bila satu jenis dipilih lewat ?jenis=
SNIPPET_CHARS = 140

# Urutan = urutan kelompok di halaman. "app" = kunci aplikasi (aksen, nama, halaman utama).
KINDS = (
    {"key": "kelas", "label": "Kelas", "app": "elearning"},
    {"key": "produk", "label": "Produk", "app": "ecommerce"},
    {"key": "tutorial", "label": "Tutorial", "app": "etutorial"},
    {"key": "artikel", "label": "Artikel", "app": "portal"},
    {"key": "topik", "label": "Topik", "app": "forum"},
)
KIND_BY_KEY = {k["key"]: k for k in KINDS}


# --------------------------------------------------------------------------
# Kata kunci
# --------------------------------------------------------------------------
def normalize_query(raw):
    """Rapikan kata kunci: buang spasi tepi dan potong maksimal 100 karakter."""
    return (raw or "").strip()[:MAX_QUERY_CHARS].strip()


def like_pattern(q):
    """Pola LIKE `%q%` dengan \\, %, dan _ di-escape (pakai bersama `ESCAPE '\\'`)."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# --------------------------------------------------------------------------
# Cuplikan
# --------------------------------------------------------------------------
def make_snippet(text, q, width=SNIPPET_CHARS):
    """Potongan teks sepanjang `width` di sekitar kecocokan pertama (awal teks bila tak ada)."""
    flat = " ".join((text or "").split())
    if len(flat) <= width:
        return flat
    hit = re.search(re.escape(q), flat, re.IGNORECASE)
    start = 0 if hit is None else max(0, hit.start() - width // 4)
    end = start + width
    piece = flat[start:end].strip()
    return ("\u2026" if start > 0 else "") + piece + ("\u2026" if end < len(flat) else "")


def highlight_parts(text, q):
    """Pecah teks menjadi [(potongan, cocok)]; potongan cocok = kata kunci (huruf besar/kecil diabaikan).

    Hasilnya teks biasa. Template yang memberi <mark>, sehingga tidak perlu |safe.
    """
    text = text or ""
    parts, pos = [], 0
    for m in re.finditer(re.escape(q), text, re.IGNORECASE):
        if m.start() > pos:
            parts.append((text[pos:m.start()], False))
        parts.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        parts.append((text[pos:], False))
    return parts


# --------------------------------------------------------------------------
# Kueri per aplikasi
# --------------------------------------------------------------------------
def _search(db, *, table, id_col, title_col, text_col, where, order_by, q, limit, extra_cols=""):
    """Hitung semua kecocokan dan ambil `limit` baris teratas (judul cocok dulu, lalu terbaru).

    Semua argumen kecuali `q` dan `limit` adalah konstanta dari kode; `q` selalu parameter.
    Mengembalikan (total, [baris]); limit 0 hanya menghitung.
    """
    pattern = like_pattern(q)
    title_like = f"{title_col} LIKE ? ESCAPE '\\'"
    match = f"({title_like} OR {text_col} LIKE ? ESCAPE '\\')"
    base = f"FROM {table} WHERE {where} AND {match}"
    total = db.execute(f"SELECT COUNT(*) {base}", (pattern, pattern)).fetchone()[0]
    if not limit or not total:
        return total, []
    rows = db.execute(
        f"SELECT {id_col} AS id, {title_col} AS title, {text_col} AS text{extra_cols} {base} "
        f"ORDER BY CASE WHEN {title_like} THEN 0 ELSE 1 END, {order_by} LIMIT ?",
        (pattern, pattern, pattern, limit),
    ).fetchall()
    return total, rows


def search_courses(db, q, limit):
    """E-Learning: judul dan deskripsi kelas yang terbit."""
    return _search(db, table="courses", id_col="id", title_col="title", text_col="description",
                   where="is_published = 1", order_by="created_at DESC, id DESC", q=q, limit=limit)


def search_products(db, q, limit):
    """E-Commerce: nama dan deskripsi produk yang aktif."""
    return _search(db, table="products", id_col="id", title_col="name", text_col="description",
                   where="is_active = 1", order_by="created_at DESC, id DESC", q=q, limit=limit,
                   extra_cols=", slug")


def search_tutorials(db, q, limit):
    """E-Tutorial: judul dan ringkasan tutorial (tabelnya belum punya kolom status terbit)."""
    return _search(db, table="tutorials", id_col="id", title_col="title", text_col="summary",
                   where="1 = 1", order_by="created_at DESC, id DESC", q=q, limit=limit,
                   extra_cols=", slug")


def search_articles(db, q, limit):
    """Portal: judul dan kutipan artikel (tabelnya belum punya kolom status terbit)."""
    return _search(db, table="articles", id_col="id", title_col="title", text_col="excerpt",
                   where="1 = 1", order_by="published_at DESC, id DESC", q=q, limit=limit,
                   extra_cols=", slug")


def search_threads(db, q, limit):
    """Forum: judul dan isi topik."""
    return _search(db, table="threads", id_col="id", title_col="title", text_col="body",
                   where="1 = 1", order_by="created_at DESC, id DESC", q=q, limit=limit)


SEARCHERS = {
    "kelas": search_courses,
    "produk": search_products,
    "tutorial": search_tutorials,
    "artikel": search_articles,
    "topik": search_threads,
}


def _url(kind, row):
    """Halaman detail yang sudah ada untuk satu hasil."""
    if kind == "kelas":
        return url_for("elearning.course_detail", course_id=row["id"])
    if kind == "produk":
        return url_for("ecommerce.product", slug=row["slug"])
    if kind == "tutorial":
        return url_for("etutorial.tutorial", slug=row["slug"])
    if kind == "artikel":
        return url_for("portal.article", slug=row["slug"])
    return url_for("forum.thread", thread_id=row["id"])


def search_all(db, q, kind=None):
    """Cari di semua jenis; mengembalikan satu kelompok per jenis (urutan KINDS).

    Tiap kelompok: {"key", "label", "app" (dict aplikasi), "total", "results"}. Jumlah (`total`) selalu
    dihitung untuk semua jenis. Baris hanya diambil untuk jenis terpilih (`kind`, maks. 20) atau,
    tanpa `kind`, untuk semua jenis (maks. 5 per jenis). Tiap hasil: {"title_parts", "snippet_parts", "url"}.
    """
    groups = []
    for spec in KINDS:
        key = spec["key"]
        wanted = kind is None or kind == key
        limit = (LIMIT_SINGLE_KIND if kind else LIMIT_PER_KIND) if wanted else 0
        total, rows = SEARCHERS[key](db, q, limit)
        results = [
            {
                "title_parts": highlight_parts(row["title"], q),
                "snippet_parts": highlight_parts(make_snippet(row["text"], q), q),
                "url": _url(key, row),
            }
            for row in rows
        ]
        groups.append({"key": key, "label": spec["label"], "app": MODULE_BY_KEY[spec["app"]],
                       "total": total, "results": results})
    return groups
