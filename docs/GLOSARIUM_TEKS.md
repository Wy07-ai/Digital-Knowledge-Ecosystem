# Glosarium teks antarmuka (DKE)

Satu rujukan untuk kata-kata yang tampil ke pengguna: halaman, tombol, `flash()`, `empty_state`,
`aria-label`, `<caption>`, judul kolom tabel, opsi filter, judul halaman, dan notifikasi.
Pakai istilah di kolom **Istilah baku**; jangan campur dengan sinonimnya di layar yang sama.

## Keputusan istilah: "aplikasi", bukan "modul"

- **Keputusan:** untuk pengguna, tiap bagian DKE (Information System, E-Commerce, E-Learning, E-Tutorial,
  Portal, Forum) disebut **aplikasi**.
- **Alasan:**
  1. Pengguna umum melihat DKE sebagai kumpulan aplikasi. Tombol 9 titik di bilah atas pun berlabel
     "Pindah aplikasi".
  2. "Modul" adalah istilah teknis internal (satu modul = satu Blueprint = satu folder template).
  3. Analisis pengguna meminta bahasa sederhana tanpa istilah teknis di menu.
- **Alternatif yang dipertimbangkan:** "layanan" (terkesan seperti layanan pelanggan/jasa) dan
  "bagian" (terlalu umum, bisa tertukar dengan bagian halaman). Keduanya tidak dipilih.
- **Batas penerapan:** hanya **teks tampilan** yang diubah. Identifier internal tetap memakai "module":
  `module_key`, `MODULES`, `MODULE_BY_KEY`, `current_module`, tabel `module_settings`, nama paket/blueprint,
  `module_content`, `badge_module`, dan parameter URL `?modul=` (URL tidak diubah supaya tautan lama tetap
  berfungsi). Komentar kode dan README bagian arsitektur boleh tetap menulis "modul" karena pembacanya
  developer.
- **Pengecualian bermakna lain:** kata "modul" dalam arti *modul Python* pada isi pelajaran (mis. materi
  "Fungsi dan Modul" di `seed.py`) adalah istilah pemrograman, bukan istilah antarmuka, jadi tetap.

Contoh penggantian yang sudah berlaku:

| Lama | Baru |
|------|------|
| Jelajahi modul | Jelajahi aplikasi |
| Filter modul / Semua modul | Filter aplikasi / Semua aplikasi |
| Pindah modul | Pindah aplikasi |
| Statistik Lintas Modul | Statistik Semua Aplikasi |
| statistik lintas modul (kalimat) | statistik dari semua aplikasi |
| Lanjutkan modul terakhir | Lanjutkan aplikasi terakhir |
| Pengaturan E-Learning | tetap (sudah memakai nama aplikasi) |

## Panduan gaya

Mengikuti Blueprint 5.5 (Perancangan Pesan): **spesifik, ramah, menyebut solusi, tidak menyalahkan pengguna,
Bahasa Indonesia sederhana.**

1. **Nada.** Ramah dan langsung, seperti staf yang membantu, bukan formulir pemerintah.
2. **Sapaan.** Selalu **"Anda"** (huruf kapital A). Jangan pakai "kamu" atau akhiran "-mu".
3. **Kalimat pendek.** Subjudul halaman maksimal **15 kata**. Satu kalimat, satu gagasan.
4. **Tombol: kata kerja di awal**, huruf besar hanya di awal kalimat: "Masuk", "Tambah ke keranjang",
   "Tandai selesai", "Lanjut bayar". Hindari "Klik di sini" dan "Submit".
5. **Judul halaman** berupa kata benda singkat ("Keranjang", "Pembayaran", "Akun Saya").
6. **Empty state:** judul + **satu kalimat penjelas** + **satu tombol aksi**. Kalimat menjelaskan apa yang
   akan muncul atau apa yang bisa dilakukan, bukan hanya "Tidak ada data".
7. **Pesan galat:** sebut apa yang terjadi dan **apa yang bisa dilakukan**, tanpa menyalahkan.
   Pola: *"[Hal] belum [valid/diisi]. [Cara memperbaiki]."* Contoh: "Email belum valid. Contoh: nama@email.com".
   Jangan: "Anda salah mengisi...", "Anda harus...", "Input tidak valid".
