"""Tes CHECK pada schema.sql: baris tidak valid ditolak DB, baris valid tetap diterima.

Skema dimuat ke database SEMENTARA (bukan instance/dke.db) dengan PRAGMA foreign_keys = ON.
Nilai enum di sini harus sama dengan konstanta/validasi di kode aplikasi
(LEVELS, PRODUCT_TYPES, PAYMENT_METHODS, MAX_CART_QTY, OPTION_KEYS, dst.).
"""
import os
import sqlite3
import unittest

from app.ecommerce.routes import MAX_CART_QTY, PAYMENT_METHODS, PRODUCT_TYPES
from app.elearning.routes import LEVELS
from app.elearning.quiz import OPTION_KEYS

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema.sql")


class SchemaConstraintTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys = ON")
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            self.db.executescript(f.read())
        self.db.execute("PRAGMA foreign_keys = ON")
        # Induk yang dipakai tabel lain (semua baris valid).
        self.db.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (1, 'U', 'u@x.test', 'h')")
        self.db.execute("INSERT INTO courses (id, title, slug) VALUES (1, 'K', 'k')")
        self.db.execute("INSERT INTO products (id, name, slug) VALUES (1, 'P', 'p')")
        self.db.execute("INSERT INTO orders (id, order_code, user_id, total) VALUES (1, 'DKE-1', 1, 0)")
        self.db.execute("INSERT INTO quizzes (id, course_id, title) VALUES (1, 1, 'Q')")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def ok(self, sql, params=()):
        self.db.execute(sql, params)

    def bad(self, sql, params=()):
        with self.assertRaises(sqlite3.IntegrityError, msg=f"{sql} {params}"):
            self.db.execute(sql, params)

    # --- users
    def test_users(self):
        ins = "INSERT INTO users (full_name, email, password_hash, role, is_active) VALUES ('A', ?, 'h', ?, ?)"
        self.ok(ins, ("a@x.test", "admin", 0))
        self.ok(ins, ("m@x.test", "member", 1))
        self.bad(ins, ("s@x.test", "superadmin", 1))
        self.bad(ins, ("t@x.test", "member", 7))

    # --- products
    def test_products(self):
        ins = "INSERT INTO products (name, slug, price, product_type) VALUES ('N', ?, ?, ?)"
        for i, (value, _label) in enumerate(PRODUCT_TYPES):
            self.ok(ins, (f"ok{i}", 0, value))
        self.bad(ins, ("neg", -1, "course"))
        self.bad(ins, ("typ", 10, "merchandise"))

    # --- cart_items
    def test_cart_items(self):
        ins = "INSERT INTO cart_items (user_id, product_id, qty) VALUES (1, 1, ?)"
        self.ok(ins, (1,))
        self.db.execute("DELETE FROM cart_items")
        self.ok(ins, (MAX_CART_QTY,))
        self.db.execute("DELETE FROM cart_items")
        for qty in (0, -3, 100000, MAX_CART_QTY + 1):
            self.bad(ins, (qty,))

    # --- orders
    def test_orders(self):
        ins = "INSERT INTO orders (order_code, user_id, total, status, payment_method) VALUES (?, 1, ?, ?, ?)"
        n = 0
        for status in ("pending", "paid", "cancelled"):
            n += 1
            self.ok(ins, (f"C{n}", 100, status, None))
        for value, _label in PAYMENT_METHODS:
            n += 1
            self.ok(ins, (f"C{n}", 100, "paid", value))
        self.bad(ins, ("X1", 100, "refunded", "transfer"))
        self.bad(ins, ("X2", 100, "paid", "bitcoin"))
        self.bad(ins, ("X3", -1, "paid", "transfer"))

    # --- order_items
    def test_order_items(self):
        ins = "INSERT INTO order_items (order_id, product_id, unit_price, qty) VALUES (1, 1, ?, ?)"
        self.ok(ins, (0, 1))
        self.bad(ins, (100, 0))
        self.bad(ins, (-1, 1))

    # --- quizzes
    def test_quizzes(self):
        ins = "INSERT INTO quizzes (course_id, title, pass_score) VALUES (1, 'Z', ?)"
        self.ok(ins, (0,))
        self.ok(ins, (100,))
        self.bad(ins, (500,))
        self.bad(ins, (-1,))

    # --- quiz_questions
    def test_quiz_questions(self):
        ins = ("INSERT INTO quiz_questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option) "
               "VALUES (1, 'Q', 'a', 'b', ?, ?, ?)")
        for key in OPTION_KEYS:
            self.ok(ins, ("c", "d", key))
        self.ok(ins, (None, None, "a"))
        self.ok(ins, (None, None, "b"))
        self.ok(ins, ("c", None, "c"))
        self.bad(ins, ("c", "d", "z"))
        self.bad(ins, (None, None, "c"))   # kunci c padahal option_c NULL
        self.bad(ins, ("c", None, "d"))    # kunci d padahal option_d NULL
        self.bad(ins, (None, None, "d"))
        self.bad(ins, ("c", "d", "A"))     # huruf besar bukan nilai yang disimpan

    # --- quiz_attempts
    def test_quiz_attempts(self):
        ins = "INSERT INTO quiz_attempts (user_id, quiz_id, score, passed) VALUES (1, 1, ?, ?)"
        self.ok(ins, (0, 0))
        self.ok(ins, (100, 1))
        self.bad(ins, (9999, 1))
        self.bad(ins, (-1, 0))
        self.bad(ins, (50, 5))

    # --- courses
    def test_courses(self):
        ins = "INSERT INTO courses (title, slug, level) VALUES ('T', ?, ?)"
        for i, (value, _label) in enumerate(LEVELS):
            self.ok(ins, (f"lv{i}", value))
        self.bad(ins, ("lvx", "pakar"))

    # --- lessons
    def test_lessons(self):
        ins = "INSERT INTO lessons (course_id, order_no, title, content_type, duration_min) VALUES (1, ?, 'L', ?, ?)"
        self.ok(ins, (1, "text", 0))
        self.ok(ins, (2, "video", None))
        self.bad(ins, (3, "audio", 5))
        self.bad(ins, (4, "text", -1))


if __name__ == "__main__":
    unittest.main()
