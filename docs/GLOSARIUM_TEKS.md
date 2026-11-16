# Glosarium teks antarmuka (DKE)

Satu rujukan untuk kata-kata yang tampil ke pengguna: halaman, tombol, `flash()`, `empty_state`,
`aria-label`, `<caption>`, judul kolom tabel, opsi filter, judul halaman, dan notifikasi.
Pakai istilah di kolom **Istilah baku**; jangan campur dengan sinonimnya di layar yang sama.

## Keputusan istilah: "aplikasi", bukan "modul"

- **Keputusan:** untuk pengguna, tiap bagian DKE (Information System, E-Commerce, E-Learning, E-Tutorial,
  Portal, Forum) disebut **aplikasi**.
- **Alasan:**
  1. Pengguna umum melihat DKE sebagai kumpulan aplikasi. Tombol 9 titik di Top-Bar pun bernama
     *App Switcher*.
  2. "Modul" adalah istilah teknis internal (satu modul = satu Blueprint = satu folder template).
  3. Analisis pengguna meminta bahasa sederhana tanpa istilah teknis di menu.
- **Alternatif yang dipertimbangkan:** "layanan" (terkesan seperti layanan pelanggan/jasa) dan
  "bagian" (terlalu umum, bisa tertukar dengan bagian halaman). Keduanya tidak dipilih.
- **Batas penerapan:** hanya **teks tampilan** yang diubah. Identifier internal tetap memakai "module":
  `module_key`, `MODULES`, `MODULE_BY_KEY`, `current_module`, tabel `module_settings`, nama paket/blueprint,
  `module_content`, `badge_module`, dan parameter URL `?modul=` (URL tidak diubah supaya tautan lama tetap
  berfungsi). Komentar kode dan README bagian arsitektur boleh tetap menulis "modul" karena pembacanya
  developer.
- **Pengecualian bermakna lain:** kata "modul" dalam arti *modul Python* pada isi pelajaran (mis. materi
  "Fungsi dan Modul" di `seed.py`) adalah istilah pemrograman, bukan istilah antarmuka, jadi tetap.

Contoh penggantian yang sudah berlaku:

| Lama | Baru |
|------|------|
| Jelajahi modul | Jelajahi aplikasi |
| Filter modul / Semua modul | Filter aplikasi / Semua aplikasi |
| Pindah modul | Pindah aplikasi |
| Statistik Lintas Modul | Statistik Semua Aplikasi |
| statistik lintas modul (kalimat) | statistik dari semua aplikasi |
| Lanjutkan modul terakhir | Lanjutkan aplikasi terakhir |
| Pengaturan E-Learning | tetap (sudah memakai nama aplikasi) |

## Istilah baku

Kolom **Dipakai di** menunjuk contoh tempat istilah itu tampil. Status "sudah" berarti UI saat ini
memang memakainya.

| Istilah baku | Arti | Dipakai di | Jangan pakai |
|--------------|------|------------|--------------|
| aplikasi | Salah satu dari 6 bagian DKE | Beranda, App Switcher, filter log, statistik | modul |
| Beranda | Halaman awal DKE (kartu 6 aplikasi) | Top-Bar, breadcrumb, tombol Kembali | Home, Dashboard, Launcher |
| akun | Identitas pengguna yang masuk | Control Panel, pendaftaran | user, member (di teks tampilan) |
| masuk / keluar | Autentikasi | Tombol di Top-Bar, halaman masuk | sign in / sign out |
| kata sandi | Rahasia akun | Formulir, galat, keamanan | password |
| kelas | Satu kursus di E-Learning | Daftar Kelas, Kelas Saya | course |
| materi | Satu pelajaran di dalam kelas | Halaman kelas, progres | lesson |
| kuis | Latihan soal di dalam kelas | Halaman kuis, hasil kuis | quiz |
| tutorial | Panduan di E-Tutorial | Daftar Tutorial | -- |
| tersimpan | Tutorial yang ditandai pengguna | Tab Tersimpan | bookmark (di teks tampilan) |
| artikel | Tulisan di Portal | Portal | berita, post |
| produk | Barang atau kursus yang dijual | E-Commerce | item |
| keranjang | Daftar produk yang akan dibeli | Halaman keranjang | cart |
| pesanan | Transaksi pembelian | Pesanan Saya, detail pesanan | order |
| diskusi | Percakapan di Forum | Tab Diskusi | -- |
| balasan | Jawaban/komentar pada diskusi | Forum, statistik | reply, komentar |
| solusi | Balasan yang ditandai menjawab pertanyaan | Forum | solved (lihat catatan) |
| profil | Halaman identitas publik pengguna | Control Panel, Forum | profile |
| pengaturan | Preferensi pribadi per aplikasi | Tab Pengaturan | settings |
| notifikasi | Pemberitahuan di lonceng Top-Bar | Top-Bar | alert |
| progres | Kemajuan belajar (persen) | Kelas, statistik | progress (di teks tampilan) |
| log aktivitas | Jejak tindakan akun | Control Panel | history, audit |
| tema | Terang/gelap | Top-Bar | skin |
| hapus / ubah / simpan | Aksi standar tombol | Semua formulir | delete / edit / save |

