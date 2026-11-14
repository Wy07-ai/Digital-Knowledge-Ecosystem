"""Portal: beranda (featured + kartu), filter kategori, detail artikel, preferensi kategori.

Use case (Blueprint 4.x): UC-PT-01 membaca artikel featured dan daftar artikel, UC-PT-02 memfilter
artikel per kategori, UC-PT-03 membaca detail artikel, UC-PT-04 mengatur preferensi kategori (Member).

Aturan penting:
  * Isi artikel berasal dari database, jadi SELALU lewat autoescape Jinja. Template modul ini tidak
    boleh memakai |safe, Markup, atau {% autoescape false %} (dijaga oleh tes).
  * Filter dan halaman memakai query string (?kategori=<slug>&halaman=<n>), sehingga tautan bisa
    dibagikan dan tombol Kembali peramban bekerja. Nilai yang tidak dikenal diabaikan, bukan error,
    dan nomor halaman dijepit ke rentang sah.
  * Preferensi kategori disimpan di module_settings (module_key = 'portal', setting_key =
    'preferred_categories', nilai = slug dipisah koma). Preferensi hanya MENGURUTKAN: kategori
    favorit tampil lebih dulu di beranda, tidak ada artikel yang disembunyikan.
  * Views bertambah satu per sesi peramban untuk tiap artikel (COUNT_ONCE_PER_SESSION), agar muat ulang
    halaman tidak menggelembungkan angka. Ubah konstanta itu ke False bila ingin menghitung tiap kunjungan.
  * Gambar sampul memakai berkas lokal (static/img/portal) atau URL http(s) dari database; nilai lain
    (mis. javascript:) ditolak dan diganti sampul bawaan.
"""
import re
import sqlite3
from datetime import datetime, timedelta, timezone

from flask import abort, current_app, flash, g, redirect, render_template, request, session, url_for

from ..db import get_db
from ..utils import csrf_valid, log_activity, login_required
from . import bp

MODULE_KEY = "portal"
SETTING_CATEGORIES = "preferred_categories"

PER_PAGE = 6          # kartu per halaman (artikel featured ditampilkan terpisah di atas)
RELATED_LIMIT = 3     # jumlah artikel terkait di halaman detail
WORDS_PER_MINUTE = 200
CHARS_PER_WORD = 6    # perkiraan kasar untuk teks Indonesia (termasuk spasi)

COUNT_ONCE_PER_SESSION = True
VIEWED_KEY = "dke_pt_viewed"
VIEWED_MAX = 100      # batas daftar artikel yang diingat sesi (cookie sesi tidak boleh membengkak)

DEFAULT_COVER = "img/portal/default.svg"
COVER_WIDTH, COVER_HEIGHT = 1200, 630
ANON_AUTHOR = "Redaksi DKE"

MSG_CSRF = "Sesi formulir kedaluwarsa. Muat ulang halaman lalu coba lagi."

WIB = timezone(timedelta(hours=7))
_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
_STATIC_PATH = re.compile(r"^[A-Za-z0-9_./-]+$")


