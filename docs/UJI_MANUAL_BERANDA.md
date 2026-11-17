# Uji manual hero Beranda (Mobile View, layar sempit, dan carousel)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/ di Chrome/Edge. Berkas terkait: `app/static/css/custom.css` (bagian 6 dan 8b), `app/templates/main/index.html`. Berkas ini dipakai ulang oleh Issue B dan C: tambahkan baris baru di bawah, jangan ganti nomor yang ada.

Tes otomatis: `python -m unittest tests.test_launcher_nav -v` (kelas `HeroMobileCssTests`), `python -m unittest tests.test_home_hero -v` (carousel), dan `python -m unittest discover -s tests`.

Baris 1-14 di bawah ditulis untuk hero lama. Sejak hero menjadi carousel (Issue C), "hero" berarti slide carousel: judul slide mengikuti aturan judul kecil, tombol slide (`.hero-slide-cta`) menggantikan tombol "Mulai belajar", dan ilustrasi besar per slide (`.hero-slide-art`) disembunyikan di Mobile View dan layar sempit. Tombol "Lanjutkan" kini ada di strip di bawah carousel (`.home-strip-cta`, atribut `data-resume` tetap).

Cara menguji dua mode tampilan:
- **Layar sempit**: biarkan Mobile View mati, lalu atur lebar jendela atau DevTools Device Toolbar ke lebar yang diminta.
- **Mobile View di desktop**: jendela 1280 px, klik tombol "Mobile" di bilah atas (`data-view='mobile'`). Lebar viewport tetap 1280 px; ini kasus yang sebelumnya rusak.

Daftar periksa untuk setiap baris: judul, paragraf, dan tombol tidak saling menimpa atau terpotong; ilustrasi "DKE" (`.home-orbit`) tidak tampil; tombol setinggi minimal 44 px; tidak ada gulir horizontal.

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 1 | 360 px | Layar sempit (Mobile View mati) | Guest | Buka `/` | Hero satu kolom tanpa kotak DKE; judul sekitar 1,6 rem; tinggi hero tidak lebih dari sekitar 320 px; tombol "Mulai belajar" selebar penuh |
| 2 | 360 px | Layar sempit | Member dengan aktivitas terakhir | Buka `/` | Tombol "Lanjutkan" utuh: label panjang terpotong dengan elipsis, jenjang tengah tersembunyi |
| 3 | 390 px | Layar sempit | Guest | Buka `/` | Sama seperti baris 1, tanpa teks terpotong |
| 4 | 390 px | Layar sempit | Member | Buka `/` | Sama seperti baris 2 |
| 5 | 430 px | Layar sempit | Guest | Buka `/` | Sama seperti baris 1 |
| 6 | 430 px | Layar sempit | Member | Buka `/` | Sama seperti baris 2 |
| 7 | 700 px | Layar sempit | Guest | Buka `/` (rentang 640-767 px) | Orbit ikut tersembunyi; tata letak sama dengan ponsel |
| 8 | 1280 px | Mobile View nyala | Guest | Klik "Mobile" | Bingkai 430 px; hero tanpa orbit, judul tidak menimpa apa pun; tinggi hero tidak lebih dari sekitar 320 px |
| 9 | 1280 px | Mobile View nyala | Member | Klik "Mobile", lihat tombol "Lanjutkan" | Label panjang terpotong dengan elipsis; jenjang tengah tersembunyi (`dke-hide-mobile`) |
| 10 | 360, 390, 430 px | Mobile View nyala (DevTools) | Guest dan Member | Ulangi baris 8-9 pada tiap lebar | Hasil sama; tidak ada pemotongan |
| 11 | Semua lebar di atas | Layar sempit dan Mobile View | Guest | Ganti tema Terang lalu Gelap | Teks hero putih di atas latar biru tua terbaca di kedua tema; tombol putih tetap berkontras |
| 12 | Semua lebar di atas | Layar sempit dan Mobile View | Guest | Aktifkan "Reduce motion" di OS, muat ulang | Hero tampil sama; tidak ada animasi baru |
| 13 | 1024 px dan 1280 px | Mobile View mati | Guest dan Member | Buka `/` | Tampilan desktop tidak berubah: dua kolom, kotak DKE tampil, judul besar |
| 14 | 1280 px | Mobile View nyala lalu mati | Guest | Klik "Mobile" dua kali | Hero kembali ke tata letak desktop penuh |

## Carousel hero Beranda (Issue C)

