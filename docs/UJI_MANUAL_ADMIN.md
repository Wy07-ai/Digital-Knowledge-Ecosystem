# Uji manual Admin

Persiapan: `python seed.py --reset` lalu `python run.py` (kunci sesi: lihat README, bagian Menjalankan).
Akun admin: `admin@dke.test` (kata sandi dari `DKE_ADMIN_PASSWORD` saat seed, atau yang dicetak `seed.py`). Akun member: `demo@dke.test` / `Demo12345`.
Akun komunitas (budi/citra/dewi/eko) dibuat seed tanpa kata sandi, jadi aman dipakai untuk uji nonaktifkan.
Tes otomatis: `python -m unittest tests.test_admin`.

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Sebagai Guest, buka `/infosys/admin` | Diarahkan ke halaman login. |
| 2 | Login sebagai demo, buka Control Panel | Sidebar **tidak** memiliki tab Admin. |
| 3 | Sebagai demo, buka `/infosys/admin` dan `/infosys/admin/thread/1/hapus` | Halaman **403** "Akses ditolak" (tidak ada data yang tampil). |
| 4 | Sebagai demo, kirim paksa POST ke `/infosys/admin/thread/1/hapus` (DevTools/curl, token CSRF sah) | **403**; thread tetap ada. |
| 5 | Login sebagai admin | Sidebar memiliki tab **Admin** (ikon gembok). |
| 6 | Buka tab Admin > Thread | Daftar thread (10 per halaman) dengan penulis, jumlah balasan, tombol Hapus. Tab Balasan dan Akun juga tampil. |
| 7 | Klik Hapus pada sebuah thread | Halaman konfirmasi: judul thread, peringatan "N balasan ikut terhapus". Belum ada yang terhapus. Klik **Batal**: kembali ke daftar, data utuh. |
| 8 | Ulangi, klik **Ya, hapus thread** | Toast "Thread dihapus."; thread dan balasannya hilang dari daftar dan dari Forum. |
| 9 | Admin > Log Aktivitas | Baris baru "Admin: hapus thread" dengan judul, penulis, dan jumlah balasan pada kolom Detail. |
| 10 | Tab Balasan > Hapus pada balasan yang punya anak/solusi | Konfirmasi menyebut "naik satu tingkat" dan/atau "thread kembali berstatus belum terjawab". Setelah dihapus, balasan anak masih tampil di Forum; label Solved hilang bila yang dihapus adalah solusi. Log: "Admin: hapus balasan". |
| 11 | Tab Akun: tombol **Nonaktifkan** pada member (bukan admin) > konfirmasi | Toast sukses, status "Nonaktif" (merah). Log: "Admin: nonaktifkan akun". |
| 12 | Akun admin sendiri dan admin lain | Tidak ada tombol Nonaktifkan. Buka URL `/infosys/admin/akun/<id-admin>/nonaktifkan` langsung: ditolak dengan pesan, status tidak berubah. |
| 13 | Dengan akun member yang sedang login di jendela lain, nonaktifkan akun itu dari admin, lalu muat ulang jendela member | Member langsung dianggap Guest (diarahkan ke login). Login ulang ditolak: "Akun ini dinonaktifkan...". |
| 14 | Admin: tombol **Aktifkan** pada akun tadi > konfirmasi | Status "Aktif"; member bisa login lagi. Log: "Admin: aktifkan akun". |
| 15 | Admin membuka `/forum/balasan/<id-orang-lain>/hapus` | Tetap **403** (moderasi hanya lewat halaman Admin). |
| 16 | Tampilan: Light, Dark, Mobile View, lebar 360/768/1280 px | Tabel bergulir horizontal di dalam kartunya; halaman tidak bergulir ke samping; tombol tinggi minimal 44 px. |
