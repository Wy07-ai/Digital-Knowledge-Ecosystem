# Teks antarmuka: sebelum → sesudah (Issue 5.5)

Dihasilkan dengan membandingkan inventaris teks tampilan sebelum dan sesudah penulisan ulang (`scripts/inventaris_teks.py`). Aturan: `docs/GLOSARIUM_TEKS.md`. Tabel ini siap ditempel ke komentar issue.

Ringkasan: 233 kalimat ditulis ulang, ditambah pergantian istilah massal (thread → topik, Solved → Terjawab, Top-Bar → bilah atas, Step → Langkah) yang tampil di banyak halaman.

## Pergantian istilah massal

| Sebelum | Sesudah | Cakupan |
|---|---|---|
| thread / Thread | topik / Topik | Forum, Akun Saya (Admin, statistik, log), navigasi, notifikasi |
| Solved | Terjawab | Lencana, filter, profil Forum |
| Control Panel | Akun Saya | Judul, menu, aria-label |
| login / logout | masuk / keluar | Riwayat masuk, Terakhir masuk, log aktivitas |
| checkout | Pembayaran / Bayar | Judul, tombol, pesan |
| bookmark | simpan / tersimpan | Teks bantuan, statistik |
| Top-Bar | bilah atas | Teks bantuan |
| Smart Landing | Saat membuka DKE | Beranda, toast |
| breadcrumb | jejak halaman | aria-label |
| Step / Estimasi / Level | Langkah / Perkiraan waktu / Tingkat | E-Tutorial, E-Learning |
| kamu / -mu | Anda | Beranda, E-Commerce |

## Beranda, navigasi, dan API

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `__init__.py` | Katalog produk, keranjang, dan checkout. | Katalog produk, keranjang, dan pembayaran. |
| `main/api.py` | Silakan masuk terlebih dahulu. | Sesi Anda berakhir. Masuk lagi, lalu ulangi. |
| `main/api.py` | Data notifikasi tidak valid. | Data notifikasi belum sesuai. Muat ulang halaman lalu coba lagi. |
| `main/api.py` | tidak valid. Pilihan: | belum sesuai. Pilih salah satu: |
| `navigation.py` | Hapus Thread | Hapus Topik |
| `navigation.py` | Buat Thread | Buat Topik |
| `navigation.py` | Thread Saya | Topik Saya |
| `static/js/launcher.js` | Berikutnya DKE akan membuka aplikasi terakhir Anda. | Pengaturan disimpan. Berikutnya DKE membuka aplikasi terakhir Anda. |
| `static/js/launcher.js` | Smart Landing dimatikan. Berikutnya DKE akan membuka Beranda. | Pengaturan disimpan. Berikutnya DKE membuka Beranda. |
| `static/js/launcher.js` | Sesi Anda berakhir. Silakan masuk lagi untuk menyimpan pengaturan. | Sesi Anda berakhir. Masuk lagi untuk menyimpan pengaturan. |
| `templates/main/index.html` | Pilih ruang belajarmu, atau lanjutkan aktivitas terakhir. | Pilih aplikasi, atau lanjutkan aktivitas terakhir. |
| `templates/main/index.html` | Satu akun, enam aplikasi. Temukan ruang baru untuk belajar dan berkarya. | Satu akun untuk enam aplikasi belajar dan berkarya. |
| `templates/main/index.html` | SATU PINTU, ENAM RUANG | SATU PINTU, ENAM APLIKASI |
| `templates/main/index.html` | Pilih perjalananmu | Pilih aplikasi Anda |
| `templates/main/index.html` | Mulai dari yang kamu butuhkan hari ini. | Mulai dari yang Anda butuhkan hari ini. |
| `templates/main/index.html` | Smart Landing: saat membuka DKE | Saat membuka DKE |
| `templates/main/index.html` | Tampilkan Beranda (matikan Smart Landing) | Selalu tampilkan Beranda |
| `templates/main/index.html` | Lanjutkan aplikasi terakhir (nyalakan) | Lanjutkan aplikasi terakhir |
| `templates/main/index.html` | Berlaku saat Anda masuk atau membuka DKE kembali. Tombol DKE di Top-Bar selalu menuju Beranda. | Berlaku saat Anda masuk atau membuka DKE lagi. Tombol DKE di bilah atas selalu ke Beranda. |
| `templates/main/nav_demo.html` | Klik jenjang di breadcrumb untuk naik langsung ke kelas atau ke daftar E-Learning. | Klik jenjang di jejak halaman untuk naik langsung ke kelas atau ke daftar E-Learning. |
| `templates/main/nav_demo.html` | Tekan tombol Mobile di Top-Bar: breadcrumb diringkas menjadi halaman aktif, dan tombol membuka jenjang yang disembunyikan. | Tekan tombol Mobile di bilah atas: jejak halaman diringkas menjadi halaman aktif, dan tombol membuka jenjang yang disembunyikan. |
| `templates/main/nav_demo.html` | Buka App Switcher (ikon 9 titik) untuk pindah aplikasi tanpa lewat Beranda. | Buka Pindah aplikasi (ikon 9 titik) untuk pindah aplikasi tanpa lewat Beranda. |
| `templates/main/ui_test.html` | Ubah lewat ikon tema dan tombol Mobile di Top-Bar, lalu muat ulang halaman: pilihan harus bertahan tanpa kedip. | Ubah lewat ikon tema dan tombol Mobile di bilah atas, lalu muat ulang halaman: pilihan harus bertahan tanpa kedip. |
| `templates/main/ui_test.html` | 4. Navigasi 3 level: Kembali, breadcrumb, App Switcher | 4. Navigasi 3 level: Kembali, jejak halaman, Pindah aplikasi |
| `templates/main/ui_test.html` | Profil Pengaturan (2 jenjang, perlu login) | Profil Pengaturan (2 jenjang, perlu masuk) |
| `templates/main/ui_test.html` | Klik kartu untuk membuka aplikasi; di sana App Switcher (ikon 9 titik) menandai aplikasi aktif. | Klik kartu untuk membuka aplikasi; di sana Pindah aplikasi (ikon 9 titik) menandai aplikasi aktif. |
| `main/api.py` | Permintaan ditolak. | Perkiraan waktu |

