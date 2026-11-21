"""Tes database sibuk: penulis lain menahan kunci, mode WAL, 503, dan Guest pada DB kosong.

Jalankan dari akar proyek:   python -m unittest discover -s tests -v
"""
import contextlib
import io
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from unittest import mock

from werkzeug.security import generate_password_hash

import seed
from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUSY_MSG = "Server sedang sibuk, coba lagi"


class DbBusyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)  # sengaja mode journal bawaan (delete)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO users (full_name, email, password_hash) VALUES (?,?,?)",
                     ("Demo", "demo@dke.test", generate_password_hash("Demo12345")))
        conn.commit()
        conn.close()
        self.writers = []

    def tearDown(self):
        for w in self.writers:
            with contextlib.suppress(sqlite3.Error):
                w.rollback()
            w.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def make_client(self, **config):
        cfg = {"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"}
        cfg.update(config)
        app = create_app(cfg)
        client = app.test_client()
        with client.session_transaction() as s:
            s["user_id"] = 1
        return app, client

    def hold(self, mode):
        w = sqlite3.connect(self.db_path, isolation_level=None)
        w.execute(f"BEGIN {mode}")
        self.writers.append(w)
        return w

    def journal_mode(self):
        c = sqlite3.connect(self.db_path)
        try:
            return c.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            c.close()

    # ---- kriteria 1: penulis menahan kunci tulis -> 200 dan cepat ----
    def test_member_get_ok_and_fast_while_writer_holds_lock(self):
        for mode in ("IMMEDIATE", "EXCLUSIVE"):
            with self.subTest(mode=mode):
                _app, client = self.make_client()
                client.get("/ecommerce/")                 # koneksi pertama mengaktifkan WAL
                self.assertEqual(self.journal_mode(), "wal")
                self.hold(mode)
                t0 = time.monotonic()
                r = client.get("/ecommerce/keranjang")
                elapsed = time.monotonic() - t0
                self.assertEqual(r.status_code, 200)
                self.assertLess(elapsed, 1.0)
                self.writers.pop().rollback()

    # ---- kriteria 4: kegagalan remember_last_page dibatasi pendek ----
    def test_last_page_update_failure_is_short_and_logged(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO user_settings (user_id) VALUES (1)")
        conn.commit()
        conn.close()
        app, client = self.make_client()
        client.get("/ecommerce/")
        self.hold("IMMEDIATE")
        t0 = time.monotonic()
        with self.assertLogs(app.logger, level="WARNING") as cm:
            r = client.get("/ecommerce/keranjang")
        self.assertEqual(r.status_code, 200)
        self.assertLess(time.monotonic() - t0, 1.0)
        self.assertTrue(any("last_module" in m for m in cm.output))

    # ---- kriteria 2: pembaca benar-benar gagal "database is locked" -> 503 ----
    def test_locked_reader_returns_503_and_keeps_session(self):
        # Mode delete + EXCLUSIVE: pembaca diblokir sungguhan. Tanpa WAL, jadi tahan konversi dengan
        # koneksi yang sudah menahan kunci sebelum aplikasi menyentuh database.
        self.hold("EXCLUSIVE")
        _app, client = self.make_client(DATABASE_BUSY_TIMEOUT_MS=200)
        t0 = time.monotonic()
        r = client.get("/ecommerce/keranjang")
        self.assertEqual(r.status_code, 503)
        self.assertLess(time.monotonic() - t0, 2.0)
        self.assertIn(BUSY_MSG, r.get_data(as_text=True))
        self.assertEqual(r.headers.get("Retry-After"), "2")
        self.assertNotIn("/infosys/login", r.headers.get("Location", ""))
        with client.session_transaction() as s:
            self.assertEqual(s.get("user_id"), 1)

    def test_locked_reader_api_returns_json_503(self):
        self.hold("EXCLUSIVE")
        _app, client = self.make_client(DATABASE_BUSY_TIMEOUT_MS=200)
        r = client.get("/elearning/api/tidak-ada")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.get_json()["status"], 503)

    # ---- kriteria 3: tabel belum ada -> tetap Guest ----
    def test_missing_tables_still_guest(self):
        empty = os.path.join(self.tmp, "kosong.db")
        sqlite3.connect(empty).close()
        app = create_app({"TESTING": True, "DATABASE": empty, "SECRET_KEY": "test"})
        client = app.test_client()
        with client.session_transaction() as s:
            s["user_id"] = 1
        with app.test_request_context("/"):
            app.preprocess_request()
            from flask import g
            self.assertIsNone(g.user)
        r = client.get("/infosys/login")
        self.assertNotEqual(r.status_code, 503)

    # ---- catatan risiko: seed --reset tetap jalan pada DB mode WAL ----
    def test_seed_reset_works_in_wal(self):
        db = os.path.join(self.tmp, "seed.db")
        env = {"DKE_ADMIN_PASSWORD": "Pilihan-Saya-42", "DKE_DEMO_PASSWORD": "Demo-Saya-4242"}
        for extra in ([], ["--reset"], ["--reset"]):
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(seed.main(["--db", db, *extra]), 0)
        c = sqlite3.connect(db)
        try:
            self.assertEqual(c.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
