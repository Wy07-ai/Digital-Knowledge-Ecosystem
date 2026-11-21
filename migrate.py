"""migrate.py - runner migrasi skema SQLite untuk DKE.

Versi skema disimpan di `PRAGMA user_version`. Langkah migrasi ada di folder `migrations/`:

    migrations/001_baseline.sql        # versi 1 = skema saat sistem ini dibuat
    migrations/002_nama_perubahan.sql  # atau .py dengan fungsi upgrade(conn)

Aturan:
  * Nomor berurutan tanpa celah (001, 002, ...). Satu langkah = satu berkas = naik satu versi.
  * Tiap langkah berjalan dalam SATU transaksi (BEGIN IMMEDIATE ... COMMIT). Bila gagal,
    langkah itu dibatalkan seluruhnya dan user_version tidak naik.
  * Selama langkah berjalan PRAGMA foreign_keys dimatikan (syarat membangun ulang tabel),
    lalu `PRAGMA foreign_key_check` dijalankan sebelum COMMIT; pelanggaran membatalkan langkah.
  * Berkas .sql berisi pernyataan biasa; JANGAN menulis BEGIN/COMMIT/PRAGMA di dalamnya.
    Berkas .py harus punya `upgrade(conn)` dan tidak boleh memanggil commit()/rollback().
  * Database lama tanpa user_version yang bentuknya cocok dengan baseline hanya ditandai
    versi 1 (data tidak disentuh). Bentuk tidak cocok -> galat, tidak ada yang diubah.
"""
import importlib.util
import os
import re
import sqlite3
from collections import namedtuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS_DIR = os.path.join(BASE_DIR, "migrations")

Migration = namedtuple("Migration", "version name path kind")
_FILE_RE = re.compile(r"^(\d{3,})_([a-z0-9_]+)\.(sql|py)$")


class MigrationError(Exception):
    """Migrasi tidak dapat dijalankan atau gagal; basis data tetap pada versi terakhir yang utuh."""


# ---------------------------------------------------------------------------
# Penemuan berkas migrasi
# ---------------------------------------------------------------------------
def discover_migrations(directory=None):
    """Daftar Migration terurut. Galat bila nomor ganda atau ada celah (harus 1, 2, 3, ...)."""
    directory = directory or MIGRATIONS_DIR
    found = {}
    for fname in sorted(os.listdir(directory)):
        m = _FILE_RE.match(fname)
        if not m:
            continue
        version = int(m.group(1))
        if version in found:
            raise MigrationError(f"Nomor migrasi ganda {version:03d}: {found[version].name} dan {fname}")
        found[version] = Migration(version, fname, os.path.join(directory, fname), m.group(3))
    for expected, version in enumerate(sorted(found), start=1):
        if version != expected:
            raise MigrationError(f"Nomor migrasi harus berurutan tanpa celah: menunggu {expected:03d}, "
                                 f"ditemukan {version:03d}")
    return [found[v] for v in sorted(found)]


def latest_version(directory=None):
    migrations = discover_migrations(directory)
    return migrations[-1].version if migrations else 0


# ---------------------------------------------------------------------------
# Pembantu skema
# ---------------------------------------------------------------------------
def get_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def user_tables(conn):
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


_NOISE_RE = re.compile(r"'(?:[^']|'')*'|--[^\n]*")


def _normalize_sql(sql):
    """Buang komentar dan rapikan spasi, supaya perbedaan format tidak dianggap perbedaan skema."""
    sql = _NOISE_RE.sub(lambda m: m.group(0) if m.group(0).startswith("'") else " ", sql)
    return re.sub(r"\s+", " ", sql).strip()


def schema_signature(conn):
    """{(jenis, nama): sql ternormalisasi} untuk semua tabel dan indeks buatan pengguna.

    Mencakup tipe, NOT NULL, DEFAULT, CHECK, UNIQUE, FK, dan indeks (bukan hanya nama kolom).
    """
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE type IN ('table', 'index') AND name NOT LIKE 'sqlite_%' AND sql IS NOT NULL")
    return {(t, n): _normalize_sql(s) for t, n, s in rows}


def schema_differences(actual, wanted):
    """Daftar perbedaan: item `wanted` yang hilang atau berbeda di `actual` (item ekstra diabaikan)."""
    problems = []
    for key, sql in sorted(wanted.items()):
        if key not in actual:
            problems.append(f"{key[0]} {key[1]}: tidak ada")
        elif actual[key] != sql:
            problems.append(f"{key[0]} {key[1]}: definisi berbeda dari skema acuan")
    return problems


# ---------------------------------------------------------------------------
# Menjalankan satu langkah
# ---------------------------------------------------------------------------
def _statements(sql):
    """Pecah skrip SQL menjadi pernyataan satu per satu (tanpa executescript, yang memaksa COMMIT)."""
    buf = ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            if buf.strip():
                yield buf
            buf = ""
    if buf.strip() and _normalize_sql(buf):
        yield buf  # sisa tanpa titik koma di akhir