## E-Commerce

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `ecommerce/routes.py` | Nomor pesanan hari ini sudah mencapai batas. | Batas pesanan hari ini sudah tercapai. Coba lagi besok. |
| `ecommerce/routes.py` | Silakan masuk untuk menambahkan produk ke keranjang. | Masuk dulu untuk menambahkan produk ke keranjang. |
| `ecommerce/routes.py` | Keranjang masih kosong. Tambahkan produk sebelum checkout. | Alamat penerima belum diisi. Isi alamat sebelum membayar. |
| `ecommerce/routes.py` | Masukkan jumlah produk yang valid. | Jumlah produk belum valid. Masukkan angka bulat. |
| `ecommerce/routes.py` | Keranjang masih kosong. Tambahkan produk sebelum checkout. | Ada kursus di keranjang yang belum terhubung ke kelas. Hubungi admin. |
| `ecommerce/routes.py` | Hapus produk yang sudah tidak tersedia sebelum checkout. | Hapus produk yang sudah tidak tersedia dari keranjang, lalu bayar lagi. |
| `ecommerce/routes.py` | Pembayaran simulasi gagal diproses. Keranjang Anda tetap tersimpan; silakan coba lagi. | Pembayaran simulasi belum berhasil. Keranjang Anda aman. Coba lagi sebentar lagi. |
| `templates/ecommerce/cart.html` | Produk yang kamu tambahkan akan muncul di sini. | Produk yang Anda tambahkan akan muncul di sini. |
| `templates/ecommerce/cart.html` | Tambahkan produk sebelum checkout. | Tambahkan produk dulu, lalu bayar. |
| `templates/ecommerce/cart.html` | Lanjut ke checkout | Lanjut bayar |
| `templates/ecommerce/checkout.html` | Alamat terisi dari Pengaturan E-Commerce. Alamat wajib diisi. | Alamat terisi dari Pengaturan E-Commerce. Isi alamat penerima sebelum membayar. |
| `templates/ecommerce/checkout.html` | Metode favorit dapat diatur di | Metode favorit bisa diatur di |
| `templates/ecommerce/checkout.html` | Dengan menekan Bayar, pesanan simulasi akan tercatat di akunmu. | Dengan menekan Bayar, pesanan simulasi akan tercatat di akun Anda. |
| `templates/ecommerce/index.html` | Produk digital pilihan untuk mendukung proses belajarmu. | Produk digital pilihan untuk mendukung proses belajar Anda. |
| `templates/ecommerce/index.html` | Temukan kursus, e-book, dan aset digital untuk kebutuhanmu. | Temukan kursus, e-book, dan aset digital untuk kebutuhan Anda. |
| `templates/ecommerce/product.html` | Produk digital pilihan untuk mendukung proses belajarmu. | Produk digital pilihan untuk mendukung proses belajar Anda. |
| `templates/ecommerce/settings.html` | Simpan alamat dan metode pembayaran favorit untuk checkout berikutnya. | Simpan alamat dan metode pembayaran favorit untuk pembayaran berikutnya. |
| `templates/ecommerce/settings.html` | Alamat ini akan terisi otomatis di checkout. Maksimal 1.000 karakter. | Alamat ini akan terisi otomatis di halaman pembayaran. Maksimal 1.000 karakter. |
| `templates/ecommerce/settings.html` | Metode ini akan terpilih otomatis di checkout dan tetap bisa diganti. | Metode ini akan terpilih otomatis di halaman pembayaran dan tetap bisa diganti. |

