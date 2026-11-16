# Uji manual transisi tema (circular reveal)

Prasyarat: `python seed.py --reset && python run.py`, buka http://127.0.0.1:5000/ memakai Chrome/Edge terbaru (mendukung View Transitions API). Berkas terkait: `app/static/js/theme.js`, bagian transisi tema di `app/static/css/custom.css`.

Tes otomatis: `python -m unittest tests.test_theme_transition -v` (pemeriksaan fallback, rumus lingkaran, kunci tombol; bagian perilaku memakai Node dan dilewati bila Node tidak ada).

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Guest, tema Terang. Klik ikon tema di bilah atas, pilih "Gelap" | Lingkaran warna gelap tumbuh dari ikon tema, melebar ke seluruh layar (sekitar 0,5-0,6 detik), lalu berhenti penuh |
| 2 | Ulangi, pilih "Terang" | Lingkaran terang tumbuh dari ikon yang sama (bukan menyusut) |
| 3 | Amati awal dan akhir transisi | Tidak ada kedip putih/hitam sebelum lingkaran mulai maupun setelah selesai |
| 4 | Amati ikon matahari/bulan | Ikon berputar sambil membesar dan berganti, mulus |
| 5 | Klik cepat ikon lalu pilihan tema berulang kali saat lingkaran masih tumbuh | Klik tambahan diabaikan; transisi selesai satu kali tanpa tema "tersangkut" |
| 6 | Aktifkan Mobile View (tombol Mobile), ulangi langkah 1-3 | Lingkaran tetap tumbuh dari ikon dan menutupi seluruh layar, termasuk area di luar bingkai |
| 7 | Perkecil jendela hingga lebar ponsel (<768 px), ulangi | Sama seperti langkah 6 |
| 8 | Muat ulang halaman setelah memilih Gelap | Halaman langsung gelap tanpa kedip (skrip anti-kedip di `base.html` tidak berubah) |
| 9 | Pilih "Sistem" saat OS bertema sama dengan tema sekarang | Tema berganti tanpa lingkaran (warna tidak berubah); centang menu pindah ke "Sistem" |
| 10 | Pilih "Sistem", lalu ubah tema OS | Tema ikut berubah langsung tanpa lingkaran (efek hanya untuk klik manual) |
| 11 | Aktifkan "Reduce motion" di OS (Windows: Efek animasi nonaktif), ulangi langkah 1 | Tema berganti langsung, tanpa lingkaran dan tanpa ikon berputar |
| 12 | Firefox lama / Safari tanpa View Transitions (atau di konsol: `document.startViewTransition = undefined` sebelum klik) | Tema berganti langsung seperti sebelumnya; tidak ada galat di konsol |
| 13 | Guest: setelah mengganti tema, buka DevTools > Application > Local Storage | `dke-theme` berisi `light`/`dark`/`system` sesuai pilihan |
| 14 | Masuk sebagai `demo@dke.test` / `Demo12345`, ganti tema, lihat tab Network | Satu `POST /api/settings/global` berisi `{"theme": ...}`; setelah muat ulang tema bertahan dari database |
| 15 | Member: putuskan jaringan (DevTools > Offline), ganti tema | Setelah gagal simpan: tema kembali ke nilai sebelumnya tanpa lingkaran, toast merah muncul |
