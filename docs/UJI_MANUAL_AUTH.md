# Skenario Uji Manual: UC-IS-01 Registrasi, UC-IS-02 Login, UC-IS-03 Logout

Persiapan (sekali): `python seed.py --reset` lalu jalankan aplikasi, buka http://127.0.0.1:5000.
Aplikasi menolak start tanpa kunci sesi saat debug mati, jadi isi `DKE_SECRET_KEY` lebih dulu (README, bagian Menjalankan),
atau untuk uji lokal pakai `FLASK_DEBUG=1 python run.py` (PowerShell: `$env:FLASK_DEBUG="1"; python run.py`).
Akun demo: `demo@dke.test` / `Demo12345`. Gunakan jendela biasa (bukan sesi yang sudah login).
Periksa database kapan saja dengan:

```bash
sqlite3 instance/dke.db "SELECT id,user_id,module_key,action,detail,created_at FROM activity_logs ORDER BY id DESC LIMIT 5;"
```

Pesan yang diharapkan mengikuti Blueprint 5.5. Tes otomatis padanannya: `python -m unittest discover -s tests -v`.

---

## Skenario A. Email ganda (UC-IS-01)

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| A1 | Buka `/infosys/register`. | Kolom **Nama lengkap** langsung terfokus. |
| A2 | Isi nama `Tester Satu`, email `demo@dke.test`, kata sandi `rahasia123`, konfirmasi `rahasia123`. Tekan **Daftar**. | Halaman dimuat ulang. Di bawah kolom Email muncul teks merah dengan ikon: **Email ini sudah terdaftar. Silakan masuk atau gunakan email lain.** Kolom Email terfokus dan berbingkai merah. Nama dan email tetap terisi, **kolom kata sandi kosong**. |
| A3 | Ulangi dengan email `DEMO@DKE.TEST` (huruf besar). | Hasil sama seperti A2 (email dibandingkan tanpa membedakan huruf besar/kecil). |
| A4 | Cek database: `SELECT COUNT(*) FROM users WHERE lower(email)='demo@dke.test';` | `1`. Tidak ada akun ganda. |
| A5 | Ganti email menjadi `tester1@mail.test`, kolom lain tetap. Tekan **Daftar**. | Pindah ke `/infosys/login`. Toast hijau: *Akun berhasil dibuat. Silakan masuk dengan email dan kata sandi Anda.* Email sudah terisi di halaman login dan kolom **Kata sandi** terfokus. |
| A6 | Cek database: `SELECT u.email,u.password_hash,s.theme,s.landing_mode FROM users u JOIN user_settings s ON s.user_id=u.id WHERE u.email='tester1@mail.test';` lalu `SELECT action FROM activity_logs WHERE user_id=(SELECT id FROM users WHERE email='tester1@mail.test');` | Satu baris `users` dan **satu baris `user_settings`** (`landing_mode=launcher`). `password_hash` berawalan `scrypt:` atau `pbkdf2:` dan tidak mengandung `rahasia123`. `activity_logs` berisi `register`. |

## Skenario B. Validasi inline per field (UC-IS-01 dan UC-IS-02, alur 3a)

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| B1 | Di `/infosys/register`, ketik `budi` di Email lalu tekan Tab. | Segera (tanpa kirim): **Email belum valid. Contoh: nama@email.com** |
| B2 | Perbaiki menjadi `budi@mail.test`. | Pesan hilang saat mengetik, bingkai kembali normal. |
| B3 | Isi kata sandi `1234567` (7 karakter), Tab. | **Kata sandi minimal 8 karakter.** Dengan `12345678` pesan hilang. |
| B4 | Isi konfirmasi `12345679`, Tab. | **Konfirmasi kata sandi belum sama. Ketik ulang kata sandi yang sama.** Ubah kata sandi di atas: pesan konfirmasi ikut diperbarui. |
| B5 | Kosongkan semua, tekan **Daftar**. | Kirim dibatalkan di peramban; semua pesan tampil; fokus ke kolom salah pertama (Nama). |
| B6 | Nonaktifkan JavaScript (DevTools), ulangi B5. | Server mengembalikan halaman yang sama dengan pesan yang sama (validasi server tetap berlaku). |
| B7 | Di `/infosys/login`, isi email `x` dan kata sandi kosong, tekan **Masuk**. | Pesan email (Blueprint 5.5) dan **Kata sandi wajib diisi.**. Aturan minimal 8 karakter **tidak** berlaku di login. |

