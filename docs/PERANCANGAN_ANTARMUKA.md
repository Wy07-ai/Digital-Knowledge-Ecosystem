# Perancangan Antarmuka — micro-interactions

Dokumen ini menjadi catatan desain antarmuka di repositori untuk Blueprint 5.4. Aturan implementasi berada di `app/static/css/custom.css`.

## Token visual

| Token | Nilai | Pemakaian |
|---|---|---|
| `--c-header-deep` | `19 39 85` (`#132755`) | Awal gradien Top-Bar dan hero |
| `--c-header` | `30 58 138` (`#1E3A8A`) | Deep Blue ekosistem |
| `--radius-card` | `1.25rem` | Hero, kartu Beranda, empty state |
| `--radius-control` | `.875rem` | Kontrol Top-Bar |
| Radius `.btn` | `.5rem` | Tombol bersama lintas aplikasi |
| `--shadow-card` | Berlapis, lembut | Permukaan kartu dan empty state |
| `--text-hero` | `clamp(2rem, 4vw, 3rem)` | Judul hero responsif |
| `--text-page` | `clamp(1.75rem, 3vw, 2.25rem)` | Judul halaman |
| `--text-section` | `1.25rem` | Judul bagian |

Warna aksen kartu mengikuti warna tiap aplikasi; nama dan deskripsi tetap tertulis agar warna bukan satu-satunya pembeda. Hero memakai teks putih di atas Deep Blue, sedangkan latar dan teks isi mengikuti token Light/Dark yang sudah ada. Body tetap 16 px dengan line-height 1.6.

## Komponen bersama

Komponen dasar didefinisikan satu kali di `app/static/css/custom.css`; template memakai kelas bersama, sementara warna disetel lewat `--accent`, `--accent-action`, `--accent-action-hover`, `--accent-soft`, dan `--accent-text` pada `body[data-app-key]`.

| Komponen | Kelas dasar dan varian |
|---|---|
| Tombol | `.btn`, `.btn--primary`, `.btn--secondary`, `.btn--ghost`, `.btn--danger` |
| Kartu | `.card`, `.card--accent`, `.card--edge-left`, `.card--lift`, `.card--clickable` |
| Badge | `.badge`, `.badge--accent`, `.badge--solid`, `.badge--outline`, `.badge--muted`, `.badge--success`, `.badge--warning` |
| Filter | `.chip`, `.chip.is-active` |
| Isian | `.field`, termasuk fokus dan keadaan `aria-invalid` |

Aksen aplikasi: E-Commerce `#92400E`, E-Learning `#2563EB`, E-Tutorial `#7C3AED`, Portal `#E11D48`, dan Forum `#0D9488`. Tombol aktif memakai warna aksi dengan kontras teks putih yang memadai; warna teks/aksen menyesuaikan tema gelap. Badge status sukses/peringatan memakai varian semantik, tidak bergantung hanya pada warna.

Modul tetap boleh memakai kelas khusus untuk fungsi yang tidak sama dengan komponen dasar, seperti status Solved dan avatar Forum, progress E-Learning, serta pengaturan ukuran huruf E-Tutorial. Target sentuh tombol dan filter minimal 44 px; tombol Forum yang nonaktif mempertahankan kursor `progress`.

## Polesan halaman

- Hero Beranda berupa carousel lima aplikasi (E-Learning, E-Commerce, E-Tutorial, Portal, Forum) dengan satu tombol per slide dan ikon aplikasi dekoratif. Sapaan sesuai status Guest/Member dan tombol Lanjutkan berada di strip tipis tepat di bawahnya.
- Kartu Beranda adalah kartu fitur: area visual berlatar gradien warna aksen yang lembut dengan ikon besar di tengah, judul, dan satu baris metrik. Deskripsi aplikasi tidak tampil; ia ada di `title` dan `aria-describedby`.
- Top-Bar menampilkan ikon Beranda dan ikon aplikasi aktif, serta menyamakan ukuran aksi Masuk/Daftar dengan gaya sekunder/primer.
- Empty state memakai bidang ilustrasi berbasis SVG inline dan aksen modul dengan tetap mempertahankan judul, pesan, serta aksi yang jelas.

## Token gerak

| Token | Nilai | Pemakaian |
|---|---|---|
| `--ease-out` | `cubic-bezier(.16, 1, .3, 1)` | Gerak masuk dan umpan balik |
| `--dur-fast` | `180ms` | Hover/fokus, kontrol, popover |
| `--dur-base` | `240ms` | Masuk kartu dan perubahan progres |
| Jeda kartu | `50ms` per kartu | Stagger pada grid Beranda dan daftar |

Animasi baru hanya mengubah `transform` dan `opacity`; perubahan visual lain tidak mengubah alur layout. Tombol tetap dapat digunakan tanpa menunggu animasi. Hover lift hanya aktif pada perangkat yang mendukung hover. Aturan global `prefers-reduced-motion: reduce` meniadakan animasi dan transisi.

## Pola yang diterapkan

- Kartu di grid Beranda, kelas, produk, artikel, tutorial, forum, dan statistik masuk dengan fade-in serta pergeseran vertikal 10 px.
- Kartu dapat naik tipis saat hover atau fokus di dalamnya; tombol mempertahankan umpan balik tekan.
- Garis bawah navigasi tumbuh menggunakan `transform`.
- Progres E-Learning dan E-Tutorial mengisi dengan `scaleX`, bukan animasi lebar, dan centang materi selesai mendapat umpan balik skala singkat.
- App Switcher, menu tema, notifikasi, dan profil memakai fade/scale saat dibuka dan ditutup. Saat reduced motion aktif, panel langsung ditutup.

## Verifikasi manual

1. Pada Beranda dan daftar kelas/produk/artikel/thread, pastikan kartu masuk berurutan dengan jarak yang singkat.
2. Pada perangkat ber-hover, uji hover kartu; pada ponsel atau Mobile View, pastikan kartu tidak tertinggal dalam keadaan terangkat.
3. Uji tombol melalui klik/tekan dan tautan navigasi dengan mouse serta keyboard.
4. Di E-Learning, tandai materi selesai dan batalkan; progress harus bergerak halus dan ikon centang memberi umpan balik.
5. Buka dan tutup App Switcher, tema, notifikasi, dan profil; uji pula Escape dan klik di luar panel.
6. Aktifkan pengaturan **Reduce motion** pada sistem/peramban, muat ulang, lalu ulangi langkah 1–5. Tidak boleh ada gerakan yang terlihat dan semua kontrol harus tetap langsung berfungsi.
7. Ulangi langkah-langkah tersebut dalam Mobile View dan pada lebar viewport ponsel.

Repositori ini tidak menyimpan sumber wiki eksternal; halaman ini mencatat token dan pola yang perlu disalin ke halaman wiki **Perancangan Antarmuka** saat wiki diperbarui.