8. **Gangguan di sisi sistem:** katakan itu bukan salah pengguna dan beri langkah berikutnya
   ("Ada gangguan di sisi kami. Coba lagi sebentar lagi.").
9. **Hindari istilah teknis** (Content-Type, sumber daya, metode permintaan) dan istilah Inggris yang punya
   padanan sehari-hari (lihat Istilah terlarang).
10. **"Silakan"** hanya bila benar-benar mempersilakan; selain itu pakai kata kerja langsung
    ("Masuk dulu untuk membuka halaman ini.").
11. **Satu sumber kalimat.** Kalimat yang dipakai di lebih dari satu tempat ditulis sekali di
    `app/messages.py` (lihat Katalog pesan). Salinan JavaScript harus sama persis; tes memeriksanya.

Contoh sebelum → sesudah:

| Sebelum | Sesudah |
|---------|---------|
| Masuk untuk membuka Control Panel | Masuk untuk melihat akun Anda |
| Jejak aktivitas akun Anda di semua aplikasi, dari yang terbaru. Hanya Anda yang dapat melihatnya. | Riwayat tindakan akun Anda, dari yang terbaru. Hanya Anda yang bisa melihatnya. |
| Nama lengkap wajib diisi. | Nama lengkap belum diisi. Tulis nama Anda. |
| Permintaan ditolak. | Permintaan tidak diterima. Muat ulang halaman lalu coba lagi. |

Daftar lengkap ada di `docs/TEKS_SEBELUM_SESUDAH.md`; semua teks tampilan bisa dilihat dengan
`python scripts/inventaris_teks.py --cari "<kata>"` atau diekspor ke `docs/INVENTARIS_TEKS.csv`.

## Istilah baku

Kolom **Dipakai di** menunjuk contoh tempat istilah itu tampil. Status "sudah" berarti UI saat ini
memang memakainya.

| Istilah baku | Arti | Dipakai di | Jangan pakai |
|--------------|------|------------|--------------|
| aplikasi | Salah satu dari 6 bagian DKE | Beranda, App Switcher, filter log, statistik | modul |
| Beranda | Halaman awal DKE (kartu 6 aplikasi) | bilah atas, jejak halaman, tombol Kembali | Home, Dashboard, Launcher |
| akun | Identitas pengguna yang masuk | Akun Saya, pendaftaran | user, member (di teks tampilan) |
| masuk / keluar | Autentikasi | Tombol di bilah atas, halaman masuk, riwayat masuk | login / logout, sign in |
| kata sandi | Rahasia akun | Formulir, galat, keamanan | password |
| kelas | Satu kursus di E-Learning | Daftar Kelas, Kelas Saya | course |
| materi | Satu pelajaran di dalam kelas | Halaman kelas, progres | lesson |
| kuis | Latihan soal di dalam kelas | Halaman kuis, hasil kuis | quiz |
| tutorial | Panduan di E-Tutorial | Daftar Tutorial | -- |
| tersimpan / simpan | Tutorial yang disimpan pengguna | Tab Tersimpan | bookmark |
| artikel | Tulisan di Portal | Portal | berita, post |
| produk | Barang atau kursus yang dijual | E-Commerce | item |
| keranjang | Daftar produk yang akan dibeli | Halaman keranjang | cart |
| pesanan | Transaksi pembelian | Pesanan Saya, detail pesanan | order |
| topik | Satu pertanyaan atau diskusi di Forum | Forum, Topik Saya | thread |
| diskusi | Percakapan di Forum (umum) | Tab Diskusi | -- |
| balasan | Jawaban/komentar pada diskusi | Forum, statistik | reply, komentar |
| solusi / terjawab | Balasan yang menjawab pertanyaan / topik yang sudah punya solusi | Forum | solved |
| profil | Halaman identitas publik pengguna | Akun Saya, Forum | profile |
| pengaturan | Preferensi pribadi per aplikasi | Tab Pengaturan | settings |
| notifikasi | Pemberitahuan di lonceng bilah atas | bilah atas | alert |
| progres | Kemajuan belajar (persen) | Kelas, statistik | progress (di teks tampilan) |
| Akun Saya | Halaman akun di Information System (profil, log, statistik, keamanan) | Menu akun, judul halaman | Control Panel |
| log aktivitas | Riwayat tindakan akun | Akun Saya | history, audit, jejak |
| pembayaran / bayar | Menyelesaikan pesanan di E-Commerce | Halaman Pembayaran, tombol Bayar | checkout |
| jejak halaman | Tautan bertingkat di atas judul | Semua halaman | breadcrumb |
| langkah | Satu bagian di dalam tutorial | E-Tutorial | step |
| perkiraan waktu | Lama baca/kerjakan tutorial | Kartu tutorial | estimasi |
| peramban | Aplikasi untuk membuka web | Pesan galat | browser |
| foto profil | Gambar pengguna | Profil | avatar |
| tingkat | Pemula/Menengah/Lanjut pada kelas dan tutorial | Filter, detail kelas | level |
| tema | Terang/gelap | bilah atas | skin |
| hapus / ubah / simpan | Aksi standar tombol | Semua formulir | delete / edit / save |

