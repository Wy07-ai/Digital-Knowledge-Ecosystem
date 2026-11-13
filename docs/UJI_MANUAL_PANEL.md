# Uji manual Control Panel (UC-IS-04..08)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/infosys/ , masuk sebagai `demo@dke.test` / `Demo12345`.

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Buka `/infosys/` sebagai Guest | Ajakan "Masuk untuk membuka Control Panel", tanpa sidebar |
| 2 | Masuk sebagai demo, buka `/infosys/` | Sidebar 5 tab, tab Ringkasan aktif (garis indigo), kartu akun, statistik singkat, aktivitas terbaru |
| 3 | Tab Profil: kosongkan nama, isi bio 301 karakter, avatar `javascript:x`, klik Simpan | Kirim dibatalkan, toast merah "Periksa kembali isian yang ditandai.", tiga pesan inline, fokus ke Nama |
| 4 | Perbaiki isian, tempel tautan gambar https valid di avatar | Pratinjau avatar berubah; bila tautan rusak, inisial tetap tampil |
| 5 | Simpan profil | Toast hijau "Profil berhasil disimpan."; data bertahan setelah muat ulang; tercatat di Log Aktivitas |
| 6 | Simpan tanpa mengubah apa pun | Toast biru "Tidak ada perubahan untuk disimpan." |
| 7 | Ganti kata sandi dengan sandi lama salah | Pesan inline di kolom "Kata sandi saat ini" + toast merah |
| 8 | Ganti kata sandi: baru = lama / kurang 8 karakter / konfirmasi beda | Pesan inline sesuai tiap kasus |
| 9 | Salah 5 kali berturut-turut, lalu coba dengan sandi benar | Toast "Terlalu banyak percobaan..." (kunci 5 menit) |
| 10 | Ganti kata sandi dengan benar | Toast hijau, tetap masuk, notifikasi muncul di lonceng, baris "Ubah kata sandi" di log |
| 11 | Tab Log Aktivitas: pilih modul "Forum" | Tabel hanya baris Forum; tombol "Hapus filter" muncul; pilih modul tanpa data memberi empty state |
| 12 | Buat 11+ baris log (mis. berkali-kali login/logout) lalu buka halaman 2 | Paginasi "Menampilkan 11-N dari M", filter ikut terbawa di tautan |
| 13 | Ubah URL jadi `?halaman=999` atau `?modul=ngawur` | Halaman terakhir ditampilkan / catatan "Filter modul tidak dikenal" |
| 14 | Tab Statistik: bandingkan dengan akun baru tanpa data | Demo: kartu terisi + progres kelas; akun baru: empty state "Belum ada statistik" |
| 15 | Tab Pengaturan Keamanan | Login terakhir, total login, tabel riwayat login (baris terbaru berlencana "Terbaru") |
| 16 | Masuk sebagai akun lain, coba `?user_id=1` di semua tab | Data tetap milik akun yang sedang login |
| 17 | Aktifkan Mobile View (tombol di Top-Bar) | Sidebar menjadi tab horizontal yang bisa digeser; tabel bisa digeser horizontal |
| 18 | Ganti ke tema Gelap | Semua kartu, tabel, dan sidebar tetap terbaca (token warna) |
