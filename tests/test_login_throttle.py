"""Tes pembatas percobaan login dan ganti kata sandi (app/infosys/throttle.py).

Jalankan:  python -m unittest discover -s tests -v
Hitungan kegagalan ada di activity_logs (bukan cookie), jadi tes juga membuktikan bahwa membuang
cookie tidak melewati batas.
"""
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from werkzeug.security import generate_password_hash

from app import create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL_MSG = "Email atau kata sandi salah. Periksa kembali dan coba lagi."
THROTTLE_MSG = "Terlalu banyak percobaan. Coba lagi dalam beberapa menit."
PW_LOCK_MSG = "Terlalu banyak percobaan. Tunggu beberapa menit, lalu coba lagi."


class ThrottleTestCase(unittest.TestCase):
    config = {}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        for uid, name, email, pw in ((1, "Demo Pengguna", "demo@dke.test", "Demo12345"),
                                     (2, "Budi Santoso", "budi@dke.test", "Budi12345")):
            conn.execute("INSERT INTO users (id, full_name, email, password_hash) VALUES (?,?,?,?)",
                         (uid, name, email, generate_password_hash(pw)))
            conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (uid,))
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test", **self.config})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- bantuan ----
    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(statement, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def new_client(self, ip=None):
        """Klien tanpa cookie (setara membuang cookie). `ip` mengganti alamat asal permintaan."""
        client = self.app.test_client()
        if ip:
            client.environ_base["REMOTE_ADDR"] = ip
        return client

    def token(self, path, client):
        html = client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def login(self, email, password, client=None):
        c = client or self.client
        return c.post("/infosys/login", data={
            "csrf_token": self.token("/infosys/login", c), "email": email, "password": password})

    def fail_logins(self, n, email="demo@dke.test", client=None):
        for _ in range(n):
            self.assertEqual(self.login(email, "SalahSalah1", client).status_code, 401)

    def age_failures(self, minutes, action="login_failed"):
        """Mundurkan waktu semua baris kegagalan (mensimulasikan jendela waktu yang berlalu)."""
        old = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat(timespec="seconds")
        self.sql("UPDATE activity_logs SET created_at = ? WHERE action = ?", (old, action))

    def failed_rows(self):
        return self.sql("SELECT * FROM activity_logs WHERE action = 'login_failed' ORDER BY id")


class LoginThrottleTests(ThrottleTestCase):
    def test_enam_percobaan_ditolak_429_walau_kata_sandi_benar(self):
        self.fail_logins(5)
        r = self.login("demo@dke.test", "Demo12345")           # benar, tapi sudah terkunci
        self.assertEqual(r.status_code, 429)
        self.assertIn(THROTTLE_MSG, r.get_data(as_text=True))
        with self.client.session_transaction() as s:
            self.assertNotIn("user_id", s)                      # tidak masuk
        self.assertEqual(self.sql("SELECT last_login_at FROM users WHERE id = 1")[0][0], None)

    def test_empat_kegagalan_belum_terkunci(self):
        self.fail_logins(4)
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 302)

    def test_membuang_cookie_tidak_melewati_batas(self):
        self.fail_logins(5)
        r = self.login("demo@dke.test", "Demo12345", client=self.new_client())
        self.assertEqual(r.status_code, 429)

    def test_setelah_jendela_waktu_lewat_login_normal_lagi(self):
        self.fail_logins(5)
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 429)
        self.age_failures(minutes=11)                            # jendela 10 menit sudah lewat
        r = self.login("demo@dke.test", "Demo12345")
        self.assertEqual(r.status_code, 302)

    def test_kegagalan_di_dalam_jendela_masih_dihitung(self):
        self.fail_logins(5)
        self.age_failures(minutes=9)                             # belum 10 menit
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 429)

    def test_jendela_dapat_diatur_lewat_config(self):
        self.app.config["LOGIN_FAIL_WINDOW_SECONDS"] = 60
        self.fail_logins(5)
        self.age_failures(minutes=2)
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 302)

    def test_kegagalan_satu_email_tidak_mengunci_email_lain(self):
        self.fail_logins(5, "demo@dke.test")
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 429)
        r = self.login("budi@dke.test", "Budi12345")             # IP sama, email lain
        self.assertEqual(r.status_code, 302)

    def test_email_tak_dikenal_juga_terkunci_dengan_respons_yang_sama(self):
        for _ in range(5):
            self.assertEqual(self.login("hantu@dke.test", "apasaja123").status_code, 401)
        locked_unknown = self.login("hantu@dke.test", "apasaja123")
        self.fail_logins(5, "demo@dke.test")
        locked_known = self.login("demo@dke.test", "SalahSalah1")
        self.assertEqual((locked_unknown.status_code, locked_known.status_code), (429, 429))
        for r in (locked_unknown, locked_known):
            self.assertIn(THROTTLE_MSG, r.get_data(as_text=True))    # tidak membocorkan email mana yang ada

    def test_pesan_email_tak_dikenal_dan_sandi_salah_tetap_sama(self):
        wrong = self.login("demo@dke.test", "SalahSalah1")
        unknown = self.login("hantu@dke.test", "SalahSalah1")
        self.assertEqual((wrong.status_code, unknown.status_code), (401, 401))
        for r in (wrong, unknown):
            html = r.get_data(as_text=True)
            self.assertIn(FAIL_MSG, html)
            self.assertNotIn(THROTTLE_MSG, html)

    def test_email_dinormalisasi_huruf_besar_dan_spasi(self):
        self.fail_logins(3, "demo@dke.test")
        self.fail_logins(2, "  DEMO@dke.test ")
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 429)

    def test_hash_tiruan_tetap_dijalankan_untuk_email_tak_dikenal(self):
        # Waktu respons seragam: satu check_password_hash per percobaan, terdaftar atau tidak.
        with mock.patch("app.infosys.routes.check_password_hash", return_value=False) as check:
            self.login("hantu@dke.test", "SalahSalah1")
            self.assertEqual(check.call_count, 1)
            self.login("demo@dke.test", "SalahSalah1")
            self.assertEqual(check.call_count, 2)

    def test_kegagalan_dicatat_di_activity_logs(self):
        self.login("demo@dke.test", "SalahSalah1")
        self.login("hantu@dke.test", "SalahSalah1")
        known, unknown = self.failed_rows()
        self.assertEqual((known["user_id"], unknown["user_id"]), (1, None))
        for row in (known, unknown):
            self.assertEqual(row["module_key"], "infosys")
            self.assertEqual(row["ip_address"], "127.0.0.1")
            self.assertNotIn("@", row["detail"])                 # email tidak tersimpan mentah
        self.assertNotEqual(known["detail"], unknown["detail"])  # tapi kunci per email berbeda

    def test_percobaan_ditolak_tidak_dicatat_dan_tidak_memperpanjang_kunci(self):
        self.fail_logins(5)
        for _ in range(3):
            self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 429)
        self.assertEqual(len(self.failed_rows()), 5)
        self.age_failures(minutes=11)
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 302)

    def test_format_salah_dan_login_berhasil_tidak_dihitung(self):
        for _ in range(6):
            self.assertEqual(self.login("bukan-email", "x").status_code, 400)
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 302)
        self.assertEqual(self.failed_rows(), [])

    def test_akun_nonaktif_dengan_sandi_benar_bukan_kegagalan(self):
        self.sql("UPDATE users SET is_active = 0 WHERE id = 2")
        for _ in range(6):
            self.assertEqual(self.login("budi@dke.test", "Budi12345").status_code, 403)
        self.assertEqual(self.failed_rows(), [])

    def test_login_failed_tampil_di_log_aktivitas_dengan_label_ramah(self):
        self.fail_logins(1)
        self.assertEqual(self.login("demo@dke.test", "Demo12345").status_code, 302)
        self.assertIn("Gagal login", self.client.get("/infosys/log").get_data(as_text=True))


