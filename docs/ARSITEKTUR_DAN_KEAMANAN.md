# Arsitektur dan Keamanan

Dokumen ini memuat detail teknis inti Digital Knowledge Ecosystem (DKE): cara kerja aplikasi Flask, konfigurasi
lingkungan, cookie sesi dan header keamanan, pembatas percobaan login, halaman galat, fondasi tampilan, dan build
CSS Tailwind offline. Ringkasan cepat ada di [`README.md`](../README.md); rincian fitur per aplikasi ada di
[`PANDUAN_FITUR_APLIKASI.md`](PANDUAN_FITUR_APLIKASI.md).

## Daftar isi

- [Konfigurasi lingkungan](#konfigurasi-lingkungan)
- [Struktur folder lengkap](#struktur-folder-lengkap)
- [Cara kerja inti](#cara-kerja-inti)
- [Catatan skema](#catatan-skema)
- [Cookie sesi dan header keamanan](#cookie-sesi-dan-header-keamanan-appsecuritypy)
- [Pembatas percobaan login](#pembatas-percobaan-login-appinfosysthrottlepy)
- [Halaman galat](#halaman-galat-blueprint-55)
- [Istilah dan teks antarmuka](#istilah-dan-teks-antarmuka)
- [Fondasi tampilan](#fondasi-tampilan-fase-1-prompt-4)
- [Build CSS Tailwind](#build-css-tailwind-blueprint-67)

## Konfigurasi lingkungan

**Kunci sesi (`DKE_SECRET_KEY`) wajib diisi.** Kunci ini menandatangani cookie sesi; siapa pun yang tahu kuncinya bisa
memalsukan cookie dan login sebagai pengguna mana pun. Bila mode debug mati (bawaan) dan `DKE_SECRET_KEY` kosong atau
masih nilai bawaan lama, `python run.py` berhenti dengan pesan yang menjelaskan cara mengisinya, dan tidak menjalankan
server. Simpan kunci di tempat aman (jangan di-commit) dan pakai kunci yang sama setiap kali aplikasi dijalankan ulang;
mengganti kunci membuat semua sesi login berakhir. Berkas `.env` **tidak** dibaca otomatis oleh aplikasi ini.

**Mode debug mati secara bawaan.** Debugger Flask dapat menjalankan kode dari peramban, jadi jangan menyalakannya pada
aplikasi yang terjangkau jaringan. Untuk pengembangan di komputer sendiri:

```bash
FLASK_DEBUG=1 python run.py      # PowerShell: $env:FLASK_DEBUG="1"; python run.py
```

Dengan debug menyala, `DKE_SECRET_KEY` boleh kosong (dipakai kunci khusus pengembangan, disertai peringatan di terminal).
`run.py` juga memberi peringatan bila debug menyala sementara `HOST` bukan alamat lokal.

| Variabel | Bawaan | Fungsi |
|----------|--------|--------|
| `DKE_SECRET_KEY` | (tidak ada) | Kunci sesi. Wajib saat debug mati; hasilkan dengan `secrets.token_hex(32)` |
| `FLASK_DEBUG` | `0` | `1` menyalakan mode debug (hanya untuk komputer sendiri) |
| `HOST`, `PORT` | `127.0.0.1`, `5000` | Alamat dan port server pengembangan |
| `DKE_HTTPS` | `0` | `1` menambahkan atribut `Secure` pada cookie sesi (dan cookie ukuran font E-Tutorial). Nyalakan hanya bila situs benar-benar dilayani lewat `https://`; di `http://127.0.0.1` cookie `Secure` tidak akan terkirim sehingga login gagal |
| `DKE_BEHIND_PROXY` | `0` | `1` memasang `ProxyFix`: `X-Forwarded-For` dan `X-Forwarded-Proto` dipercaya, sehingga IP login dan pembatas login memakai IP klien, bukan IP reverse proxy. Jangan dinyalakan bila aplikasi bisa diakses langsung tanpa proxy (klien dapat memalsukan header) |
| `DKE_PROXY_HOPS` | `1` | Jumlah proxy tepercaya di depan aplikasi (dipakai bersama `DKE_BEHIND_PROXY=1`) |
| `DKE_UI_TEST` | `1` | Halaman uji `/dev/ui-test`; hanya nilai persis `1` yang menyalakannya, isi `0` untuk mematikannya di produksi |
| `DKE_ADMIN_PASSWORD` | (tidak ada) | Kata sandi akun admin saat `seed.py` pertama kali membuatnya (lihat [Database dan akun seed](PANDUAN_FITUR_APLIKASI.md#database-dan-data-contoh)) |
| `DKE_DEMO_PASSWORD` | (kosong, memakai `Demo12345`) | Kata sandi akun demo saat `seed.py` pertama kali membuatnya |

Nilai aktif untuk variabel bertanda `1`: `1`, `true`, `yes`, atau `on`. Nilai lain (atau kosong) = mati.

Tes otomatis tidak terpengaruh: setiap tes memberi `SECRET_KEY` sendiri lewat `create_app(test_config)`.

## Struktur folder lengkap

```
dke/
├── run.py                  # titik masuk (SECRET_KEY wajib saat debug mati)
├── requirements.txt
├── package.json, tailwind.config.js, scripts/   # HANYA untuk build CSS (Node tidak perlu saat menjalankan)
├── instance/               # dke.db dibuat di sini (tidak masuk Git)
└── app/
    ├── __init__.py         # create_app (+ cek SECRET_KEY), MODULES, registrasi blueprint, hook, context processor
    ├── db.py               # get_db, close_db, init_app
    ├── security.py         # cookie sesi, ProxyFix opsional, header keamanan + CSP (nonce)
    ├── messages.py         # satu sumber kalimat pesan bersama (MSG_*), dipakai Python dan dicek terhadap JS
    ├── utils.py            # login_required, log_activity, notify, slugify
    ├── main/               # Beranda, API pengaturan global (api.py), halaman uji
    ├── infosys/ ecommerce/ elearning/ etutorial/ portal/ forum/
    │   ├── __init__.py     # Blueprint
    │   ├── routes.py       # rute modul
    │   └── admin.py        # (khusus infosys) halaman admin minimal, UC-AD-01/02
    ├── templates/
    │   ├── base.html       # tailwind.css lokal, tema anti-kedip, Top-Bar sticky, toast-root
    │   ├── _components/    # topbar, app_switcher, breadcrumb, module_card, empty_state, _icons
    │   ├── main/
    │   └── <modul>/        # layout_<modul>.html + halaman modul
    └── static/
        ├── css/custom.css  # token Light/Dark, keyframes, Mobile View, reduced-motion
        ├── css/tailwind.css      # HASIL BUILD (di-commit; jangan diedit tangan)
        ├── css/tailwind.src.css  # sumber build: @font-face Inter + @tailwind
        ├── fonts/          # Inter latin 400/500/600/700 (woff2)
        └── js/             # theme.js toast.js switcher.js app.js elearning.js quiz.js ...
```

Aturan: satu blueprint = satu modul = satu folder template = satu `layout_<modul>.html`
yang mewarisi `base.html`.

## Cara kerja inti

- **`before_request`** mengisi `g.user` (dari `session["user_id"]`) dan `g.settings`
  (dari tabel `user_settings`, atau nilai bawaan untuk Guest atau bila DB belum dibuat).
- **`after_request`** menyimpan `last_module` dan `last_path` Member untuk tombol
  "Lanjutkan" dan Smart Landing. Hanya halaman HTML modul (GET, status 200); halaman
  login/register/logout dilewati.
- **`login_required`** mengarahkan Guest ke `/infosys/login?next=<halaman asal>`;
  `is_safe_next()` disediakan untuk mencegah open redirect.
- **`context_processor`** menyediakan `MODULES`, `current_module`, `accent`,
  `current_user`, dan `settings` ke semua template.

## Catatan skema

Nama kolom `activity_logs` dan `notifications` di `app/utils.py` sudah disesuaikan dengan `schema.sql`
(`module_key`, `message`, `link_url`). `notify()` menggabungkan `title` dan `body` menjadi satu `message`,
karena Blueprint hanya mendefinisikan kolom `message`.

## Cookie sesi dan header keamanan (`app/security.py`)

- Cookie sesi selalu `HttpOnly` dan `SameSite=Lax`. Atribut `Secure` mengikuti `DKE_HTTPS` (tidak dipaksa).
- **Di belakang reverse proxy** (Nginx, Caddy, dsb.): isi `DKE_BEHIND_PROXY=1` (dan `DKE_PROXY_HOPS` bila proxy lebih dari satu).
  Tanpa ini `request.remote_addr` berisi IP proxy, sehingga peringatan "lebih dari satu IP" di tab Keamanan dan
  pembatas login per IP tidak akurat. Proxy harus menimpa/menambahkan `X-Forwarded-For` dan `X-Forwarded-Proto`.
- Setiap respons (halaman HTML, API JSON, berkas statis, redirect, galat) membawa `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, dan `Content-Security-Policy`.
- CSP mengizinkan hanya sumber yang dipakai: skrip dari berkas sendiri + skrip inline ber-`nonce` (hanya skrip tema
  anti-kedip), stylesheet dan font dari berkas sendiri (Tailwind dan Inter lokal, **tanpa CDN**), iframe YouTube
  (`youtube-nocookie.com`) dan Vimeo, gambar `https:`/`data:`, `connect-src 'self'`, `object-src 'none'`,
  `frame-ancestors 'none'`.
- **Skrip inline wajib memakai nonce**: tulis `<script nonce="{{ csp_nonce() }}">`. Nonce dibuat baru tiap permintaan.
  Atribut event (`onclick=...`) dan URL `javascript:` akan diblokir; pasang handler lewat berkas JS.
- `style-src` masih memuat `'unsafe-inline'`, kini hanya karena beberapa templat memakai `style="width: N%"`
  (bukan lagi karena Tailwind). Menghapusnya butuh mengganti atribut `style` itu dengan kelas/variabel CSS.
- Tes: `python -m unittest tests.test_security`.

## Pembatas percobaan login (`app/infosys/throttle.py`)

Kegagalan login dicatat sebagai baris `activity_logs` dengan `action = 'login_failed'` (tanpa tabel baru, skema tetap
23 tabel) lalu dihitung dalam jendela geser:

- Setelah **5 kegagalan dalam 10 menit untuk satu email**, `POST /infosys/login` ditolak dengan **status 429** dan pesan
  *"Terlalu banyak percobaan. Coba lagi dalam beberapa menit."*, **walau kata sandinya benar**. Kunci pulih sendiri
  begitu kegagalan tertua keluar dari jendela 10 menit.
- Ada hitungan kedua **per alamat IP** (20 kegagalan dalam 10 menit, untuk email apa pun). Batasnya lebih longgar supaya
  jaringan bersama (kampus, kantor) tidak terkunci karena satu orang salah ketik.
- Hitungan ada di database, bukan di cookie, jadi membuang cookie atau memakai peramban lain tidak melewatinya.
  Kegagalan satu email tidak mengunci email lain (selama batas IP belum tercapai).
- Pesan untuk email tak dikenal dan kata sandi salah tetap sama (401). Email tak dikenal juga dihitung dan dikunci
  dengan cara yang sama, sehingga 429 tidak membocorkan email mana yang terdaftar. Hash tiruan tetap dijalankan agar
  waktu respons seragam; percobaan yang sudah ditolak 429 tidak menjalankan hash sama sekali (hemat CPU).
- Yang dihitung hanya kata sandi salah atau email tak dikenal. Isian berformat salah (400), akun nonaktif (403), dan
  percobaan yang ditolak 429 tidak dicatat dan tidak memperpanjang kunci.
- Email tidak disimpan mentah: kolom `detail` memuat hash HMAC (kunci = `SECRET_KEY`) sebagai kunci hitung. Baris milik
  akun terdaftar terisi `user_id`-nya sehingga tampil di Log Aktivitas pemiliknya ("Gagal login"); baris email tak
  dikenal berisi `user_id` NULL.
- Alamat IP diambil dari `request.remote_addr`; header `X-Forwarded-For` sengaja **tidak** dipercaya karena bisa
  dipalsukan klien. Di belakang reverse proxy, isi `DKE_BEHIND_PROXY=1` (dan `DKE_PROXY_HOPS`) agar `ProxyFix`
  aktif dan IP yang terlihat adalah IP klien (lihat [Cookie sesi dan header keamanan](#cookie-sesi-dan-header-keamanan-appsecuritypy)).
- Pembatas yang sama dipakai oleh form **Ganti kata sandi** (kunci akun = `user_id`, hitungan dari baris
  `password_change_failed`), menggantikan penghitung berbasis sesi yang lama. Setelah 5 kali salah dalam 10 menit, form
  ditolak dengan status 429, dihitung dari `activity_logs` per akun dan per IP sehingga tidak bisa dilewati dengan
  membuang cookie. Berhasil atau gagal, kejadiannya dicatat di `activity_logs`, dan keberhasilan juga membuat notifikasi.
- Nilai dapat diubah lewat `app.config`: `LOGIN_MAX_FAILS` (5), `LOGIN_MAX_FAILS_PER_IP` (20),
  `LOGIN_FAIL_WINDOW_SECONDS` (600).
- Keterbatasan: penyerang yang tahu email korban dapat membuat email itu terkunci sementara dengan sengaja gagal
  login (jalan tengah yang umum untuk pembatas per akun). Untuk produksi, tambahkan rate-limit di tingkat server
  (reverse proxy) sebagai lapisan kedua.
- Indeks `idx_activity_logs_action` (bukan tabel) ditambahkan ke `schema.sql` agar penghitungan tetap cepat. Pada
  database lama, jalankan `python seed.py` (aman diulang) atau `python seed.py --reset`.
- Tes: `python -m unittest tests.test_login_throttle`.

Rute autentikasi dan aturan validasinya ada di
[`PANDUAN_FITUR_APLIKASI.md`](PANDUAN_FITUR_APLIKASI.md#autentikasi-fase-1-uc-is-0103).

## Halaman galat (Blueprint 5.5)

`app/errors.py` mendaftarkan `errorhandler` untuk **403, 404, 405, dan 500**.

- **Halaman HTML**: `app/templates/main/error.html` mewarisi `base.html`, sehingga Top-Bar, tema, Dark Mode, dan Mobile View
  tetap berlaku. Teks Bahasa Indonesia, tombol **Kembali ke Beranda**. Halaman ini bukan rute dan tidak muncul di
  hierarki `app/navigation.py` (breadcrumb/Kembali sengaja kosong), jadi tidak memengaruhi `NavigationCoverageTest`.
- **JSON untuk API**: jalur `/api/...` dan `/<modul>/api/...` (mis. `/elearning/api/materi/3/selesai`) menerima
  `{"ok": false, "error": "...", "status": 404}`, bukan HTML. Kode HTTP lain (mis. 400) pada jalur API juga dijadikan JSON.
  Respons JSON yang sudah dibuat endpoint sendiri tidak berubah.
- **500**: hanya pesan umum. Detail galat tidak pernah dikirim ke pengguna (tetap tercatat di log server). Bila template
  galat sendiri gagal dirender, dipakai halaman cadangan statis tanpa database.
- Uji: `python -m unittest tests.test_errors`.

## Istilah dan teks antarmuka

**Istilah antarmuka:** untuk pengguna, tiap bagian DKE disebut **aplikasi** (bukan "modul"). Di kode tetap `module_key`,
`MODULES`, dan sejenisnya. Daftar istilah baku, keputusan, dan istilah Inggris yang dihindari ada di
[`GLOSARIUM_TEKS.md`](GLOSARIUM_TEKS.md).

**Teks antarmuka:** panduan gaya (nada, "Anda", subjudul maks. 15 kata, empty state satu kalimat, pesan galat dengan
solusi), istilah terlarang, dan katalog pesan ada di [`GLOSARIUM_TEKS.md`](GLOSARIUM_TEKS.md). Kalimat bersama ditulis
sekali di `app/messages.py`. Untuk meninjau semua teks tampilan: `python scripts/inventaris_teks.py --cari "kata"` atau
`--csv docs/INVENTARIS_TEKS.csv`. Tes: `tests/test_teks_ui.py`.

## Fondasi tampilan (Fase 1, Prompt 4)

- **Tema** Light/Dark/Sistem dan **tampilan** Desktop/Mobile: Guest -> `localStorage`
  (`dke-theme`, `dke-view`); Member -> `POST /api/settings/global` (tabel `user_settings`),
  dan nilai dari database dipakai saat halaman dimuat. Skrip anti-kedip di `<head>` `base.html`.
  Klik manual pada pilihan tema memakai efek *circular reveal* (View Transitions API): warna baru tumbuh
  dari ikon tema ke seluruh layar. Tanpa dukungan API itu atau saat `prefers-reduced-motion` aktif, tema
  berganti langsung. Mode Sistem yang berubah otomatis tidak beranimasi. Tes: `python -m unittest tests.test_theme_transition`;
  uji manual: [`UJI_MANUAL_TEMA.md`](UJI_MANUAL_TEMA.md).
- **Toast** menggantikan `alert()`: `toast(pesan, 'success|error|info|warning', ms)`.
  Pesan `flash()` Flask otomatis tampil sebagai toast (kategori `danger` -> error, tanpa kategori -> info).
- **Mobile View paksa**: beri kelas `launcher-grid` / `product-grid` / `card-grid` pada grid,
  `stack-mobile` pada tumpukan flex, `dke-hide-mobile` pada elemen yang disembunyikan di mobile.
  Kelas responsif Tailwind (`md:`, `lg:`) mengikuti lebar jendela sungguhan, jadi untuk elemen
  baru yang harus patuh pada Mobile View gunakan kelas-kelas tersebut.
- **Komponen** (`{% from "_components/xxx.html" import xxx %}`): `breadcrumb()`, `back_link()`,
  `module_card()`, `empty_state()`; `topbar` dan `app_switcher` di-include oleh `base.html`.
- **Token warna Tailwind**: `bg-page bg-surface text-ink text-muted border-line bg-primary text-on-primary bg-header text-success`.
  Nilainya di `custom.css`, sehingga satu kelas berlaku untuk Light dan Dark.
- **Halaman uji**: http://127.0.0.1:5000/dev/ui-test (semua jenis toast, flash() dari server, status tema).
  Matikan di produksi dengan `DKE_UI_TEST=0`.
- Tailwind dan font Inter **dilayani dari berkas sendiri** (lihat bagian [Build CSS Tailwind](#build-css-tailwind-blueprint-67)), jadi tampilan sama
  persis tanpa internet.

## Build CSS Tailwind (Blueprint 6.7)

Tailwind **tidak lagi dimuat dari CDN**. `app/static/css/tailwind.css` adalah hasil build yang **di-commit ke Git**,
jadi menjalankan atau mendemokan aplikasi **tidak butuh Node maupun internet**.

Node hanya diperlukan bila Anda menambah/mengubah kelas Tailwind di templat atau JS:

```bash
npm install                 # sekali saja: tailwindcss 3.4.17 + @fontsource/inter (devDependencies)
npm run build:css           # = npx tailwindcss -c tailwind.config.js -i app/static/css/tailwind.src.css -o app/static/css/tailwind.css --minify
npm run watch:css           # build ulang otomatis saat berkas berubah (pengembangan)
npm run build:fonts         # hanya bila ingin menyalin ulang Inter ke app/static/fonts
```

- `tailwind.config.js`: `darkMode: 'class'`, token warna (nilainya di `custom.css`, variabel `--c-*`), dan `content` yang
  memindai `app/templates/**/*.html`, `app/static/js/**/*.js`, dan `app/**/*.py`.
- **Kelas yang dirangkai di JS/Python** (mis. `'bg-' + warna`) tidak terdeteksi pemindai. Tulis nama kelas **utuh**
  (`'bg-red-600'`) atau daftarkan di `safelist` pada `tailwind.config.js`.
- Setelah mengubah templat/JS dengan kelas baru, jalankan `npm run build:css` lalu **commit `tailwind.css`**.
  Tes `tests.test_security.StaticAssetsTests` gagal bila build basi untuk kelas inti.
- `tailwind.css` dimuat **setelah** `custom.css` dan blok `head_extra` di `base.html`. Urutan ini meniru Play CDN
  (yang menyisipkan `<style>` di akhir `<head>`) agar kaskade tidak berubah. Jangan dipindah.
- Font Inter (subset latin, 4 bobot) ada di `app/static/fonts/` dan dideklarasikan lewat `@font-face` di `tailwind.src.css`;
  `font-display: swap` dengan cadangan `system-ui`.
