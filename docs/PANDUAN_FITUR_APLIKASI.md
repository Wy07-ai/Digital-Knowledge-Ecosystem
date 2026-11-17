# Panduan Fitur Aplikasi

Dokumen ini memuat rincian fitur dan rute tiap aplikasi DKE, sistem navigasi 3 level, integrasi lintas modul, fitur
admin minimal, serta rincian database dan akun seed. Ringkasan cepat ada di [`README.md`](../README.md); detail
arsitektur dan keamanan ada di [`ARSITEKTUR_DAN_KEAMANAN.md`](ARSITEKTUR_DAN_KEAMANAN.md).

## Daftar isi

- [Alamat aplikasi](#alamat-aplikasi)
- [Information System / Akun Saya](#information-system--akun-saya)
  - [Autentikasi](#autentikasi-fase-1-uc-is-0103)
  - [Akun Saya](#akun-saya-information-system-fase-2-uc-is-0408)
  - [Admin minimal](#admin-minimal-uc-ad-01-dan-uc-ad-02-prioritas-c)
- [E-Commerce](#e-commerce)
- [E-Learning dan Kuis](#e-learning-dan-kuis)
- [E-Tutorial](#e-tutorial-aksen-violet-7c3aed)
- [Portal](#portal-aksen-rose-e11d48)
- [Forum](#forum-aksen-teal-0d9488)
- [Beranda dan navigasi 3 level](#beranda-dan-navigasi-3-level-fase-1-prompt-6)
- [Pencarian terpadu (/cari)](#pencarian-terpadu-cari)
- [Integrasi lintas modul](#integrasi-lintas-modul-notifikasi-smart-landing-statistik-pengaturan)
- [Database dan data contoh](#database-dan-data-contoh)

## Alamat aplikasi

| Blueprint   | URL          | Aksen     |
|-------------|--------------|-----------|
| main        | `/`, `/cari` | -         |
| infosys     | `/infosys/`  | `#4F46E5` |
| ecommerce   | `/ecommerce/`| `#F59E0B` |
| elearning   | `/elearning/`| `#2563EB` |
| etutorial   | `/etutorial/`| `#7C3AED` |
| portal      | `/portal/`   | `#E11D48` |
| forum       | `/forum/`    | `#0D9488` |

## Information System / Akun Saya

### Autentikasi (Fase 1, UC-IS-01..03)

| URL | Metode | Fungsi |
|-----|--------|--------|
| `/infosys/register` | GET, POST | Registrasi: membuat `users` + `user_settings` + log `register` dalam satu transaksi |
| `/infosys/login`    | GET, POST | Login; mendukung `?next=<halaman asal>`; mencatat `activity_logs` dan `last_login_at` |
| `/infosys/logout`   | POST      | Logout (mencatat `activity_logs`); GET hanya mengarahkan ke Beranda |
| `/infosys/profil`   | GET, POST | Tab Profil di Akun Saya (lihat bagian [Akun Saya](#akun-saya-information-system-fase-2-uc-is-0408)) |

- Validasi inline (Blueprint 5.5) ada di `app/infosys/validation.py` (server) dan `static/js/auth.js` (peramban); aturannya harus sama.
- Kata sandi: `werkzeug.security.generate_password_hash`; kredensial salah memberi pesan sama untuk email tak dikenal dan kata sandi salah.
- `next` hanya diterima bila jalur lokal (`utils.safe_next` memakai `is_safe_next`, menolak URL absolut, `//`, backslash, karakter kontrol, dan halaman login/register/logout).
- Form dilindungi token CSRF per sesi (`utils.csrf_token` / `csrf_valid`); tombol Keluar memakai POST.
- **Pembatas percobaan login**: lima kegagalan dalam 10 menit untuk satu email (atau 20 per IP) membuat login ditolak
  dengan status 429. Rincian lengkap ada di
  [`ARSITEKTUR_DAN_KEAMANAN.md`](ARSITEKTUR_DAN_KEAMANAN.md#pembatas-percobaan-login-appinfosysthrottlepy).
- Tes otomatis: `python -m unittest discover -s tests -v` (autentikasi, Beranda, dan navigasi). Skenario uji manual: [`UJI_MANUAL_AUTH.md`](UJI_MANUAL_AUTH.md).

### Akun Saya Information System (Fase 2, UC-IS-04..08)

Layout **sidebar tab di kiri, panel di kanan**, aksen indigo (`#4F46E5`). Di layar sempit dan Mobile View
paksa, sidebar menjadi deretan tab horizontal yang bisa digeser (`custom.css` bagian 9).

| Tab | URL | Isi |
|-----|-----|-----|
| Ringkasan | `/infosys/` | Kartu akun, 4 statistik singkat, 5 aktivitas terbaru. Guest melihat ajakan masuk |
| Profil | `/infosys/profil` | Ubah nama, bio (maks. 300), `avatar_url` (https, maks. 500) dengan pratinjau; form terpisah **Ganti kata sandi** (`POST /infosys/profil/sandi`) |
| Log Aktivitas | `/infosys/log?modul=&halaman=` | Tabel dengan filter aplikasi dan paginasi 10 baris per halaman |
| Statistik Semua Aplikasi | `/infosys/statistik` | 6 kartu: pesanan, kelas diikuti, rata-rata progres, tutorial tersimpan, thread, balasan; progres per kelas |
| Pengaturan Keamanan | `/infosys/keamanan?halaman=` | Riwayat login (waktu + IP) dengan paginasi, peringatan bila ada lebih dari satu IP, tautan ganti kata sandi |

**Aturan penting**

- **Data hanya milik pengguna yang login.** Id pengguna selalu diambil dari sesi (`g.user["id"]`), tidak pernah dari
  query string atau form. Semua kueri di `app/infosys/panel.py` memakai `WHERE user_id = ?`. Tes `tests/test_panel.py`
  memakai dua akun yang berbagi satu database untuk membuktikan tidak ada kebocoran (termasuk `?user_id=2`).
- **Riwayat login memakai `activity_logs`** (`action = 'login'`; kegagalan: `login_failed`), bukan tabel baru, supaya skema tetap 23 tabel sesuai Blueprint 3.3.
  Skema tidak punya kolom user-agent, jadi yang ditampilkan waktu dan alamat IP.
- **Setiap aksi form memberi toast** (`flash()` Flask atau `toast()` JS), dan **validasi inline** ada di server
  (`app/infosys/validation.py`) dan peramban (`static/js/panel.js`); aturannya harus sama. Form selalu `novalidate`,
  dilindungi token CSRF, dan kata sandi tidak pernah dikirim balik ke HTML.
- **Ganti kata sandi:** kata sandi saat ini diverifikasi dengan hash; setelah 5 kali salah dalam 10 menit, form ditolak
  dengan status 429 (pembatas bersama dengan login, `app/infosys/throttle.py`, dihitung dari `activity_logs` per akun dan
  per IP sehingga tidak bisa dilewati dengan membuang cookie; lihat bagian [Autentikasi](#autentikasi-fase-1-uc-is-0103)). Berhasil atau gagal,
  kejadiannya dicatat di `activity_logs`, dan keberhasilan juga membuat notifikasi.
- **Empty state** ditangani per tab (log kosong, filter tanpa hasil, statistik nol semua, riwayat login kosong) memakai
  komponen `empty_state()`; bagian kecil di Ringkasan memakai pesan ringkas.
- Filter `modul` yang tidak dikenal diabaikan (bukan error) dan nomor halaman dijepit ke rentang sah.
- Waktu ditampilkan dalam WIB (UTC+7); database tetap menyimpan UTC ISO-8601.

Tes otomatis: `python -m unittest discover -s tests -v` (catatan lama README: 464 tes, termasuk 62 tes Portal, 108 tes
Forum, dan 24 tes pembatas login; jumlah terkini lebih banyak karena tes terus bertambah).
Skenario uji manual: [`UJI_MANUAL_PANEL.md`](UJI_MANUAL_PANEL.md).

### Admin minimal (UC-AD-01 dan UC-AD-02, prioritas C)

Hanya akun `users.role = 'admin'` (seed membuat `admin@dke.test`). Tab **Admin** muncul di sidebar Akun Saya
hanya untuk admin. Guest diarahkan ke login; Member biasa mendapat **403** di semua rute admin (GET maupun POST).

| URL | Fungsi |
|-----|--------|
| `/infosys/admin?tab=thread\|balasan\|akun&halaman=N` | Daftar thread, balasan, dan akun (10 per halaman) |
| `/infosys/admin/thread/<id>/hapus` | GET konfirmasi, POST hapus thread (balasannya ikut terhapus) |
| `/infosys/admin/balasan/<id>/hapus` | GET konfirmasi, POST hapus balasan (anak naik satu tingkat; solusi dihapus -> thread belum terjawab) |
| `/infosys/admin/akun/<id>/nonaktifkan` dan `/aktifkan` | GET konfirmasi, POST ubah `users.is_active` |

- Setiap POST memeriksa token CSRF dan dilakukan dalam satu transaksi.
- Setiap aksi dicatat di `activity_logs` (`user_id` = admin, `module_key = 'infosys'`) dengan action `admin_delete_thread`,
  `admin_delete_reply`, `admin_deactivate_user`, `admin_activate_user`; tampil di Log Aktivitas admin.
- Akun nonaktif tidak bisa login, dan **sesi yang sedang berjalan langsung tidak berlaku** (dicek tiap permintaan di
  `load_user_and_settings`).
- Admin tidak bisa menonaktifkan dirinya sendiri maupun admin lain (tidak ada jalur kunci-keluar).
- **Batasan yang disengaja** (untuk responsi): cakupan "kelola konten" dibatasi pada *menghapus* konten Forum; tidak ada
  tambah/ubah konten Portal, E-Learning, E-Tutorial, atau katalog E-Commerce lewat UI admin (diisi lewat `seed.py`).
  Tidak ada pengelolaan peran (tak ada UI mengangkat/menurunkan admin) dan tidak ada notifikasi ke penulis yang kontennya
  dihapus. Forum tetap menolak admin mengubah/menghapus balasan orang lain lewat rute Forum; moderasi hanya lewat halaman
  ini agar selalu tercatat.
- Tes: `python -m unittest tests.test_admin`. Uji manual: [`UJI_MANUAL_ADMIN.md`](UJI_MANUAL_ADMIN.md).

## E-Commerce

E-Commerce menyediakan katalog dan detail produk, keranjang, checkout simulasi,
konfirmasi serta riwayat pesanan, dan pengaturan alamat/metode pembayaran favorit.
Checkout menyimpan pesanan, item, enrollment kursus, notifikasi, dan log dalam satu
transaksi database. Alur ini tercakup dalam `python -m unittest tests.test_ecommerce`.

Produk bertipe kursus terhubung ke kursus E-Learning lewat `course_id`; kursus hasil checkout
(`enrollments.source = 'order'`) langsung tampil di Kelas Saya (lihat [E-Learning](#e-learning-dan-kuis)).

## E-Learning dan Kuis

**Bagian 1.** E-Learning menyediakan daftar kelas dengan filter level, detail kelas, enroll kelas gratis,
Kelas Saya, Ruang Belajar (materi teks atau embed video + sidebar daftar bab), tombol Tandai Selesai
tanpa reload (progress bar bertransisi 300 ms), navigasi materi sebelumnya/berikutnya, serta tab
Pengaturan (kecepatan video, target belajar). `progress_percent` selalu dihitung dari `lesson_progress`;
kursus hasil checkout (`enrollments.source = 'order'`) langsung tampil di Kelas Saya; Ruang Belajar dan API
progres menolak pengguna yang belum terdaftar.
Uji: `python -m unittest tests.test_elearning`; panduan manual: [`UJI_MANUAL_ELEARNING.md`](UJI_MANUAL_ELEARNING.md).

**Bagian 2 (kuis, UC-EL-05/06).** Soal tampil satu per satu dengan indikator nomor,
jawaban sementara disimpan di `localStorage` browser, dialog konfirmasi bila ada soal kosong, lalu
dikumpulkan ke server. **Penilaian hanya di server** (`app/elearning/quiz.py: grade()`): server hanya
menerima pilihan `a/b/c/d` per soal dan mengabaikan skor dari klien. Halaman pengerjaan tidak memuat
`correct_option` maupun `explanation`; keduanya baru tampil di halaman hasil setelah percobaan
tersimpan di `quiz_attempts` (`score`, `passed`, `answers_json`). Skor = persen benar dibulatkan ke
bawah, sehingga `score >= pass_score` selalu sama dengan keputusan lulus. Bila lulus, `enrollments.completed_at`
diisi (sekali, tidak ditimpa kelulusan berikutnya) dan semua materi kelas ditandai selesai di
`lesson_progress`, sehingga `progress_percent` yang dihitung menjadi 100%. Gagal tidak mencabut status selesai.
Uji: `python -m unittest tests.test_quiz`; panduan manual: [`UJI_MANUAL_KUIS.md`](UJI_MANUAL_KUIS.md).

| Rute E-Learning | Fungsi |
|-----------------|--------|
| `/elearning/` (`?level=`) | Daftar kelas (UC-EL-01) |
| `/elearning/kelas/<id>` | Detail kelas; tombol enroll gratis (UC-EL-02) |
| `/elearning/kelas-saya` | Kelas Saya + target belajar hari ini |
| `/elearning/kelas/<id>/materi/<no>` | Ruang Belajar (UC-EL-03), hanya peserta terdaftar |
| `POST /elearning/api/materi/<id>/selesai` | Tandai/batalkan selesai (UC-EL-04), JSON + token CSRF |
| `/elearning/kelas/<id>/kuis` | Mengerjakan kuis, satu soal per layar (UC-EL-05), hanya peserta terdaftar |
| `POST /elearning/kelas/<id>/kuis/kumpul` | Kumpulkan jawaban; dinilai di server, lalu redirect ke hasil; token CSRF |
| `/elearning/kelas/<id>/kuis/hasil/<attempt_id>` | Skor, lulus/belum, pembahasan tiap soal, tombol Coba Lagi (UC-EL-06); hanya pemilik percobaan |
| `/elearning/pengaturan` | Kecepatan video dan target belajar (UC-EL-07) |

## E-Tutorial (aksen violet `#7C3AED`)

- **Daftar tutorial** (`/etutorial/`): filter kategori dan tingkat kesulitan (kombinasi AND, angka tombol mengikuti filter lain), estimasi menit, jumlah langkah, penanda Tersimpan.
- **Halaman tutorial** (`/etutorial/tutorial/<slug>/langkah/<n>`): satu kolom, satu langkah per halaman, stepper Step 1..n dengan tombol Sebelumnya/Berikutnya, bar posisi, dan titik indikator.
- **Blok kode + Salin** (`static/js/copy.js`): toast "Kode disalin"; memakai Clipboard API dan cadangan `execCommand` untuk http:// non-aman.
- **Bookmark** (UC-ET-04, Member): POST `/etutorial/tutorial/<slug>/simpan` (CSRF, idempoten, dicatat di activity_logs) dan halaman **Tersimpan** (`/etutorial/tersimpan`).
- **Ukuran font** Kecil/Sedang/Besar (14/16/20 px): Member di `module_settings` (`etutorial` / `font_size` = `sm|md|lg`), Guest di cookie `dke_et_font`. Besar punya aturan khusus ponsel (layar sempit dan Mobile View): tombol bawah ditumpuk, kode dibungkus baris, target sentuh >= 48 px.
- **Keamanan**: semua teks dan kode dari database dicetak lewat autoescape Jinja (tanpa `|safe`/`Markup`); tes memindai template agar tetap begitu.

Uji: `python -m unittest tests.test_etutorial`; panduan manual: [`UJI_MANUAL_ETUTORIAL.md`](UJI_MANUAL_ETUTORIAL.md).

## Portal (aksen rose `#E11D48`)

- **Beranda** (`/portal/`): artikel *featured* besar di atas (gambar + judul + kutipan + penulis, tanggal, waktu baca) dan kartu artikel di bawahnya. Bila tidak ada artikel featured, artikel terbaru dipakai dan lencananya berubah menjadi "Terbaru".
- **Chip kategori** sebagai filter (`?kategori=<slug>`), lengkap dengan jumlah artikel. Slug tak dikenal diabaikan dengan pemberitahuan.
- **Paginasi** (`?halaman=<n>`, 6 kartu per halaman). Artikel featured hanya tampil di halaman 1 dan tidak pernah muncul dobel di kartu. Nomor halaman di luar rentang dijepit.
- **Empty state**: kategori tanpa artikel ("Belum ada artikel di kategori ...") dan Portal yang sama sekali kosong. Seed sengaja membuat kategori *Kesehatan Digital* tanpa artikel untuk demo.
- **Detail artikel** (`/portal/artikel/<slug>`): waktu baca (kolom `read_minutes`, bila kosong diperkirakan dari panjang teks), penulis (bila kosong "Redaksi DKE"), tanggal (WIB), jumlah views, dan hingga 3 **artikel terkait** dari kategori yang sama.
- **Views**: bertambah lewat `UPDATE articles SET views = views + 1` (atomik). Bawaan: satu kali per sesi peramban untuk tiap artikel supaya muat ulang tidak menggelembungkan angka; HEAD dan 404 tidak dihitung. Untuk menghitung tiap kunjungan, set `COUNT_ONCE_PER_SESSION = False` di `app/portal/routes.py`.
- **Preferensi kategori** (`/portal/pengaturan`, Member): disimpan di `module_settings` (`portal` / `preferred_categories` = slug dipisah koma). Pengaruhnya pada beranda tanpa filter: artikel featured dari kategori favorit dipilih lebih dulu, kartu kategori favorit tampil lebih dulu (lalu terbaru), dan chip favorit diberi bintang + teks "(favorit)". Preferensi hanya **mengurutkan**, tidak ada artikel yang disembunyikan. Guest diarahkan ke login (UC-PT-04 khusus Member).
- **Gambar**: semua `<img>` memakai `loading="lazy"`, `decoding="async"`, `width`/`height` (cegah layout bergeser), dan teks `alt` ("Sampul artikel: <judul>"). Sampul lokal ada di `static/img/portal/` (SVG ringan, satu per artikel + `default.svg`); `cover_url` boleh berisi jalur relatif static atau URL http(s), nilai lain (mis. `javascript:`) diganti sampul bawaan. `static/js/portal.js` mengganti gambar yang gagal dimuat dengan sampul bawaan.
- **Keamanan**: semua teks dari database lewat autoescape Jinja (tanpa `|safe`/`Markup`; tes memindai template).

Uji: `python -m unittest tests.test_portal`; panduan manual: [`UJI_MANUAL_PORTAL.md`](UJI_MANUAL_PORTAL.md).

## Forum (aksen teal `#0D9488`)

- **Daftar thread** (`/forum/`): judul, kategori, penulis, waktu, **jumlah balasan**, dilihat, dan lencana **Solved** (ikon centang + kata, bukan hanya warna). 8 thread per halaman (`?halaman=<n>`).
- **Filter kategori** (`?kategori=<slug>`) dan **urutan** (`?urut=terbaru` bawaan, atau `?urut=belum-terjawab`). *Belum terjawab* = thread yang belum punya balasan bertanda solusi; yang paling sedikit balasannya tampil lebih dulu. Angka di chip kategori mengikuti urutan terpilih. Nilai tak dikenal diabaikan dengan pemberitahuan.
- **Buat thread** (`/forum/buat`, Member): kategori, judul (5-150 karakter), isi (10-5000). Validasi dua lapis: inline di peramban (pesan di bawah field, penghitung karakter) dan ulang di server (422, isian dipertahankan). Draf tersimpan sementara di `sessionStorage`.
- **Detail thread** (`/forum/thread/<id>`): isi thread dan balasan bersarang lewat `posts.parent_post_id`. Di database kedalaman tidak dibatasi, tetapi **tampilan dibatasi 3 tingkat** (`MAX_DISPLAY_LEVEL` di `app/forum/logic.py`): balasan tingkat 4 dst. ditampilkan sejajar tingkat 3 dengan keterangan "Membalas <nama>". Balasan induk harus berada di thread yang sama.
- **Form balas** (Member): meluncur naik (*slide-up* 250 ms) saat membalas balasan tertentu; balasan baru juga muncul dengan slide-up sekali, disertai toast sukses. Tanpa JavaScript, tautan `?balas=<id>#form-balas` tetap berfungsi. Mengikuti `prefers-reduced-motion`.
- **Tandai solusi** (`POST /forum/thread/<id>/solusi`): hanya **pemilik thread** (403 untuk yang lain). Satu solusi per thread, bisa dipindah atau dibatalkan.
- **Ubah/hapus balasan** (`/forum/balasan/<id>/ubah|hapus`): hanya **penulis balasan** (403 untuk orang lain, termasuk pemilik thread). Hapus lewat halaman konfirmasi; balasan anak naik ke induk yang dihapus agar jawaban orang lain tidak hilang, dan bila yang dihapus adalah solusi, thread kembali belum terjawab.
- **Thread Saya** (`/forum/saya`, Member): daftar thread milik sendiri, jumlah dan jumlah Solved.
- **Pengaturan** (`/forum/pengaturan`, Member): *privasi profil* (Publik / Hanya anggota / Privat) dan *notifikasi balasan* (Aktif / Nonaktif), disimpan di `module_settings` (`forum` / `profile_privacy` dan `notify_reply`). Privasi mengatur halaman profil Forum `/forum/pengguna/<id>` (bio, tanggal bergabung, ringkasan); nama penulis tetap tampil di thread dan balasannya, email tidak pernah ditampilkan.
- **Notifikasi**: balasan dari anggota lain membuat baris `notifications` untuk penulis thread (tautan langsung ke balasannya) bila ia mengizinkan; belum diatur dianggap diizinkan. Balasan dari penulis thread sendiri tidak membuat notifikasi. Semuanya dalam satu transaksi dengan penyimpanan balasan.
- **Keamanan**: semua isi pengguna lewat autoescape Jinja (tanpa `|safe`/`Markup`; JavaScript hanya memakai `textContent`; tes memindai template dan skrip). Setiap POST memeriksa token CSRF, SQL memakai parameter, hak ubah/hapus/solusi diperiksa di server, bukan hanya dengan menyembunyikan tombol.
- **Aksesibilitas**: tombol dan chip minimal 44 px; teks putih memakai teal `#0F766E` (5,47:1) karena putih di atas `#0D9488` hanya 3,74:1; status tidak hanya warna; fokus terlihat; dukungan Dark Mode dan Mobile View.

Uji: `python -m unittest tests.test_forum`; panduan manual: [`UJI_MANUAL_FORUM.md`](UJI_MANUAL_FORUM.md).

## Beranda dan navigasi 3 level (Fase 1, Prompt 6)

**Beranda** (`/`, `app/main/routes.py` + `app/main/launcher.py`)

- **Hero carousel** (`_components/hero_carousel.html`, `static/js/carousel.js`, `custom.css` bagian 8c): lima slide
  berurutan E-Learning, E-Commerce, E-Tutorial, Portal, dan Forum (Information System tidak ikut). Data slide ada di
  `HERO_SLIDES` (`app/main/launcher.py`): `key`, judul, satu kalimat maks. 15 kata yang menyapa dengan "Anda", dan label
  tombol. Tombol slide menuju `url_for(key ~ '.index')`; aksen aplikasi dari `MODULE_BY_KEY` hanya menjadi cahaya
  dekoratif di belakang ikon besar (teks selalu putih di atas dasar navy, kontras >= 4,5:1 di Terang dan Gelap).
  - **Geser otomatis** tiap 10 detik (nilai dari `data-interval`, bukan di JavaScript). Berhenti saat hover dan fokus
    (lanjut bila kursor dan fokus sudah keluar), saat tab tersembunyi, dan tidak berjalan sama sekali bila
    `prefers-reduced-motion: reduce` aktif (perubahan pengaturan dipantau langsung). Tombol Jeda/Putar adalah pilihan
    tetap pengguna (WCAG 2.2.2).
  - **Kontrol**: Jeda/Putar, Sebelumnya, Berikutnya, dan titik indikator (area sentuh 44 x 44 px, titik aktif berbentuk
    pil dan ber-`aria-current`). ArrowLeft/ArrowRight (juga Home/End) pada kontrol, geser sentuh dengan ambang 40 px.
  - **Aksesibilitas**: pembungkus `aria-roledescription="carousel"`, tiap slide grup "n dari 5", slide tak aktif memakai
    `visibility: hidden` (tidak bisa difokus), `aria-live` "off" saat otomatis dan "polite" saat dijeda atau dipindah manual.
  - **Tanpa JavaScript**: slide pertama tampil, tombol slide tetap tautan, kontrol tersembunyi (kelas `.carousel-js`
    dipasang oleh `carousel.js`). Tanpa skrip inline dan atribut event, jadi CSP tidak dilonggarkan.
  - **Mobile View dan layar sempit**: tanpa ilustrasi besar, judul kecil, tombol slide selebar penuh (aturan Issue A).
  - Strip tipis di bawah carousel berisi sapaan dan tombol **Lanjutkan** (`data-resume`); lihat bagian di bawah.
  - Uji: `python -m unittest tests.test_home_hero`; uji manual: [`UJI_MANUAL_BERANDA.md`](UJI_MANUAL_BERANDA.md) baris 15-33.
- Grid kartu aplikasi: 3 kolom x 2 baris di desktop (`lg`), 2 kolom di tablet, dan 2 kolom x 3 baris di layar di bawah 768 px
  serta di Mobile View (kelas `grid-cols-2 gap-3 lg:grid-cols-3 lg:gap-4`; aturan Mobile View dan layar sempit untuk `.launcher-grid`
  ada di `custom.css` bagian 6). Grid `.product-grid` dan `.card-grid` di halaman lain tetap satu kolom di mobile.
  Setiap kartu adalah kartu fitur: area visual berlatar gradien aksen dengan ikon besar di tengah (sekitar 52 px di desktop, 38 px di mobile),
  judul aplikasi yang tegas (maks. 2 baris), lalu satu baris metrik atau ajakan (maks. ~40 karakter, angka ditonjolkan; teks yang kepanjangan
  dipotong dengan elipsis). Deskripsi aplikasi tidak tampil di kartu; ia ada di `title` (tooltip) dan di elemen `sr-only` yang dirujuk
  `aria-describedby`, tanpa `aria-label` supaya metrik tetap dibaca pembaca layar. Warna gradien dan ikon dicampur dari token tema
  (`--card-accent`, `--c-surface`, `--c-ink`), jadi kontras terjaga di Terang dan Gelap. Zona metrik menempel di dasar kartu dengan tinggi
  tetap; hover lift 4 px + glow 200 ms (`.launcher-card` di `custom.css`) hanya aktif di perangkat dengan hover sungguhan dan saat
  reduced-motion mati.
- Widget dibaca dari database, satu fungsi per modul di `launcher.py`. Data kosong tampil sebagai pesan
  ramah berwarna redup ("Keranjang masih kosong"), dan kegagalan satu widget tidak merusak halaman.
  Guest melihat satu ajakan pendek per kartu ("Lihat produk", "Lihat kelas", "Baca artikel", "Lihat diskusi").
- Tombol **Lanjutkan: aplikasi > halaman terakhir** (di strip di bawah carousel) dibangun dari `user_settings.last_module` dan `last_path`.
  Jalurnya divalidasi ulang tiap tampil (lokal, masih cocok dengan rute, sesuai modul); bila tidak valid
  tombol disembunyikan. Label halaman diambil dari hierarki di `app/navigation.py`.
- **landing_mode**: `launcher` menampilkan Beranda; `last_module` mengalihkan ke halaman terakhir, tetapi
  hanya pada kedatangan pertama di sesi (penanda sesi `dke_landed`), supaya tombol DKE di Top-Bar tetap
  bisa membuka Beranda. Login dan logout memanggil `session.clear()`, jadi login baru dialihkan lagi.
  Member mengubahnya lewat tombol "Saat membuka DKE" di Beranda (`static/js/launcher.js`, memakai
  `POST /api/settings/global`).

**Pencarian terpadu (`/cari`)**

Satu halaman hasil untuk semua aplikasi, bisa dibuka Guest dan Member. Berfungsi tanpa JavaScript (formulir GET), mudah diuji,
dan cocok untuk mobile. Modal pencarian cepat bisa menjadi issue lanjutan.

| URL | Metode | Fungsi |
|-----|--------|--------|
| `/cari?q=&jenis=` | GET | Mencari kelas, produk, tutorial, artikel, dan topik Forum. `jenis` = `kelas`, `produk`, `tutorial`, `artikel`, atau `topik` (opsional) |

- **Kode:** rute `main.search` di `app/main/routes.py`; kueri per aplikasi di `app/search.py` (`search_courses`, `search_products`,
  `search_tutorials`, `search_articles`, `search_threads`); templat `main/search.html`; pemicu di bilah atas
  `_components/search_trigger.html` (di-include dari `topbar.html`); pintasan keyboard `static/js/search.js`.
- **Sumber data:** kelas (`title`, `description`, hanya `is_published = 1`), produk (`name`, `description`, hanya `is_active = 1`),
  tutorial (`title`, `summary`), artikel (`title`, `excerpt`), topik Forum (`title`, `body`). Tabel `tutorials`, `articles`, dan
  `threads` belum punya kolom status terbit, jadi semua barisnya publik. Hanya data publik yang dicari; tidak ada email atau data akun.
- **Kata kunci:** `strip`, maksimal 100 karakter, minimal 2 karakter. Kosong, hanya spasi, atau terlalu pendek menampilkan
  `empty_state()` tanpa mencari.
- **Keamanan:** kueri berparameter (`LIKE ? ESCAPE '\'`); karakter `%`, `_`, dan `\` di-escape sehingga dicari sebagai teks biasa
  (pola yang sama dengan `?q=` di katalog E-Commerce). Tidak ada `|safe`: judul dan cuplikan dipecah di Python menjadi potongan teks
  biasa (`highlight_parts`), lalu dicetak lewat autoescape Jinja dengan `<mark>` hanya untuk potongan yang cocok.
- **Hasil:** dikelompokkan per aplikasi dengan label dan aksen aplikasi (Kelas, Produk, Tutorial, Artikel, dan **Topik** untuk Forum),
  judul cocok diurutkan lebih dulu, lalu yang terbaru. Maksimal 5 hasil per jenis; ada tautan "Lihat semua N hasil" yang membuka
  `?jenis=` (maksimal 20 hasil). Jumlah di chip filter selalu jumlah sebenarnya. `jenis` tak dikenal diabaikan dengan catatan
  "Jenis hasil itu tidak dikenal, jadi semua jenis dicari." (pola yang sama dengan filter di aplikasi lain). Tiap hasil menaut ke
  halaman detail yang sudah ada.
- **Navigasi:** `node("main.search", "Pencarian", parent="main.index")` di `app/navigation.py`, ditambah `node("main.index", "Beranda")`
  karena Beranda bukan modul dan tidak otomatis menjadi akar. Hasilnya jejak halaman Beranda > Pencarian dan tombol Kembali ke Beranda.
- **Bilah atas:** di desktop, kolom `<form role="search" action="/cari">` dengan ikon kaca pembesar dan petunjuk "Cari kelas, produk,
  tutorial...", melebar saat fokus (kelas `dke-hide-mobile`). Di layar sempit dan Mobile View diganti tombol ikon (tautan ke `/cari`,
  `aria-label="Cari"`, minimal 44 px) dengan kelas `dke-show-mobile`, kebalikan `dke-hide-mobile` di `custom.css` bagian 6 (berlaku di
  media query dan `html[data-view='mobile']`, karena kelas `md:` Tailwind tidak mengikuti Mobile View). Halaman `/cari` juga punya kolom
  sendiri untuk mobile. Saat kata kunci kosong, kolom mendapat `autofocus`. Tombol `/` memindahkan fokus ke kolom desktop
  (`search.js`, tidak wajib).
- Uji: `python -m unittest tests.test_search`; uji manual: [`UJI_MANUAL_PENCARIAN.md`](UJI_MANUAL_PENCARIAN.md).

**Navigasi 3 level** (Blueprint 5.2)

| Level | Komponen | Sumber |
|-------|----------|--------|
| 1 | Tombol Kembali: menuju induk langsung di hierarki halaman, bukan riwayat browser | `app/navigation.py` |
| 2 | Breadcrumb: tiap jenjang bisa diklik; di mobile menjadi `... > Halaman`, tombol `...` membuka jenjang tersembunyi | `_components/breadcrumb.html` |
| 3 | App Switcher (9 titik) + tombol DKE di Top-Bar, aplikasi aktif ditandai | `_components/app_switcher.html` |

Breadcrumb dan Kembali tampil **otomatis** di atas konten (`{% block page_nav %}` di `base.html`) untuk
setiap halaman yang terdaftar di `app/navigation.py`. Contoh menambah halaman bersarang:

```python
node("elearning.course_detail", _course_title, parent="elearning.index")
node("elearning.lesson", _lesson_title, parent="elearning.course_detail")
```

Contoh langsung 3 jenjang (E-Learning > judul kelas > Materi N): http://127.0.0.1:5000/dev/ui-test/navigasi/kelas/1/materi/1
(ikut dimatikan oleh `DKE_UI_TEST=0`). Contoh nyata 2 jenjang: Information System > Profil & Pengaturan.

## Integrasi lintas modul (notifikasi, Smart Landing, statistik, pengaturan)

- **Notifikasi Top-Bar.** Lonceng menampilkan jumlah belum dibaca (lencana, `9+` bila lebih), panel berisi notifikasi terbaru beserta aplikasi dan waktunya, dan tautan ke halaman asal. Klik notifikasi bertautan menandainya dibaca sambil membuka halaman asal; notifikasi tanpa tautan berupa tombol yang hanya menandai dibaca. Tombol "Tandai semua dibaca" membersihkan seluruhnya. Endpoint: `POST /api/notifications/read` (`{"id": N}` atau `{"all": true}`, JSON same-origin, hanya milik akun sendiri), klien: `static/js/notif.js`, logika: `utils.mark_notifications_read`.
- **Smart Landing.** Kontrol di Beranda menampilkan statusnya (aktif/nonaktif). "Tampilkan Beranda" mematikannya; "Lanjutkan aplikasi terakhir" menyalakannya. Tersimpan di `user_settings.landing_mode`.
- **Statistik Information System** (`/infosys/statistik`) memuat data keenam aplikasi: pesanan, kelas, kemajuan, bookmark, thread, balasan, kuis lulus, artikel Portal (umum), kategori favorit, aktivitas tercatat, dan rincian aktivitas per aplikasi.
- **Pengaturan per modul** memakai satu pola: `app/module_settings.py` (`get_setting`, `set_setting`, `MSG_SAVE_FAILED`, `msg_saved`). Modul tidak boleh menulis SQL `module_settings` sendiri (dijaga tes). `set_setting(..., None)` menghapus; `commit=False` untuk transaksi gabungan. Setiap simpan tercatat di log aktivitas.
- **Navigasi.** Setiap halaman GET modul harus punya node di `app/navigation.py` (dijaga `NavigationCoverageTest`); E-Commerce kini ikut.
- Uji: `python -m unittest tests.test_integration`; panduan manual: [`UJI_MANUAL_INTEGRASI.md`](UJI_MANUAL_INTEGRASI.md); rincian perubahan: [`PERUBAHAN_INTEGRASI.md`](PERUBAHAN_INTEGRASI.md).

## Database dan data contoh

- `schema.sql` : 23 tabel sesuai Blueprint 3.3 (dapat dijalankan sendiri di SQLite).
- `seed.py`    : membuat database dari awal dan mengisi data contoh berbahasa Indonesia.

```bash
python seed.py            # aman dijalankan ulang: tidak menggandakan data, tidak menimpa kata sandi
python seed.py --reset    # hapus semua tabel lalu bangun ulang dari nol (data lama hilang)
```

Isi seed: kategori per modul, 6 produk (2 bertipe kursus, terhubung ke kursus lewat `course_id`),
3 kursus (15 pelajaran, 3 kuis, 15 soal; 1 kursus gratis), 5 tutorial (22 langkah dengan snippet kode),
10 artikel (2 featured), 5 thread dengan 20 balasan (thread 3 sengaja berantai 4 tingkat untuk demo batas tampilan), serta data contoh untuk akun demo.
Seed ditutup dengan pemeriksaan kewajaran data dan jumlah baris tiap tabel.

| Akun  | Email            | Kata sandi |
|-------|------------------|------------|
| Demo  | demo@dke.test    | `Demo12345` bila `DKE_DEMO_PASSWORD` kosong (**bawaan publik, hanya untuk lokal**) |
| Admin | admin@dke.test   | **tidak ada kata sandi bawaan**: dari `DKE_ADMIN_PASSWORD`, atau acak dan dicetak sekali di terminal |

**Akun admin.** Isi kata sandinya lewat variabel lingkungan sebelum seed pertama:

```bash
export DKE_ADMIN_PASSWORD='<kata sandi pilihan Anda>'      # PowerShell: $env:DKE_ADMIN_PASSWORD="<kata sandi pilihan Anda>"
python seed.py
```

Bila `DKE_ADMIN_PASSWORD` kosong, `seed.py` tetap berhasil dan membuat kata sandi **acak** untuk admin yang dicetak
**satu kali** di terminal, tepat saat akun dibuat. Catat saat itu juga; kata sandi tidak disimpan di mana pun dan tidak
akan ditampilkan lagi. Setelah masuk, ganti lewat Information System > Pengaturan Keamanan. Lupa kata sandi admin dari
seed acak: jalankan `python seed.py --reset` (menghapus semua data) dengan `DKE_ADMIN_PASSWORD` terisi.

**Akun demo (peringatan).** `Demo12345` tertulis di repositori ini, jadi siapa pun bisa mencobanya. Pakai **hanya untuk
lokal** di komputer sendiri; `seed.py` mencetak peringatan yang sama di terminal. Bila aplikasi dapat dijangkau jaringan
atau repositori dipublikasikan, isi `DKE_DEMO_PASSWORD` sebelum seed pertama.

`seed.py` aman dijalankan ulang: kata sandi akun yang sudah ada tidak pernah ditimpa, dan `DKE_ADMIN_PASSWORD` /
`DKE_DEMO_PASSWORD` hanya berlaku saat akunnya dibuat (seed ulang menyebutkannya bila variabel itu diabaikan).
Akun budi/citra/dewi/eko@dke.test hanya pelengkap konten forum dan tidak bisa dipakai login.
Uji: `python -m unittest tests.test_seed`.
