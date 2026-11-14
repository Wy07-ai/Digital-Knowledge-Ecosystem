"""Logika murni modul Forum (tanpa akses database dan tanpa Flask), supaya mudah diuji.

Isi: aturan validasi formulir, perataan pohon balasan ke 3 tingkat tampilan, format tanggal,
inisial avatar, dan aturan privasi profil.

Semua teks pengguna di sini tetap TEKS POLOS. Tidak ada HTML yang dibangun; pelolosan (escape)
dilakukan oleh autoescape Jinja saat template mencetaknya.
"""
import re
from datetime import datetime, timedelta, timezone

# ---- Batas isian (dipakai server, dan dikirim ke template agar JS memakai angka yang sama) ----
TITLE_MIN, TITLE_MAX = 5, 150
THREAD_BODY_MIN, THREAD_BODY_MAX = 10, 5000
POST_MIN, POST_MAX = 3, 3000

# Tampilan balasan bersarang dibatasi 3 tingkat. Balasan yang lebih dalam tetap disimpan dengan
# parent_post_id aslinya, tetapi ditampilkan sejajar dengan tingkat 3 (diberi keterangan "membalas ...").
MAX_DISPLAY_LEVEL = 3

# Nilai pengaturan Forum (module_settings, module_key = 'forum')
SETTING_PRIVACY = "profile_privacy"
SETTING_NOTIFY = "notify_reply"
PRIVACY_CHOICES = ("public", "members", "private")
PRIVACY_LABELS = {
    "public": ("Publik", "Siapa pun, termasuk pengunjung yang belum masuk, dapat melihat profil Forum Anda."),
    "members": ("Hanya anggota", "Hanya pengguna yang sudah masuk yang dapat melihat profil Forum Anda."),
    "private": ("Privat", "Hanya Anda yang dapat melihat halaman profil Forum Anda."),
}
DEFAULT_PRIVACY = "public"

SORT_CHOICES = ("terbaru", "belum-terjawab")

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WIB = timezone(timedelta(hours=7))
_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


# --------------------------------------------------------------------------
# Pembersihan dan validasi teks
# --------------------------------------------------------------------------
def clean_text(value):
    """Normalisasi teks isian: None -> '', ganti CRLF jadi LF, buang karakter kontrol, rapikan tepi.

    Isi TIDAK diubah menjadi HTML dan karakter seperti < > & dibiarkan apa adanya (di-escape saat dicetak).
    """
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_CHARS.sub("", text).strip()


def collapse_spaces(value):
    """Untuk judul satu baris: semua spasi/baris baru beruntun menjadi satu spasi."""
    return re.sub(r"\s+", " ", clean_text(value))


def validate_thread(title, body, category_id, valid_category_ids):
    """Validasi formulir thread baru.

    Mengembalikan (nilai_bersih, galat) di mana galat adalah dict {field: pesan}. Kosong = lolos.
    """
    title = collapse_spaces(title)
    body = clean_text(body)
    errors = {}
    if not title:
        errors["title"] = "Judul wajib diisi."
    elif len(title) < TITLE_MIN:
        errors["title"] = f"Judul terlalu pendek. Tulis minimal {TITLE_MIN} karakter."
    elif len(title) > TITLE_MAX:
        errors["title"] = f"Judul terlalu panjang. Maksimal {TITLE_MAX} karakter (sekarang {len(title)})."

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        category_id = None
    if category_id is None or category_id not in valid_category_ids:
        errors["category"] = "Pilih salah satu kategori."
        category_id = None

    if not body:
        errors["body"] = "Isi thread wajib diisi."
    elif len(body) < THREAD_BODY_MIN:
        errors["body"] = f"Isi terlalu pendek. Jelaskan minimal {THREAD_BODY_MIN} karakter agar mudah dijawab."
    elif len(body) > THREAD_BODY_MAX:
        errors["body"] = f"Isi terlalu panjang. Maksimal {THREAD_BODY_MAX} karakter (sekarang {len(body)})."
    return {"title": title, "body": body, "category_id": category_id}, errors


def validate_post(body):
    """Validasi isi balasan. Mengembalikan (isi_bersih, pesan_galat atau None)."""
    body = clean_text(body)
    if not body:
        return body, "Balasan tidak boleh kosong."
    if len(body) < POST_MIN:
        return body, f"Balasan terlalu pendek. Tulis minimal {POST_MIN} karakter."
    if len(body) > POST_MAX:
        return body, f"Balasan terlalu panjang. Maksimal {POST_MAX} karakter (sekarang {len(body)})."
    return body, None


# --------------------------------------------------------------------------
# Pengaturan
# --------------------------------------------------------------------------
def normalize_privacy(value):
    value = str(value or "").strip().lower()
    return value if value in PRIVACY_CHOICES else DEFAULT_PRIVACY


def notify_enabled(value):
    """Nilai tersimpan -> bool. Belum pernah diatur (None) = aktif. Hanya '0' (dan sejenisnya) yang mematikan."""
    if value is None:
        return True
    return str(value).strip().lower() not in ("0", "false", "off", "tidak", "no", "")


def can_view_profile(privacy, viewer_id, owner_id):
    """Aturan privasi profil Forum. Pemilik selalu boleh melihat profilnya sendiri."""
    if viewer_id is not None and viewer_id == owner_id:
        return True
    privacy = normalize_privacy(privacy)
    if privacy == "public":
        return True
    if privacy == "members":
        return viewer_id is not None
    return False