## E-Learning

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `elearning/routes.py` | Kelas ini berbayar. Beli kelas lewat E-Commerce, lalu kelas otomatis muncul di Kelas Saya. | Kelas ini berbayar. Beli lewat E-Commerce, lalu kelas muncul otomatis di Kelas Saya. |
| `elearning/routes.py` | Kelas ini belum memiliki materi, jadi belum bisa diikuti. | Kelas ini belum punya materi, jadi belum bisa diikuti. Coba lagi nanti. |
| `elearning/routes.py` | Jawaban belum bisa disimpan. Coba kumpulkan lagi; jawaban Anda masih tersimpan di browser. | Jawaban belum bisa dikumpulkan. Coba lagi; jawaban Anda masih tersimpan di peramban ini. |
| `elearning/routes.py` | Isi target dengan angka bulat, | Isi target dengan angka bulat antara |
| `elearning/routes.py` | Target belajar harus antara | Target belajar antara |
| `static/js/elearning.js` | Tandai Selesai | Tandai selesai |
| `static/js/elearning.js` | Sesi Anda berakhir. Silakan masuk lagi, lalu ulangi. | Sesi Anda berakhir. Masuk lagi, lalu ulangi. |
| `static/js/elearning.js` | Koneksi bermasalah. Progres belum tersimpan, coba lagi. | Koneksi terputus. Progres belum tersimpan. Coba lagi. |
| `templates/elearning/course_detail.html` | Setelah checkout, kelas langsung muncul di Kelas Saya. | Setelah membayar, kelas langsung muncul di Kelas Saya. |
| `templates/elearning/index.html` | Belum ada kelas level | Belum ada kelas tingkat |
| `templates/elearning/index.html` | Coba level lain atau tampilkan semua kelas. | Coba tingkat lain atau tampilkan semua kelas. |
| `templates/elearning/index.html` | Kelas baru akan muncul di sini. Sementara itu, jelajahi aplikasi lain. | Kelas akan muncul di sini setelah ditambahkan. |
| `templates/elearning/index.html` | Filter level kelas | Filter tingkat kelas |
| `templates/elearning/index.html` | Semua level | Semua tingkat |
| `templates/elearning/index.html` | Filter level tidak dikenal, jadi semua kelas ditampilkan. | Filter tingkat tidak dikenal, jadi semua kelas ditampilkan. |
| `templates/elearning/index.html` | Menampilkan kelas level . | Menampilkan kelas tingkat . |
| `templates/elearning/lesson.html` | Tandai Selesai | Tandai selesai |
| `templates/elearning/lesson.html` | Tautan video materi ini tidak didukung atau belum diisi. Anda tetap bisa melanjutkan ke materi berikutnya. | Video materi ini belum tersedia. Anda tetap bisa lanjut ke materi berikutnya. |
| `templates/elearning/settings.html` | Atur kecepatan putar video dan target belajar harian Anda. Perubahan berlaku mulai materi berikutnya. | Atur kecepatan video dan target belajar harian. Berlaku mulai materi berikutnya. |
| `elearning/routes.py` | Permintaan ditolak. | Perkiraan waktu |

## Galat

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `errors.py` | Permintaan tidak dapat diproses | Permintaan belum bisa diproses |
| `errors.py` | Permintaan tidak dapat diproses. | Tindakan ini tidak tersedia untuk alamat tersebut. |
| `errors.py` | Anda tidak punya izin untuk mengakses sumber ini. | Akun Anda tidak punya izin untuk tindakan ini. |
| `errors.py` | Sumber yang diminta tidak ditemukan. | Data yang diminta tidak ditemukan. |
| `errors.py` | Metode permintaan tidak diizinkan untuk alamat ini. | Muat ulang halaman lalu coba lagi. |
| `errors.py` | Terjadi kesalahan di server. Coba lagi sebentar lagi. | Ada gangguan di sisi kami. Coba lagi sebentar lagi. |
| `errors.py` | Anda tidak punya izin untuk membuka halaman ini. | Akun Anda tidak punya izin membuka halaman ini. Kembali ke Beranda untuk melanjutkan. |
| `errors.py` | Alamat yang Anda tuju tidak tersedia. Mungkin salah ketik atau halamannya sudah dipindahkan. | Alamat ini tidak tersedia atau halamannya sudah dipindahkan. Kembali ke Beranda untuk mencari lagi. |
| `errors.py` | Cara akses tidak diizinkan | Ada gangguan di sisi kami |
| `errors.py` | Halaman ini tidak bisa dibuka dengan cara tersebut. Silakan kembali dan gunakan tombol atau tautan yang tersedia. | Kembali ke halaman sebelumnya, lalu gunakan tombol atau tautan yang tersedia. |
| `errors.py` | Terjadi kesalahan di server | Ini bukan salah Anda. Coba lagi sebentar lagi. |
| `errors.py` | Maaf, ada gangguan di sisi kami. Silakan coba lagi sebentar lagi. | Halaman tidak bisa dibuka dengan cara ini |

