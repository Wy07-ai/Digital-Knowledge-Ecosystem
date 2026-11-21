"""Tes sistem migrasi skema (migrate.py, migrations/, seed.py --migrate, PRAGMA user_version).

Jalankan:  python -m unittest tests.test_migrations
"""
import contextlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import migrate  # noqa: E402
import seed  # noqa: E402

SCHEMA_PATH = os.path.join(ROOT, "schema.sql")
BASELINE = os.path.join(ROOT, "migrations", "001_baseline.sql")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def schema_db(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.executescript(read(SCHEMA_PATH))
    return conn


def legacy_db(path):
    """DB buatan skema lama: tabel dari schema.sql, tetapi tanpa user_version, dan berisi data."""
    conn = schema_db(path)
    conn.execute("PRAGMA user_version = 0")
    conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (1, 'Ani', 'ani@x.test', 'h')")
    conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (2, 'Budi', 'b@x.test', 'h')")
    conn.execute("INSERT INTO user_settings (user_id, theme) VALUES (1, 'dark')")
    conn.execute("INSERT INTO courses (id, title, slug) VALUES (1, 'K', 'k')")
    conn.execute("INSERT INTO products (id, name, slug, price, course_id) VALUES (1, 'P', 'p', 5000, 1)")
    conn.execute("INSERT INTO orders (id, order_code, user_id, total) VALUES (1, 'DKE-1', 1, 5000)")
    conn.execute("INSERT INTO order_items (order_id, product_id, unit_price, qty) VALUES (1, 1, 5000, 1)")
    conn.commit()
    return conn


def dump(conn):
    """Isi seluruh tabel (terurut) untuk membandingkan data sebelum dan sesudah."""
    out = {}
    for table in migrate.user_tables(conn):
        out[table] = conn.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
    return out


class TmpCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "dke.db")
        self.mdir = os.path.join(self.tmp, "migrations")
        os.makedirs(self.mdir)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add(self, name, text):
        with open(os.path.join(self.mdir, name), "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(text))

    def add_baseline(self):
        shutil.copy(BASELINE, os.path.join(self.mdir, "001_baseline.sql"))

    def run_seed(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = seed.main(["--db", self.db, *args])
        return code, out.getvalue(), err.getvalue()


class VersionOnFreshDbTests(TmpCase):
    def test_schema_sql_memuat_versi_terbaru(self):
        conn = schema_db()
        self.assertEqual(migrate.get_version(conn), migrate.latest_version())
        conn.close()

    def test_seed_pada_db_baru_menghasilkan_versi_terbaru(self):
        code, out, err = self.run_seed()
        self.assertEqual(code, 0, out + err)
        conn = sqlite3.connect(self.db)
        self.assertEqual(migrate.get_version(conn), migrate.latest_version())
        conn.close()

    def test_reset_mengosongkan_lalu_mengisi_versi_terbaru(self):
        self.run_seed()
        code, out, err = self.run_seed("--reset")
        self.assertEqual(code, 0, out + err)
        conn = sqlite3.connect(self.db)
        self.assertEqual(migrate.get_version(conn), migrate.latest_version())
        conn.close()

    def test_drop_all_tables_mengembalikan_versi_ke_nol(self):
        conn = schema_db()
        seed.drop_all_tables(conn)
        self.assertEqual(migrate.get_version(conn), 0)
        self.assertEqual(migrate.user_tables(conn), [])
        conn.close()

    def test_migrate_pada_berkas_kosong_membangun_skema_penuh(self):
        conn = sqlite3.connect(self.db)
        applied = migrate.migrate(conn)
        self.assertEqual(applied, list(range(1, migrate.latest_version() + 1)))
        self.assertEqual(set(migrate.user_tables(conn)), set(seed.EXPECTED_TABLES))
        conn.close()


class LegacyDbTests(TmpCase):
    def test_db_lama_tanpa_versi_dinaikkan_dan_data_tetap(self):
        conn = legacy_db(self.db)
        self.assertEqual(migrate.get_version(conn), 0)
        before = dump(conn)
        conn.close()

        code, out, err = self.run_seed("--migrate")
        self.assertEqual(code, 0, out + err)

        conn = sqlite3.connect(self.db)
        self.assertEqual(migrate.get_version(conn), 1)
        self.assertEqual(dump(conn), before)
        conn.close()

    def test_migrate_dua_kali_tidak_berefek_pada_kali_kedua(self):
        legacy_db(self.db).close()
        self.assertEqual(self.run_seed("--migrate")[0], 0)
        conn = sqlite3.connect(self.db)
        snapshot = (migrate.get_version(conn), dump(conn), migrate.schema_signature(conn))
        conn.close()

        code, out, err = self.run_seed("--migrate")
        self.assertEqual(code, 0, out + err)
        self.assertIn("sudah versi terbaru", out)

        conn = sqlite3.connect(self.db)
        self.assertEqual((migrate.get_version(conn), dump(conn), migrate.schema_signature(conn)), snapshot)
        conn.close()

    def test_apply_schema_mengarahkan_ke_migrate_bukan_reset(self):
        legacy_db(self.db).close()
        with self.assertRaises(SystemExit) as ctx:
            conn = sqlite3.connect(self.db)
            try:
                seed.apply_schema(conn)
            finally:
                conn.close()
        msg = str(ctx.exception)
        self.assertIn("--migrate", msg)
        self.assertNotIn("--reset", msg)

    def test_seed_pada_db_lama_berhenti_tanpa_mengubah_data(self):
        conn = legacy_db(self.db)
        before = dump(conn)
        conn.close()
        with self.assertRaises(SystemExit) as ctx:
            self.run_seed()
        self.assertIn("--migrate", str(ctx.exception))
        conn = sqlite3.connect(self.db)
        self.assertEqual(dump(conn), before)
        self.assertEqual(migrate.get_version(conn), 0)
        conn.close()

    def test_db_lama_dengan_bentuk_tidak_cocok_ditolak_tanpa_perubahan(self):
        conn = legacy_db(self.db)
        conn.execute("ALTER TABLE users ADD COLUMN extra TEXT")  # kolom tambahan = bukan baseline
        conn.commit()
        before = dump(conn)
        conn.close()

        code, out, err = self.run_seed("--migrate")
        self.assertEqual(code, 1)
        self.assertIn("users", err)
        conn = sqlite3.connect(self.db)
        self.assertEqual(migrate.get_version(conn), 0)
        self.assertEqual(dump(conn), before)
        conn.close()

    def test_db_lama_tanpa_check_dianggap_tidak_cocok(self):
        """Perbedaan non-kolom (CHECK) kini terdeteksi; sebelumnya lolos karena hanya nama kolom yang dibandingkan."""
        conn = legacy_db(self.db)
        sql = read(SCHEMA_PATH).replace("CHECK (price >= 0)", "")
        conn.close()
        os.remove(self.db)
        conn = sqlite3.connect(self.db)
        conn.executescript(sql)
        conn.execute("PRAGMA user_version = 0")
        conn.close()
        code, out, err = self.run_seed("--migrate")
        self.assertEqual(code, 1)
        self.assertIn("products", err)

    def test_db_lebih_baru_dari_kode_ditolak(self):
        conn = schema_db(self.db)
        conn.execute(f"PRAGMA user_version = {migrate.latest_version() + 5}")
        conn.close()
        with self.assertRaises(SystemExit):
            self.run_seed()
        code, out, err = self.run_seed("--migrate")
        self.assertEqual(code, 1)
        self.assertIn("lebih baru", err)

    def test_drift_pada_versi_terbaru_menyarankan_pemulihan(self):
        conn = schema_db(self.db)
        conn.execute("ALTER TABLE users ADD COLUMN extra TEXT")
        conn.commit()
        conn.close()
        with self.assertRaises(SystemExit) as ctx:
            self.run_seed()
        self.assertIn("users", str(ctx.exception))


class FailureAndAtomicityTests(TmpCase):
    def setUp(self):
        super().setUp()
        self.add_baseline()
        conn = legacy_db(self.db)
        conn.close()

    def snapshot(self):
        conn = sqlite3.connect(self.db)
        try:
            return migrate.get_version(conn), migrate.schema_signature(conn), dump(conn)
        finally:
            conn.close()

    def migrate_db(self):
        conn = sqlite3.connect(self.db)
        try:
            return migrate.migrate(conn, self.mdir)
        finally:
            conn.close()

    def test_langkah_sql_gagal_di_tengah_dibatalkan(self):
        self.migrate_db()  # naik ke v1
        before = self.snapshot()
        self.add("002_rusak.sql", """
            CREATE TABLE setengah_jadi (id INTEGER PRIMARY KEY);
            ALTER TABLE users ADD COLUMN baru TEXT;
            INSERT INTO tabel_yang_tidak_ada VALUES (1);
        """)
        with self.assertRaises(migrate.MigrationError) as ctx:
            self.migrate_db()
        self.assertIn("002_rusak.sql", str(ctx.exception))
        self.assertEqual(self.snapshot(), before)  # tidak ada skema setengah jadi, versi tetap 1
        self.assertEqual(before[0], 1)

    def test_langkah_python_gagal_setelah_ddl_dibatalkan(self):
        self.migrate_db()
        before = self.snapshot()
        self.add("002_rusak_py.py", """
            def upgrade(conn):
                conn.execute("CREATE TABLE sisa (id INTEGER)")
                raise RuntimeError("sengaja gagal")
        """)
        with self.assertRaises(migrate.MigrationError):
            self.migrate_db()
        self.assertEqual(self.snapshot(), before)

    def test_langkah_berhasil_tetap_tersimpan_bila_langkah_berikutnya_gagal(self):
        self.migrate_db()
        self.add("002_ok.sql", "CREATE TABLE catatan_ok (id INTEGER PRIMARY KEY);")
        self.add("003_rusak.sql", "CREATE TABLE sisa (id INTEGER); SELECT * FROM tidak_ada;")
        with self.assertRaises(migrate.MigrationError):
            self.migrate_db()
        conn = sqlite3.connect(self.db)
        self.assertEqual(migrate.get_version(conn), 2)
        tables = migrate.user_tables(conn)
        self.assertIn("catatan_ok", tables)
        self.assertNotIn("sisa", tables)
        conn.close()

    def test_pelanggaran_foreign_key_membatalkan_langkah(self):
        self.migrate_db()
        before = self.snapshot()
        self.add("002_fk_rusak.sql", "INSERT INTO user_settings (user_id, theme) VALUES (999, 'dark');")
        with self.assertRaises(migrate.MigrationError) as ctx:
            self.migrate_db()
        self.assertIn("foreign key", str(ctx.exception))
        self.assertEqual(self.snapshot(), before)

    def test_langkah_sukses_sql_dan_python_menaikkan_versi(self):
        self.add("002_tambah_tabel.sql", """
            -- komentar dengan titik koma; tidak boleh memecah pernyataan
            CREATE TABLE tag (id INTEGER PRIMARY KEY, nama TEXT NOT NULL); -- sisa baris
            INSERT INTO tag (nama) VALUES ('a;b');
        """)
        self.add("003_isi_py.py", """
            def upgrade(conn):
                conn.execute("INSERT INTO tag (nama) VALUES ('dari-python')")
        """)
        self.assertEqual(self.migrate_db(), [1, 2, 3])
        conn = sqlite3.connect(self.db)
        self.assertEqual(migrate.get_version(conn), 3)
        self.assertEqual([r[0] for r in conn.execute("SELECT nama FROM tag ORDER BY id")], ["a;b", "dari-python"])
        conn.close()
        self.assertEqual(self.migrate_db(), [])  # kedua kali: tidak ada efek

    def test_membangun_ulang_tabel_tidak_memicu_cascade(self):
        """Pola 'buat baru, salin, drop, rename' (mis. menambah CHECK): anak ON DELETE CASCADE harus selamat."""
        self.add("002_check_nama.sql", """
            CREATE TABLE users_baru (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              full_name TEXT NOT NULL CHECK (length(full_name) > 0),
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
              avatar_url TEXT, bio TEXT,
              is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              last_login_at TEXT
            );
            INSERT INTO users_baru SELECT * FROM users;
            DROP TABLE users;
            ALTER TABLE users_baru RENAME TO users;
        """)
        conn = sqlite3.connect(self.db)
        before = {t: rows for t, rows in dump(conn).items() if t != "users"}
        users_before = dump(conn)["users"]
        conn.close()

        self.migrate_db()

        conn = sqlite3.connect(self.db)
        after = dump(conn)
        self.assertEqual(after["users"], users_before)
        self.assertEqual({t: after[t] for t in before}, before)  # user_settings, orders, dst. tidak terhapus
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO users (full_name, email, password_hash) VALUES ('', 'k@x.test', 'h')")
        conn.close()

    def test_foreign_keys_dikembalikan_seperti_semula(self):
        for initial in (1, 0):
            conn = sqlite3.connect(self.db)
            conn.execute(f"PRAGMA foreign_keys = {initial}")
            migrate.migrate(conn, self.mdir)
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], initial)
            conn.close()