def _load_upgrade(path):
    spec = importlib.util.spec_from_file_location("dke_migration_" + os.path.basename(path)[:-3], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "upgrade", None)):
        raise MigrationError(f"{os.path.basename(path)}: harus mendefinisikan upgrade(conn)")
    return module.upgrade


def _run_body(conn, migration):
    if migration.kind == "sql":
        with open(migration.path, encoding="utf-8") as f:
            for stmt in _statements(f.read()):
                conn.execute(stmt)
    else:
        _load_upgrade(migration.path)(conn)


def _apply_step(conn, migration, expected_before, body=None):
    """Satu transaksi: jalankan isi, naikkan user_version, periksa FK, COMMIT. Gagal -> ROLLBACK."""
    try:
        conn.execute("BEGIN IMMEDIATE")
    except sqlite3.Error as exc:
        raise MigrationError(f"Tidak bisa memulai transaksi untuk {migration.name} "
                             f"(database terkunci?): {exc}") from exc
    try:
        # Setelah kunci tulis didapat: pastikan tidak ada proses lain yang sudah menaikkan versi.
        if get_version(conn) != expected_before:
            raise MigrationError(f"{migration.name}: versi database berubah oleh proses lain; jalankan ulang")
        (body or _run_body)(conn, migration)
        conn.execute(f"PRAGMA user_version = {int(migration.version)}")  # ikut transaksi (ikut batal bila gagal)
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise MigrationError(f"{migration.name}: {len(violations)} pelanggaran foreign key setelah migrasi")
        conn.execute("COMMIT")
    except BaseException as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        if isinstance(exc, MigrationError):
            raise
        if isinstance(exc, Exception):
            raise MigrationError(f"{migration.name} gagal dan dibatalkan: {exc}") from exc
        raise


# ---------------------------------------------------------------------------
# API utama
# ---------------------------------------------------------------------------
def migrate(conn, directory=None, log=None):
    """Terapkan migrasi yang belum dijalankan. Mengembalikan daftar versi yang diterapkan.

    Aman dipanggil berulang: bila sudah terbaru, tidak ada yang dilakukan dan hasilnya [].
    """
    log = log or (lambda msg: None)
    migrations = discover_migrations(directory)
    latest = migrations[-1].version if migrations else 0

    conn.commit()
    old_isolation = conn.isolation_level
    fk_was_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.isolation_level = None                      # kendali transaksi di tangan runner
    conn.execute("PRAGMA foreign_keys = OFF")        # tidak berlaku di dalam transaksi, jadi diset dulu
    applied = []
    try:
        version = get_version(conn)
        if version > latest:
            raise MigrationError(
                f"Database berversi {version}, lebih baru dari migrasi terbaru di kode ({latest}). "
                "Perbarui kode aplikasi; jangan jalankan migrasi mundur.")

        if version == 0 and user_tables(conn):
            version = _stamp_legacy(conn, migrations, log)
            applied.append(version)

        for migration in migrations:
            if migration.version <= version:
                continue
            log(f"  menerapkan {migration.name} ...")
            _apply_step(conn, migration, expected_before=version)
            version = migration.version
            applied.append(version)
        return applied
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.execute(f"PRAGMA foreign_keys = {'ON' if fk_was_on else 'OFF'}")
        conn.isolation_level = old_isolation


def _stamp_legacy(conn, migrations, log):
    """Database lama tanpa user_version: tandai sebagai versi 1 bila bentuknya cocok dengan baseline."""
    if not migrations or migrations[0].kind != "sql":
        raise MigrationError("migrations/001_*.sql (baseline) tidak ditemukan")
    baseline = migrations[0]

    ref = sqlite3.connect(":memory:")
    try:
        with open(baseline.path, encoding="utf-8") as f:
            for stmt in _statements(f.read()):
                ref.execute(stmt)
        wanted = {k: v for k, v in schema_signature(ref).items() if k[0] == "table"}
    finally:
        ref.close()

    problems = schema_differences(schema_signature(conn), wanted)
    if problems:
        raise MigrationError(
            "Database lama tanpa versi skema, tetapi bentuknya tidak cocok dengan baseline (versi 1):\n  - "
            + "\n  - ".join(problems)
            + "\nTidak ada yang diubah. Pulihkan dari cadangan, atau jalankan `python seed.py --reset` "
              "bila datanya boleh hilang.")

    log("  database lama cocok dengan baseline: ditandai versi 1 (data tidak diubah)")
    # Baseline bersifat idempoten (IF NOT EXISTS): tabel sudah ada, hanya indeks yang mungkin belum ada yang dibuat.
    _apply_step(conn, baseline, expected_before=0)
    return baseline.version
