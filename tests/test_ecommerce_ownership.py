"""Tes kepemilikan data E-Commerce: pengguna B tidak boleh menyentuh data pengguna A.

Rute yang dijaga filter `user_id`:
  - GET  /ecommerce/pesanan, /ecommerce/pesanan/<kode>
  - POST /ecommerce/keranjang/item/<id>/jumlah
  - POST /ecommerce/keranjang/item/<id>/hapus
Tes ini mengunci perilaku tersebut agar refaktor tidak melemahkannya tanpa terdeteksi.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from urllib.parse import urlsplit

from werkzeug.security import generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

A_ID, B_ID = 1, 2
A_CODE = "DKE-20260101-0001"
B_CODE = "DKE-20260101-0002"
A_ADDRESS = "Jl. Rahasia Alpha No. 77, Surabaya"
A_PRODUCT = "Buku Rahasia Alpha"
B_PRODUCT = "Poster Milik Beta"
JSON_HEADERS = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


class EcommerceOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as schema:
            conn.executescript(schema.read())
        conn.executemany(
            "INSERT INTO users (id, full_name, email, password_hash) VALUES (?, ?, ?, ?)",
            (
                (A_ID, "Alice Alpha", "alice@dke.test", generate_password_hash("Alice12345")),
                (B_ID, "Bob Beta", "bob@dke.test", generate_password_hash("Bob123456")),
            ),
        )
        conn.execute(
            "INSERT INTO categories (id, module_key, name, slug) VALUES (1, 'ecommerce', 'E-Book', 'e-book')"
        )
        conn.executemany(
            "INSERT INTO products (id, category_id, name, slug, description, price, product_type) "
            "VALUES (?, 1, ?, ?, 'Deskripsi', ?, 'ebook')",
            (
                (1, A_PRODUCT, "buku-alpha", 100000),
                (2, B_PRODUCT, "poster-beta", 50000),
            ),
        )
        # Pesanan: satu milik A, satu milik B (agar daftar B tidak kosong).
        conn.executemany(
            "INSERT INTO orders (id, order_code, user_id, total, status, payment_method, "
            "recipient_name, address) VALUES (?, ?, ?, ?, 'paid', 'transfer', ?, ?)",
            (
                (1, A_CODE, A_ID, 200000, "Alice Alpha", A_ADDRESS),
                (2, B_CODE, B_ID, 50000, "Bob Beta", "Jl. Beta No. 5, Bandung"),
            ),
        )
        conn.executemany(
            "INSERT INTO order_items (order_id, product_id, unit_price, qty) VALUES (?, ?, ?, ?)",
            ((1, 1, 100000, 2), (2, 2, 50000, 1)),
        )
        # Keranjang: id 1 milik A (qty 2), id 2 milik B (qty 1).
        conn.executemany(
            "INSERT INTO cart_items (id, user_id, product_id, qty) VALUES (?, ?, ?, ?)",
            ((1, A_ID, 1, 2), (2, B_ID, 2, 1)),
        )
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.guest = self.app.test_client()
        self.client_a = self.login_client(A_ID)
        self.client_b = self.login_client(B_ID)
        self.a_item_id = self.sql("SELECT id FROM cart_items WHERE user_id = ?", (A_ID,))[0][0]
        self.b_item_id = self.sql("SELECT id FROM cart_items WHERE user_id = ?", (B_ID,))[0][0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def login_client(self, user_id):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = user_id
        return client

    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        try:
            result = conn.execute(statement, params).fetchall()
            conn.commit()
            return result
        finally:
            conn.close()

    def token(self, client):
        html = client.get("/ecommerce/keranjang").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def a_qty(self):
        return self.sql("SELECT qty FROM cart_items WHERE id = ?", (self.a_item_id,))[0][0]

    # ---- Sanity: fixture dua pengguna benar-benar terpisah ----
    def test_fixture_owner_can_see_own_data(self):
        """Pagar pengaman agar tes 404 di bawah tidak lulus karena data salah ketik."""
        detail = self.client_a.get(f"/ecommerce/pesanan/{A_CODE}")
        self.assertEqual(detail.status_code, 200)
        html = detail.get_data(as_text=True)
        self.assertIn(A_PRODUCT, html)
        self.assertIn(A_ADDRESS, html)
        listing = self.client_a.get("/ecommerce/pesanan").get_data(as_text=True)
        self.assertIn(A_CODE, listing)
        self.assertNotIn(B_CODE, listing)

    # ---- Pesanan ----
    def test_other_user_cannot_open_order_detail(self):
        response = self.client_b.get(f"/ecommerce/pesanan/{A_CODE}")
        self.assertEqual(response.status_code, 404)
        html = response.get_data(as_text=True)
        self.assertNotIn(A_PRODUCT, html)
        self.assertNotIn(A_ADDRESS, html)
        self.assertNotIn("Alice Alpha", html)

    def test_other_user_order_list_hides_foreign_order_codes(self):
        response = self.client_b.get("/ecommerce/pesanan")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn(A_CODE, html)
        self.assertIn(B_CODE, html)  # daftar B sendiri tetap tampil

    def test_user_can_still_open_own_order_after_other_user_was_denied(self):
        self.assertEqual(self.client_b.get(f"/ecommerce/pesanan/{A_CODE}").status_code, 404)
        own = self.client_b.get(f"/ecommerce/pesanan/{B_CODE}")
        self.assertEqual(own.status_code, 200)
        self.assertIn(B_PRODUCT, own.get_data(as_text=True))

    # ---- Ubah jumlah item keranjang ----
    def test_other_user_cannot_update_cart_quantity_html(self):
        token = self.token(self.client_b)
        response = self.client_b.post(
            f"/ecommerce/keranjang/item/{self.a_item_id}/jumlah",
            data={"csrf_token": token, "qty": "9"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.a_qty(), 2)

    def test_other_user_cannot_update_cart_quantity_json(self):
        token = self.token(self.client_b)
        response = self.client_b.post(
            f"/ecommerce/keranjang/item/{self.a_item_id}/jumlah",
            data={"csrf_token": token, "qty": "9"},
            headers=JSON_HEADERS,
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json["success"])
        self.assertEqual(self.a_qty(), 2)
        # Respons tidak membocorkan data keranjang A.
        self.assertNotIn(A_PRODUCT, response.get_data(as_text=True))

    # ---- Hapus item keranjang ----
    def test_other_user_cannot_remove_cart_item_html(self):
        token = self.token(self.client_b)
        response = self.client_b.post(
            f"/ecommerce/keranjang/item/{self.a_item_id}/hapus",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.sql("SELECT user_id, qty FROM cart_items WHERE id = ?", (self.a_item_id,)),
            [(A_ID, 2)],
        )

    def test_other_user_cannot_remove_cart_item_json(self):
        token = self.token(self.client_b)
        response = self.client_b.post(
            f"/ecommerce/keranjang/item/{self.a_item_id}/hapus",
            data={"csrf_token": token},
            headers=JSON_HEADERS,
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json["success"])
        self.assertEqual(
            self.sql("SELECT user_id, qty FROM cart_items WHERE id = ?", (self.a_item_id,)),
            [(A_ID, 2)],
        )

    def test_denied_cart_mutations_leave_other_users_own_item_untouched(self):
        token = self.token(self.client_b)
        self.client_b.post(
            f"/ecommerce/keranjang/item/{self.a_item_id}/jumlah",
            data={"csrf_token": token, "qty": "9"},
        )
        self.client_b.post(
            f"/ecommerce/keranjang/item/{self.a_item_id}/hapus",
            data={"csrf_token": token},
        )
        self.assertEqual(
            self.sql("SELECT user_id, qty FROM cart_items ORDER BY id"),
            [(A_ID, 2), (B_ID, 1)],
        )

    # ---- Guest ----
    def test_guest_is_redirected_to_login_for_orders(self):
        for path in ("/ecommerce/pesanan", f"/ecommerce/pesanan/{A_CODE}"):
            with self.subTest(path=path):
                response = self.guest.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlsplit(response.location).path, "/infosys/login")
                body = response.get_data(as_text=True)
                self.assertNotIn(A_PRODUCT, body)
                self.assertNotIn(A_ADDRESS, body)

    def test_guest_cannot_mutate_cart_items(self):
        for action, data in (("jumlah", {"qty": "9"}), ("hapus", {})):
            with self.subTest(action=action):
                response = self.guest.post(
                    f"/ecommerce/keranjang/item/{self.a_item_id}/{action}", data=data
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(urlsplit(response.location).path, "/infosys/login")
        self.assertEqual(self.a_qty(), 2)


if __name__ == "__main__":
    unittest.main()