## E-Tutorial

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `etutorial/routes.py` | Ukuran font bacaan: | Ukuran huruf bacaan: |
| `etutorial/routes.py` | Tutorial ini memang belum disimpan. | Tutorial ini belum ada di Tersimpan. |
| `etutorial/routes.py` | Ukuran font bacaan: | Ukuran huruf bacaan: |
| `etutorial/routes.py` | Pilih salah satu ukuran font yang tersedia. | Pilih salah satu ukuran huruf yang tersedia. |
| `templates/etutorial/index.html` | Tutorial baru akan muncul di sini. Sementara itu, jelajahi aplikasi lain. | Tutorial akan muncul di sini setelah ditambahkan. |
| `templates/etutorial/saved.html` | Tutorial yang Anda bookmark, yang terbaru di atas. | Tutorial yang Anda simpan, dari yang terbaru. |
| `templates/etutorial/settings.html` | Pilih ukuran font bacaan tutorial. Pratinjau di bawah berubah langsung saat Anda memilih. | Pilih ukuran huruf untuk membaca tutorial. Pratinjau berubah langsung. |
| `templates/etutorial/settings.html` | Ukuran font bacaan | Ukuran huruf bacaan |
| `templates/etutorial/tutorial.html` | Langkah-langkahnya sedang disiapkan. Coba tutorial lain dulu. | Langkah tutorial ini sedang disiapkan, coba tutorial lain dulu. |
| `templates/etutorial/tutorial.html` | Step dari | Langkah dari |
| `templates/etutorial/tutorial.html` | Salin kode Step | Salin kode Langkah |
| `templates/etutorial/tutorial.html` | Kode Step | Kode Langkah |
| `templates/etutorial/tutorial.html` | · Step max-w-3xl | · Langkah max-w-3xl |
| `templates/etutorial/tutorial.html` | Ukuran font: · Ubah | Ukuran huruf: · Ubah |
| `templates/etutorial/tutorial.html` | Step dari | Langkah dari |
| `templates/etutorial/tutorial.html` | Anda sudah sampai di langkah terakhir. Coba ulangi dari nol tanpa menyalin kode untuk memastikan Anda benar-benar paham. | Ini langkah terakhir. Coba ulangi tanpa menyalin kode untuk menguji pemahaman Anda. |
| `templates/etutorial/tutorial.html` | Ulangi dari Step 1 | Ulangi dari Langkah 1 |

