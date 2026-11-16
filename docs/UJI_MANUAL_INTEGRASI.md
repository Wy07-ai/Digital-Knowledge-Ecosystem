# Uji manual: integrasi lintas modul

Persiapan: `python seed.py --reset`, `python run.py` (kunci sesi: lihat README, bagian Menjalankan), masuk sebagai `demo@dke.test` / `Demo12345`.

## 1. Notifikasi bilah atas
1. Di Beranda, lonceng menampilkan lencana **2** (dua balasan Forum belum dibaca).
2. Buka panel: tiga baris teratas berisi pesan, aplikasi, dan waktu; yang belum dibaca bertitik dan tebal.
3. Klik satu notifikasi bertautan: halaman topik terbuka; kembali ke Beranda, lencana menjadi **1**.
4. Buka panel lagi, klik **Tandai semua dibaca**: lencana hilang, titik hilang, tombol tersembunyi, muncul toast sukses.
5. Muat ulang: keadaan tetap (tersimpan di server). Widget Forum di Beranda berubah menjadi "Tidak ada balasan baru".
6. Putuskan jaringan lalu klik tombol: muncul toast galat, bukan `alert`.

## 2. pilihan Saat membuka DKE
1. Kunjungi `/portal/`, kembali ke Beranda, pilih **Lanjutkan aplikasi terakhir**: status berubah "aktif".
2. Buka DKE di tab/sesi baru: langsung ke `/portal/`.
3. Pilih **Tampilkan Beranda**: status "nonaktif"; sesi baru kini membuka Beranda.

## 3. Statistik
Buka `/infosys/statistik`: sepuluh kartu (termasuk Kuis lulus, Artikel Portal, Kategori favorit, Aktivitas tercatat) dan daftar "Aktivitas per aplikasi" untuk keenam aplikasi. Bandingkan satu angka dengan halaman aplikasinya.

## 4. Pengaturan
Untuk tiap aplikasi (E-Commerce, E-Learning, E-Tutorial, Portal, Forum): ubah dan simpan. Harapkan kalimat "Pengaturan <Nama aplikasi> berhasil disimpan.", nilai tetap setelah muat ulang, dan satu baris baru di `/infosys/log` ("Ubah pengaturan ...").

## 5. Navigasi E-Commerce
Pada Produk, Keranjang, Pembayaran, Pesanan Saya, Detail Pesanan, dan Pengaturan: jejak halaman dan tombol Kembali tampil.