## Istilah Inggris yang sebaiknya dihindari

Status:

- **Sudah** = UI sudah memakai istilah baku, tidak ada sisa istilah Inggris.
- **Usulan** = istilah baku sudah disepakati sebagai arah, tetapi UI **belum** diubah. Mengubahnya menyentuh
  banyak template, `flash()`, dan tes (jumlah kemunculan di bawah dihitung saat glosarium ini dibuat),
  jadi dikerjakan sebagai tugas terpisah setelah disetujui.

| Hindari | Gunakan | Status | Catatan |
|---------|---------|--------|---------|
| modul | aplikasi | **Sudah** | Lihat keputusan di atas |
| checkout | Bayar | Usulan | Masih dipakai di sekitar 15 tempat (judul halaman, tombol "Lanjut ke checkout", teks bantuan, `flash()`) |
| thread | Topik | Usulan | Masih dominan: sekitar 70 kemunculan di template (Thread Saya, Buat thread, kartu statistik). Perlu keputusan menyeluruh: apakah "Topik" juga menggantikan "Thread Solved" dan tab "Thread Saya" |
| Solved | Terjawab | Usulan | Dipakai sebagai lencana dan teks ("sudah Solved"); "belum-terjawab" sudah dipakai di URL pengurutan |
| login / logout | masuk / keluar | Sebagian | Tombol sudah "Masuk"/"Keluar", tetapi kalimat seperti "Login sebelumnya" dan "login pertama Anda" masih ada |
| password | kata sandi | Sebagian | Teks tampilan sudah "kata sandi"; "password" hanya tersisa pada atribut/identifier formulir |
| bookmark | tersimpan / simpan | Usulan | Masih ada di beberapa aria-label dan teks bantuan |
| dashboard | Beranda | Sudah | Hanya tersisa di komentar kode |
| Control Panel | -- | Dipertahankan | Nama fitur (judul Information System), bukan kata umum; ikut aturan nama aplikasi |
| Smart Landing | -- | Dipertahankan | Nama fitur; teks bantuannya memakai bahasa Indonesia |
| App Switcher | -- | Dipertahankan | Nama tombol 9 titik; label aksesibilitasnya "Pindah aplikasi" |

## Aturan penulisan singkat

1. Satu konsep, satu kata, di seluruh aplikasi. Bila istilah baku berubah, ubah di template, `flash()`,
   `empty_state`, `aria-label`, `<caption>`, judul kolom, opsi filter, dan judul halaman sekaligus.
2. Nama aplikasi (E-Learning, Forum, dst.) ditulis apa adanya dan tidak perlu diganti kata "aplikasi".
3. Bahasa sederhana, kalimat aktif, tanpa istilah teknis di menu dan tombol.
4. Jangan menulis istilah baru yang tidak ada di tabel ini tanpa menambahkannya di sini.

## Menjaga konsistensi

`tests/test_teks_ui.py` memindai template, `flash()`/teks tampilan di `app/`, dan JavaScript, lalu gagal bila
kata "modul" muncul lagi di teks tampilan. Pengecualian yang diizinkan didaftar eksplisit di tes itu.
