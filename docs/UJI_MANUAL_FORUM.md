# Uji manual Forum

Persiapan: `python seed.py --reset` lalu `python run.py`, buka http://127.0.0.1:5000/forum/.
Akun demo: `demo@dke.test` / `Demo12345` (penulis thread 3, punya 2 notifikasi balasan belum dibaca).
Akun admin dan akun komunitas (budi/citra/dewi/eko) dibuat seed; hanya admin dan demo yang bisa login (lihat README).
Tes otomatis: `python -m unittest tests.test_forum`.

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Buka `/forum/` sebagai Guest | 5 thread, tiap baris: kategori, judul, penulis, waktu, dilihat, **jumlah balasan**. Dua thread berlabel **Solved** (ikon centang + kata). Aksen teal. |
| 2 | Klik chip "Tanya Jawab Teknis" | Daftar menyempit (`?kategori=tanya-jawab-teknis`), chip aktif teal dengan `aria-current`. |
| 3 | Ketik `?kategori=ngawur` | Semua thread tampil, ada pesan "Kategori itu tidak dikenal". |
| 4 | Klik tab "Belum terjawab" | Hanya 3 thread tanpa solusi; yang paling sedikit balasannya di atas. Angka chip ikut berubah. "Terbaru" mengembalikan urutan semula. |
| 5 | Buka thread 3 ("Urutan belajar...") | Balasan berlekuk dengan garis utas teal: tingkat 1, 2, 3. Balasan ke-4 tingkat (Pengguna Demo > Budi) tampil sejajar tingkat 3 dengan keterangan "Membalas Budi Santoso" dan catatan "lebih dari 3 tingkat". |
| 6 | Sebagai Guest, lihat bagian bawah thread | Tidak ada form; ada ajakan "Masuk untuk membalas" yang kembali ke thread setelah login. Tidak ada tombol Balas/Ubah/Hapus. |
| 7 | Login sebagai demo, buka `/forum/buat` | Form kategori, judul, isi. |
| 8 | Kirim form kosong | Pesan inline di bawah tiap field (ikon + teks), field berborder merah, toast "Periksa kembali isian yang ditandai.", fokus ke field pertama yang salah. Tidak ada thread baru. |
| 9 | Judul `abc`, isi `pendek`, lalu perbaiki | Pesan "terlalu pendek" muncul saat meninggalkan field dan hilang saat sudah benar. Penghitung karakter bergerak. Setelah sah, thread dibuat dan Anda dibawa ke halamannya dengan toast sukses. |
| 10 | Matikan JavaScript, kirim form kosong | Server tetap menolak (422) dengan pesan yang sama dan isian dipertahankan. |
| 11 | Di thread orang lain, klik "Balas" pada sebuah balasan | Form balas **meluncur naik** tepat di bawah balasan itu, tertulis "Membalas <nama>: <kutipan>", fokus di kotak teks. "Batal membalas" atau tombol Esc mengembalikannya ke bawah. |
| 12 | Kirim balasan | Halaman memuat ulang ke balasan baru, yang muncul dengan animasi slide-up dan sorotan singkat; toast "Balasan terkirim." Muat ulang halaman: animasi tidak berulang. |
| 13 | Kirim balasan kosong atau `ab` | Pesan inline "Balasan tidak boleh kosong" / "terlalu pendek"; teks tidak hilang. |
| 14 | Login sebagai admin, balas thread milik demo (mis. thread 3); lalu login sebagai demo | Lonceng demo bertambah: "<nama admin> membalas thread Anda: ...", klik membuka thread tepat di balasannya. Beranda: widget Forum menghitung "N balasan baru". |
| 15 | Demo membalas thread milik sendiri | Tidak ada notifikasi baru. |
| 16 | Demo: Forum > Pengaturan > Notifikasi "Nonaktif" > Simpan; admin membalas thread demo lagi | Balasan tersimpan, tetapi demo tidak mendapat notifikasi baru. Setel "Aktif" untuk mengembalikan. |
| 17 | Demo membuka thread miliknya (thread 3, belum Solved), klik "Tandai sebagai solusi" pada satu balasan | Toast sukses, balasan berlencana "Solusi" dengan latar hijau, thread berlabel **Solved** (juga di daftar). Pilih balasan lain: solusi pindah. "Batalkan tanda solusi": kembali belum terjawab. |
| 18 | Login sebagai admin, buka thread milik demo | Tidak ada tombol "Tandai sebagai solusi". Kirim paksa lewat DevTools/curl: 403. |
| 19 | Demo: lihat balasan sendiri | Ada "Ubah" dan "Hapus" hanya pada balasan milik demo. |
| 20 | Ubah balasan sendiri | Form terisi teks lama; setelah disimpan kembali ke balasan itu dengan toast. Waktu kirim tidak berubah. |
| 21 | Buka `/forum/balasan/<id-balasan-orang-lain>/ubah` dan `/hapus` | Halaman 403 (juga untuk pemilik thread). POST paksa: 403, data tetap. |
| 22 | Hapus balasan sendiri yang punya balasan anak | Halaman konfirmasi menyebut jumlah balasan yang naik satu tingkat. Setelah dihapus, balasan anak tetap tampil. Menghapus balasan solusi mengembalikan thread ke belum terjawab. |
| 23 | Forum > Thread Saya | Hanya thread milik sendiri, dengan ringkasan "N thread, M Solved". Akun tanpa thread melihat empty state dengan tombol "Buat thread pertama". |
| 24 | Pengaturan: Privasi "Privat", simpan; buka `/forum/pengguna/<id-demo>` sebagai Guest/akun lain | "Profil ini privat"; bio dan ringkasan tidak tampil, nama tetap. Demo sendiri melihat profilnya dengan catatan. "Hanya anggota": Guest diminta masuk, anggota melihat profil. |
| 25 | Buat thread berjudul `<script>alert(1)</script>`, balasan `<img src=x onerror=alert(2)>`, ubah nama profil jadi `<b>x</b>` | Semua tampil sebagai teks literal di daftar, detail, Thread Saya, profil, dan lonceng; tidak ada pop-up. |
| 26 | Aktifkan Dark Mode, lalu Mobile View (atau lebar 360 px) | Teks terbaca, lekuk balasan menyempit, tidak ada gulir samping, tombol minimal 44 px. Aktifkan "kurangi gerak" di sistem: tidak ada animasi. |
| 27 | Log Aktivitas (Information System) | Baris "Buat thread", "Balas thread", "Tandai solusi", "Ubah balasan", "Hapus balasan", "Ubah pengaturan Forum". |