## Skenario C. Kata sandi salah (UC-IS-02, alur 4a)

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| C1 | Buka `/infosys/login`, isi `demo@dke.test` dan `salah12345`, tekan **Masuk**. | **Toast merah** di kanan atas: **Email atau kata sandi salah. Periksa kembali dan coba lagi.** Kursor kembali ke kolom **Kata sandi** (kosong); email tetap terisi. Tidak ada teks merah di bawah kolom (ini bukan galat format). |
| C2 | Isi `tidakada@mail.test` dan `apasaja123`. | Pesan toast **sama persis** seperti C1 (tidak membocorkan apakah email terdaftar). |
| C3 | Cek `activity_logs`. | Tidak ada baris `login` baru dari percobaan gagal; yang tercatat adalah baris `login_failed` (satu per percobaan, tanpa email mentah di `detail`). Top-Bar masih menampilkan **Masuk** (masih Guest). |
| C4 | Isi kata sandi benar `Demo12345`, tekan **Masuk**. | Masuk ke Beranda. Toast hijau *Selamat datang kembali, Demo.* Top-Bar menampilkan nama pengguna. |
| C5 | Cek database: `SELECT last_login_at FROM users WHERE email='demo@dke.test';` dan `activity_logs`. | `last_login_at` terisi; ada baris `infosys | login | Login berhasil` untuk user tersebut. |

## Skenario D. Halaman terlindungi sebagai Guest (alur 5a) dan open redirect

Halaman terlindungi yang tersedia saat ini: `/infosys/profil` (penampung UC-IS-04, memakai `@login_required`).

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| D1 | Sebagai Guest, buka langsung `http://127.0.0.1:5000/infosys/profil`. | Dialihkan ke `/infosys/login?next=/infosys/profil`. Toast kuning: *Silakan masuk terlebih dahulu untuk mengakses halaman ini.* |
| D2 | Login dengan akun demo. | Mendarat di **`/infosys/profil`** (halaman asal), bukan Beranda. |
| D3 | Logout, lalu buka `/infosys/profil?tab=log`. Login lagi. | Mendarat di `/infosys/profil?tab=log` (query string ikut kembali). |
| D4 | Logout. Buka `/infosys/login?next=https://evil.example`. Login dengan akun demo. | Mendarat di **Beranda `/`**, bukan situs lain. |
| D5 | Ulangi D4 dengan `next` berikut: `//evil.example`, `/\evil.example`, `javascript:alert(1)`, `/infosys/login`. | Selalu mendarat di Beranda. Cek sumber halaman login: `<input type="hidden" name="next" value="">` (nilai berbahaya dibuang). |
| D6 | Buka `/infosys/login?next=/forum/`. Login. | Mendarat di `/forum/` (jalur lokal yang sah diizinkan). |
| D7 | Sudah login, buka `/infosys/login` atau `/infosys/register`. | Langsung dialihkan ke Beranda (tidak menampilkan form). |

## Skenario E. Logout (UC-IS-03)

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| E1 | Login, buka menu profil di Top-Bar, pilih **Keluar**. | Beranda tampil sebagai Guest; toast hijau *Anda sudah keluar. Sampai jumpa lagi.* Top-Bar kembali menampilkan **Masuk** dan **Daftar**. |
| E2 | Cek `activity_logs`. | Baris `infosys | logout | Logout` untuk user tersebut. |
| E3 | Tekan tombol Kembali peramban, lalu muat ulang `/infosys/profil`. | Dialihkan ke login (sesi sudah hilang di server). |
| E4 | Sudah login, ketik `/infosys/logout` di address bar. | Hanya kembali ke Beranda; **tidak** logout (keluar hanya lewat tombol, memakai POST + token CSRF). |