class LoginThrottleByIpTests(ThrottleTestCase):
    config = {"LOGIN_MAX_FAILS": 100, "LOGIN_MAX_FAILS_PER_IP": 3}

    def test_satu_ip_yang_gagal_di_banyak_email_ditolak(self):
        for email in ("a@dke.test", "b@dke.test", "c@dke.test"):
            self.assertEqual(self.login(email, "SalahSalah1").status_code, 401)
        r = self.login("budi@dke.test", "Budi12345")             # email bersih, IP sama
        self.assertEqual(r.status_code, 429)
        self.assertIn(THROTTLE_MSG, r.get_data(as_text=True))

    def test_ip_lain_tidak_terpengaruh(self):
        for email in ("a@dke.test", "b@dke.test", "c@dke.test"):
            self.login(email, "SalahSalah1")
        other = self.new_client(ip="203.0.113.7")
        self.assertEqual(self.login("budi@dke.test", "Budi12345", client=other).status_code, 302)

    def test_header_x_forwarded_for_tidak_dipercaya(self):
        for email in ("a@dke.test", "b@dke.test", "c@dke.test"):
            self.login(email, "SalahSalah1")
        c = self.new_client()
        r = c.post("/infosys/login", headers={"X-Forwarded-For": "198.51.100.9"}, data={
            "csrf_token": self.token("/infosys/login", c), "email": "budi@dke.test", "password": "Budi12345"})
        self.assertEqual(r.status_code, 429)

    def test_ip_pulih_setelah_jendela_waktu(self):
        for email in ("a@dke.test", "b@dke.test", "c@dke.test"):
            self.login(email, "SalahSalah1")
        self.age_failures(minutes=11)
        self.assertEqual(self.login("budi@dke.test", "Budi12345").status_code, 302)


