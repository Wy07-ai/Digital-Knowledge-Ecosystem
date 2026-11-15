# Uji manual: integrasi lintas modul

Persiapan: `python seed.py --reset`, `python run.py`, masuk sebagai `demo@dke.test` / `Demo12345`.

## 1. Notifikasi Top-Bar
1. Di Beranda, lonceng menampilkan lencana **2** (dua balasan Forum belum dibaca).
2. Buka panel: tiga baris teratas berisi pesan, modul, dan waktu; yang belum dibaca bertitik dan tebal.
3. Klik satu notifikasi bertautan: halaman thread terbuka; kembali ke Beranda, lencana menjadi **1**.
4. Buka panel lagi, klik **Tandai semua dibaca**: lencana hilang, titik hilang, tombol tersembunyi, muncul toast sukses.
5. Muat ulang: keadaan tetap (tersimpan di server). Widget Forum di Beranda berubah menjadi "Tidak ada balasan baru".
6. Putuskan jaringan lalu klik tombol: muncul toast galat, bukan `alert`.

## 2. Smart Landing
1. Kunjungi `/portal/`, kembali ke Beranda, pilih **Lanjutkan modul terakhir**: status berubah "aktif".
2. Buka DKE di tab/sesi baru: langsung ke `/portal/`.
3. Pilih **Tampilkan Beranda**: status "nonaktif"; sesi baru kini membuka Beranda.

## 3. Statistik
Buka `/infosys/statistik`: sepuluh kartu (termasuk Kuis lulus, Artikel Portal, Kategori favorit, Aktivitas tercatat) dan daftar "Aktivitas per modul" untuk keenam modul. Bandingkan satu angka dengan halaman modulnya.

## 4. Pengaturan
Untuk tiap modul (E-Commerce, E-Learning, E-Tutorial, Portal, Forum): ubah dan simpan. Harapkan kalimat "Pengaturan <Modul> berhasil disimpan.", nilai tetap setelah muat ulang, dan satu baris baru di `/infosys/log` ("Ubah pengaturan ...").

## 5. Navigasi E-Commerce
Pada Produk, Keranjang, Checkout, Pesanan Saya, Detail Pesanan, dan Pengaturan: breadcrumb dan tombol Kembali tampil.
