"""Tes konfigurasi keamanan awal: SECRET_KEY wajib saat debug mati, FLASK_DEBUG bawaan mati.

Jalankan:  python -m unittest discover -s tests -v
Tidak ada server yang dijalankan: Flask.run diganti tiruan, dan `python run.py` hanya dijalankan
untuk kasus yang memang harus gagal cepat.
"""
import io
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

from app import DEV_SECRET_KEY, ConfigError, create_app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_PY = os.path.join(ROOT, "run.py")
GOOD_KEY = "a3f1" * 16


def clean_env(**extra):
    """Lingkungan tanpa DKE_SECRET_KEY/FLASK_DEBUG milik mesin pengembang, ditambah `extra`."""
    env = {k: v for k, v in os.environ.items() if k not in ("DKE_SECRET_KEY", "FLASK_DEBUG")}
    env.update(extra)
    return env


class SecretKeyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = os.path.join(self.tmp.name, "t.db")

    def make(self, env, **config):
        with mock.patch.dict(os.environ, clean_env(**env), clear=True):
            return create_app({"DATABASE": self.db, **config})

    def test_tanpa_kunci_dan_debug_mati_menolak_start_dengan_pesan_jelas(self):
        with self.assertRaises(ConfigError) as ctx:
            self.make({})
        msg = str(ctx.exception)
        self.assertIn("DKE_SECRET_KEY", msg)
        self.assertIn("secrets.token_hex(32)", msg)

    def test_kunci_bawaan_dari_env_ditolak_saat_debug_mati(self):
        with self.assertRaises(ConfigError):
            self.make({"DKE_SECRET_KEY": DEV_SECRET_KEY})

    def test_kunci_kosong_atau_spasi_ditolak(self):
        for value in ("", "   "):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                self.make({"DKE_SECRET_KEY": value})

    def test_debug_eksplisit_false_tetap_menolak(self):
        for flag in ("0", "false", "no"):
            with self.subTest(flag=flag), self.assertRaises(ConfigError):
                self.make({"FLASK_DEBUG": flag})

    def test_kunci_acak_dari_env_dipakai(self):
        app = self.make({"DKE_SECRET_KEY": GOOD_KEY})
        self.assertEqual(app.config["SECRET_KEY"], GOOD_KEY)
        self.assertFalse(app.debug)

    def test_debug_menyala_boleh_tanpa_kunci_dengan_peringatan(self):
        with self.assertLogs("app", level="WARNING") as logs:
            app = self.make({"FLASK_DEBUG": "1"})
        self.assertTrue(app.debug)
        self.assertEqual(app.config["SECRET_KEY"], DEV_SECRET_KEY)
        self.assertIn("SECRET_KEY bawaan", logs.output[0])

    def test_debug_menyala_dengan_kunci_sendiri_tanpa_peringatan(self):
        app = self.make({"FLASK_DEBUG": "1", "DKE_SECRET_KEY": GOOD_KEY})
        self.assertEqual(app.config["SECRET_KEY"], GOOD_KEY)

    def test_test_config_boleh_memakai_kunci_sendiri(self):
        app = self.make({}, TESTING=True, SECRET_KEY="test")
        self.assertEqual(app.config["SECRET_KEY"], "test")

    def test_test_config_tanpa_kunci_tetap_ditolak_saat_debug_mati(self):
        with self.assertRaises(ConfigError):
            self.make({}, TESTING=True)

    def test_test_config_dengan_kunci_bawaan_ditolak_saat_debug_mati(self):
        with self.assertRaises(ConfigError):
            self.make({}, TESTING=True, SECRET_KEY=DEV_SECRET_KEY)

    def test_cookie_sesi_ditandatangani_dengan_kunci_env(self):
        app = self.make({"DKE_SECRET_KEY": GOOD_KEY})
        self.assertEqual(app.secret_key, GOOD_KEY)
        self.assertNotEqual(app.secret_key, DEV_SECRET_KEY)


class RunPyTests(unittest.TestCase):
    def test_python_run_py_tanpa_env_gagal_dengan_pesan_jelas(self):
        r = subprocess.run([sys.executable, RUN_PY], cwd=ROOT, env=clean_env(),
                           capture_output=True, text=True, timeout=60)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DKE_SECRET_KEY", r.stderr)
        self.assertIn("secrets.token_hex(32)", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn("Running on", r.stderr)          # server tidak sempat jalan

    def run_main(self, env):
        """Jalankan run.py sebagai __main__ dengan Flask.run ditiru; kembalikan (argumen run, stderr)."""
        err = io.StringIO()
        with mock.patch.dict(os.environ, clean_env(**env), clear=True), \
                mock.patch("flask.Flask.run") as run, redirect_stderr(err):
            runpy.run_path(RUN_PY, run_name="__main__")
        return run.call_args.kwargs, err.getvalue()

    def test_debug_bawaan_mati(self):
        kwargs, _ = self.run_main({"DKE_SECRET_KEY": GOOD_KEY})
        self.assertIs(kwargs["debug"], False)
        self.assertEqual((kwargs["host"], kwargs["port"]), ("127.0.0.1", 5000))

    def test_debug_hanya_bila_diaktifkan_eksplisit(self):
        kwargs, err = self.run_main({"FLASK_DEBUG": "1"})
        self.assertIs(kwargs["debug"], True)
        self.assertNotIn("PERINGATAN", err)               # localhost: tidak ada peringatan jaringan

    def test_debug_dengan_host_terbuka_memberi_peringatan(self):
        kwargs, err = self.run_main({"FLASK_DEBUG": "1", "HOST": "0.0.0.0"})
        self.assertIs(kwargs["debug"], True)
        self.assertIn("PERINGATAN", err)

    def test_host_terbuka_tanpa_debug_tidak_memberi_peringatan(self):
        kwargs, err = self.run_main({"DKE_SECRET_KEY": GOOD_KEY, "HOST": "0.0.0.0"})
        self.assertIs(kwargs["debug"], False)
        self.assertNotIn("PERINGATAN", err)

    def test_mengimpor_run_py_tanpa_menjalankan_server(self):
        with mock.patch.dict(os.environ, clean_env(DKE_SECRET_KEY=GOOD_KEY), clear=True), \
                mock.patch("flask.Flask.run") as run:
            ns = runpy.run_path(RUN_PY, run_name="run")
        run.assert_not_called()
        self.assertEqual(ns["app"].config["SECRET_KEY"], GOOD_KEY)


if __name__ == "__main__":
    unittest.main()
