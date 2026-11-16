# Uji manual hero Beranda (Mobile View dan layar sempit)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/ di Chrome/Edge. Berkas terkait: `app/static/css/custom.css` (bagian 6 dan 8b), `app/templates/main/index.html`. Berkas ini dipakai ulang oleh Issue B dan C: tambahkan baris baru di bawah, jangan ganti nomor yang ada.

Tes otomatis: `python -m unittest tests.test_launcher_nav -v` (kelas `HeroMobileCssTests`) dan `python -m unittest discover -s tests`.

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