# --------------------------------------------------------------------------
# Pohon balasan
# --------------------------------------------------------------------------
def flatten_posts(rows, max_level=MAX_DISPLAY_LEVEL):
    """Susun balasan menjadi daftar datar berurutan (penelusuran DFS) dengan tingkat tampilan 1..max_level.

    `rows`: iterable dict/Row dengan kunci id, parent_post_id, created_at, user_id, author_name.
    Hasil: list dict (salinan baris + `level`, `depth`, `reply_to`, `child_count`) dalam urutan baca:
      * balasan tingkat atas diurutkan terlama dulu (percakapan dibaca dari atas ke bawah);
      * anak sebuah balasan muncul tepat di bawah induknya, juga terlama dulu;
      * `depth` = kedalaman sebenarnya di database (1 = tingkat atas), `level` = depth yang dijepit ke max_level;
      * `parent_author` = nama penulis induk (None untuk tingkat atas);
      * `reply_to` = `parent_author` hanya bila depth > max_level, karena balasan itu ditampilkan sejajar
        dengan tingkat terakhir sehingga induknya tidak lagi terlihat dari lekuknya.
    Baris yang induknya tidak ada di daftar (data yatim) diperlakukan sebagai tingkat atas. Siklus
    (data rusak) dipatahkan: baris yang tidak terjangkau dari akar tetap ditampilkan sebagai tingkat atas.
    """
    items = [dict(r) for r in rows]
    by_id = {p["id"]: p for p in items}
    children = {}
    roots = []
    for p in items:
        parent = p.get("parent_post_id")
        if parent is not None and parent in by_id and parent != p["id"]:
            children.setdefault(parent, []).append(p)
        else:
            roots.append(p)

    def sort_key(p):
        return (str(p.get("created_at") or ""), p["id"])

    roots.sort(key=sort_key)
    for kids in children.values():
        kids.sort(key=sort_key)

    ordered, seen = [], set()

    def visit(post, depth):
        if post["id"] in seen:
            return
        seen.add(post["id"])
        post["depth"] = depth
        post["level"] = min(depth, max_level)
        parent = by_id.get(post.get("parent_post_id"))
        post["parent_author"] = parent.get("author_name") if parent else None
        post["reply_to"] = post["parent_author"] if depth > max_level else None
        post["child_count"] = len(children.get(post["id"], []))
        ordered.append(post)
        for kid in children.get(post["id"], []):
            visit(kid, depth + 1)

    # Rekursi dibatasi panjang rantai; untuk data wajar (puluhan tingkat) tidak masalah, dan siklus
    # sudah ditangani `seen`. Iteratif tidak dipakai agar urutan DFS mudah dibaca.
    for root in roots:
        visit(root, 1)
    for p in items:  # sisa (hanya mungkin bila ada siklus)
        if p["id"] not in seen:
            visit(p, 1)
    return ordered


def descendants(rows, post_id):
    """Himpunan id keturunan (anak, cucu, ...) dari post_id. Dipakai tes dan pemeriksaan data."""
    kids = {}
    for r in rows:
        kids.setdefault(r["parent_post_id"], []).append(r["id"])
    found, stack = set(), list(kids.get(post_id, []))
    while stack:
        current = stack.pop()
        if current in found:
            continue
        found.add(current)
        stack.extend(kids.get(current, []))
    return found


# --------------------------------------------------------------------------
# Tampilan
# --------------------------------------------------------------------------
def parse_page(raw):
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def paginate(total, page, per_page):
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


def format_datetime(value):
    """'13 Nov 2026, 14.05 WIB'."""
    dt = parse_time(value)
    if dt is None:
        return value or ""
    return f"{dt.day} {_BULAN[dt.month - 1]} {dt.year}, {dt.hour:02d}.{dt.minute:02d} WIB"


def relative_time(value, now=None):
    """'baru saja', '5 menit lalu', '3 jam lalu', '2 hari lalu'; lewat 30 hari memakai tanggal."""
    dt = parse_time(value)
    if dt is None:
        return value or ""
    now = (now or datetime.now(timezone.utc)).astimezone(WIB)
    seconds = int((now - dt).total_seconds())
    if seconds < 45:
        return "baru saja"
    minutes = seconds // 60
    if minutes < 60:
        return f"{max(minutes, 1)} menit lalu"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} jam lalu"
    days = hours // 24
    if days < 30:
        return f"{days} hari lalu"
    return format_date(value)


def initials(name):
    """'Dewi Anggraini' -> 'DA'; nama kosong -> '?'. Hanya huruf/angka agar aman dan rapi."""
    parts = [p for p in re.split(r"\s+", str(name or "").strip()) if p]
    letters = []
    for part in parts:
        for ch in part:
            if ch.isalnum():
                letters.append(ch.upper())
                break
        if len(letters) == 2:
            break
    return "".join(letters) or "?"


def paragraphs(text):
    """Teks polos -> daftar paragraf (dipisah baris kosong). Baris tunggal tetap satu paragraf
    (baris baru ditampilkan lewat CSS white-space: pre-line), tidak ada HTML yang dibangun."""
    if not text:
        return []
    return [p.strip() for p in re.split(r"\n\s*\n", str(text).replace("\r\n", "\n")) if p.strip()]


def plural_replies(count):
    """0 -> 'Belum ada balasan', n -> 'n balasan'."""
    return "Belum ada balasan" if not count else f"{count} balasan"
