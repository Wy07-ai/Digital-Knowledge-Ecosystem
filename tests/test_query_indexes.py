"""Tes indeks kueri dan jumlah kueri halaman Kelas Saya.

Jalankan:  python -m unittest tests.test_query_indexes
"""
import contextlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from werkzeug.security import generate_password_hash

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import migrate  # noqa: E402
import seed  # noqa: E402
from app import create_app  # noqa: E402

SCHEMA_PATH = os.path.join(ROOT, "schema.sql")

# Kueri disalin dari kode (isi WHERE/ORDER BY sama; _thread_select disederhanakan ke tabel threads).
QUERIES = {
    "soal kuis per quiz_id (quiz.get_public_questions)": (
        "SELECT id, question, option_a, option_b, option_c, option_d "
        "FROM quiz_questions WHERE quiz_id = ? ORDER BY id ASC", "idx_quiz_questions_quiz"),
    "kuis per course_id (quiz.get_quiz)": (
        "SELECT id, course_id, title, pass_score FROM quizzes WHERE course_id = ? ORDER BY id ASC LIMIT 1",
        "idx_quizzes_course"),
    "COUNT kiriman per pengguna (forum profil)": (
        "SELECT COUNT(*) FROM posts WHERE user_id = ?", "idx_posts_user"),
    "thread milik pengguna (forum my_threads)": (
        "SELECT * FROM threads t WHERE t.user_id = ? "
        "ORDER BY datetime(t.created_at) DESC, t.id DESC LIMIT 10 OFFSET 0", "idx_threads_user"),
    "anak balasan (forum delete_post)": (
        "SELECT COUNT(*) FROM posts WHERE parent_post_id = ?", "idx_posts_parent"),
}
NEW_INDEXES = sorted({v[1] for v in QUERIES.values()})


def plan(conn, sql):
    return [r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql, (1,))]


class QueryPlanTests(unittest.TestCase):
    def check(self, conn):
        for name, (sql, index) in QUERIES.items():
            with self.subTest(name):
                steps = plan(conn, sql)
                self.assertTrue(any("USING" in s and "INDEX" in s and index in s for s in steps), steps)
                self.assertFalse(any(s.startswith("SCAN") for s in steps), steps)

    def test_schema_sql_memakai_indeks(self):
        conn = sqlite3.connect(":memory:")
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        self.check(conn)

    def test_migrasi_002_menambah_indeks_pada_db_lama_tanpa_mengubah_data(self):
        conn = sqlite3.connect(":memory:")
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        for name in NEW_INDEXES:
            conn.execute(f"DROP INDEX {name}")
        conn.execute("PRAGMA user_version = 1")
        conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (1, 'A', 'a@x.test', 'h')")
        conn.commit()
        for sql, _ in QUERIES.values():
            self.assertTrue(any(s.startswith("SCAN") for s in plan(conn, sql)))  # sebelum: SCAN
        self.assertEqual(migrate.migrate(conn), [2])
        self.assertEqual(migrate.get_version(conn), migrate.latest_version())
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        self.check(conn)
        self.assertEqual(migrate.migrate(conn), [])  # idempoten

    def test_seed_migrate_pada_db_lama(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "lama.db")
            conn = sqlite3.connect(path)
            with open(SCHEMA_PATH, encoding="utf-8") as f:
                conn.executescript(f.read())
            for name in NEW_INDEXES:
                conn.execute(f"DROP INDEX {name}")
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
            conn.close()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(seed.main(["--db", path, "--migrate"]), 0)
            conn = sqlite3.connect(path)
            self.check(conn)
            conn.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class MyCoursesQueryCountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "t.db")
        conn = sqlite3.connect(self.db_path)
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (1, 'Demo', 'demo@dke.test', ?)",
                     (generate_password_hash("Demo12345"),))
        conn.execute("INSERT INTO categories (id, module_key, name, slug) VALUES (1, 'elearning', 'Prog', 'prog')")
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def add_courses(self, n):
        conn = sqlite3.connect(self.db_path)
        start = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        for i in range(start + 1, start + n + 1):
            conn.execute("INSERT INTO courses (id, category_id, title, slug, level, instructor_name) "
                         "VALUES (?, 1, ?, ?, 'pemula', 'P')", (i, f"Kelas {i}", f"kelas-{i}"))
            for k in (1, 2, 3):
                conn.execute("INSERT INTO lessons (course_id, order_no, title, content_type, content_body, duration_min) "
                             "VALUES (?, ?, ?, 'text', 'x', 5)", (i, k, f"Materi {k}"))
            conn.execute("INSERT INTO enrollments (user_id, course_id, source) VALUES (1, ?, 'free')", (i,))
        conn.commit()
        conn.close()

    def login(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1

    def count_queries(self):
        statements = []
        real_connect = sqlite3.connect

        def traced(*a, **kw):
            c = real_connect(*a, **kw)
            c.set_trace_callback(statements.append)
            return c

        with mock.patch("app.db.sqlite3.connect", traced):
            resp = self.client.get("/elearning/kelas-saya")
        self.assertEqual(resp.status_code, 200)
        return len([s for s in statements if not s.upper().startswith(("PRAGMA", "BEGIN", "COMMIT"))]), resp

    def test_jumlah_kueri_tidak_bertambah_dengan_jumlah_kursus(self):
        self.login()
        self.add_courses(1)
        one, _ = self.count_queries()
        self.add_courses(4)
        five, resp = self.count_queries()
        self.assertEqual(one, five)
        self.assertEqual(resp.get_data(as_text=True).count("Mulai belajar"), 5)

    def test_tombol_lanjutkan_menuju_materi_belum_selesai(self):
        self.login()
        self.add_courses(2)
        conn = sqlite3.connect(self.db_path)
        # kursus 1: materi 1 selesai -> lanjut ke materi 2; kursus 2: semua selesai -> materi 1
        ids = {(c, o): i for i, c, o in conn.execute("SELECT id, course_id, order_no FROM lessons")}
        conn.execute("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, ?)", (ids[(1, 1)],))
        for o in (1, 2, 3):
            conn.execute("INSERT INTO lesson_progress (user_id, lesson_id) VALUES (1, ?)", (ids[(2, o)],))
        conn.commit()
        conn.close()
        html = self.client.get("/elearning/kelas-saya").get_data(as_text=True)
        self.assertIn("/elearning/kelas/1/materi/2", html)
        self.assertIn("/elearning/kelas/2/materi/1", html)
        self.assertNotIn("/elearning/kelas/1/materi/1", html)


if __name__ == "__main__":
    unittest.main()
