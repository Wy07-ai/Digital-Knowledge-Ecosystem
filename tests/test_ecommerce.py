"""Tes katalog publik dan alur keranjang E-Commerce."""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

from werkzeug.security import generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class EcommerceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as schema:
            conn.executescript(schema.read())
        conn.execute(
            "INSERT INTO users (id, full_name, email, password_hash) VALUES (1, ?, ?, ?)",
            ("Demo Pengguna", "demo@dke.test", generate_password_hash("Demo12345")),
        )
        conn.executemany(
            "INSERT INTO categories (id, module_key, name, slug) VALUES (?, 'ecommerce', ?, ?)",
            (
                (1, "Kursus Digital", "kursus-digital"),
                (2, "E-Book", "e-book"),
                (3, "Template & Aset", "template-aset"),
            ),
        )
        conn.executemany(
            "INSERT INTO products "
            "(id, category_id, name, slug, description, price, product_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                (1, 1, "Kursus Dasar Python", "kursus-python", "Belajar Python dari awal", 150000, "course"),
                (2, 1, "Kursus SQL", "kursus-sql", "Belajar kueri basis data", 179000, "course"),
                (3, 2, "E-Book Flask", "ebook-flask", "Panduan Flask untuk pemula", 79000, "ebook"),
            ),
        )
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        try:
            result = conn.execute(statement, params).fetchall()
            conn.commit()
            return result
        finally:
            conn.close()

    def login(self, client=None):
        with (client or self.client).session_transaction() as session:
            session["user_id"] = 1

    def token(self, client=None, path="/ecommerce/keranjang"):
        response = (client or self.client).get(path)
        return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    def test_guest_can_filter_catalog_and_prices_use_rupiah_format(self):
        response = self.client.get(
            "/ecommerce/?category=kursus-digital&type=course&min_price=140000"
            "&max_price=160000&q=Python&sort=price_asc"
        )
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Kursus Dasar Python", html)
        self.assertIn("Rp 150.000", html)
        self.assertRegex(html, r'data-cart-count[^>]*>0</span>')
        self.assertNotIn("Kursus SQL", html)
        self.assertNotIn("E-Book Flask", html)

    def test_catalog_supports_sorting_and_escaped_search(self):
        response = self.client.get("/ecommerce/?q=%25&sort=price_desc")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Produk tidak ditemukan", response.get_data(as_text=True))
        response = self.client.get("/ecommerce/?sort=price_desc")
        html = response.get_data(as_text=True)
        self.assertLess(html.index("Kursus SQL"), html.index("Kursus Dasar Python"))

    def test_product_detail_is_public_and_unknown_products_are_not_found(self):
        response = self.client.get("/ecommerce/produk/kursus-python")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tentang produk", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/ecommerce/produk/tidak-ada").status_code, 404)

    def test_guest_add_redirects_to_login_then_back_to_same_product(self):
        detail = self.client.get("/ecommerce/produk/kursus-python").get_data(as_text=True)
        token = re.search(r'name="csrf_token" value="([^"]+)"', detail).group(1)
        response = self.client.post(
            "/ecommerce/keranjang/tambah/1",
            data={"csrf_token": token, "next": "/ecommerce/produk/kursus-python"},
        )
        query = parse_qs(urlsplit(response.location).query)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.location).path, "/infosys/login")
        self.assertEqual(query["next"], ["/ecommerce/produk/kursus-python"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM cart_items")[0][0], 0)

        login_page = self.client.get(response.location).get_data(as_text=True)
        login_token = re.search(r'name="csrf_token" value="([^"]+)"', login_page).group(1)
        login = self.client.post(
            response.location,
            data={
                "csrf_token": login_token,
                "email": "demo@dke.test",
                "password": "Demo12345",
                "next": "/ecommerce/produk/kursus-python",
            },
        )
        self.assertEqual(urlsplit(login.location).path, "/ecommerce/produk/kursus-python")

    def test_guest_cart_requires_login_and_empty_cart_has_clear_state(self):
        response = self.client.get("/ecommerce/keranjang")
        self.assertEqual(urlsplit(response.location).path, "/infosys/login")
        self.login()
        response = self.client.get("/ecommerce/keranjang")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Keranjang masih kosong", response.get_data(as_text=True))

    def test_member_add_update_remove_and_live_totals(self):
        self.login()
        token = self.token()
        added = self.client.post(
            "/ecommerce/keranjang/tambah/1",
            data={"csrf_token": token, "next": "/ecommerce/produk/kursus-python"},
        )
        self.assertEqual(urlsplit(added.location).path, "/ecommerce/produk/kursus-python")
        self.client.post(
            "/ecommerce/keranjang/tambah/1",
            data={"csrf_token": token, "next": "/ecommerce/produk/kursus-python"},
        )
        header_html = self.client.get("/ecommerce/produk/kursus-python").get_data(as_text=True)
        self.assertRegex(header_html, r'data-cart-count[^>]*>2</span>')
        item_id = self.sql("SELECT id FROM cart_items WHERE user_id = 1")[0][0]
        response = self.client.post(
            f"/ecommerce/keranjang/item/{item_id}/jumlah",
            data={"csrf_token": token, "qty": "3"},
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            "success": True,
            "qty": 3,
            "line_total": 450000,
            "subtotal": 450000,
            "total": 450000,
            "cart_count": 3,
        })

        response = self.client.post(
            f"/ecommerce/keranjang/item/{item_id}/hapus",
            data={"csrf_token": token},
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        self.assertEqual(response.json["cart_count"], 0)
        self.assertEqual(response.json["subtotal"], 0)
        cart_html = self.client.get("/ecommerce/keranjang").get_data(as_text=True)
        self.assertIn("Keranjang masih kosong", cart_html)

    def test_plain_form_update_still_redirects_and_invalid_quantity_is_rejected(self):
        self.login()
        self.sql("INSERT INTO cart_items (user_id, product_id, qty) VALUES (1, 1, 1)")
        item_id = self.sql("SELECT id FROM cart_items WHERE user_id = 1")[0][0]
        token = self.token()
        invalid = self.client.post(
            f"/ecommerce/keranjang/item/{item_id}/jumlah",
            data={"csrf_token": token, "qty": "0"},
        )
        self.assertEqual(invalid.status_code, 302)
        self.assertEqual(self.sql("SELECT qty FROM cart_items WHERE id = ?", (item_id,))[0][0], 1)
        updated = self.client.post(
            f"/ecommerce/keranjang/item/{item_id}/jumlah",
            data={"csrf_token": token, "qty": "2"},
        )
        self.assertEqual(urlsplit(updated.location).path, "/ecommerce/keranjang")
        self.assertEqual(self.sql("SELECT qty FROM cart_items WHERE id = ?", (item_id,))[0][0], 2)


if __name__ == "__main__":
    unittest.main()
