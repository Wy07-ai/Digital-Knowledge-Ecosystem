# Panduan Kontribusi

Terima kasih sudah tertarik berkontribusi pada Digital Knowledge Ecosystem (DKE). Panduan ini menjelaskan alur kerja
dan aturan khusus proyek ini. Dengan berkontribusi, Anda setuju mematuhi [Kode Etik](CODE_OF_CONDUCT.md), dan
kontribusi Anda dilisensikan di bawah [Lisensi MIT](LICENSE).

## Daftar isi

- [Persiapan lingkungan](#persiapan-lingkungan)
- [Alur Git: satu branch per fitur atau issue](#alur-git-satu-branch-per-fitur-atau-issue)
- [Penamaan istilah: "aplikasi" di antarmuka, `module_key` di kode](#penamaan-istilah-aplikasi-di-antarmuka-module_key-di-kode)
- [Mengubah tampilan: wajib build `tailwind.css`](#mengubah-tampilan-wajib-build-tailwindcss)
- [Keamanan: CSP `nonce` dan autoescape Jinja](#keamanan-csp-nonce-dan-autoescape-jinja)
- [Menjalankan tes sebelum PR atau merge](#menjalankan-tes-sebelum-pr-atau-merge)
- [Checklist pull request](#checklist-pull-request)
- [Melaporkan masalah keamanan](#melaporkan-masalah-keamanan)

## Persiapan lingkungan

Ikuti bagian *Quick Start (Menjalankan)* di [`README.md`](README.md#quick-start-menjalankan). Ringkasnya:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py
FLASK_DEBUG=1 python run.py      # debug hanya untuk komputer sendiri
```

Node.js hanya dibutuhkan bila Anda mengubah kelas Tailwind (lihat bagian build CSS di bawah).
Detail arsitektur ada di [`docs/ARSITEKTUR_DAN_KEAMANAN.md`](docs/ARSITEKTUR_DAN_KEAMANAN.md) dan rincian fitur di
[`docs/PANDUAN_FITUR_APLIKASI.md`](docs/PANDUAN_FITUR_APLIKASI.md).

## Alur Git: satu branch per fitur atau issue

1. Buat atau pilih issue yang menjelaskan perubahan.
2. Perbarui cabang utama, lalu buat **satu branch per fitur atau issue**:

   ```bash
   git checkout main
   git pull
   git checkout -b fitur/forum-filter-tanggal      # atau perbaikan/login-429, dokumen/perbarui-readme
   ```

   Awalan yang disarankan: `fitur/`, `perbaikan/`, `dokumen/`, `refaktor/`, `tes/`. Gunakan huruf kecil dan tanda hubung.
3. Buat commit kecil dan fokus dengan pesan yang jelas (Bahasa Indonesia atau Inggris, konsisten dalam satu PR),
   misalnya `Forum: tambah filter tanggal pada daftar thread`.
4. Jangan mencampur beberapa fitur atau issue tak terkait dalam satu branch.
5. Jalankan tes (lihat di bawah), dorong branch, lalu buka pull request ke cabang utama dan tautkan issue-nya.
6. Jangan men-commit rahasia: `.env`, `instance/*`, berkas `*.db`, atau nilai `DKE_SECRET_KEY`.

## Penamaan istilah: "aplikasi" di antarmuka, `module_key` di kode

- **Teks yang dilihat pengguna** menyebut tiap bagian DKE sebagai **aplikasi** (bukan "modul"): Information System,
  E-Commerce, E-Learning, E-Tutorial, Portal, Forum.
- **Kode tetap memakai** `module_key`, `MODULES`, `MODULE_BY_KEY`, `current_module`, tabel `module_settings`, serta nama
  paket dan blueprint. Jangan diganti nama.
- Semua istilah baku, keputusan penamaan, istilah Inggris yang dihindari, panduan gaya (nada, "Anda", subjudul
  maksimal 15 kata, empty state satu kalimat, pesan galat dengan solusi), dan katalog pesan ada di
  [`docs/GLOSARIUM_TEKS.md`](docs/GLOSARIUM_TEKS.md). **Baca berkas itu sebelum menulis atau mengubah teks tampilan.**
- Kalimat yang dipakai bersama ditulis sekali di `app/messages.py`, jangan diduplikasi.
- Untuk meninjau teks tampilan: `python scripts/inventaris_teks.py --cari "kata"`. Tes `tests/test_teks_ui.py`
  menjaga aturan ini.

## Mengubah tampilan: wajib build `tailwind.css`

`app/static/css/tailwind.css` adalah hasil build yang **di-commit ke Git** agar aplikasi berjalan tanpa Node dan
tanpa internet. Bila Anda menambah atau mengubah kelas Tailwind di templat (`app/templates/**/*.html`), JS
(`app/static/js/**/*.js`), atau Python (`app/**/*.py`):

```bash
npm install            # sekali saja
npm run build:css
```

lalu **commit `app/static/css/tailwind.css` bersama perubahan Anda**. Jangan mengedit berkas itu dengan tangan.

- Tulis nama kelas **utuh** (`'bg-red-600'`), jangan dirangkai (`'bg-' + warna`), atau daftarkan di `safelist` pada
  `tailwind.config.js`.
- Jangan memindahkan urutan pemuatan `tailwind.css` di `base.html`.
- Tes `tests.test_security.StaticAssetsTests` gagal bila build basi untuk kelas inti.

Rincian: [`docs/ARSITEKTUR_DAN_KEAMANAN.md`](docs/ARSITEKTUR_DAN_KEAMANAN.md#build-css-tailwind-blueprint-67).

## Keamanan: CSP `nonce` dan autoescape Jinja

- **Skrip inline wajib ber-`nonce`**: `<script nonce="{{ csp_nonce() }}">`. Atribut event (`onclick="..."`) dan URL
  `javascript:` diblokir oleh Content-Security-Policy; pasang handler lewat berkas JS di `app/static/js/`.
- **Jangan melonggarkan CSP** dan jangan memuat skrip, stylesheet, atau font dari CDN. Semua aset dilayani dari
  berkas sendiri.
- **Jangan memakai `|safe` atau `Markup`** pada teks dari database atau masukan pengguna. Biarkan autoescape Jinja
  bekerja. Di JavaScript, gunakan `textContent`, bukan `innerHTML`, untuk isi dari pengguna. Tes memindai templat dan
  skrip untuk menjaga aturan ini.
- Setiap `POST` harus memeriksa **token CSRF**, memakai kueri SQL **berparameter**, dan memeriksa hak akses di server
  (bukan hanya menyembunyikan tombol).
- Id pengguna selalu diambil dari sesi, tidak pernah dari query string atau form.

Rincian: [`docs/ARSITEKTUR_DAN_KEAMANAN.md`](docs/ARSITEKTUR_DAN_KEAMANAN.md#cookie-sesi-dan-header-keamanan-appsecuritypy).

## Menjalankan tes sebelum PR atau merge

Jalankan seluruh unit test dan pastikan **semuanya lulus** sebelum membuka pull request atau melakukan merge:

```bash
python -m unittest discover -s tests
```

- Tambahkan `-v` untuk keluaran rinci, atau jalankan satu berkas: `python -m unittest tests.test_forum`.
- Perubahan perilaku harus disertai tes baru atau pembaruan tes yang ada.
- Halaman GET baru di sebuah aplikasi wajib punya node di `app/navigation.py` (dijaga `NavigationCoverageTest`).
- Bila perubahan menyentuh antarmuka, jalankan juga skenario uji manual terkait di [`docs/`](docs/) (berkas
  `UJI_MANUAL_*.md`).
- Jangan menonaktifkan atau menghapus tes agar PR lulus.

## Checklist pull request

- [ ] Branch khusus untuk satu fitur atau issue, issue ditautkan
- [ ] `python -m unittest discover -s tests` lulus
- [ ] Teks tampilan mengikuti [`docs/GLOSARIUM_TEKS.md`](docs/GLOSARIUM_TEKS.md) ("aplikasi", bukan "modul")
- [ ] Bila kelas UI berubah: `npm run build:css` dijalankan dan `tailwind.css` ikut di-commit
- [ ] Skrip inline memakai `nonce`, tidak ada `|safe`/`Markup` untuk masukan pengguna, POST memeriksa CSRF
- [ ] Dokumentasi di `docs/` dan `README.md` diperbarui bila perilaku atau konfigurasi berubah
- [ ] Tidak ada rahasia, berkas `.env`, atau database lokal di dalam commit

## Melaporkan masalah keamanan

Jangan membuka issue publik untuk celah keamanan. Hubungi pemilik repositori secara pribadi (Wyo Nugraha) lewat
pesan langsung di platform tempat repositori ini dihosting, sertakan langkah reproduksi, dan beri waktu yang wajar
untuk perbaikan sebelum diumumkan.