## Forum

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `forum/logic.py` | Siapa pun, termasuk pengunjung yang belum masuk, dapat melihat profil Forum Anda. | Siapa pun, termasuk pengunjung yang belum masuk, bisa melihat profil Forum Anda. |
| `forum/logic.py` | Hanya pengguna yang sudah masuk yang dapat melihat profil Forum Anda. | Hanya pengguna yang sudah masuk yang bisa melihat profil Forum Anda. |
| `forum/logic.py` | Hanya Anda yang dapat melihat halaman profil Forum Anda. | Hanya Anda yang bisa melihat halaman profil Forum Anda. |
| `forum/logic.py` | Judul wajib diisi. | Judul belum diisi. Tulis judul yang jelas. |
| `forum/logic.py` | Isi thread wajib diisi. | Isi topik belum diisi. Jelaskan pertanyaan atau cerita Anda. |
| `forum/logic.py` | Balasan tidak boleh kosong. | Balasan belum diisi. Tulis balasan Anda. |
| `forum/routes.py` | Perubahan belum bisa disimpan. Coba lagi sebentar lagi. | Topik berhasil dibuat. Tunggu balasan dari anggota lain. |
| `forum/routes.py` | Tanda solusi dibatalkan. Thread kembali berstatus belum terjawab. | Tanda solusi dibatalkan. Topik kembali berstatus belum terjawab. |
| `forum/routes.py` | Balasan ditandai sebagai solusi. Thread kini berlabel Solved. | Balasan ditandai sebagai solusi. Topik kini berlabel Terjawab. |
| `forum/routes.py` | Thread Saya | Topik Saya |
| `forum/routes.py` | Buat Thread | Buat Topik |
| `forum/routes.py` | membalas thread Anda | membalas topik Anda |
| `forum/routes.py` | Balasan yang dipilih tidak ditemukan di thread ini. | Balasan yang dipilih tidak ditemukan di topik ini. |
| `templates/forum/delete_post.html` | Di thread: | Di topik: |
| `templates/forum/delete_post.html` | Balasan ini ditandai sebagai solusi, jadi thread kembali berstatus belum terjawab. | Balasan ini ditandai sebagai solusi, jadi topik kembali berstatus belum terjawab. |
| `templates/forum/edit_post.html` | Di thread: | Di topik: |
| `templates/forum/index.html` | Semua thread | Semua topik |
| `templates/forum/index.html` | Tidak ada pertanyaan yang menunggu solusi. Lihat semua thread atau mulai diskusi baru. | Semua pertanyaan di sini sudah punya solusi. |
| `templates/forum/index.html` | Lihat semua thread | Lihat semua topik |
| `templates/forum/index.html` | Belum ada thread di kategori | Belum ada topik di kategori |
| `templates/forum/index.html` | Buat thread | Buat topik |
| `templates/forum/index.html` | Belum ada thread | Belum ada topik |
| `templates/forum/index.html` | Buat thread pertama | Buat topik pertama |
| `templates/forum/index.html` | Urutan thread | Urutan topik |
| `templates/forum/index.html` | Daftar thread | Daftar topik |
| `templates/forum/index.html` | Buat thread | Buat topik |
| `templates/forum/index.html` | Kategori itu tidak dikenal, jadi semua thread ditampilkan. | Kategori itu tidak dikenal, jadi semua topik ditampilkan. |
| `templates/forum/index.html` | Urutan itu tidak dikenal, jadi thread diurutkan dari yang terbaru. | Urutan itu tidak dikenal, jadi topik diurutkan dari yang terbaru. |
| `templates/forum/index.html` | Menampilkan thread yang belum punya jawaban bertanda solusi. Yang paling sedikit balasannya ada di atas. | Menampilkan topik yang belum punya solusi, dari yang paling sedikit balasannya. |
| `templates/forum/layout_forum.html` | Thread Saya | Topik Saya |
| `templates/forum/my_threads.html` | Anda belum membuat thread | Anda belum membuat topik |
| `templates/forum/my_threads.html` | Punya pertanyaan atau cerita belajar? Mulai diskusi pertama Anda. | Mulai diskusi pertama Anda dengan pertanyaan atau cerita belajar. |
| `templates/forum/my_threads.html` | Buat thread pertama | Buat topik pertama |
| `templates/forum/my_threads.html` | Daftar thread saya | Daftar topik saya |
| `templates/forum/my_threads.html` | Thread Saya | Topik Saya |
| `templates/forum/my_threads.html` | Thread saya | Topik saya |
| `templates/forum/my_threads.html` | thread yang Anda mulai, di antaranya sudah Solved. Thread yang Anda mulai akan muncul di sini. | topik yang Anda mulai, di antaranya sudah terjawab. Topik yang Anda mulai akan muncul di sini. |
| `templates/forum/my_threads.html` | Buat thread | Buat topik |
| `templates/forum/new_thread.html` | Isi thread | Isi topik |
| `templates/forum/new_thread.html` | Membuat thread&hellip; | Membuat topik&hellip; |
| `templates/forum/new_thread.html` | Buat Thread max-w-3xl | Buat Topik max-w-3xl |
| `templates/forum/new_thread.html` | Buat thread baru | Buat topik baru |
| `templates/forum/new_thread.html` | Isi thread | Isi topik |
| `templates/forum/new_thread.html` | Buat thread | Buat topik |
| `templates/forum/profile.html` | Thread terbaru | Topik terbaru |
| `templates/forum/profile.html` | belum membuat thread. | belum membuat topik. |
| `templates/forum/profile.html` | Pemilik profil memilih untuk tidak membagikan detailnya. Anda tetap bisa membaca thread dan balasannya di Forum. | Pemilik profil memilih untuk tidak membagikan detailnya. Anda tetap bisa membaca topik dan balasannya di Forum. |
| `templates/forum/settings.html` | Atur siapa yang bisa melihat profil Forum Anda dan apakah Anda diberi tahu saat ada yang membalas thread Anda. | Atur siapa yang bisa melihat profil Forum Anda dan notifikasi balasan. |
| `templates/forum/settings.html` | Nama Anda tetap tampil pada thread dan balasan Anda. Pengaturan ini mengatur halaman profil Forum: bio, tanggal bergabung, dan ringkasan aktivitas. | Nama Anda tetap tampil pada topik dan balasan. Pengaturan ini hanya untuk halaman profil: bio, tanggal bergabung, dan ringkasan aktivitas. |
| `templates/forum/settings.html` | Bila aktif, Anda mendapat notifikasi di lonceng Top-Bar setiap ada anggota lain yang membalas thread Anda. Balasan Anda sendiri tidak dihitung. | Bila aktif, lonceng di bilah atas memberi tahu Anda saat anggota lain membalas topik Anda. Balasan Anda sendiri tidak dihitung. |
| `templates/forum/thread.html` | Penulis thread | Penulis topik |
| `templates/forum/thread.html` | Membalas thread ini. | Membalas topik ini. |
| `templates/forum/thread.html` | Masuk dulu untuk membalas thread ini. Setelah masuk, Anda kembali ke halaman ini. | Masuk dulu untuk membalas topik ini. Setelah masuk, Anda kembali ke halaman ini. |

