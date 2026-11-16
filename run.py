"""Titik masuk aplikasi DKE.

Jalankan dengan:  python run.py
Variabel lingkungan:
    DKE_SECRET_KEY  WAJIB saat debug mati (bawaan). Buat dengan:
                    python -c "import secrets; print(secrets.token_hex(32))"
    FLASK_DEBUG=1   nyalakan mode debug (bawaan: 0 = mati). Hanya untuk komputer sendiri:
                    debugger Flask dapat menjalankan kode dari peramban. Dengan debug aktif,
                    DKE_SECRET_KEY boleh kosong (dipakai kunci bawaan khusus pengembangan).
    HOST, PORT      alamat dan port (bawaan 127.0.0.1:5000)
"""
import os
import sys

from flask.helpers import get_debug_flag

from app import ConfigError, create_app

try:
    app = create_app()
except ConfigError as exc:
    sys.exit(f"\n[DKE] Aplikasi tidak dijalankan.\n\n{exc}\n")

LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    debug = get_debug_flag()  # bawaan False; hanya menyala bila FLASK_DEBUG=1 diset eksplisit
    if debug and host not in LOOPBACK_HOSTS:
        print(f"[DKE] PERINGATAN: debug aktif dan HOST={host} terjangkau jaringan. "
              "Debugger Flask memungkinkan eksekusi kode dari peramban. Matikan FLASK_DEBUG.",
              file=sys.stderr)
    app.run(host=host, port=int(os.environ.get("PORT", "5000")), debug=debug)
