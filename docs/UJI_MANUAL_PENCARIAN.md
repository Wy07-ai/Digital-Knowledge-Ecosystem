# Uji manual pencarian terpadu (/cari)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/ di Chrome/Edge. Uji sebagai Guest dan sebagai Member
(akun seed, lihat [`PANDUAN_FITUR_APLIKASI.md`](PANDUAN_FITUR_APLIKASI.md#database-dan-data-contoh)). Berkas terkait:
`app/search.py` (kueri), rute `main.search` di `app/main/routes.py`, `app/templates/main/search.html`,
`app/templates/_components/search_trigger.html`, `app/static/js/search.js`, dan `app/static/css/custom.css` (bagian 6 dan 6a).

Tes otomatis: `python -m unittest tests.test_search -v`, lalu `python -m unittest discover -s tests` sebelum PR.

Cara menguji dua mode tampilan:
- **Layar sempit**: biarkan Mobile View mati, lalu atur lebar jendela atau DevTools Device Toolbar (di bawah 768 px).
- **Mobile View di desktop**: jendela 1280 px, klik tombol "Mobile" di bilah atas (`data-view='mobile'`). Lebar viewport tetap 1280 px,
  jadi kelas responsif Tailwind (`md:`) tidak berlaku; karena itu pencarian memakai `dke-hide-mobile` dan `dke-show-mobile`.

Daftar periksa untuk setiap baris: tidak ada teks yang saling menimpa atau terpotong, tidak ada gulir horizontal, target sentuh
minimal 44 px, dan kontras terbaca di tema Terang dan Gelap.

## Bilah atas

| # | Lebar | Mode tampilan | Akun | Langkah | Hasil yang diharapkan |
|---|-------|---------------|------|---------|-----------------------|
| 1 | 1280 px | Mobile View mati | Guest | Buka `/` | Di bilah atas, sebelum tombol tema, ada kolom pencarian dengan ikon kaca pembesar dan petunjuk "Cari kelas, produk, tutorial..."; tidak ada tombol ikon terpisah |
| 2 | 1280 px | Mobile View mati | Member | Buka `/` | Kolom pencarian sama; tombol tema, Mobile, lonceng, dan profil tetap tampil dan tidak terdorong keluar bilah |
| 3 | 1280 px | Mobile View mati | Guest | Klik kolom pencarian | Kolom melebar dengan halus, latar menjadi putih, ada cincin fokus putih; petunjuk tetap terbaca |
| 4 | 1280 px | Mobile View mati | Guest | Tekan Tab dari tombol DKE sampai ke kolom | Kolom bisa difokus keyboard; cincin fokus tampak jelas |
| 5 | 1280 px | Mobile View mati | Guest | Tekan `/` di halaman mana pun (fokus di luar kolom isian) | Fokus pindah ke kolom pencarian dan isinya terpilih |
| 6 | 1280 px | Mobile View mati | Member | Buka `/forum/buat`, klik kolom judul topik, ketik `/` | Karakter `/` masuk ke kolom judul; fokus tidak direbut |
| 7 | 1280 px | Mobile View mati | Guest | Ketik `kelas` lalu tekan Enter | Peramban membuka `/cari?q=kelas`; kolom di bilah atas tetap berisi `kelas` |
| 8 | 1280 px | Mobile View mati | Guest | Buka `/ecommerce/` | Kolom pencarian tampil dan menuju `/cari`; judul aplikasi di bilah atas tetap terbaca (terpotong dengan elipsis bila sempit) |
| 9 | 1280 px | Mobile View nyala | Guest | Klik "Mobile" | Kolom pencarian hilang; muncul tombol ikon kaca pembesar di sisi kanan, sebelum tombol tema |
| 10 | 1280 px | Mobile View nyala | Guest | Klik tombol ikon | Membuka `/cari` dengan kata kunci kosong; kursor langsung berada di kolom pencarian halaman |
| 11 | 1280 px | Mobile View nyala | Guest | Tekan `/` di luar kolom isian | Karakter tidak diambil alih (kolom bilah atas tersembunyi), tidak ada galat |
| 12 | 360, 390, 430 px | Layar sempit | Guest dan Member | Buka `/` | Hanya tombol ikon yang tampil (tanpa kolom); tingginya minimal 44 px; bilah atas tidak meluap |
| 13 | 360 px | Layar sempit | Guest | Buka `/cari` | Di atas hasil ada kolom pencarian halaman dengan tombol "Cari"; kursor sudah di dalam kolom (autofokus) |
| 14 | 1280 px | Mobile View nyala lalu mati | Guest | Klik "Mobile" dua kali | Bilah atas kembali menampilkan kolom pencarian |
| 15 | 1280 px | Mobile View mati | Guest | Aktifkan pembaca layar, buka `/` | Kolom diumumkan sebagai pencarian dengan label "Cari kelas, produk, tutorial, artikel, atau topik"; tombol ikon (mobile) diumumkan "Cari" |

## Halaman hasil

Siapkan data dengan kata kunci yang ada di seed, mis. `python` (kelas, tutorial, topik) atau `belajar`.

| # | Skenario | Langkah | Hasil yang diharapkan |
|---|----------|---------|-----------------------|
| 16 | Guest bisa mencari | Tanpa masuk, buka `/cari?q=python` | Status 200; hasil dikelompokkan per jenis; tiap kelompok punya ikon dan warna aksen aplikasinya |
| 17 | Member bisa mencari | Masuk, ulangi baris 16 | Hasil sama dengan Guest |
| 18 | Label kelompok | Cari kata yang ada di semua jenis | Label berturut-turut: Kelas (E-Learning), Produk (E-Commerce), Tutorial (E-Tutorial), Artikel (Portal), Topik (Forum). Forum berlabel "Topik", bukan nama lain |
| 19 | Tiap hasil menaut ke detail | Klik satu hasil per jenis | Kelas membuka `/elearning/kelas/<id>`, produk `/ecommerce/produk/<slug>`, tutorial `/etutorial/tutorial/<slug>`, artikel `/portal/artikel/<slug>`, topik `/forum/thread/<id>`; semuanya status 200 |
| 20 | Kata kunci disorot | Cari `python` | Kata yang cocok pada judul dan cuplikan tampil tebal dengan latar aksen; huruf besar/kecil tidak berpengaruh |
| 21 | Kata kunci kosong | Buka `/cari` atau `/cari?q=` | Empty state "Cari di seluruh DKE" dengan satu kalimat dan satu tombol; tidak ada hasil |
| 22 | Hanya spasi | Buka `/cari?q=%20%20` | Sama seperti baris 21 |
| 23 | Kata kunci terlalu pendek | Cari `a` | Empty state "Kata kunci terlalu pendek" dengan petunjuk minimal 2 karakter; tidak ada hasil |
| 24 | Tanpa hasil | Cari `zzqxkv` | Empty state "Tidak ada hasil untuk “zzqxkv”" dengan saran mengganti kata kunci; hanya satu empty state |
| 25 | Pembatasan jumlah | Cari kata yang cocok dengan lebih dari 5 kelas (mis. `belajar`) | Tiap jenis menampilkan maksimal 5 hasil; ada tautan "Lihat semua N hasil <jenis>" bila lebih |
| 26 | Filter jenis | Klik chip "Kelas" (atau buka `/cari?q=belajar&jenis=kelas`) | Hanya kelompok Kelas yang tampil, sampai 20 hasil; chip "Kelas" bertanda aktif; angka di chip tetap jumlah sebenarnya |
| 27 | Jenis tak dikenal | Buka `/cari?q=python&jenis=hantu` | Catatan "Jenis hasil itu tidak dikenal, jadi semua jenis dicari."; semua kelompok tampil |
| 28 | Jenis tanpa kecocokan | Cari `python` dengan `jenis=produk` (bila produk tidak cocok) | Empty state "Tidak ada produk yang cocok" dengan tombol "Lihat semua hasil" |
| 29 | Kata kunci panjang | Tempel 150 karakter ke kolom lalu kirim | Kolom hanya menerima 100 karakter (`maxlength`); `/cari?q=` dengan 150 karakter tetap berhasil dan dipotong di server |
| 30 | Breadcrumb dan Kembali | Buka `/cari?q=python` | Di atas judul ada tombol "Kembali ke Beranda" dan jejak halaman "Beranda > Pencarian"; tombol Kembali membuka `/` |
| 31 | Tanpa JavaScript | Matikan JavaScript di peramban, ketik kata di kolom bilah atas, tekan Enter | Pencarian tetap berjalan (formulir GET); halaman hasil tampil lengkap |

## Konten tersembunyi dan keamanan

| # | Skenario | Langkah | Hasil yang diharapkan |
|---|----------|---------|-----------------------|
| 32 | Kelas belum terbit | Di `instance/dke.db`: `UPDATE courses SET is_published = 0 WHERE id = 1;` lalu cari judul kelas itu | Kelas tidak muncul di hasil, tidak ikut terhitung di chip dan jumlah. Kembalikan: `SET is_published = 1` |
| 33 | Produk tidak aktif | `UPDATE products SET is_active = 0 WHERE id = 1;` lalu cari namanya | Produk tidak muncul dan tidak terhitung. Kembalikan: `SET is_active = 1` |
| 34 | Persen sebagai teks biasa | Buat kelas berjudul `Diskon 100% Hemat` dan `Diskon 1000 Hemat`, cari `100%` | Hanya yang berjudul `100%` yang muncul (bukan keduanya) |
| 35 | Garis bawah sebagai teks biasa | Buat judul `snake_case` dan `snakeXcase`, cari `snake_case` | Hanya `snake_case` yang muncul |
| 36 | Garis miring terbalik | Cari `c:\` (kata kunci minimal 2 karakter) | Tidak ada galat 500; hanya judul atau cuplikan yang memuat `c:\` yang cocok |
| 37 | Hanya wildcard | Cari `%%`, `__`, dan `%_` | Tidak ada hasil (bukan semua data) |
| 38 | Skrip tidak dijalankan | Cari `<script>alert(1)</script>` | Tidak ada kotak peringatan; kata kunci tampil sebagai teks di kolom, judul "Tidak ada hasil untuk ...", dan catatan jumlah; sumber halaman memuat `&lt;script&gt;` |
| 39 | Skrip dari konten | Buat topik Forum berisi `<script>alert(1)</script>` lalu cari `alert` | Cuplikan menampilkan teks tag apa adanya; tidak ada kotak peringatan |
| 40 | Kutip di kata kunci | Cari `" autofocus onfocus=alert(1) x="` | Kolom hanya berisi teks tersebut; tidak ada kotak peringatan dan atribut baru tidak muncul |
| 41 | Tanpa data akun | Cari email seed (mis. `rina@dke.test`) dan nama pengguna | Tidak ada hasil; email dan data akun tidak pernah tampil |
| 42 | Isi artikel tidak dicari | Cari kata yang hanya ada di isi artikel (bukan judul atau kutipan) | Artikel itu tidak muncul |
| 43 | Tema Gelap | Ganti ke tema Gelap, ulangi baris 16, 20, dan 3 | Teks, sorotan, chip, dan kolom pencarian bilah atas terbaca; tidak ada teks gelap di atas latar gelap |
| 44 | Reduce motion | Aktifkan "Reduce motion" di OS, fokuskan kolom bilah atas | Kolom langsung berubah tanpa animasi lebar |