Berkas terkait: `app/templates/_components/hero_carousel.html`, `app/static/js/carousel.js`, `app/static/css/custom.css` (bagian 8c), data slide `HERO_SLIDES` di `app/main/launcher.py`. Jeda geser otomatis dibaca dari `data-interval="10000"` (10 detik). Untuk menguji tanpa menunggu 10 detik, ubah `HERO_INTERVAL_MS` sementara (jangan di-commit).

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/ di Chrome/Edge. Uji Guest dan Member (untuk Member, buka satu halaman aplikasi dulu agar tombol "Lanjutkan" muncul). Lakukan pemeriksaan kontras di Terang dan Gelap (tombol tema di bilah atas).

| # | Skenario | Langkah | Hasil yang diharapkan |
|---|----------|---------|-----------------------|
| 15 | Isi dan urutan slide | Buka `/`, biarkan carousel bergeser lima kali | Urutan E-Learning, E-Commerce, E-Tutorial, Portal, Forum, lalu kembali ke E-Learning. Tidak ada slide atau tautan Information System. Tiap tombol slide membuka `/elearning/`, `/ecommerce/`, `/etutorial/`, `/portal/`, `/forum/` |
| 16 | Titik indikator | Lihat bagian bawah carousel; klik titik ke-4 | Ada 5 titik di bawah hero; titik aktif berbentuk pil lebih panjang (bukan hanya beda warna); klik titik membuka slide yang sesuai. Pembaca layar menyebut "Slide 4: Portal" dan menandai titik aktif sebagai saat ini |
| 17 | Geser otomatis | Buka `/`, jangan sentuh apa pun, hitung waktunya | Slide berganti tiap 10 detik dengan transisi pudar-geser sekitar 0,4 detik, tanpa lonjakan tinggi hero |
| 18 | Hover | Arahkan kursor ke carousel lebih dari 10 detik | Slide tidak berganti selama kursor di atas carousel. Setelah kursor keluar, geser berlanjut (sekitar 10 detik kemudian) |
| 19 | Fokus keyboard | Tekan Tab sampai fokus masuk ke tombol slide atau kontrol | Slide berhenti berganti selama fokus di dalam carousel. Pindah Tab antar kontrol di dalam carousel tidak melanjutkan geser. Setelah Tab keluar dari carousel, geser berlanjut |
| 20 | Fokus hanya pada slide aktif | Tekan Tab berulang dari awal halaman | Fokus tidak pernah masuk ke tombol slide yang tidak tampil. Urutan: tombol slide aktif, titik aktif, Jeda, Sebelumnya, Berikutnya. Cincin fokus putih terlihat jelas di semua kontrol |
| 21 | Jeda dan Putar | Klik tombol Jeda, pindahkan kursor masuk lalu keluar, tunggu 30 detik; klik Putar | Selama Jeda, slide tidak berganti, juga setelah kursor keluar. Ikon dan label tombol berubah ("Putar geser otomatis"). Setelah Putar dan kursor di luar carousel, geser berlanjut |
| 22 | Keyboard | Fokus pada tombol Sebelumnya atau Berikutnya, tekan ArrowRight, ArrowLeft, End, Home. Fokus pada sebuah titik, tekan ArrowRight | Slide berpindah sesuai tombol; pada titik, fokus ikut pindah ke titik yang baru. Ujung carousel berputar ke ujung lainnya |
| 23 | Tab tersembunyi | Pindah ke tab lain selama 30 detik, lalu kembali | Slide tidak maju selama tab tersembunyi. Setelah kembali, geser berlanjut dengan jeda penuh |
| 24 | Reduced motion (muat) | Aktifkan "Reduce motion" di OS (atau DevTools > Rendering > Emulate prefers-reduced-motion), muat ulang | Tidak ada geser otomatis (tunggu minimal 30 detik), tidak ada transisi, tombol Jeda disembunyikan. Tombol Sebelumnya/Berikutnya dan titik tetap berfungsi dan berpindah seketika |
| 25 | Reduced motion (berubah saat dibuka) | Buka `/` dengan reduced motion mati, lalu nyalakan lewat DevTools tanpa memuat ulang; setelah itu matikan lagi | Saat dinyalakan geser berhenti dan tombol Jeda hilang; saat dimatikan geser berjalan lagi tanpa memuat ulang |
| 26 | Geser sentuh | Mobile View di DevTools (perangkat sentuh), usap ke kiri lalu kanan | Usapan lebih dari sekitar 40 px berpindah slide; usapan pendek atau dominan vertikal tidak berpindah dan halaman tetap bisa digulir |
| 27 | Pembaca layar | Nyalakan pembaca layar (NVDA/VoiceOver) | Wilayah dikenali sebagai "carousel" berlabel "Sorotan aplikasi"; tiap slide "slide, 1 dari 5". Geser otomatis tidak diumumkan; pindah manual (tombol, titik, panah) mengumumkan slide baru |
| 28 | Tanpa JavaScript | Matikan JavaScript di DevTools (Command Menu > Disable JavaScript), muat ulang | Hanya slide pertama (E-Learning) tampil, tinggi hero stabil, tombol "Jelajahi kelas" berfungsi sebagai tautan. Titik, Jeda, Sebelumnya, dan Berikutnya tidak tampil. Strip sapaan tetap ada |
| 29 | Kontras Terang dan Gelap | Untuk tiap dari 5 slide, di tema Terang lalu Gelap, ukur teks judul, kalimat, label aplikasi, dan tombol (DevTools > Inspect > pemeriksa kontras) | Semua teks minimal 4,5:1. Latar slide tetap navy gelap di kedua tema; warna aksen (amber, teal, dll.) hanya cahaya dekoratif di belakang ikon. Tes `CssTests.test_kontras_teks_putih_di_atas_dasar_dan_cahaya_aksen_terburuk` menghitung kasus terburuknya |
| 30 | Ukuran kontrol | Periksa tombol Jeda, Sebelumnya, Berikutnya, tiap titik, dan tombol slide di DevTools | Setiap kontrol berukuran minimal 44 x 44 px (titik: bulatan kecil, area sentuh 44 px) |
| 31 | Mobile View dan 360 px | Ulangi baris 1, 2, 8, 9 pada 360 px dan pada Mobile View (jendela 1280 px) | Tanpa ilustrasi besar; judul slide sekitar 1,6 rem; tombol slide selebar penuh; kontrol tidak keluar bingkai (titik dan tombol boleh turun ke baris kedua); tidak ada gulir horizontal |
| 32 | Sapaan dan Lanjutkan (Member) | Login sebagai Member yang sudah membuka satu halaman aplikasi, buka `/` | Strip tipis tepat di bawah carousel berisi "Halo, <nama>." dan tombol "Lanjutkan: ..." yang membuka halaman terakhir. Member tanpa riwayat melihat tombol "Jelajahi kelas". Guest melihat judul dan kalimat umum tanpa tombol Lanjutkan |
| 33 | Tema | Ganti Terang ke Gelap saat carousel berjalan | Slide tetap terbaca, kontrol tetap terlihat, strip mengikuti tema, tidak ada kedip atau slide yang macet |

