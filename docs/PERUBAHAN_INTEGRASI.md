# Perubahan integrasi lintas modul

## Fitur
| Area | Perubahan | Berkas utama |
|---|---|---|
| Notifikasi | Tandai dibaca (satu/semua), modul + waktu di panel, API baru | `utils.py`, `main/api.py`, `static/js/notif.js`, `_components/topbar.html`, `base.html` |
| Smart Landing | Status aktif/nonaktif terlihat, teks tombol dan toast jelas | `main/index.html`, `static/js/launcher.js` |
| Statistik | Kuis lulus, Artikel Portal, Kategori favorit, Aktivitas; aktivitas per modul | `infosys/panel.py`, `infosys/routes.py`, `infosys/stats.html` |
| Pengaturan | `get_setting`/`set_setting` + pesan bersama; lima modul dialihkan; simpan tercatat di log | `module_settings.py`, `*/routes.py`, `infosys/panel.py` |
| Seed | Notifikasi balasan beruntun dari orang yang sama tertimpa, sehingga demo tanpa notifikasi belum dibaca; `created_at` kini ikut kunci | `seed.py` |

## Ketidakkonsistenan yang diperbaiki
- E-Commerce tidak ada di hierarki navigasi (tanpa breadcrumb/Kembali, tautan Kembali buatan sendiri): node ditambah, tautan dobel dihapus.
- Judul halaman: `text-2xl` (Information System, Beranda, detail pesanan) vs `text-3xl` modul lain: disamakan ke `text-3xl font-bold tracking-tight`.
- Teks galat form: `red-600` vs `red-700`: disamakan.
- Kalimat CSRF punya dua versi: satu `utils.MSG_CSRF`.
- Tab Pengaturan: kartu/lebar (E-Commerce, E-Learning), judul tab E-Commerce, label tombol Portal, kalimat sukses/gagal.

## Sengaja dibiarkan
- CSS tombol dasar terduplikasi (`.btn`, `.el-btn`, `.et-btn`, `.pt-btn`, `.fm-btn`, `.ecom-button`) dengan ukuran sama; hanya warna aksen yang berbeda. Menyatukannya butuh refaktor lebih besar.
- `fm-btn:disabled` memakai kursor "progress" (status sibuk).
- `quiz.js` memakai `window.confirm` hanya sebagai cadangan peramban tanpa `<dialog>`.
- Empty state mini inline (garis putus) vs makro `empty_state` halaman penuh.

## Tes
`tests/test_integration.py` (23 tes baru). Diubah: ekspektasi kartu statistik di `test_panel.py`; dua pernyataan `test_ecommerce.py` dipersempit ke log `checkout`.
