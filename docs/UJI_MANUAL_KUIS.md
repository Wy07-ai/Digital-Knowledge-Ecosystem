# Uji manual E-Learning bagian 2: kuis (UC-EL-05, UC-EL-06)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/elearning/ .
Akun: `demo@dke.test` / `Demo12345` (terdaftar di kelas gratis "Prinsip Desain Antarmuka", kuis 5 soal, nilai lulus 70).

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Sebagai Guest buka `/elearning/kelas/<id>/kuis` | Diarahkan ke login (`?next=`) |
| 2 | Masuk sebagai demo, buka detail kelas yang diikuti | Tombol "Kerjakan kuis" dengan keterangan jumlah soal dan nilai lulus |
| 3 | Buka halaman kuis kelas yang belum diikuti (mis. kelas berbayar) | Kembali ke detail kelas + toast merah "Anda belum terdaftar..." |
| 4 | Buka halaman kuis | Hanya satu soal tampil; indikator nomor 1-5 di atas; teks "Soal 1 dari 5 · terjawab 0 dari 5"; Sebelumnya nonaktif |
| 5 | Pilih jawaban, klik Selanjutnya | Pindah ke soal 2; nomor 1 berwarna "terjawab"; nomor 2 aktif |
| 6 | Klik nomor 4 pada indikator | Melompat ke soal 4 |
| 7 | Pada soal terakhir | Tombol Selanjutnya berganti Kumpulkan |
| 8 | Jawab soal 1 saja, muat ulang halaman (F5) | Kembali ke soal yang sama, jawaban terpilih tetap ada (disimpan di browser) |
| 9 | Buka DevTools > Application > Local Storage | Ada kunci `dke:quiz:<id pengguna>:<id kuis>` berisi jawaban |
| 10 | Klik Kumpulkan dengan soal kosong | Dialog "Masih ada soal yang kosong" menyebut nomor yang kosong |
| 11 | Klik "Periksa lagi" | Dialog tertutup, langsung ke soal kosong pertama |
| 12 | Kumpulkan lagi, klik "Kumpulkan sekarang" | Terkirim sekali (tombol nonaktif), pindah ke halaman hasil |
| 13 | Halaman hasil, jawaban kurang dari batas lulus | "Belum lulus", nilai besar, "Benar X dari 5", pembahasan tiap soal (Benar/Salah/Tidak dijawab, jawaban benar, jawaban Anda, penjelasan), tombol **Coba Lagi** |
| 14 | Cek Local Storage setelah halaman hasil terbuka | Kunci kuis sudah terhapus |
| 15 | Klik Coba Lagi | Kuis mulai dari soal 1 tanpa jawaban terisi |
| 16 | Kerjakan sampai nilai >= 70, kumpulkan | "Lulus"; kelas ditandai selesai, progres 100%; detail kelas menampilkan "5 dari 5 materi · 100%"; ada notifikasi "Kelas selesai" di lonceng |
| 17 | Setelah lulus, buka `/infosys/log` | Ada baris "Lulus kuis" (dan "Kuis belum lulus" untuk percobaan gagal) |
| 18 | Lulus lagi di percobaan berikutnya | Tanggal selesai kelas tidak berubah; tidak ada notifikasi kedua |
| 19 | Nilai sebelumnya lulus, sekarang sengaja gagal | Kelas tetap selesai (status lulus tidak dicabut) |
| 20 | **Anti-bocor:** pada halaman kuis, klik kanan > View Source, cari `correct`, nama pembahasan, atau kata dari penjelasan | Tidak ada kunci jawaban maupun penjelasan di HTML. Opsi benar tidak bisa dibedakan dari pengecoh |
| 21 | Di DevTools > Network lihat permintaan Kumpulkan | Payload hanya `csrf_token` dan `q_<id>=a/b/c/d`, tanpa skor |
| 22 | Ubah isi form lewat DevTools: tambah field `score=100` lalu kumpulkan | Nilai tetap dihitung server dari jawaban; field tambahan diabaikan |
| 23 | Buka URL hasil milik pengguna lain (ganti angka `hasil/<id>`) | 404 |
| 24 | Matikan JavaScript, buka halaman kuis | Semua soal tampil berurutan; tombol "Kumpulkan jawaban" tetap bisa dipakai |
| 25 | Mobile View / layar sempit, mode gelap | Indikator nomor membungkus rapi; opsi dan hasil tetap terbaca; Benar/Salah punya ikon dan teks, bukan hanya warna |
| 26 | Navigasi: tombol Kembali dan breadcrumb | Kuis: E-Learning > judul kelas > Kuis; hasil: ... > Kuis > Hasil Kuis; Kembali menuju induk langsung |