## Kartu aplikasi Beranda (kartu fitur)

Berkas terkait: `app/templates/_components/module_card.html`, `app/templates/main/index.html`, `app/static/css/custom.css` (bagian 6, 8, dan 8d). Kartu dipakai juga di halaman uji `/dev/ui-test` (bagian 5).

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/. Uji Guest dan Member (login `demo@dke.test`; kata sandi bawaan ada di `seed.py`). Untuk mengganti tema pakai tombol tema di bilah atas. Tes otomatis: `python -m unittest tests.test_launcher_nav -v` (kelas `BerandaGuestTests`, `LauncherGridCssTests`, `KartuAplikasiTemplatTests`).

Susunan kartu yang diharapkan di semua baris: (1) area visual berlatar gradien dan pola titik lembut berwarna aksen, ikon besar di tengah; (2) judul aplikasi yang tegas; (3) satu baris metrik atau ajakan. Tidak ada kalimat deskripsi yang terlihat.

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 34 | 1280 px | Mobile View mati | Guest dan Member | Buka `/` | Grid 3 kolom x 2 baris; kartu berukuran sama; ikon sekitar 52 px; judul satu baris; metrik atau ajakan satu baris; tidak ada kalimat deskripsi |
| 35 | 768 px | Layar sempit mati (lebar tablet) | Guest | Buka `/` | 2 kolom x 3 baris; ukuran ikon dan judul seperti desktop |
| 36 | 360 px | Layar sempit | Guest | Buka `/` | 2 kolom x 3 baris; tiap kartu sekitar 158 px; ikon sekitar 38 px; "Information System" memakai 2 baris dan tidak terpotong; judul lain satu baris; ajakan ("Masuk ke akun", "Lihat produk", dst.) utuh; tidak ada gulir horizontal |
| 37 | 360 px | Layar sempit | Member dengan data | Buka `/` | Metrik pendek utuh ("2 tersimpan", "2 balasan baru"). Metrik panjang (judul kelas, "Keranjang masih kosong", "artikel baru minggu ini") tetap satu baris dan dipotong dengan elipsis, tidak membungkus dan tidak menimpa kartu lain. Progress bar E-Learning dan persennya tampil utuh |
| 38 | 390 px dan 430 px | Layar sempit | Guest dan Member | Ulangi baris 36-37 | 2 kolom x 3 baris; tidak ada teks menimpa atau keluar kartu; elipsis hanya pada metrik yang kepanjangan |
| 39 | 1280 px | Mobile View nyala | Guest dan Member | Klik "Mobile" di bilah atas | Bingkai 430 px; 2 kolom x 3 baris; ukuran seluruh isi kartu seperti ponsel (ikon sekitar 38 px, padding kecil); klik "Mobile" lagi mengembalikan 3 kolom x 2 baris |
| 40 | Semua lebar di atas | Layar sempit dan Mobile View | Guest dan Member | Ganti tema Terang lalu Gelap | Gradien dan ikon tetap berkontras; di Gelap latar menjadi tinta gelap beraksen dan ikon menjadi lebih terang; judul dan metrik terbaca (minimal 4,5:1 di pemeriksa kontras DevTools). Kontras ikon terhadap gradien dihitung oleh `test_ikon_berkontras_di_atas_3_banding_1_pada_terang_dan_gelap` |
| 41 | 1280 px | Mobile View mati | Guest | Arahkan kursor ke tiap kartu | Tooltip menampilkan deskripsi aplikasi dari atribut `title`; deskripsi tidak pernah tampil sebagai teks di kartu |
| 42 | 1280 px | Mobile View mati | Guest | DevTools > Elements > Accessibility, pilih salah satu kartu | Role "link"; Name = nama aplikasi + metrik (tanpa deskripsi); Description = deskripsi aplikasi; tautan tidak memiliki `aria-label` |
| 43 | - | - | Guest dan Member | Nyalakan pembaca layar (NVDA atau VoiceOver) dan pindah ke kartu | Dibaca nama aplikasi dan metrik, lalu deskripsi satu kali (tidak berulang). Metrik tidak hilang dari bacaan; ikon dan area visual tidak dibaca |
| 44 | 1280 px dan 360 px | Mobile View mati | Guest | Tekan Tab dari awal halaman sampai kartu | Fokus masuk ke tiap kartu berurutan (6 tautan, satu per kartu); cincin fokus tebal (3 px) terlihat jelas di Terang dan Gelap; Enter membuka aplikasi |
| 45 | 360 px | Layar sempit (mode sentuh DevTools) | Guest | Periksa tiap kartu di DevTools | Seluruh kartu adalah satu tautan; tinggi dan lebar kartu jauh di atas 44 px dan seluruh areanya bisa diketuk |
| 46 | 1280 px dan 360 px | Mobile View mati | Member baru tanpa data | Buka `/` | Teks metrik kosong tampil redup (abu-abu) dan tanpa angka 0; baris metrik tetap sejajar antar kartu |
| 47 | 1280 px dan 360 px | Mobile View mati | Guest | Buka `/` | Ajakan tiap kartu tampil sebagai teks berwarna primer tebal dengan tanda "›" (bukan data) |
| 48 | 1280 px dan 360 px | Mobile View mati | Member yang mengikuti kelas dengan progres | Buka `/` | Kartu E-Learning memuat nama kelas, progress bar berwarna aksen, dan persen (mis. 40%); bar sejajar di dasar kartu |
| 49 | 1280 px | Mobile View mati | Member | Hentikan server, ubah nama satu tabel di salinan database (mis. `sqlite3 instance/dke.db "ALTER TABLE articles RENAME TO articles_x;"`), jalankan lagi, buka `/`. Pulihkan dengan `python seed.py --reset` | Kartu Portal menampilkan "Ringkasan belum tersedia" redup; lima kartu lain dan grid tetap utuh 3 x 2 |
| 50 | 1280 px | Mobile View mati | Guest | Kursor di atas sebuah kartu (reduced motion mati) | Kartu naik sekitar 4 px dengan bayangan beraksen; animasi masuk bertahap saat halaman dimuat tidak berubah |
| 51 | 1280 px dan 360 px | Layar sempit dan desktop | Guest | Aktifkan "Reduce motion" di OS (atau DevTools > Rendering > Emulate prefers-reduced-motion), muat ulang, arahkan kursor dan tekan kartu | Tidak ada animasi masuk; kartu tidak naik, tidak ada glow, dan tidak mengecil saat ditekan |
| 52 | 360 px | Mode sentuh DevTools | Guest | Ketuk sebuah kartu lalu kembali | Tidak ada kartu yang "menempel" naik atau bergaris bayangan setelah disentuh |
| 53 | 1280 px dan 360 px | Mobile View mati dan nyala | Guest | Buka `/dev/ui-test`, lihat bagian 5 | Grid kartu sama dengan Beranda: 3 kolom di desktop, 2 kolom di mobile dan Mobile View |
| 54 | 360 px dan Mobile View | Layar sempit dan Mobile View | Guest | Buka `/ecommerce/` dan `/infosys/` | Grid produk dan kartu di sana tetap satu kolom (tidak ikut berubah menjadi 2 kolom) |