## Istilah terlarang

Istilah di kolom **Hindari** tidak boleh tampil di teks antarmuka. `tests/test_teks_ui.py` memeriksanya
otomatis (daftar `ISTILAH_TERLARANG`). Identifier, URL, komentar, dan isi seed tidak ikut diperiksa.

| Hindari | Gunakan | Status |
|---------|---------|--------|
| modul | aplikasi | Sudah |
| Control Panel | Akun Saya | Sudah |
| checkout | Pembayaran (judul), Bayar (tombol) | Sudah |
| thread | topik (Topik Saya, Buat topik) | Sudah |
| Solved | Terjawab (lencana), "sudah terjawab" (kalimat) | Sudah |
| login / logout | masuk / keluar ("Riwayat masuk", "Terakhir masuk") | Sudah |
| bookmark | simpan / tersimpan | Sudah |
| Top-Bar | bilah atas | Sudah |
| Smart Landing | "Saat membuka DKE" (pilihan: Beranda / aplikasi terakhir) | Sudah |
| App Switcher | "Pindah aplikasi" | Sudah |
| breadcrumb | jejak halaman | Sudah |
| Step, Estimasi | Langkah, Perkiraan waktu | Sudah |
| browser, avatar | peramban, foto profil | Sudah |
| Level | Tingkat | Sudah |
| password | kata sandi | Sudah (kata "password" hanya tersisa di atribut formulir) |
| kamu, -mu | Anda | Sudah |
| Silakan (pengisi) | kata kerja langsung | Sudah |
| wajib diisi, tidak valid | "belum diisi" / "belum valid" + petunjuk | Sudah |
| dapat (melihat/diubah/...) | bisa | Sudah |

Dipertahankan sebagai nama fitur atau kata baku yang dipahami pengguna: **Information System** (nama aplikasi),
**Mobile** (tombol tampilan ponsel), email, admin, filter, tab, profil, notifikasi.

## Aturan penulisan singkat

1. Satu konsep, satu kata, di seluruh aplikasi. Bila istilah baku berubah, ubah di template, `flash()`,
   `empty_state`, `aria-label`, `<caption>`, judul kolom, opsi filter, dan judul halaman sekaligus.
2. Nama aplikasi (E-Learning, Forum, dst.) ditulis apa adanya dan tidak perlu diganti kata "aplikasi".
3. Bahasa sederhana, kalimat aktif, tanpa istilah teknis di menu dan tombol.
4. Jangan menulis istilah baru yang tidak ada di tabel ini tanpa menambahkannya di sini.

## Katalog pesan

Sumber tunggal: `app/messages.py`. Kolom JS = salinan persis ada di `app/static/js/`.

