# Uji manual E-Learning bagian 1 (UC-EL-01..04, 07)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/elearning/ .
Akun: `demo@dke.test` / `Demo12345` (sudah terdaftar di kelas gratis "Prinsip Desain Antarmuka", 2 dari 5 materi).

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Sebagai Guest buka `/elearning/` lalu klik filter Pemula / Menengah / Lanjut | Kartu tersaring; tiap filter menampilkan jumlah; level kosong menampilkan empty state |
| 2 | Ubah URL menjadi `?level=ngawur` | Catatan "Filter level tidak dikenal", semua kelas tampil |
| 3 | Guest buka detail kelas, klik "Masuk untuk mengikuti kelas" | Diarahkan ke login, setelah masuk kembali ke detail kelas |
| 4 | Guest buka langsung `/elearning/kelas/1/materi/1` | Diarahkan ke login (`?next=`) |
| 5 | Masuk sebagai demo, buka detail kelas berbayar | Tombol "Beli di E-Commerce"; tidak ada tombol enroll gratis |
| 6 | Buka `/elearning/kelas/<id kelas yang belum diikuti>/materi/1` | Kembali ke detail kelas + toast merah "Anda belum terdaftar di kelas ini..." |
| 7 | Daftar Kelas: kartu kelas yang sudah diikuti | Menampilkan progress bar dan tombol Lanjutkan belajar |
| 8 | Buka Kelas Saya | Kartu kelas + progres, kartu "Target belajar hari ini" |
| 9 | Ruang Belajar materi 3: klik Tandai Selesai | Tanpa reload: tombol jadi "Selesai · Batalkan", bab 3 tercentang, progress bar naik 40% → 60% dalam 300 ms, toast hijau |
| 10 | Klik tombol sekali lagi | Tanda selesai dibatalkan, progres kembali 40%, toast biru |
| 11 | Klik Sebelumnya / Berikutnya, lalu materi pertama dan terakhir | Tombol di ujung menjadi nonaktif ("Ini materi terakhir") |
| 12 | Muat ulang halaman setelah menandai selesai | Progres dan centang bab bertahan (dibaca dari database) |
| 13 | Beli kursus Python lewat E-Commerce (checkout simulasi), klik "Mulai belajar di Kelas Saya" | Kursus langsung ada di Kelas Saya; materi 2 berupa video (embed) |
| 14 | Pengaturan: pilih 1,5× dan target 45 menit, Simpan | Toast hijau; data bertahan; materi video memakai kecepatan 1,5× (upaya terbaik untuk YouTube/Vimeo) |
| 15 | Pengaturan: target 0 atau "abc" | Pesan inline, data tidak tersimpan |
| 16 | Mobile View / layar sempit | Satu kolom; daftar bab menjadi tombol "Daftar bab" yang bisa dibuka |
| 17 | Mode gelap | Semua kartu, sidebar, dan progress bar tetap terbaca |
