# Uji manual Portal

Persiapan: `python seed.py --reset` lalu `python run.py`, buka http://127.0.0.1:5000/portal/.
Akun demo: `demo@dke.test` / `Demo12345` (sudah punya preferensi `teknologi,pendidikan`). Tes otomatis: `python -m unittest tests.test_portal`.

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Buka `/portal/` sebagai Guest | Satu artikel featured besar di atas (lencana "Featured", gambar, judul, kutipan, penulis, tanggal, "N menit baca"), kartu artikel di bawahnya. Aksen rose. |
| 2 | Lihat deretan chip | "Semua (10)" dan 5 kategori dengan jumlahnya; "Kesehatan Digital (0)". Chip aktif berwarna rose dan bertanda `aria-current`. |
| 3 | Klik chip "Karier" | Daftar menyempit ke artikel Karier. Tautan bisa dibagikan (`?kategori=karier`). |
| 4 | Klik chip "Kesehatan Digital" | Empty state "Belum ada artikel di kategori Kesehatan Digital" dengan tombol "Lihat semua artikel". |
| 5 | Ketik `?kategori=ngawur` | Semua artikel tampil dengan pesan "Kategori itu tidak dikenal". |
| 6 | Di beranda, klik "Berikutnya" (atau `?halaman=2`) | Halaman 2 berisi sisa kartu (3), artikel featured tidak tampil lagi, "Menampilkan 7-9 dari 9 artikel lainnya". `?halaman=999` menampilkan halaman terakhir. |
| 7 | Klik sebuah kartu (di mana saja pada kartu) | Halaman detail: judul, kategori, penulis, tanggal, waktu baca, "N kali dibaca", isi artikel, dan bagian "Artikel terkait di <kategori>" (maks. 3, sekategori, tanpa artikel ini). |
| 8 | Catat angka views, muat ulang halaman detail | Angka bertambah 1 pada kunjungan pertama; muat ulang tidak menambah lagi (satu kali per sesi). Buka jendela privat: bertambah lagi. |
| 9 | Buka artikel yang sendirian di kategorinya (mis. ubah kategori lewat SQLite) | Muncul "Belum ada artikel lain di kategori ini." |
| 10 | Buka DevTools > Network (Throttling: Slow 3G), muat beranda | Gambar kartu di bawah layar baru diunduh saat digulir mendekat (lazy loading). Tab Elements: semua `<img>` punya `loading="lazy"` dan `alt` berisi judul. |
| 11 | Sebagai Guest buka `/portal/pengaturan` | Diarahkan ke login; setelah login kembali ke Pengaturan Portal. |
| 12 | Login sebagai demo, buka Pengaturan | "Teknologi" dan "Pendidikan" tercentang. Beranda: chip keduanya di depan dengan tanda bintang dan "(favorit)", catatan "Urutan disesuaikan dengan kategori favorit Anda". |
| 13 | Centang hanya "Karier", Simpan | Toast sukses; `module_settings` berisi `portal / preferred_categories / karier`. Beranda: artikel Karier tampil paling awal di deretan kartu (seed tidak punya artikel Karier yang featured, jadi artikel besar di atas tetap yang featured terbaru). Jumlah artikel tetap sama (tidak ada yang hilang). |
| 14 | Klik "Hapus preferensi" | Baris `module_settings` dihapus; beranda kembali diurutkan terbaru; catatan "Urutan disesuaikan" hilang. |
| 15 | Login sebagai akun lain atau buka sebagai Guest | Urutan beranda tidak terpengaruh preferensi akun demo. |
| 16 | Aktifkan Dark Mode, lalu tombol Mobile View (atau lebar 360 px) | Teks tetap terbaca (kontras), grid kartu menjadi 1 kolom, tidak ada gulir samping, nomor halaman diganti "1/2". |
| 17 | Sisipkan artikel dengan judul `<b>x</b>`, isi `<script>alert(1)</script>`, dan `cover_url` `javascript:alert(1)` lewat SQLite | Tampil sebagai teks literal, tidak ada pop-up; gambar memakai sampul bawaan. |
| 18 | Log Aktivitas (Information System) setelah menyimpan preferensi | Ada baris "Ubah preferensi Portal". |