| Konstanta | Teks | JS |
|-----------|------|----|
| `MSG_CSRF` | Sesi formulir kedaluwarsa. Muat ulang halaman lalu coba lagi. | - |
| `MSG_LOGIN_REQUIRED` | Masuk dulu untuk membuka halaman ini. | - |
| `MSG_API_LOGIN_REQUIRED` | Sesi Anda berakhir. Masuk lagi, lalu ulangi. | - |
| `MSG_REQUEST_REJECTED` | Permintaan tidak diterima. Muat ulang halaman lalu coba lagi. | - |
| `MSG_JSON_REQUIRED` | Format permintaan belum sesuai. Muat ulang halaman lalu coba lagi. | - |
| `MSG_DATA_INVALID` | Data belum sesuai. Muat ulang halaman lalu coba lagi. | - |
| `MSG_FORM_INVALID` | Periksa kembali isian yang ditandai. | ya |
| `MSG_CHANGE_FAILED` | Perubahan belum bisa disimpan. Coba lagi sebentar lagi. | - |
| `MSG_SAVE_FAILED` | Pengaturan belum bisa disimpan. Coba lagi sebentar lagi. | - |
| `MSG_EMAIL_INVALID` | Email belum valid. Contoh: nama@email.com | ya |
| `MSG_PASSWORD_MIN` | Kata sandi minimal 8 karakter. | ya |
| `MSG_LOGIN_FAILED` | Email atau kata sandi salah. Periksa kembali dan coba lagi. | ya |
| `MSG_LOGIN_THROTTLED` | Terlalu banyak percobaan. Coba lagi dalam beberapa menit. | - |
| `MSG_NAME_REQUIRED` | Nama lengkap belum diisi. Tulis nama Anda. | ya |
| `MSG_NAME_TOO_LONG` | Nama lengkap terlalu panjang. Maksimal 100 karakter. | ya |
| `MSG_PASSWORD_MAX` | Kata sandi terlalu panjang. Maksimal 128 karakter. | ya |
| `MSG_CONFIRM_MISMATCH` | Konfirmasi kata sandi belum sama. Ketik ulang kata sandi yang sama. | ya |
| `MSG_PASSWORD_REQUIRED` | Kata sandi belum diisi. Ketik kata sandi Anda. | ya |
| `MSG_EMAIL_TAKEN` | Email ini sudah terdaftar. Masuk, atau pakai email lain. | - |
| `MSG_ACCOUNT_INACTIVE` | Akun ini dinonaktifkan. Hubungi admin untuk mengaktifkannya kembali. | - |
| `MSG_BIO_TOO_LONG` | Bio terlalu panjang. Maksimal 300 karakter. | ya |
| `MSG_AVATAR_INVALID` | Tautan foto belum valid. Gunakan alamat gambar yang diawali https:// | ya |
| `MSG_AVATAR_TOO_LONG` | Tautan foto terlalu panjang. Maksimal 500 karakter. | ya |
| `MSG_CURRENT_REQUIRED` | Ketik kata sandi Anda saat ini. | ya |
| `MSG_CURRENT_WRONG` | Kata sandi saat ini salah. Periksa kembali dan coba lagi. | - |
| `MSG_NEW_SAME` | Kata sandi baru sama dengan yang lama. Pilih kata sandi yang berbeda. | ya |
| `MSG_NEW_CONFIRM_MISMATCH` | Konfirmasi kata sandi baru belum sama. Ketik ulang kata sandi yang sama. | ya |
| `MSG_PASSWORD_LOCKED` | Terlalu banyak percobaan. Tunggu beberapa menit, lalu coba lagi. | - |
| `MSG_ALREADY_ENROLLED` | Anda sudah terdaftar di kelas ini. Lanjutkan belajar! | - |
| `MSG_NOT_ENROLLED` | Anda belum terdaftar di kelas ini. Ikuti kelas lebih dulu. | - |
| `MSG_ADDED_TO_CART` | Produk ditambahkan ke keranjang. | ya |
| `MSG_CART_EMPTY` | Keranjang masih kosong. Tambahkan produk dulu, lalu bayar. | - |
| `MSG_CART_ITEM_MISSING` | Produk tidak ada di keranjang. Muat ulang halaman lalu coba lagi. | - |
| `MSG_PROGRESS_AUTOSAVED` | Progres belajar tersimpan otomatis. | ya |
| `MSG_SLOW_CONNECTION` | Koneksi lambat. Perubahan akan disimpan saat tersambung kembali. | ya |

## Menjaga konsistensi

`tests/test_teks_ui.py` memindai template, `flash()`/teks tampilan di `app/`, dan JavaScript, lalu gagal bila
muncul kata "modul" atau istilah terlarang, subjudul lebih dari 15 kata, empty state lebih dari satu kalimat,
kalimat ganda, atau salinan JavaScript yang berbeda dari `app/messages.py`. Pengecualian didaftar eksplisit di tes itu.
