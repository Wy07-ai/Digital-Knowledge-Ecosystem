# Perancangan Antarmuka — micro-interactions

Dokumen ini menjadi catatan desain antarmuka di repositori untuk Blueprint 5.4. Aturan implementasi berada di `app/static/css/custom.css`.

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
