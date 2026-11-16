# Uji manual: tampil tanpa internet (Tailwind dan Inter lokal)

Persiapan: `python seed.py --reset` lalu `python run.py`. **Tidak perlu Node.** Bukan hanya "putuskan Wi-Fi": karena peramban
mungkin menyimpan cache CDN lama, lakukan uji ini dengan cache kosong (DevTools > Network > centang *Disable cache*).
Tes otomatis: `python -m unittest tests.test_security.StaticAssetsTests`.

| # | Langkah | Hasil yang diharapkan |
|---|---------|-----------------------|
| 1 | Matikan jaringan (mode pesawat / cabut kabel), muat ulang keras (Ctrl+Shift+R) `http://127.0.0.1:5000/` | Beranda tampil lengkap: Top-Bar biru, kartu 6 aplikasi, font Inter. Tab Network: **tidak ada** permintaan ke `cdn.tailwindcss.com`, `fonts.googleapis.com`, `fonts.gstatic.com`. |
| 2 | Tab Network, filter `tailwind` dan `inter` | `css/tailwind.css` dan `fonts/inter-latin-*.woff2` berstatus 200 dari `127.0.0.1`. |
| 3 | Konsol peramban | Tidak ada galat CSP atau `tailwind is not defined`. |
| 4 | Tema Light > Dark > Sistem, tombol Mobile/Desktop | Berfungsi; warna mengikuti token. |
| 5 | Lebar 360, 768, 1280 px pada Beranda, Forum, E-Commerce, Control Panel | Tata letak sama dengan sebelumnya (kolom grid, sidebar menjadi tab di layar sempit). |
| 6 | Buka halaman lain (E-Learning, E-Tutorial, Portal, login) | Semua bergaya. |
| 7 | Periksa sumber halaman (View Source) | Tidak ada `<script src="https://...">` maupun `tailwind.config`. Hanya satu skrip inline (tema anti-kedip) ber-`nonce`. |