class PasswordChangeThrottleTests(ThrottleTestCase):
    def as_user(self, uid=1, ip=None):
        client = self.new_client(ip)
        with client.session_transaction() as s:
            s["user_id"] = uid
        return client

    def change(self, client, current):
        return client.post("/infosys/profil/sandi", data={
            "csrf_token": self.token("/infosys/profil", client), "current_password": current,
            "new_password": "SandiBaru99", "confirm_password": "SandiBaru99"})

    def test_terkunci_setelah_lima_kali_salah_walau_cookie_dibuang(self):
        c = self.as_user()
        for _ in range(5):
            self.assertIn(self.change(c, "SalahSalah1").status_code, (400, 429))
        for client in (c, self.as_user()):                       # sesi yang sama dan sesi baru
            r = self.change(client, "Demo12345")                 # benar, tapi terkunci
            self.assertEqual(r.status_code, 429)
            self.assertIn(PW_LOCK_MSG, r.get_data(as_text=True))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM activity_logs WHERE action = 'change_password'")[0][0], 0)

    def test_pulih_setelah_jendela_waktu(self):
        c = self.as_user()
        for _ in range(5):
            self.change(c, "SalahSalah1")
        self.age_failures(minutes=11, action="password_change_failed")
        self.assertEqual(self.change(c, "Demo12345").status_code, 302)

    def test_kunci_satu_akun_tidak_mengunci_akun_lain(self):
        c = self.as_user(1)
        for _ in range(5):
            self.change(c, "SalahSalah1")
        other = self.as_user(2)
        r = other.post("/infosys/profil/sandi", data={
            "csrf_token": self.token("/infosys/profil", other), "current_password": "Budi12345",
            "new_password": "SandiBaru99", "confirm_password": "SandiBaru99"})
        self.assertEqual(r.status_code, 302)

    def test_kegagalan_login_dan_ganti_sandi_dihitung_terpisah(self):
        self.fail_logins(4)
        c = self.as_user()
        self.assertEqual(self.change(c, "Demo12345").status_code, 302)


if __name__ == "__main__":
    unittest.main()