# --------------------------------------------------------------------------
# Pembantu tampilan (tanpa akses database, mudah diuji)
# --------------------------------------------------------------------------
def parse_page(raw):
    """Nomor halaman dari query string; nilai buruk jadi 1."""
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def paginate(total, page, per_page=PER_PAGE):
    """Halaman dijepit ke rentang sah, sehingga ?halaman=999 menampilkan halaman terakhir."""
    pages = max(1, -(-total // per_page))
    page = min(max(1, page), pages)
    return {"page": page, "pages": pages, "total": total, "per_page": per_page,
            "offset": (page - 1) * per_page,
            "first": (page - 1) * per_page + 1 if total else 0,
            "last": min(page * per_page, total)}


def parse_time(value):
    """ISO-8601 (tanpa zona dianggap UTC) -> datetime WIB, atau None bila tak terbaca."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(WIB)


def format_date(value):
    """'13 Nov 2026' (WIB); teks asli bila tidak bisa dibaca."""
    dt = parse_time(value)
    if dt is None:
        return value or ""
    return f"{dt.day} {_BULAN[dt.month - 1]} {dt.year}"


def format_views(count):
    """1248 -> '1.248' (pemisah ribuan gaya Indonesia)."""
    return f"{int(count or 0):,}".replace(",", ".")


def estimate_minutes(char_count):
    """Waktu baca perkiraan (menit, minimal 1) dari jumlah karakter isi artikel."""
    words = (char_count or 0) / CHARS_PER_WORD
    return max(1, round(words / WORDS_PER_MINUTE))


def paragraphs(text):
    """Teks polos -> daftar paragraf (dipisah baris kosong). Tiap paragraf tetap teks biasa
    yang di-escape oleh Jinja; tidak ada HTML yang dibangun di sini."""
    if not text:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n", str(text).replace("\r\n", "\n")) if p.strip()]


def cover_src(cover_url):
    """URL gambar sampul yang aman dipakai di <img src>.

    Diterima: http(s)://..., atau jalur relatif di folder static (mis. img/portal/x.svg).
    Selain itu (kosong, javascript:, data:, '..') diganti sampul bawaan.
    """
    value = (cover_url or "").strip()
    if value.lower().startswith(("http://", "https://")) and not any(ch in value for ch in " \r\n\t\"'<>"):
        return value
    if value and _STATIC_PATH.match(value) and ".." not in value and not value.startswith(("/", ".")):
        return url_for("static", filename=value)
    return url_for("static", filename=DEFAULT_COVER)


# --------------------------------------------------------------------------
# Pembantu data
# --------------------------------------------------------------------------
def _select(extra_columns=""):
    """SELECT artikel + kategori + penulis. Parameter fungsi ini hanya konstanta kode."""
    return f"""
    SELECT a.id, a.title, a.slug, a.excerpt, a.cover_url, a.is_featured, a.read_minutes, a.views,
           a.published_at, LENGTH(a.body) AS body_len{extra_columns},
           c.name AS category_name, c.slug AS category_slug, u.full_name AS author_name
      FROM articles a
      LEFT JOIN categories c ON c.id = a.category_id
      LEFT JOIN users u ON u.id = a.author_id
    """


def _view(row):
    """Baris database -> dict siap tampil (sampul, alt, tanggal, waktu baca, penulis)."""
    article = dict(row)
    published = parse_time(article["published_at"])
    article["cover_src"] = cover_src(article.get("cover_url"))
    article["cover_alt"] = f"Sampul artikel: {article['title']}"
    article["read_minutes"] = article.get("read_minutes") or estimate_minutes(article.get("body_len"))
    article["date_label"] = format_date(article["published_at"])
    article["date_iso"] = published.date().isoformat() if published else ""
    article["author_label"] = article.get("author_name") or ANON_AUTHOR
    article["views_label"] = format_views(article["views"])
    return article


def get_categories(db):
    """Kategori Portal + jumlah artikelnya (kategori kosong tetap muncul dengan jumlah 0)."""
    return db.execute(
        "SELECT c.id, c.name, c.slug, COUNT(a.id) AS article_count "
        "FROM categories c LEFT JOIN articles a ON a.category_id = c.id "
        "WHERE c.module_key = ? GROUP BY c.id ORDER BY c.name COLLATE NOCASE",
        (MODULE_KEY,),
    ).fetchall()


def get_preferred(valid_slugs):
    """Slug kategori favorit Member (hanya yang masih ada), selain itu daftar kosong. Guest: kosong."""
    if g.get("user") is None:
        return []
    row = get_db().execute(
        "SELECT setting_value FROM module_settings WHERE user_id = ? AND module_key = ? AND setting_key = ?",
        (g.user["id"], MODULE_KEY, SETTING_CATEGORIES),
    ).fetchone()
    chosen = []
    for part in ((row["setting_value"] if row else "") or "").split(","):
        slug = part.strip().lower()
        if slug in valid_slugs and slug not in chosen:
            chosen.append(slug)
    return chosen


def save_preferred(user_id, slugs):
    """Simpan (atau hapus bila kosong) preferensi kategori di module_settings."""
    db = get_db()
    if slugs:
        db.execute(
            "INSERT INTO module_settings (user_id, module_key, setting_key, setting_value) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, module_key, setting_key) DO UPDATE SET setting_value = excluded.setting_value",
            (user_id, MODULE_KEY, SETTING_CATEGORIES, ",".join(slugs)),
        )
    else:
        db.execute(
            "DELETE FROM module_settings WHERE user_id = ? AND module_key = ? AND setting_key = ?",
            (user_id, MODULE_KEY, SETTING_CATEGORIES),
        )
    db.commit()


def _preference_rank(preferred):
    """Suku ORDER BY (diakhiri koma): kategori favorit = 0, lainnya = 1. Mengembalikan (SQL, parameter);
    SQL kosong bila tidak ada favorit. Hanya jumlah tanda tanya yang dibangun dari kode; nilai slug
    selalu lewat parameter."""
    if not preferred:
        return "", []
    marks = ", ".join("?" for _ in preferred)
    return f"CASE WHEN c.slug IN ({marks}) THEN 0 ELSE 1 END,", list(preferred)


def pick_featured(db, category, preferred):
    """Artikel besar di atas: yang is_featured lebih dulu, lalu kategori favorit, lalu terbaru.
    Bila tidak ada yang featured, artikel terbaru (favorit lebih dulu) dipakai sebagai gantinya."""
    where, params = ("WHERE c.slug = ?", [category]) if category else ("", [])
    rank, rank_params = _preference_rank(preferred)
    row = db.execute(
        _select() + f" {where} ORDER BY a.is_featured DESC, {rank} datetime(a.published_at) DESC, a.id DESC LIMIT 1",
        params + rank_params,
    ).fetchone()
    return _view(row) if row else None


def list_cards(db, category, preferred, exclude_id, limit, offset):
    """Kartu artikel (tanpa artikel besar): kategori favorit dulu, lalu terbaru."""
    clauses, params = [], []
    if category:
        clauses.append("c.slug = ?")
        params.append(category)
    if exclude_id is not None:
        clauses.append("a.id <> ?")
        params.append(exclude_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rank, rank_params = _preference_rank(preferred)
    rows = db.execute(
        _select() + f" {where} ORDER BY {rank} datetime(a.published_at) DESC, a.id DESC LIMIT ? OFFSET ?",
        params + rank_params + [limit, offset],
    ).fetchall()
    return [_view(r) for r in rows]


def related_articles(db, article, limit=RELATED_LIMIT):
    """Artikel lain di kategori yang sama, terbaru dulu. Artikel tanpa kategori tidak punya terkait."""
    if not article.get("category_slug"):
        return []
    rows = db.execute(
        _select() + " WHERE c.slug = ? AND a.id <> ? ORDER BY datetime(a.published_at) DESC, a.id DESC LIMIT ?",
        (article["category_slug"], article["id"], limit),
    ).fetchall()
    return [_view(r) for r in rows]


def _count_view(db, article_id):
    """Tambah views artikel (UPDATE atomik). True bila benar-benar ditambah.

    HEAD tidak dihitung. Bila COUNT_ONCE_PER_SESSION, tiap artikel dihitung sekali per sesi peramban.
    Kegagalan database tidak boleh merusak halaman: dicatat lalu dilewati."""
    if request.method != "GET":
        return False
    seen = list(session.get(VIEWED_KEY, []))
    if COUNT_ONCE_PER_SESSION and article_id in seen:
        return False
    try:
        db.execute("UPDATE articles SET views = views + 1 WHERE id = ?", (article_id,))
        db.commit()
    except sqlite3.Error:
        db.rollback()
        current_app.logger.warning("Gagal menambah views artikel id=%s", article_id, exc_info=True)
        return False
    if COUNT_ONCE_PER_SESSION:
        seen.append(article_id)
        session[VIEWED_KEY] = seen[-VIEWED_MAX:]
    return True


def _pager(info, category):
    """Tautan halaman sebelumnya/berikutnya + nomor yang ditampilkan (dengan elipsis)."""
    page, pages = info["page"], info["pages"]
    shown = sorted({1, pages, page - 1, page, page + 1} & set(range(1, pages + 1)))
    numbers, prev = [], 0
    for n in shown:
        if n - prev > 1:
            numbers.append(None)  # elipsis
        numbers.append(n)
        prev = n
    return {**info, "numbers": numbers,
            "url": lambda n: url_for("portal.index", kategori=category or None, halaman=n if n > 1 else None)}


# --------------------------------------------------------------------------
# Beranda Portal (UC-PT-01, UC-PT-02)
# --------------------------------------------------------------------------
@bp.route("/")
def index():
    db = get_db()
    categories = get_categories(db)
    by_slug = {c["slug"]: c for c in categories}
    all_total = db.execute("SELECT COUNT(*) FROM articles").fetchone()[0]

    req_cat = (request.args.get("kategori") or "").strip().lower()
    category = req_cat if req_cat in by_slug else None
    unknown_filter = bool(req_cat) and category is None

    preferred = get_preferred(set(by_slug))
    featured = pick_featured(db, category, preferred)
    in_filter = by_slug[category]["article_count"] if category else all_total
    card_total = max(0, in_filter - (1 if featured else 0))
    info = paginate(card_total, parse_page(request.args.get("halaman")))
    cards = list_cards(db, category, preferred, featured["id"] if featured else None,
                       info["per_page"], info["offset"]) if card_total else []

    # Chip: favorit lebih dulu (urutan nama tetap di dalam tiap kelompok).
    chips = sorted(
        ({"slug": c["slug"], "name": c["name"], "count": c["article_count"], "preferred": c["slug"] in preferred}
         for c in categories),
        key=lambda chip: not chip["preferred"],
    )
    return render_template(
        "portal/index.html",
        page_title="Portal",
        featured=featured if info["page"] == 1 else None,
        cards=cards,
        chips=chips,
        all_total=all_total,
        category=category,
        category_name=by_slug[category]["name"] if category else None,
        unknown_filter=unknown_filter,
        preferred_names=[by_slug[s]["name"] for s in preferred],
        pager=_pager(info, category),
        cover_size=(COVER_WIDTH, COVER_HEIGHT),
    )


# --------------------------------------------------------------------------
# Detail artikel (UC-PT-03)
# --------------------------------------------------------------------------
@bp.route("/artikel/<slug>")
def article(slug):
    db = get_db()
    row = db.execute(_select(", a.body AS body") + " WHERE a.slug = ?", (slug,)).fetchone()
    if row is None:
        abort(404)
    if _count_view(db, row["id"]):
        # Baca ulang agar angka yang tampil sama dengan database (termasuk kunjungan serentak).
        row = db.execute(_select(", a.body AS body") + " WHERE a.id = ?", (row["id"],)).fetchone()
    item = _view(row)
    item["paragraphs"] = paragraphs(row["body"])
    return render_template(
        "portal/article.html",
        page_title=item["title"],
        article=item,
        related=related_articles(db, item),
        cover_size=(COVER_WIDTH, COVER_HEIGHT),
    )


# --------------------------------------------------------------------------
# Pengaturan: preferensi kategori (UC-PT-04, Member)
# --------------------------------------------------------------------------
@bp.route("/pengaturan", methods=["GET", "POST"])
@login_required
def settings():
    db = get_db()
    categories = get_categories(db)
    valid = {c["slug"] for c in categories}

    if request.method == "POST":
        if not csrf_valid():
            flash(MSG_CSRF, "error")
            return redirect(url_for("portal.settings"))
        action = request.form.get("action", "save")
        if action not in ("save", "reset"):
            abort(400)
        # Slug yang tidak dikenal (formulir lama atau diubah manual) diabaikan; urutan mengikuti kategori.
        submitted = {s.strip().lower() for s in request.form.getlist("categories")}
        chosen = [] if action == "reset" else [c["slug"] for c in categories if c["slug"] in submitted]
        try:
            save_preferred(g.user["id"], chosen)
            log_activity(MODULE_KEY, "portal_preferences",
                         ("Kategori favorit: " + ", ".join(chosen)) if chosen else "Preferensi kategori dihapus")
        except sqlite3.Error:
            db.rollback()
            current_app.logger.exception("Gagal menyimpan preferensi Portal user_id=%s", g.user["id"])
            flash("Preferensi belum bisa disimpan. Coba lagi sebentar lagi.", "error")
            return redirect(url_for("portal.settings"))
        if chosen:
            names = ", ".join(c["name"] for c in categories if c["slug"] in chosen)
            flash(f"Preferensi disimpan. Beranda Portal kini mendahulukan: {names}.", "success")
        else:
            flash("Preferensi dihapus. Beranda Portal kembali diurutkan dari yang terbaru.", "success")
        return redirect(url_for("portal.settings"))

    return render_template(
        "portal/settings.html",
        page_title="Pengaturan Portal",
        categories=categories,
        preferred=get_preferred(valid),
    )