## Akun Saya (Information System)

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `infosys/admin.py` | Thread yang dihapus tidak bisa dikembalikan. | Topik yang dihapus tidak bisa dikembalikan. |
| `infosys/admin.py` | Thread dihapus. | Topik dihapus. |
| `infosys/admin.py` | Hapus thread ini? | Hapus topik ini? |
| `infosys/admin.py` | Ya, hapus thread | Ya, hapus topik |
| `infosys/admin.py` | Balasan ini ditandai sebagai solusi, jadi thread kembali berstatus belum terjawab. | Balasan ini ditandai sebagai solusi, jadi topik kembali berstatus belum terjawab. |
| `infosys/admin.py` | Pengguna dapat login kembali dengan kata sandinya. | Pengguna bisa masuk lagi dengan kata sandinya. |
| `infosys/admin.py` | Pengguna tidak bisa login, dan sesi yang sedang berjalan langsung tidak berlaku. | Pengguna tidak bisa masuk, dan sesi yang sedang berjalan langsung berakhir. |
| `infosys/admin.py` | Thread dan balasannya tetap ada. Akun bisa diaktifkan kembali kapan saja. | Topik dan balasannya tetap ada. Akun bisa diaktifkan kembali kapan saja. |
| `infosys/admin.py` | di thread " | di topik " |
| `infosys/admin.py` | Thread # | Topik # |
| `infosys/admin.py` | Thread oleh | Topik oleh |
| `infosys/admin.py` | di thread # | di topik # |
| `infosys/panel.py` | Registrasi akun | Daftar akun |
| `infosys/panel.py` | Gagal login | Gagal masuk |
| `infosys/panel.py` | Gagal ubah kata sandi | Gagal mengubah kata sandi |
| `infosys/panel.py` | Buat thread | Buat topik |
| `infosys/panel.py` | Balas thread | Balas topik |
| `infosys/panel.py` | Admin: hapus thread | Admin: hapus topik |
| `infosys/panel.py` | Hapus simpanan tutorial | Hapus tutorial tersimpan |
| `infosys/routes.py` | Akun berhasil dibuat. Silakan masuk dengan email dan kata sandi Anda. | Akun berhasil dibuat. Masuk dengan email dan kata sandi Anda. |
| `infosys/routes.py` | Login berhasil | Berhasil masuk |
| `infosys/throttle.py` | Percobaan login gagal (ref | Percobaan masuk gagal (ref |
| `templates/infosys/_panel.html` | Menu Control Panel | Menu Akun Saya |
| `templates/infosys/_panel.html` | Tab Control Panel | Tab Akun Saya |
| `templates/infosys/activity.html` | Login, belanja, belajar, dan diskusi Anda akan tercatat di sini secara otomatis. | Aktivitas Anda di semua aplikasi akan tercatat di sini. |
| `templates/infosys/activity.html` | Jejak aktivitas akun Anda di semua aplikasi, dari yang terbaru. Hanya Anda yang dapat melihatnya. | Riwayat tindakan akun Anda, dari yang terbaru. Hanya Anda yang bisa melihatnya. |
| `templates/infosys/admin.html` | Moderasi konten Forum dan pengelolaan akun. Setiap tindakan dicatat di Log Aktivitas Anda. | Kelola konten Forum dan akun pengguna. Setiap tindakan tercatat di Log Aktivitas Anda. |
| `templates/infosys/index.html` | Masuk untuk membuka Control Panel | Masuk untuk melihat akun Anda |
| `templates/infosys/index.html` | Profil, log aktivitas, statistik dari semua aplikasi, dan pengaturan keamanan hanya tersedia setelah Anda masuk. | Profil, log aktivitas, dan keamanan akun tersedia setelah Anda masuk. |
| `templates/infosys/index.html` | Gambaran singkat akun dan aktivitas Anda di seluruh aplikasi DKE. | Ringkasan akun dan aktivitas Anda. |
| `templates/infosys/index.html` | Anggota sejak Login sebelumnya Ini login pertama Anda | Anggota sejak Terakhir masuk Ini pertama kalinya Anda masuk |
| `templates/infosys/index.html` | Belum ada data dari semua aplikasi. Mulailah dengan | Belum ada data. Mulai dengan |
| `templates/infosys/index.html` | mengikuti kelas | ikut kelas |
| `templates/infosys/index.html` | menyimpan tutorial | simpan tutorial |
| `templates/infosys/index.html` | Belum ada aktivitas tercatat. Aktivitas Anda di semua aplikasi akan muncul di sini. | Belum ada aktivitas. Aktivitas Anda akan muncul di sini. |
| `templates/infosys/login.html` | Masuk untuk memakai keranjang, kelas, bookmark, dan forum. | Masuk untuk memakai keranjang, kelas, tutorial tersimpan, dan forum. |
| `templates/infosys/profile.html` | Tautan avatar (avatar_url) | Tautan foto profil |
| `templates/infosys/profile.html` | tidak dapat diubah. | tidak bisa diubah. |
| `templates/infosys/profile.html` | Pratinjau avatar. Tempel tautan gambar di bawah; bila kosong atau gagal dimuat, inisial nama dipakai. | Pratinjau foto. Tempel tautan gambar di bawah. Bila kosong, inisial nama yang tampil. |
| `templates/infosys/profile.html` | Gunakan minimal 8 karakter. Setelah diganti, Anda tetap masuk di perangkat ini. | Minimal 8 karakter. Anda tetap masuk di perangkat ini setelah diganti. |
| `templates/infosys/security.html` | Login terakhir | Terakhir masuk |
| `templates/infosys/security.html` | Total login tercatat | Total riwayat masuk |
| `templates/infosys/security.html` | Login berhasil | Berhasil masuk |
| `templates/infosys/security.html` | Belum ada riwayat login | Belum ada riwayat masuk |
| `templates/infosys/security.html` | Pantau riwayat login akun Anda dan jaga kata sandi tetap aman. | Lihat riwayat masuk akun Anda dan jaga kata sandi tetap aman. |
| `templates/infosys/security.html` | Disarankan diganti berkala, dan segera bila ada login yang tidak Anda kenali. | Ganti secara berkala, dan segera jika ada riwayat masuk yang tidak Anda kenali. |
| `templates/infosys/security.html` | Riwayat login | Riwayat masuk |
| `templates/infosys/security.html` | Halaman ini memuat lebih dari satu alamat IP. Bila ada yang tidak Anda kenali, ganti kata sandi Anda. | Ada lebih dari satu alamat IP di halaman ini. Jika ada yang tidak Anda kenali, ganti kata sandi. |
| `templates/infosys/security.html` | Riwayat login, halaman dari | Riwayat masuk, halaman dari |
| `templates/infosys/stats.html` | Tutorial yang Anda bookmark. | Tutorial yang Anda simpan. |
| `templates/infosys/stats.html` | Thread dibuat | Topik dibuat |
| `templates/infosys/stats.html` | Belum membuat thread. | Belum membuat topik. |
| `templates/infosys/stats.html` | Belum membalas thread. | Belum membalas topik. |
| `templates/infosys/stats.html` | Belum ada login tercatat. | Belum ada riwayat masuk. |
| `templates/infosys/stats.html` | Angka dari keenam aplikasi DKE. Semuanya mencakup akun Anda, kecuali jumlah artikel Portal yang bersifat umum. | Angka dari keenam aplikasi DKE untuk akun Anda. Jumlah artikel Portal bersifat umum. |
| `infosys/admin.py` | Perubahan belum bisa disimpan. Coba lagi sebentar lagi. | Pengaturan belum bisa disimpan. Coba lagi sebentar lagi. |
| `infosys/validation.py` | Nama lengkap wajib diisi. | Nama lengkap belum diisi. Tulis nama Anda. |
| `infosys/validation.py` | Nama lengkap maksimal 100 karakter. | Nama lengkap terlalu panjang. Maksimal 100 karakter. |
| `infosys/validation.py` | Kata sandi maksimal 128 karakter. | Kata sandi terlalu panjang. Maksimal 128 karakter. |
| `infosys/validation.py` | Kata sandi wajib diisi. | Ketik kata sandi Anda saat ini. |
| `infosys/validation.py` | Email ini sudah terdaftar. Silakan masuk atau gunakan email lain. | Email ini sudah terdaftar. Masuk, atau pakai email lain. |
| `infosys/validation.py` | Bio maksimal 300 karakter. | Bio terlalu panjang. Maksimal 300 karakter. |
| `infosys/validation.py` | Tautan avatar belum valid. Gunakan alamat gambar yang diawali https:// | Tautan foto belum valid. Gunakan alamat gambar yang diawali https:// |
| `infosys/validation.py` | Tautan avatar maksimal 500 karakter. | Tautan foto terlalu panjang. Maksimal 500 karakter. |
| `infosys/validation.py` | Kata sandi saat ini wajib diisi. | Kata sandi saat ini salah. Periksa kembali dan coba lagi. |
| `infosys/validation.py` | Kata sandi baru harus berbeda dari kata sandi saat ini. | Kata sandi baru sama dengan yang lama. Pilih kata sandi yang berbeda. |

## Lainnya

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `static/js/auth.js` | Kata sandi maksimal 128 karakter. | Kata sandi terlalu panjang. Maksimal 128 karakter. |
| `static/js/auth.js` | Kata sandi wajib diisi. | Kata sandi belum diisi. Ketik kata sandi Anda. |
| `static/js/auth.js` | Nama lengkap wajib diisi. | Nama lengkap belum diisi. Tulis nama Anda. |
| `static/js/auth.js` | Nama lengkap maksimal 100 karakter. | Nama lengkap terlalu panjang. Maksimal 100 karakter. |
| `static/js/panel.js` | Nama lengkap wajib diisi. | Nama lengkap belum diisi. Tulis nama Anda. |
| `static/js/panel.js` | Nama lengkap maksimal 100 karakter. | Nama lengkap terlalu panjang. Maksimal 100 karakter. |
| `static/js/panel.js` | Bio maksimal 300 karakter. | Bio terlalu panjang. Maksimal 300 karakter. |
| `static/js/panel.js` | Tautan avatar maksimal 500 karakter. | Tautan foto terlalu panjang. Maksimal 500 karakter. |
| `static/js/panel.js` | Kata sandi saat ini wajib diisi. | Ketik kata sandi Anda saat ini. |
| `static/js/panel.js` | Kata sandi maksimal 128 karakter. | Kata sandi terlalu panjang. Maksimal 128 karakter. |
| `static/js/panel.js` | Kata sandi baru harus berbeda dari kata sandi saat ini. | Kata sandi baru sama dengan yang lama. Pilih kata sandi yang berbeda. |

## Pesan bersama (API, tema, notifikasi)

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `static/js/notif.js` | Sesi Anda berakhir. Silakan masuk lagi. | Sesi Anda berakhir. Masuk lagi untuk melanjutkan. |
| `static/js/theme.js` | Sesi Anda berakhir. Silakan masuk lagi untuk menyimpan pengaturan. | Sesi Anda berakhir. Masuk lagi untuk menyimpan pengaturan. |
| `elearning/routes.py` | Anda belum terdaftar di kelas ini. Ikuti kelas lebih dulu untuk membuka ruang belajar. | Anda belum terdaftar di kelas ini. Ikuti kelas lebih dulu. |
| `forum/routes.py` | Thread berhasil dibuat. Tunggu balasan dari anggota lain. | Topik berhasil dibuat. Tunggu balasan dari anggota lain. |
| `utils.py` | Silakan masuk terlebih dahulu untuk mengakses halaman ini. | Masuk dulu untuk membuka halaman ini. |

## Portal

| Berkas | Sebelum | Sesudah |
|---|---|---|
| `templates/portal/index.html` | Artikel baru akan muncul di sini. Sementara itu, jelajahi kategori lain. | Artikel di kategori ini akan muncul di sini setelah ditambahkan. |
| `templates/portal/index.html` | Artikel baru akan muncul di sini. Sementara itu, jelajahi aplikasi lain. | Artikel akan muncul di sini setelah ditambahkan. |
| `templates/portal/settings.html` | Pilih kategori favorit Anda. Artikel dari kategori itu tampil lebih dulu di beranda Portal. Tidak ada artikel yang disembunyikan. | Artikel dari kategori favorit tampil lebih dulu di Portal. Tidak ada yang disembunyikan. |

## Label satu kata yang berubah

Checkout → Pembayaran/Bayar, Login → Masuk, Logout → Keluar, Thread → Topik, Breadcrumb → Jejak halaman, Solved → Terjawab (label menu, kolom, lencana, log aktivitas).
