# Uji manual E-Tutorial

Persiapan: `python seed.py --reset` lalu `python run.py`, buka http://127.0.0.1:5000/etutorial/.
Akun demo: `demo@dke.test` / `Demo12345`. Tes otomatis: `python -m unittest tests.test_etutorial`.

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Buka `/etutorial/` sebagai Guest | 5 kartu tutorial, tiap kartu menampilkan kategori, tingkat, "Estimasi N menit", dan jumlah langkah. Aksen violet. |
| 2 | Klik kategori "Python", lalu tingkat "Mudah" | Daftar menyempit (AND). Angka di tombol menyesuaikan filter lain. "Atur ulang filter" muncul dan mengembalikan semua. |
| 3 | Ketik `?kategori=ngawur` di URL | Semua tutorial tampil dengan pesan "Sebagian filter tidak dikenal". |
| 4 | Buka tutorial "Membuat Aplikasi Flask Pertama" | Step 1 dari 5, bar posisi, titik langkah 1-5, tombol Sebelumnya nonaktif, Berikutnya aktif. |
| 5 | Klik Berikutnya sampai Step 5 | URL berubah per langkah, langkah yang dilewati bercentang, Step 5 menampilkan "Selesai" dan kartu "Tutorial selesai". Panah kiri/kanan keyboard juga berpindah langkah. |
| 6 | Di langkah ber-kode, klik Salin | Toast hijau "Kode disalin", tombol berubah "Tersalin" 2 detik. Tempel ke editor: kode persis sama, termasuk karakter `<`, `>`, `{{ }}`. |
| 7 | Buka lewat IP LAN dari ponsel (http://192.168.x.x:5000) lalu Salin | Tetap berhasil (jalur cadangan tanpa Clipboard API). |
| 8 | Sebagai Guest klik "Masuk untuk menyimpan" | Diarahkan ke login; setelah login kembali ke tutorial yang sama. |
| 9 | Login, klik "Simpan tutorial" | Toast "Tutorial disimpan ke Tersimpan", tombol berubah "Hapus dari Tersimpan" dan Anda tetap di langkah yang sama. |
| 10 | Buka tab Tersimpan | Tutorial tadi muncul (terbaru di atas). Tombol Hapus mengeluarkannya; bila kosong tampil empty state. |
| 11 | Tab Pengaturan, pilih Besar, Simpan | Toast sukses; `module_settings` berisi `etutorial / font_size / lg`. Buka tutorial: teks 20 px. Pilihan bertahan setelah logout-login. |
| 12 | Pengaturan sebagai Guest | Ada catatan "hanya disimpan di peramban ini"; pilihan tersimpan lewat cookie dan tidak menulis ke database. |
| 13 | Font Besar di ponsel (lebar 320-430 px) atau tombol Mobile View | Tidak ada gulir samping; tombol Sebelumnya/Berikutnya ditumpuk selebar layar (tinggi 56 px); kode dibungkus baris; Salin dan titik langkah >= 48 px. |
| 14 | Sisipkan baris `tutorials` dengan judul `<b>x</b>` dan kode `<script>alert(1)</script>` lewat SQLite | Tampil sebagai teks literal, tidak ada pop-up, tidak ada cetak tebal. |
