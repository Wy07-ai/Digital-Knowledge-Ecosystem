# Uji manual bilah navigasi bawah (mobile)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/ di Chrome/Edge. Uji sebagai Guest dan sebagai Member
(akun seed, lihat [`PANDUAN_FITUR_APLIKASI.md`](PANDUAN_FITUR_APLIKASI.md#database-dan-data-contoh)). Berkas terkait:
`app/templates/_components/bottom_nav.html`, `app/templates/base.html` (`{% block bottom_nav %}`), `app/static/js/switcher.js`
(pemicu `data-popover-open`), `app/static/css/custom.css` (bagian 16), dan ikon `grid` di `_components/_icons.html`.

Tes otomatis: `python -m unittest tests.test_bottom_nav -v`, lalu `python -m unittest discover -s tests` sebelum PR.
Tes otomatis memeriksa markup, tujuan menu, penanda aktif, dan teks aturan CSS; tampilan sebenarnya hanya bisa dinilai lewat tabel ini.

Cara menguji dua mode tampilan:
- **Layar sempit**: biarkan Mobile View mati, lalu atur lebar jendela atau DevTools Device Toolbar (di bawah 768 px).
- **Mobile View di desktop**: jendela 1280 px, klik tombol "Mobile" di bilah atas (`data-view='mobile'`). Lebar viewport tetap 1280 px,
  jadi `@media` tidak berlaku; karena itu bilah punya aturan ganda (media query dan `html[data-view='mobile']`).

Daftar periksa untuk setiap baris: tidak ada teks yang saling menimpa atau terpotong, tidak ada gulir horizontal, target sentuh
minimal 44 x 44 px, fokus terlihat, dan kontras terbaca di tema Terang dan Gelap.

## Tampil dan sembunyi

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 1 | 1280 px | Mobile View mati | Guest | Buka `/` | Tidak ada bilah di dasar layar; tidak ada ruang kosong tambahan di bawah halaman |
| 2 | 767 px | Mobile View mati | Guest | Buka `/` | Bilah muncul di dasar layar dengan empat menu: Beranda, Aplikasi, Cari, Akun (ikon dan label terlihat) |
| 3 | 768 px | Mobile View mati | Guest | Perlebar jendela sampai 768 px | Bilah hilang |
| 4 | 1280 px | Mobile View nyala | Guest dan Member | Klik "Mobile" di bilah atas | Bilah muncul selebar bingkai 430 px dan dipusatkan, bukan selebar jendela; klik "Mobile" lagi menyembunyikannya |
| 5 | 360 px | Layar sempit | Guest | Buka `/` lalu gulir ke dasar halaman | Konten terbawah (kartu aplikasi terakhir) terlihat utuh di atas bilah, tidak tertutup |
| 6 | 360 px | Layar sempit | Guest | Buka `/` | Bilah tidak ikut bergulir; ia tetap menempel di dasar layar |
| 7 | 360 px | Layar sempit | Guest | Cetak halaman (Ctrl+P, pratinjau cetak) | Bilah tidak ikut tercetak |

## Menu dan penanda aktif

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 8 | 360 px | Layar sempit | Guest | Buka `/` | Hanya Beranda yang aktif: garis tebal di atas ikon, ikon berisi lembut, teks lebih tebal (bukan hanya warna) |
| 9 | 360 px | Layar sempit | Guest | Ketuk Cari | Membuka `/cari`; Cari aktif, Beranda tidak |
| 10 | 360 px | Layar sempit | Guest | Ketuk Beranda | Membuka `/`; Beranda aktif |
| 11 | 360 px | Layar sempit | Guest | Ketuk Akun | Membuka halaman masuk (`/infosys/login`); Akun aktif |
| 12 | 360 px | Layar sempit | Member | Ketuk Akun | Membuka Information System (`/infosys/`); Akun aktif, Aplikasi tidak aktif |
| 13 | 360 px | Layar sempit | Member | Buka `/forum/`, `/ecommerce/`, `/elearning/`, `/etutorial/`, `/portal/` | Di semua halaman itu, Aplikasi yang aktif (satu menu saja) |
| 14 | 360 px | Layar sempit | Guest | Buka `/alamat-yang-tidak-ada` | Halaman galat tampil wajar: kartu galat tidak tertutup bilah, empat menu ada, tidak ada menu aktif |

## Menu Aplikasi (App Switcher)

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 15 | 360 px | Layar sempit | Guest | Ketuk Aplikasi | Panel App Switcher yang sama dengan tombol 9 titik di bilah atas terbuka (enam aplikasi, tautan "Semua aplikasi (Beranda)"); `aria-expanded` pada Aplikasi menjadi `true` dan tombol 9 titik juga `true` |
| 16 | 360 px | Layar sempit | Guest | Ketuk Aplikasi lagi | Panel menutup (tidak membuka ulang); `aria-expanded` kembali `false` |
| 17 | 360 px | Layar sempit | Guest | Buka panel, ketuk di luar panel | Panel menutup |
| 18 | 360 px | Layar sempit | Guest | Buka panel, ketuk salah satu aplikasi | Membuka aplikasi itu; di halaman baru, Aplikasi aktif |
| 19 | 360 px | Layar sempit | Guest | Tab sampai Aplikasi, tekan Enter | Panel terbuka dan fokus pindah ke item aktif atau item pertama; panah, Home, dan End berpindah antar item |
| 20 | 360 px | Layar sempit | Guest | Dengan panel terbuka lewat Aplikasi, tekan Esc | Panel menutup dan fokus kembali ke tombol Aplikasi di bilah bawah (bukan ke bilah atas) |
| 21 | 360 px | Layar sempit | Guest | Buka panel lewat tombol 9 titik di bilah atas, lalu tekan Esc | Fokus kembali ke tombol 9 titik, seperti sebelumnya |
| 22 | 360 px | Layar sempit | Guest | Buka panel, lalu ketuk menu tema di bilah atas | Panel App Switcher menutup; hanya satu panel terbuka |

## Papan ketik, fokus, dan target sentuh

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 23 | 360 px | Layar sempit | Guest | Tekan Tab berulang sampai ke bilah bawah | Urutan fokus: Beranda, Aplikasi, Cari, Akun; cincin fokus terlihat jelas di Terang dan Gelap dan tidak terpotong |
| 24 | 320 px | Layar sempit | Guest | DevTools > pilih tiap item bilah | Tiap item minimal 44 x 44 px (tingginya 56 px); label tidak terpotong dan tidak menimpa item lain |
| 25 | 360 px | Layar sempit | Guest | DevTools > Accessibility, pilih bilah | Landmark "navigation" bernama "Navigasi bawah"; menu aktif memiliki `current = page` |

## Konten, toast, dan elemen di dasar halaman

Di proyek ini tidak ada elemen selain bilah yang `position: fixed` atau `sticky` di dasar layar; Sebelumnya/Berikutnya E-Tutorial,
navigasi kuis, form balas Forum, dan ringkasan keranjang berada di alur halaman. Ruang di dasar halaman diberikan `padding-bottom`
pada `body` (setinggi bilah ditambah area aman), dan `scroll-padding-bottom` pada `html` mencegah fokus dan `scrollIntoView()` berhenti di balik bilah.

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 26 | 360 px | Layar sempit | Guest | Buka tutorial E-Tutorial, gulir ke dasar | Tombol Sebelumnya dan Berikutnya terlihat utuh di atas bilah dan bisa diketuk |
| 27 | 360 px | Layar sempit | Member | Buka kuis E-Learning, gulir ke dasar | Navigasi soal dan tombol Selanjutnya/Kirim terlihat utuh; berpindah soal tidak membuat soal berhenti di balik bilah |
| 28 | 360 px | Layar sempit | Member | Buka sebuah topik Forum, ketuk Balas | Form balas meluncur ke tengah layar; kolom isian dan tombol Kirim tidak tertutup bilah; keyboard layar tidak menimpa tombol |
| 29 | 360 px | Layar sempit | Member | Isi keranjang E-Commerce, buka `/ecommerce/keranjang`, gulir ke dasar | Ringkasan dan tombol Bayar terlihat utuh di atas bilah |
| 30 | 360 px | Layar sempit | Member | Tambahkan produk ke keranjang | Toast muncul tepat di atas bilah (bukan di balik bilah, bukan di bilah atas) dan hilang otomatis |
| 31 | 1280 px | Mobile View nyala | Member | Ulangi baris 26-30 | Hasil sama; toast terpusat di atas bilah dalam bingkai 430 px |
| 32 | 360 px | Layar sempit | Member | Buka dialog konfirmasi kuis ("Kirim jawaban") | Dialog dan latar gelapnya menutupi bilah; bilah tidak tampak di atas dialog |

## Tema dan Mobile View

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 33 | 360 px | Layar sempit | Guest | Ganti tema Terang lalu Gelap | Latar bilah, garis atas, ikon, dan label mengikuti tema; teks label minimal 4,5:1 di pemeriksa kontras DevTools |
| 34 | 1280 px | Mobile View nyala | Guest | Ganti tema Terang lalu Gelap | Sama seperti baris 33, di dalam bingkai 430 px |
| 35 | 360 px | Layar sempit | Guest | Nyalakan "Reduce motion" di OS atau DevTools > Rendering | Tidak ada animasi garis atas dan umpan tekan |
| 36 | Ponsel dengan takik atau bar gestur | Layar sempit | Guest | Buka `/` di ponsel asli (iOS Safari atau Chrome Android) | Bilah tidak tertutup bar gestur. Catatan: `padding-bottom: env(safe-area-inset-bottom)` baru berpengaruh bila tag viewport memakai `viewport-fit=cover`; tag saat ini belum, jadi peramban sendiri yang menjaga area aman |

## Menyembunyikan bilah di halaman tertentu

Kosongkan blok di templat halaman itu: `{% block bottom_nav %}{% endblock %}`. Bilah, padding dasar halaman, dan pergeseran toast ikut hilang
(aturan CSS memakai `body:has(> .bottom-nav)`), jadi tidak ada ruang kosong yang tertinggal. Periksa di satu halaman uji setelah mengosongkan blok.