## Skenario F. Pembatasan percobaan login dan ganti kata sandi (429)

Aturan bawaan: **5 kegagalan dalam 10 menit per email** (dan 20 per IP) menolak percobaan berikutnya dengan **status 429**,
walau kata sandinya benar. Hitungan berasal dari `activity_logs` (`login_failed`, `password_change_failed`), bukan cookie.
Status HTTP terlihat di DevTools > Network. Mulai dari database segar (`python seed.py --reset`), lalu jalankan aplikasi ulang.

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| F1 | Di `/infosys/login`, masukkan `demo@dke.test` dengan kata sandi salah, 4 kali berturut-turut. | Setiap kali status 401 dan toast merah **Email atau kata sandi salah. Periksa kembali dan coba lagi.** |
| F2 | Kata sandi salah untuk kelima kalinya. | Masih 401 dengan pesan yang sama. |
| F3 | Masukkan kata sandi **benar** `Demo12345`. | **Status 429**, toast merah **Terlalu banyak percobaan. Coba lagi dalam beberapa menit.** Tidak masuk (Top-Bar tetap **Masuk**). |
| F4 | Cek: `SELECT user_id,action,detail,ip_address FROM activity_logs WHERE action='login_failed';` | Tepat 5 baris (percobaan F3 yang ditolak tidak dicatat), `user_id` terisi, `detail` berisi `ref <hash>` tanpa alamat email. |
| F5 | Hapus cookie situs (DevTools > Application > Cookies) atau buka jendela privat, lalu coba `demo@dke.test` / `Demo12345` lagi. | Tetap **429**. Membuang cookie tidak melewati batas. |
| F6 | Di jendela yang sama, masuk dengan akun lain: `admin@dke.test` / `Admin12345!`. | Berhasil. Kegagalan satu email tidak mengunci email lain. |
| F7 | Logout. Gagal 5 kali dengan `hantu@mail.test` (tidak terdaftar), lalu coba keenam kalinya. | 5 kali pertama 401 dengan pesan yang sama seperti F1; percobaan keenam **429** dengan pesan yang sama seperti F3. Status 429 tidak membedakan email terdaftar dan tidak. |
| F8 | Percepat jendela waktu: `UPDATE activity_logs SET created_at = strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-11 minutes') WHERE action='login_failed';` lalu login `demo@dke.test` / `Demo12345`. | Berhasil masuk (jendela 10 menit sudah lewat). Tanpa perintah SQL, tunggu 10 menit sejak kegagalan terakhir. |
| F9 | Setelah masuk, buka **Profil**, ganti kata sandi dengan kata sandi saat ini yang salah, 5 kali. Lalu isi yang benar. | Status **429**, toast **Terlalu banyak percobaan. Tunggu beberapa menit, lalu coba lagi.** Kata sandi tidak berubah. |
| F10 | Logout, login lagi (kata sandi lama benar, login memakai hitungan terpisah), buka Profil, coba ganti kata sandi dengan benar. | Tetap **429**. Kunci ganti kata sandi melekat pada akun, bukan pada cookie sesi. |
| F11 | Percepat: `UPDATE activity_logs SET created_at = strftime('%Y-%m-%dT%H:%M:%S+00:00','now','-11 minutes') WHERE action='password_change_failed';` lalu ganti kata sandi dengan benar. | Berhasil (toast hijau). |
| F12 | Buka **Log Aktivitas** sebagai Demo. | Baris **Gagal login** dan **Gagal ubah kata sandi** tampil di samping baris Login. |

Batas per IP (20) dan perilaku header `X-Forwarded-For` (diabaikan) dicakup tes otomatis `tests/test_login_throttle.py`,
karena sulit diuji dengan tangan. Batas dapat diubah lewat `app.config`: `LOGIN_MAX_FAILS`, `LOGIN_MAX_FAILS_PER_IP`,
`LOGIN_FAIL_WINDOW_SECONDS`.