class DiscoveryTests(TmpCase):
    def test_celah_nomor_ditolak(self):
        self.add("001_a.sql", "SELECT 1;")
        self.add("003_c.sql", "SELECT 1;")
        with self.assertRaises(migrate.MigrationError):
            migrate.discover_migrations(self.mdir)

    def test_nomor_ganda_ditolak(self):
        self.add("001_a.sql", "SELECT 1;")
        self.add("001_b.py", "def upgrade(conn): pass")
        with self.assertRaises(migrate.MigrationError):
            migrate.discover_migrations(self.mdir)

    def test_py_tanpa_upgrade_ditolak_dan_dibatalkan(self):
        self.add("001_a.py", "x = 1")
        conn = sqlite3.connect(self.db)
        with self.assertRaises(migrate.MigrationError):
            migrate.migrate(conn, self.mdir)
        self.assertEqual(migrate.get_version(conn), 0)
        conn.close()

    def test_berkas_lain_diabaikan(self):
        self.add("001_a.sql", "CREATE TABLE t (id INTEGER);")
        self.add("README.md", "bukan migrasi")
        self.assertEqual([m.version for m in migrate.discover_migrations(self.mdir)], [1])


class ConsistencyTests(unittest.TestCase):
    def test_schema_sql_sama_dengan_semua_migrasi_dari_nol(self):
        """Skema baru (schema.sql) harus identik dengan skema lama + semua migrasi."""
        via_migrations = sqlite3.connect(":memory:")
        migrate.migrate(via_migrations)
        via_schema = schema_db()
        self.assertEqual(migrate.schema_signature(via_migrations), migrate.schema_signature(via_schema))
        self.assertEqual(migrate.get_version(via_migrations), migrate.get_version(via_schema))
        via_migrations.close()
        via_schema.close()

    def test_db_lama_setelah_migrasi_sama_dengan_skema_baru(self):
        tmp = tempfile.mkdtemp()
        try:
            conn = legacy_db(os.path.join(tmp, "lama.db"))
            migrate.migrate(conn)
            via_schema = schema_db()
            self.assertEqual(migrate.schema_signature(conn), migrate.schema_signature(via_schema))
            self.assertEqual(migrate.get_version(conn), migrate.get_version(via_schema))
            conn.close()
            via_schema.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_baseline_beku_sama_dengan_skema_versi_1(self):
        """Selama baru ada migrasi 001, schema.sql dan baseline harus sama persis (setara)."""
        if migrate.latest_version() != 1:
            self.skipTest("sudah ada migrasi setelah baseline; konsistensi dijaga tes di atas")
        base = sqlite3.connect(":memory:")
        for stmt in migrate._statements(read(BASELINE)):
            base.execute(stmt)
        self.assertEqual(migrate.schema_signature(base), migrate.schema_signature(schema_db()))
        base.close()

    def test_nomor_versi_di_schema_sql_sama_dengan_migrasi_terbaru(self):
        conn = schema_db()
        self.assertEqual(migrate.get_version(conn), migrate.discover_migrations()[-1].version)
        conn.close()


if __name__ == "__main__":
    unittest.main()
