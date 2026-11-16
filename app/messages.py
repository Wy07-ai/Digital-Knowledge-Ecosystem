"""Satu sumber untuk kalimat tampilan yang dipakai di lebih dari satu tempat.

Panduan gaya: docs/GLOSARIUM_TEKS.md (bagian "Panduan gaya"). Ringkasnya, tiap pesan harus
spesifik, ramah, menyebut jalan keluar, tidak menyalahkan pengguna, dan memakai "Anda".

Aturan pakai:
  * Kalimat yang muncul di dua tempat atau lebih (dua rute, atau Python + JavaScript) didefinisikan
    SEKALI di sini. Modul lain memakai `from ..messages import MSG_...`; jangan menulis ulang kalimatnya.
  * `utils.py`, `module_settings.py`, dan `infosys/validation.py` mengimpor dari sini, jadi nama lama
    (`from ..utils import MSG_CSRF`) tetap berfungsi.
  * Pesan yang ditampilkan juga oleh JavaScript (`static/js/auth.js`, `panel.js`, `app.js`, ...) ditandai
    "[JS]". `tests/test_teks_ui.py` memeriksa bahwa salinan di JavaScript sama persis dengan di sini.
  * Pesan yang hanya dipakai satu rute boleh tetap ditulis di rute itu.
"""

# --- Umum --------------------------------------------------------------------
MSG_CSRF = "Sesi formulir kedaluwarsa. Muat ulang halaman lalu coba lagi."
MSG_LOGIN_REQUIRED = "Masuk dulu untuk membuka halaman ini."
MSG_API_LOGIN_REQUIRED = "Sesi Anda berakhir. Masuk lagi, lalu ulangi."
MSG_REQUEST_REJECTED = "Permintaan tidak diterima. Muat ulang halaman lalu coba lagi."
MSG_JSON_REQUIRED = "Format permintaan belum sesuai. Muat ulang halaman lalu coba lagi."
MSG_DATA_INVALID = "Data belum sesuai. Muat ulang halaman lalu coba lagi."
MSG_FORM_INVALID = "Periksa kembali isian yang ditandai."  # [JS]
MSG_CHANGE_FAILED = "Perubahan belum bisa disimpan. Coba lagi sebentar lagi."
MSG_SAVE_FAILED = "Pengaturan belum bisa disimpan. Coba lagi sebentar lagi."

# --- Masuk dan daftar (validasi di infosys/validation.py; salinan JS di auth.js) -------------
MSG_EMAIL_INVALID = "Email belum valid. Contoh: nama@email.com"  # [JS]
MSG_PASSWORD_MIN = "Kata sandi minimal 8 karakter."  # [JS]
MSG_LOGIN_FAILED = "Email atau kata sandi salah. Periksa kembali dan coba lagi."  # [JS]
MSG_LOGIN_THROTTLED = "Terlalu banyak percobaan. Coba lagi dalam beberapa menit."
MSG_NAME_REQUIRED = "Nama lengkap belum diisi. Tulis nama Anda."  # [JS]
MSG_NAME_TOO_LONG = "Nama lengkap terlalu panjang. Maksimal 100 karakter."  # [JS]
MSG_PASSWORD_MAX = "Kata sandi terlalu panjang. Maksimal 128 karakter."  # [JS]
MSG_CONFIRM_MISMATCH = "Konfirmasi kata sandi belum sama. Ketik ulang kata sandi yang sama."  # [JS]
MSG_PASSWORD_REQUIRED = "Kata sandi belum diisi. Ketik kata sandi Anda."  # [JS]
MSG_EMAIL_TAKEN = "Email ini sudah terdaftar. Masuk, atau pakai email lain."
MSG_ACCOUNT_INACTIVE = "Akun ini dinonaktifkan. Hubungi admin untuk mengaktifkannya kembali."

# --- Profil dan kata sandi (salinan JS di panel.js) --------------------------------------
MSG_BIO_TOO_LONG = "Bio terlalu panjang. Maksimal 300 karakter."  # [JS]
MSG_AVATAR_INVALID = "Tautan foto belum valid. Gunakan alamat gambar yang diawali https://"  # [JS]
MSG_AVATAR_TOO_LONG = "Tautan foto terlalu panjang. Maksimal 500 karakter."  # [JS]
MSG_CURRENT_REQUIRED = "Ketik kata sandi Anda saat ini."  # [JS]
MSG_CURRENT_WRONG = "Kata sandi saat ini salah. Periksa kembali dan coba lagi."
MSG_NEW_SAME = "Kata sandi baru sama dengan yang lama. Pilih kata sandi yang berbeda."  # [JS]
MSG_NEW_CONFIRM_MISMATCH = "Konfirmasi kata sandi baru belum sama. Ketik ulang kata sandi yang sama."  # [JS]
MSG_PASSWORD_LOCKED = "Terlalu banyak percobaan. Tunggu beberapa menit, lalu coba lagi."

# --- E-Learning -----------------------------------------------------------------------
MSG_ALREADY_ENROLLED = "Anda sudah terdaftar di kelas ini. Lanjutkan belajar!"
MSG_NOT_ENROLLED = "Anda belum terdaftar di kelas ini. Ikuti kelas lebih dulu."

# --- E-Commerce -----------------------------------------------------------------------
MSG_ADDED_TO_CART = "Produk ditambahkan ke keranjang."  # [JS]
MSG_CART_EMPTY = "Keranjang masih kosong. Tambahkan produk dulu, lalu bayar."
MSG_CART_ITEM_MISSING = "Produk tidak ada di keranjang. Muat ulang halaman lalu coba lagi."

# --- Pesan toast contoh di halaman Uji Komponen (diulang di app.js) ---------------------------
MSG_PROGRESS_AUTOSAVED = "Progres belajar tersimpan otomatis."  # [JS]
MSG_SLOW_CONNECTION = "Koneksi lambat. Perubahan akan disimpan saat tersambung kembali."  # [JS]
