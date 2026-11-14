#!/usr/bin/env python3
"""seed.py - membuat dan mengisi database Digital Knowledge Ecosystem (DKE).

Pemakaian (dari folder proyek, sejajar dengan run.py):

    python seed.py                 # buat instance/dke.db bila belum ada, lalu isi data contoh
    python seed.py --reset         # hapus SEMUA tabel lalu bangun ulang dari nol
    python seed.py --db jalur.db   # pakai berkas database lain

Sifat penting:
  * Aman dijalankan ulang (idempoten): setiap baris dicari lewat kunci alaminya
    (email, slug, order_code, ...). Bila sudah ada, konten contoh diperbarui,
    bukan digandakan. Data yang dibuat pengguna (keranjang, pesanan baru,
    balasan forum, dsb.) tidak disentuh, dan kata sandi akun yang sudah ada
    tidak pernah ditimpa.
  * Seluruh pengisian berjalan dalam SATU transaksi; bila ada kesalahan,
    semuanya dibatalkan (ROLLBACK).
  * Kata sandi disimpan sebagai hash (werkzeug.security.generate_password_hash).
  * Semua waktu memakai jangkar tetap (ANCHOR) agar hasilnya deterministik.

Kata sandi bawaan (ubah lewat variabel lingkungan sebelum seed pertama):
    DKE_DEMO_PASSWORD    bawaan: Demo12345     (demo@dke.test)
    DKE_ADMIN_PASSWORD   bawaan: Admin12345!   (admin@dke.test)
Ganti kata sandi bawaan ini bila aplikasi diakses di luar komputer sendiri.
"""
import argparse
import json
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
DEFAULT_DB = os.path.join(BASE_DIR, "instance", "dke.db")

# Jangkar waktu tetap: seluruh stempel waktu dihitung mundur dari sini.
ANCHOR = datetime(2026, 11, 13, 9, 0, 0, tzinfo=timezone.utc)

DEMO_EMAIL = "demo@dke.test"
ADMIN_EMAIL = "admin@dke.test"
DEMO_PASSWORD = os.environ.get("DKE_DEMO_PASSWORD", "Demo12345")
ADMIN_PASSWORD = os.environ.get("DKE_ADMIN_PASSWORD", "Admin12345!")

# 23 tabel menurut Blueprint 3.2 (urutan: kelompok seperti di Blueprint).
EXPECTED_TABLES = [
    "users", "user_settings", "module_settings", "activity_logs", "notifications", "categories",
    "products", "cart_items", "orders", "order_items",
    "courses", "lessons", "enrollments", "lesson_progress", "quizzes", "quiz_questions", "quiz_attempts",
    "tutorials", "tutorial_steps", "tutorial_bookmarks",
    "articles",
    "threads", "posts",
]


def ts(days_ago=0, hours=0):
    """Stempel waktu ISO-8601 (UTC) = ANCHOR dikurangi days_ago hari, ditambah `hours` jam."""
    return (ANCHOR - timedelta(days=days_ago) + timedelta(hours=hours)).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Pembantu basis data
# ---------------------------------------------------------------------------
def ensure(conn, table, lookup, values=None, fixed=None):
    """Cari baris lewat `lookup`; buat bila belum ada, perbarui `values` bila sudah ada.

    lookup : kolom kunci alami (dipakai mencari)
    values : kolom isi konten (dipakai saat INSERT dan UPDATE)
    fixed  : kolom yang hanya diisi saat INSERT (mis. created_at), tak diubah saat seed ulang
    Mengembalikan id baris. Nama tabel/kolom berasal dari kode ini (bukan input pengguna);
    seluruh nilai dikirim lewat parameter `?`.
    """
    values, fixed = values or {}, fixed or {}
    where = " AND ".join(f"{col} = ?" for col in lookup)
    row = conn.execute(f"SELECT id FROM {table} WHERE {where}", tuple(lookup.values())).fetchone()
    if row is None:
        data = {**lookup, **values, **fixed}
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))
        return cur.lastrowid
    if values:
        sets = ", ".join(f"{col} = ?" for col in values)
        conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*values.values(), row[0]))
    return row[0]


def insert_ignore(conn, table, data):
    """INSERT OR IGNORE untuk tabel dengan UNIQUE/PRIMARY KEY alami. True bila baris baru dibuat."""
    cols = ", ".join(data)
    marks = ", ".join("?" for _ in data)
    cur = conn.execute(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({marks})", tuple(data.values()))
    return cur.rowcount == 1


def table_columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def drop_all_tables(conn):
    """Hapus semua tabel (untuk --reset). Tidak menghapus berkas, jadi aman bila Windows mengunci berkas."""
    conn.execute("PRAGMA foreign_keys = OFF")
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")]
    for name in names:
        conn.execute(f"DROP TABLE IF EXISTS {name}")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def apply_schema(conn):
    """Jalankan schema.sql, lalu pastikan tabel yang sudah ada cocok dengan skema (anti-drift)."""
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        sql = f.read()
    conn.executescript(sql)
    conn.execute("PRAGMA foreign_keys = ON")

    ref = sqlite3.connect(":memory:")
    ref.executescript(sql)
    problems = []
    for table in EXPECTED_TABLES:
        want, have = table_columns(ref, table), table_columns(conn, table)
        if want != have:
            problems.append(f"  - {table}: kolom di database {have} != skema {want}")
    ref.close()
    if problems:
        raise SystemExit(
            "Skema database lama tidak cocok dengan schema.sql:\n" + "\n".join(problems) +
            "\nJalankan:  python seed.py --reset   (menghapus data lama lalu membangun ulang)")


# ---------------------------------------------------------------------------
# DATA: akun
# ---------------------------------------------------------------------------
# (email, nama, peran, bio, hari_lalu_dibuat, kata_sandi atau None = tidak dapat dipakai login)
USERS = [
    (ADMIN_EMAIL, "Admin DKE", "admin",
     "Pengelola konten dan moderator Digital Knowledge Ecosystem.", 60, ADMIN_PASSWORD),
    (DEMO_EMAIL, "Pengguna Demo", "member",
     "Akun contoh untuk mencoba seluruh modul DKE. Mahasiswa Teknik Informatika semester 3.", 14, DEMO_PASSWORD),
    ("budi@dke.test", "Budi Santoso", "member",
     "Mahasiswa semester 5, sedang belajar Flask dan basis data.", 45, None),
    ("citra@dke.test", "Citra Lestari", "member",
     "Calon web developer. Suka membangun proyek kecil sampai selesai.", 40, None),
    ("dewi@dke.test", "Dewi Anggraini", "member",
     "Mahasiswa Sistem Informasi, sedang mendalami SQL.", 33, None),
    ("eko@dke.test", "Eko Prasetyo", "member",
     "Pekerja kantoran yang belajar pemrograman sepulang kerja.", 28, None),
]

# ---------------------------------------------------------------------------
# DATA: kategori per module_key  (module_key, nama, slug)
# Modul infosys tidak memiliki konten berkategori sehingga tidak diberi kategori.
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("ecommerce", "Kursus Digital", "kursus-digital"),
    ("ecommerce", "E-Book", "e-book"),
    ("ecommerce", "Template & Aset", "template-aset"),

    ("elearning", "Pemrograman", "pemrograman"),
    ("elearning", "Basis Data", "basis-data"),
    ("elearning", "Desain & UI/UX", "desain-ui-ux"),
    ("elearning", "Pengembangan Diri", "pengembangan-diri"),

    ("etutorial", "Python", "python"),
    ("etutorial", "Web", "web"),
    ("etutorial", "Alat Developer", "alat-developer"),

    ("portal", "Teknologi", "teknologi"),
    ("portal", "Pendidikan", "pendidikan"),
    ("portal", "Karier", "karier"),
    ("portal", "Produktivitas", "produktivitas"),

    ("forum", "Diskusi Umum", "diskusi-umum"),
    ("forum", "Tanya Jawab Teknis", "tanya-jawab-teknis"),
    ("forum", "Karier & Belajar", "karier-belajar"),
    ("forum", "Showcase Proyek", "showcase-proyek"),
]


# ---------------------------------------------------------------------------
# DATA: 3 kursus lengkap (lessons + kuis)
# lessons  : (judul, durasi_menit, isi)      kuis: (soal, a, b, c, d, jawaban, penjelasan)
# ---------------------------------------------------------------------------
COURSES = [
    # ------------------------------------------------------------------ 1
    {
        "slug": "dasar-pemrograman-python",
        "title": "Dasar Pemrograman Python untuk Pemula",
        "category": "pemrograman",
        "level": "pemula",
        "instructor": "Rizky Pratama, M.Kom.",
        "hours": 6.0,
        "days_ago": 50,
        "description": (
            "Kursus pengantar bagi Anda yang belum pernah menulis program. Anda akan mengenal sintaks Python, "
            "variabel dan tipe data, percabangan, perulangan, fungsi, hingga membaca dan menulis berkas. "
            "Setiap pelajaran disertai contoh kode pendek yang dapat langsung dicoba dan ditutup dengan kuis "
            "untuk mengukur pemahaman."),
        "lessons": [
            ("Mengenal Python dan Menyiapkan Lingkungan Kerja", 12, """
Python adalah bahasa pemrograman tingkat tinggi yang dikenal sintaksnya ringkas dan mudah dibaca. Bahasa ini dipakai di banyak bidang, mulai dari pengembangan web, analisis data, otomasi tugas, hingga pembelajaran mesin. Karena sintaksnya mirip bahasa sehari-hari, Python sering dipilih sebagai bahasa pertama bagi pemula.

Untuk mulai, pasang Python versi 3.10 atau lebih baru dari situs resmi python.org. Pada Windows, centang opsi "Add Python to PATH" saat instalasi agar perintah python dapat dipanggil dari terminal. Setelah selesai, periksa dengan menjalankan:

    python --version

Anda dapat menulis kode di editor teks apa pun, tetapi Visual Studio Code dengan ekstensi Python memberi saran kode dan penyorotan kesalahan yang membantu pemula. Buat berkas halo.py berisi satu baris berikut, lalu jalankan dengan perintah python halo.py:

    print("Halo, dunia!")

Jika teks muncul di terminal, lingkungan kerja Anda sudah siap. Pada pelajaran berikutnya kita akan mengenal variabel dan tipe data."""),
            ("Variabel, Tipe Data, dan Operator", 15, """
Variabel adalah nama yang menunjuk ke sebuah nilai di memori. Di Python Anda tidak perlu menyatakan tipe variabel; cukup berikan nilai dengan tanda sama dengan.

    nama = "Sari"
    umur = 20
    tinggi = 1.62
    sedang_belajar = True

Empat tipe data dasar yang paling sering dipakai adalah str (teks), int (bilangan bulat), float (bilangan pecahan), dan bool (benar atau salah). Gunakan fungsi type() untuk memeriksa tipe sebuah nilai; misalnya type(tinggi) menghasilkan float.

Operator aritmetika meliputi + (tambah), - (kurang), * (kali), / (bagi), // (bagi bulat), % (sisa bagi), dan ** (pangkat). Perhatikan bahwa 7 / 2 menghasilkan 3.5, sedangkan 7 // 2 menghasilkan 3 dan 7 % 2 menghasilkan 1.

Beri nama variabel yang bermakna, ditulis huruf kecil dengan garis bawah (snake_case), misalnya total_belanja. Nama seperti x1 atau data2 menyulitkan Anda sendiri saat membaca kode beberapa minggu kemudian."""),
            ("Percabangan dan Perulangan", 18, """
Percabangan memungkinkan program memilih tindakan berdasarkan kondisi. Python memakai if, elif, dan else, dan blok kode ditandai dengan indentasi (empat spasi).

    nilai = 78
    if nilai >= 85:
        print("A")
    elif nilai >= 70:
        print("B")
    else:
        print("Perlu mengulang")

Perulangan menjalankan kode berulang kali. Gunakan for untuk mengulang sejumlah kali atau menelusuri kumpulan data, dan while untuk mengulang selama kondisi bernilai benar.

    for i in range(3):
        print("Putaran", i)   # mencetak putaran 0, 1, dan 2

    saldo = 100
    while saldo > 0:
        saldo -= 30

Hati-hati dengan while: pastikan ada langkah yang akhirnya membuat kondisi menjadi salah, jika tidak program akan berjalan tanpa henti. Tekan Ctrl+C di terminal untuk menghentikannya."""),
            ("Fungsi dan Modul", 20, """
Fungsi adalah blok kode bernama yang dapat dipakai berulang kali. Dengan fungsi, program menjadi lebih rapi dan mudah diuji. Fungsi didefinisikan dengan kata kunci def.

    def hitung_diskon(harga, persen=10):
        return harga - harga * persen / 100

    print(hitung_diskon(200000))      # 180000.0
    print(hitung_diskon(200000, 25))  # 150000.0

Parameter persen memiliki nilai bawaan 10, sehingga boleh tidak diisi saat fungsi dipanggil. Kata kunci return mengembalikan hasil ke pemanggil; tanpa return, fungsi mengembalikan None.

Modul adalah berkas Python yang berisi fungsi atau variabel yang dapat diimpor ke berkas lain. Python menyediakan banyak modul bawaan, misalnya math dan random.

    import math
    print(math.sqrt(144))   # 12.0

Anda juga dapat membuat modul sendiri: simpan fungsi di berkas utilitas.py, lalu panggil dengan perintah import utilitas."""),
            ("Membaca dan Menulis Berkas", 15, """
Program sering perlu menyimpan atau membaca data dari berkas. Fungsi open() membuka berkas, dan pernyataan with memastikan berkas ditutup otomatis setelah selesai dipakai.

    with open("catatan.txt", "w", encoding="utf-8") as f:
        f.write("Belajar Python hari ini\\n")

    with open("catatan.txt", "r", encoding="utf-8") as f:
        for baris in f:
            print(baris.strip())

Mode yang umum dipakai: "r" untuk membaca, "w" untuk menulis (isi lama ditimpa), dan "a" untuk menambah di akhir berkas tanpa menghapus isi lama. Selalu tentukan encoding="utf-8" agar huruf dan simbol tampil benar di semua sistem.

Bila berkas mungkin tidak ada, tangani kesalahan dengan try dan except FileNotFoundError supaya program tidak berhenti mendadak. Dengan keterampilan ini Anda siap menulis program kecil yang menyimpan datanya sendiri."""),
        ],
        "quiz_title": "Kuis Dasar Pemrograman Python",
        "pass_score": 70,
        "questions": [
            ("Fungsi bawaan Python manakah yang dipakai untuk menampilkan teks ke layar?",
             "print()", "echo()", "show()", "display()", "a",
             "Fungsi print() menampilkan nilai ke layar. echo(), show(), dan display() bukan fungsi bawaan Python."),
            ("Apa tipe data dari nilai 3.14 di Python?",
             "int", "float", "str", "bool", "b",
             "Bilangan dengan titik desimal bertipe float. int dipakai untuk bilangan bulat seperti 3."),
            ("Berapakah hasil dari ekspresi 7 // 2?",
             "3.5", "4", "3", "1", "c",
             "Operator // adalah pembagian bulat sehingga 7 // 2 menghasilkan 3. Operator / menghasilkan 3.5 dan % menghasilkan sisa bagi, yaitu 1."),
            ("Kata kunci apa yang dipakai untuk mendefinisikan sebuah fungsi?",
             "function", "func", "def", "define", "c",
             "Python memakai kata kunci def, misalnya def hitung_diskon(harga):."),
            ("Mode open() mana yang menambahkan isi di akhir berkas tanpa menghapus isi lama?",
             "\"a\"", "\"w\"", "\"r\"", "\"x\"", "a",
             "Mode \"a\" (append) menambah di akhir berkas. Mode \"w\" menimpa isi lama, \"r\" hanya membaca, dan \"x\" membuat berkas baru lalu gagal bila sudah ada."),
        ],
    },
    # ------------------------------------------------------------------ 2
    {
        "slug": "dasar-sql-perancangan-basis-data",
        "title": "Dasar SQL dan Perancangan Basis Data",
        "category": "basis-data",
        "level": "menengah",
        "instructor": "Sinta Maharani, S.Kom., M.T.",
        "hours": 5.5,
        "days_ago": 46,
        "description": (
            "Pelajari cara berpikir dalam basis data relasional: dari tabel, kunci utama, dan kunci asing, "
            "hingga menulis kueri SELECT, JOIN, dan agregasi. Kursus ini juga membahas normalisasi sampai "
            "bentuk normal ketiga, indeks, dan transaksi, dengan contoh yang dapat dijalankan memakai SQLite."),
        "lessons": [
            ("Memahami Basis Data Relasional", 14, """
Basis data adalah kumpulan data terorganisasi yang disimpan agar mudah dicari, diubah, dan dijaga konsistensinya. Pada basis data relasional, data disusun dalam tabel yang terdiri dari baris (record) dan kolom (field).

Setiap tabel sebaiknya memiliki kunci utama (primary key), yaitu kolom yang nilainya unik untuk setiap baris, misalnya id pada tabel mahasiswa. Hubungan antartabel dibuat dengan kunci asing (foreign key), yaitu kolom yang merujuk ke kunci utama tabel lain. Misalnya kolom mahasiswa_id pada tabel nilai merujuk ke id pada tabel mahasiswa.

Bahasa yang dipakai untuk berinteraksi dengan basis data relasional adalah SQL (Structured Query Language). Pada kursus ini kita memakai SQLite karena tidak memerlukan server dan seluruh basis datanya tersimpan dalam satu berkas. Contoh tabel sederhana:

    CREATE TABLE mahasiswa (
      id INTEGER PRIMARY KEY,
      nama TEXT NOT NULL,
      prodi TEXT
    );"""),
            ("Perintah SELECT dan Penyaringan dengan WHERE", 18, """
Perintah SELECT dipakai untuk mengambil data. Tanda bintang berarti semua kolom, atau Anda dapat menyebut kolom tertentu.

    SELECT nama, prodi FROM mahasiswa;
    SELECT * FROM mahasiswa WHERE prodi = 'Teknik Informatika';

Klausa WHERE menyaring baris berdasarkan kondisi. Anda dapat menggabungkan kondisi dengan AND dan OR, serta memakai operator perbandingan (=, <>, >, <), BETWEEN, IN, dan LIKE untuk pencarian pola, misalnya nama LIKE 'A%' untuk nama yang diawali huruf A.

Untuk mengurutkan hasil gunakan ORDER BY, dan untuk membatasi jumlah baris gunakan LIMIT.

    SELECT nama FROM mahasiswa
    WHERE prodi = 'Sistem Informasi'
    ORDER BY nama ASC
    LIMIT 5;

Fungsi agregat seperti COUNT, SUM, AVG, MIN, dan MAX meringkas banyak baris menjadi satu nilai, dan GROUP BY mengelompokkannya, contohnya menghitung jumlah mahasiswa per program studi."""),
            ("JOIN: Menggabungkan Data Antartabel", 20, """
Data yang sudah dipecah ke beberapa tabel perlu digabungkan kembali saat dibaca. Itulah fungsi JOIN. INNER JOIN hanya mengembalikan baris yang memiliki pasangan di kedua tabel.

    SELECT m.nama, n.mata_kuliah, n.nilai
    FROM mahasiswa m
    INNER JOIN nilai n ON n.mahasiswa_id = m.id;

LEFT JOIN mengembalikan semua baris dari tabel kiri, termasuk yang belum punya pasangan di tabel kanan; kolom dari tabel kanan akan berisi NULL. Ini berguna untuk mencari data yang belum punya relasi, misalnya mahasiswa yang belum memiliki nilai:

    SELECT m.nama
    FROM mahasiswa m
    LEFT JOIN nilai n ON n.mahasiswa_id = m.id
    WHERE n.id IS NULL;

Gunakan alias tabel (m dan n) agar kueri lebih ringkas, dan selalu tulis kondisi ON dengan benar. Kondisi ON yang salah dapat menghasilkan baris berlipat ganda yang sulit dilacak."""),
            ("Normalisasi: 1NF, 2NF, dan 3NF", 20, """
Normalisasi adalah proses menata tabel untuk mengurangi pengulangan data dan mencegah anomali saat data diubah. Bayangkan satu tabel pesanan yang menyimpan nama pelanggan dan alamatnya di setiap baris; jika pelanggan pindah alamat, Anda harus mengubah banyak baris dan mudah ada yang terlewat.

Bentuk normal pertama (1NF): setiap kolom hanya berisi satu nilai atomik, tidak ada kolom yang berisi daftar seperti "Python, SQL, Flask". Bentuk normal kedua (2NF): memenuhi 1NF dan setiap kolom non-kunci bergantung pada seluruh kunci utama, bukan hanya sebagian (relevan untuk kunci gabungan). Bentuk normal ketiga (3NF): memenuhi 2NF dan tidak ada kolom non-kunci yang bergantung pada kolom non-kunci lain.

Contohnya, memisahkan data pelanggan ke tabel tersendiri lalu merujuknya lewat pelanggan_id adalah langkah normalisasi yang umum. Meski begitu, normalisasi bukan tujuan mutlak; pada beberapa kasus pelaporan, denormalisasi terbatas dipilih demi kecepatan baca."""),
            ("Indeks dan Transaksi", 16, """
Indeks adalah struktur tambahan yang mempercepat pencarian pada kolom tertentu, mirip daftar isi pada buku. Tanpa indeks, basis data harus memeriksa baris satu per satu. Buat indeks pada kolom yang sering dipakai di WHERE atau JOIN.

    CREATE INDEX idx_mahasiswa_prodi ON mahasiswa(prodi);

Indeks tidak gratis: ia memakan ruang penyimpanan dan membuat penulisan (INSERT, UPDATE, DELETE) sedikit lebih lambat karena indeks ikut diperbarui. Karena itu buat indeks seperlunya.

Transaksi mengelompokkan beberapa perintah agar berhasil seluruhnya atau dibatalkan seluruhnya. Contohnya saat checkout, pesanan dan rinciannya harus tersimpan bersama.

    BEGIN;
    INSERT INTO pesanan (kode, total) VALUES ('P-001', 150000);
    INSERT INTO rincian_pesanan (pesanan_id, produk, qty) VALUES (1, 'Kursus Python', 1);
    COMMIT;

Jika terjadi kesalahan di tengah jalan, jalankan ROLLBACK agar data tetap konsisten."""),
        ],
        "quiz_title": "Kuis Dasar SQL dan Perancangan Basis Data",
        "pass_score": 70,
        "questions": [
            ("Perintah SQL manakah yang dipakai untuk mengambil data dari tabel?",
             "SELECT", "INSERT", "UPDATE", "FETCH", "a",
             "SELECT dipakai untuk membaca data. INSERT menambah, UPDATE mengubah, dan FETCH bukan perintah dasar SQL untuk membaca tabel."),
            ("Klausa apa yang dipakai untuk menyaring baris berdasarkan kondisi?",
             "ORDER BY", "GROUP BY", "WHERE", "LIMIT", "c",
             "WHERE menyaring baris. ORDER BY mengurutkan, GROUP BY mengelompokkan, dan LIMIT membatasi jumlah baris."),
            ("INNER JOIN antara tabel A dan tabel B menghasilkan...",
             "Semua baris tabel A, dengan atau tanpa pasangan di B",
             "Hanya baris yang memiliki pasangan di kedua tabel",
             "Semua baris dari A dan B tanpa syarat",
             "Hanya baris tabel B yang tidak punya pasangan di A", "b",
             "INNER JOIN hanya mengembalikan baris yang cocok di kedua tabel. Pilihan pertama adalah ciri LEFT JOIN."),
            ("Sebuah tabel dikatakan memenuhi bentuk normal kedua (2NF) bila...",
             "Setiap kolom berisi lebih dari satu nilai",
             "Tidak memiliki kunci utama",
             "Memenuhi 1NF dan kolom non-kunci bergantung pada seluruh kunci utama",
             "Semua kolomnya bertipe teks", "c",
             "2NF mensyaratkan 1NF terpenuhi dan tidak ada ketergantungan parsial pada sebagian kunci utama."),
            ("Apa manfaat utama indeks pada sebuah kolom?",
             "Mempercepat pencarian, dengan konsekuensi penulisan data sedikit lebih lambat",
             "Menghapus data ganda secara otomatis",
             "Mengenkripsi isi kolom",
             "Mengurangi ukuran berkas basis data", "a",
             "Indeks mempercepat pencarian dan pengurutan, tetapi memakan ruang dan memperlambat INSERT, UPDATE, dan DELETE."),
        ],
    },
    # ------------------------------------------------------------------ 3 (gratis)
    {
        "slug": "prinsip-desain-antarmuka-pemula",
        "title": "Prinsip Desain Antarmuka untuk Pemula",
        "category": "desain-ui-ux",
        "level": "pemula",
        "instructor": "Dimas Aryanto, S.Ds.",
        "hours": 4.0,
        "days_ago": 42,
        "description": (
            "Kursus gratis tentang dasar Interaksi Manusia dan Komputer (IMK): memahami pengguna, hierarki "
            "visual, warna dan tipografi, Delapan Aturan Emas Shneiderman, merancang umpan balik dan pesan "
            "kesalahan, hingga uji kebergunaan sederhana dengan System Usability Scale (SUS)."),
        "lessons": [
            ("Mengapa Antarmuka Perlu Dirancang", 10, """
Antarmuka pengguna (user interface) adalah titik temu antara manusia dan sistem. Program yang secara teknis benar tetap dianggap buruk bila pengguna bingung memakainya, salah menekan tombol, atau meninggalkannya sebelum tugasnya selesai. Itulah alasan Interaksi Manusia dan Komputer (IMK) dipelajari sebagai disiplin tersendiri.

Rancangan yang baik berangkat dari pengguna, bukan dari fitur. Mulailah dengan tiga pertanyaan: siapa penggunanya, tugas apa yang ingin mereka selesaikan, dan di mana serta dengan perangkat apa mereka bekerja. Seorang pelajar yang belajar lewat ponsel di perjalanan membutuhkan tampilan yang berbeda dari seorang analis yang bekerja di layar lebar.

Ukuran kebergunaan (usability) yang umum dipakai meliputi kemudahan dipelajari, efisiensi, kemudahan diingat kembali, tingkat kesalahan, dan kepuasan. Sepanjang kursus ini, kelima ukuran itu akan menjadi tolok ukur setiap keputusan desain yang kita ambil."""),
            ("Hierarki Visual, Warna, dan Tipografi", 15, """
Hierarki visual mengarahkan mata pengguna ke hal terpenting lebih dahulu. Anda mengaturnya lewat ukuran, ketebalan, warna, jarak, dan posisi. Judul yang lebih besar dan tebal, tombol utama berwarna mencolok, dan ruang kosong yang cukup membuat halaman mudah dipindai.

Gunakan warna dengan tujuan. Pilih satu warna aksen untuk aksi utama dan jangan mengandalkan warna saja untuk menyampaikan makna, karena sebagian pengguna sulit membedakan warna tertentu. Pastikan kontras antara teks dan latar cukup; pedoman WCAG menyarankan rasio minimal 4,5:1 untuk teks berukuran normal.

Untuk tipografi, batasi diri pada satu atau dua jenis huruf. Ukuran teks isi sebaiknya sekitar 16 piksel agar nyaman dibaca di layar, dengan jarak antarbaris sekitar 1,5 kali ukuran huruf. Panjang baris yang ideal berkisar 50 sampai 75 karakter. Konsistensi pada hal-hal ini membuat antarmuka terasa rapi dan dapat dipercaya."""),
            ("Delapan Aturan Emas Shneiderman", 18, """
Ben Shneiderman merumuskan delapan aturan emas perancangan antarmuka yang masih relevan hingga kini. Berikut ringkasannya: (1) berusaha untuk konsisten; (2) memungkinkan pengguna berpengalaman memakai pintasan (pada edisi yang lebih baru disebut kegunaan universal); (3) memberi umpan balik yang informatif; (4) merancang dialog yang memberi penutupan; (5) mencegah kesalahan dan menyediakan penanganan kesalahan yang sederhana; (6) memudahkan pembatalan tindakan; (7) memberi pengguna rasa kendali; dan (8) mengurangi beban ingatan jangka pendek.

Contoh penerapannya: tombol utama selalu berada di posisi dan berwarna sama di semua halaman (konsisten); halaman konfirmasi pesanan menyatakan dengan jelas bahwa pembelian selesai (penutupan); dialog "Hapus balasan ini?" muncul sebelum data benar-benar dihapus (pencegahan kesalahan dan pembatalan).

Saat meninjau rancangan, jadikan kedelapan aturan ini sebagai daftar periksa. Cukup telusuri satu layar demi satu layar dan catat aturan mana yang belum terpenuhi."""),
            ("Umpan Balik dan Pesan Kesalahan yang Baik", 15, """
Pengguna perlu tahu apa yang sedang terjadi. Setiap tindakan sebaiknya mendapat respons yang terlihat: tombol berubah saat ditekan, indikator muncul saat data dimuat, dan notifikasi singkat (toast) tampil setelah penyimpanan berhasil. Respons yang cepat membuat pengguna yakin sistem bekerja.

Pesan kesalahan yang baik memiliki tiga ciri: spesifik, ramah, dan memberi jalan keluar. Bandingkan "Error 400" dengan "Email belum valid. Contoh: nama@email.com". Pesan kedua menjelaskan masalah dan cara memperbaikinya tanpa menyalahkan pengguna.

Hindari memakai alert() bawaan peramban untuk pesan penting karena tampilannya kaku dan memblokir halaman. Gunakan toast untuk informasi ringan dan dialog konfirmasi untuk tindakan berisiko, seperti menghapus data. Tampilkan pesan validasi di dekat kolom yang bermasalah supaya pengguna tidak perlu mencari-cari."""),
            ("Uji Kebergunaan Sederhana dengan SUS", 18, """
Rancangan yang menurut perancangnya jelas belum tentu jelas bagi pengguna. Karena itu uji dengan pengguna sungguhan. Uji kebergunaan sederhana dapat dilakukan dengan lima sampai delapan orang: beri satu tugas, misalnya "beli kursus dan mulai belajar", lalu amati tanpa membantu. Catat di mana mereka ragu, salah klik, atau berhenti.

Setelah itu, ukur kepuasan memakai System Usability Scale (SUS), yaitu kuesioner sepuluh pernyataan dengan skala setuju 1 sampai 5. Skor akhirnya berada pada rentang 0 sampai 100. Skor sekitar 68 sering dipakai sebagai rata-rata acuan; skor di bawahnya menandakan masih ada masalah kebergunaan yang perlu diperbaiki.

Tuliskan temuan sebagai daftar masalah beserta tingkat keparahannya, lalu perbaiki yang paling berdampak lebih dulu. Ulangi pengujian setelah perbaikan untuk memastikan masalahnya benar-benar hilang."""),
        ],
        "quiz_title": "Kuis Prinsip Desain Antarmuka",
        "pass_score": 70,
        "questions": [
            ("Manakah yang termasuk Delapan Aturan Emas Shneiderman?",
             "Gunakan sebanyak mungkin warna agar menarik",
             "Beri umpan balik yang informatif",
             "Sembunyikan fitur yang jarang dipakai selamanya",
             "Utamakan keinginan perancang daripada pengguna", "b",
             "Umpan balik yang informatif adalah salah satu dari delapan aturan emas. Pilihan lain bertentangan dengan prinsip IMK."),
            ("Manakah pesan kesalahan yang paling baik?",
             "Error 400",
             "Input salah!",
             "Email belum valid. Contoh: nama@email.com",
             "Terjadi kesalahan, hubungi administrator", "c",
             "Pesan yang baik spesifik, ramah, dan memberi jalan keluar, seperti pilihan ketiga."),
            ("Menurut pedoman WCAG, berapa rasio kontras minimal untuk teks berukuran normal?",
             "1,5:1", "3:1", "4,5:1", "10:1", "c",
             "WCAG menyarankan rasio kontras minimal 4,5:1 untuk teks normal agar tetap terbaca oleh banyak pengguna."),
            ("Skor System Usability Scale (SUS) berada pada rentang...",
             "0 sampai 10", "0 sampai 100", "1 sampai 5", "-100 sampai 100", "b",
             "Jawaban 1 sampai 5 pada tiap pernyataan dikonversi menjadi skor akhir 0 sampai 100."),
            ("Apa tujuan hierarki visual dalam sebuah antarmuka?",
             "Memperbanyak elemen di satu halaman",
             "Mengarahkan perhatian pengguna ke hal terpenting lebih dulu",
             "Membuat semua elemen tampak sama penting",
             "Menghilangkan kebutuhan akan teks", "b",
             "Hierarki visual memakai ukuran, warna, jarak, dan posisi agar pengguna tahu apa yang perlu dilihat lebih dulu."),
        ],
    },
]


# ---------------------------------------------------------------------------
# DATA: 6 produk. course_slug mengisi products.course_id (hanya produk bertipe 'course').
# Kursus "Prinsip Desain Antarmuka" sengaja gratis (tanpa produk) -> pendaftaran source='free'.
# (slug, nama, kategori, tipe, harga_rupiah, course_slug, hari_lalu, deskripsi)
# ---------------------------------------------------------------------------
PRODUCTS = [
    ("kursus-dasar-pemrograman-python", "Kursus Dasar Pemrograman Python untuk Pemula", "kursus-digital",
     "course", 149000, "dasar-pemrograman-python", 48,
     "Akses selamanya ke kursus Dasar Pemrograman Python: 5 pelajaran bertahap, contoh kode yang bisa "
     "dicoba langsung, dan kuis akhir. Cocok untuk Anda yang belum pernah memprogram. Setelah pembayaran, "
     "kursus otomatis muncul di E-Learning."),
    ("kursus-dasar-sql-basis-data", "Kursus Dasar SQL dan Perancangan Basis Data", "kursus-digital",
     "course", 179000, "dasar-sql-perancangan-basis-data", 44,
     "Dari tabel dan kunci hingga JOIN, normalisasi, indeks, dan transaksi. Dilengkapi contoh kueri SQLite "
     "dan kuis akhir. Setelah pembayaran, kursus otomatis terdaftar di akun Anda."),
    ("ebook-panduan-praktis-flask", "E-Book Panduan Praktis Flask untuk Pemula", "e-book",
     "ebook", 79000, None, 40,
     "E-book 120 halaman yang memandu Anda membangun aplikasi web dengan Flask langkah demi langkah: "
     "routing, template Jinja2, formulir, autentikasi sesi, dan basis data SQLite. Format PDF."),
    ("ebook-latihan-soal-sql", "E-Book 100 Latihan Soal SQL dan Pembahasan", "e-book",
     "ebook", 59000, None, 36,
     "Kumpulan 100 soal latihan SQL dari tingkat dasar sampai menengah beserta pembahasan tiap soal. "
     "Cocok untuk persiapan ujian praktikum basis data. Format PDF."),
    ("template-laporan-tugas-besar", "Template Laporan Tugas Besar (Word)", "template-aset",
     "template", 39000, None, 30,
     "Template dokumen Word dengan gaya judul, penomoran bab, daftar isi otomatis, dan format daftar "
     "pustaka yang rapi. Tinggal isi dan sesuaikan dengan pedoman kampus Anda."),
    ("template-wireframe-mobile", "Kit Wireframe Aplikasi Mobile", "template-aset",
     "template", 89000, None, 26,
     "Kumpulan 40 kerangka layar aplikasi mobile (beranda, daftar, detail, formulir, profil) dalam format "
     "yang dapat dibuka di Figma. Mempercepat tahap perancangan antarmuka sebelum mulai menulis kode."),
]

# ---------------------------------------------------------------------------
# DATA: 5 tutorial dengan langkah dan snippet kode
# langkah: (judul, isi, bahasa_kode, kode)
# ---------------------------------------------------------------------------
TUTORIALS = [
    {
        "slug": "membuat-aplikasi-flask-pertama",
        "title": "Membuat Aplikasi Flask Pertama",
        "category": "web", "difficulty": "mudah", "minutes": 20, "days_ago": 38,
        "summary": "Bangun aplikasi web kecil dengan Flask: dari lingkungan virtual, route, sampai template HTML.",
        "steps": [
            ("Siapkan folder dan lingkungan virtual",
             "Buat folder proyek lalu lingkungan virtual agar paket Python proyek ini tidak bercampur dengan proyek lain. Aktifkan lingkungan tersebut sebelum memasang paket apa pun.",
             "bash", r'''mkdir flask-pertama
cd flask-pertama
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate'''),
            ("Pasang Flask",
             "Pasang Flask dengan pip, lalu pastikan terpasang dengan menampilkan informasi paketnya. Bila nama lingkungan muncul di awal baris terminal, berarti lingkungan virtual sudah aktif.",
             "bash", r'''pip install Flask
pip show flask'''),
            ("Tulis aplikasi pertama",
             "Buat berkas app.py. Objek Flask adalah inti aplikasi, dan dekorator @app.route mengaitkan alamat URL dengan sebuah fungsi. Fungsi render_template akan mencari berkas HTML di folder templates.",
             "python", r'''from flask import Flask, render_template

app = Flask(__name__)


@app.route("/")
def beranda():
    return render_template("beranda.html", nama="Dunia")'''),
            ("Buat template HTML dengan Jinja2",
             "Buat folder templates lalu berkas beranda.html di dalamnya. Tanda {{ nama }} akan diganti dengan nilai yang dikirim dari fungsi beranda. Jinja2 otomatis meng-escape isi variabel sehingga aman dari XSS.",
             "html", r'''<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <title>Halo Flask</title>
</head>
<body>
  <h1>Halo, {{ nama }}!</h1>
</body>
</html>'''),
            ("Jalankan dan coba",
             "Jalankan server pengembangan dengan opsi --debug agar halaman dimuat ulang otomatis setiap kode berubah, lalu buka alamat yang tampil di terminal (biasanya http://127.0.0.1:5000). Jangan memakai mode debug pada server yang dapat diakses publik.",
             "bash", r'''flask --app app run --debug'''),
        ],
    },
    {
        "slug": "membaca-data-csv-dengan-pandas",
        "title": "Membaca dan Merangkum Data CSV dengan pandas",
        "category": "python", "difficulty": "mudah", "minutes": 15, "days_ago": 34,
        "summary": "Baca berkas CSV penjualan, periksa isinya, hitung total per produk, lalu simpan hasilnya.",
        "steps": [
            ("Pasang pandas",
             "pandas adalah pustaka populer untuk mengolah data tabel. Pasang dengan pip di lingkungan virtual yang aktif.",
             "bash", r'''pip install pandas'''),
            ("Siapkan berkas CSV contoh",
             "Simpan data berikut sebagai penjualan.csv di folder yang sama dengan skrip Anda. Baris pertama adalah nama kolom, dan antarkolom dipisahkan koma.",
             "csv", r'''tanggal,produk,jumlah,harga
2026-11-01,Buku Tulis,10,5000
2026-11-01,Pulpen,25,3000
2026-11-02,Buku Tulis,5,5000
2026-11-02,Penghapus,12,2000'''),
            ("Baca dan periksa data",
             "Fungsi read_csv memuat berkas menjadi DataFrame. Opsi parse_dates mengubah kolom tanggal menjadi tipe tanggal. Gunakan head() dan dtypes untuk memastikan data terbaca dengan benar sebelum diolah.",
             "python", r'''import pandas as pd

df = pd.read_csv("penjualan.csv", parse_dates=["tanggal"])
print(df.head())
print(df.dtypes)'''),
            ("Hitung total per produk dan simpan",
             "Tambahkan kolom total, kelompokkan menurut produk dengan groupby, jumlahkan, lalu urutkan dari yang terbesar. Hasil akhirnya dapat disimpan ke berkas CSV baru.",
             "python", r'''df["total"] = df["jumlah"] * df["harga"]
ringkasan = df.groupby("produk")["total"].sum().sort_values(ascending=False)
print(ringkasan)
ringkasan.to_csv("ringkasan_produk.csv")'''),
        ],
    },
    {
        "slug": "dasar-git-commit-branch-merge",
        "title": "Dasar Git: Commit, Branch, dan Merge",
        "category": "alat-developer", "difficulty": "mudah", "minutes": 25, "days_ago": 30,
        "summary": "Kenali alur kerja Git sehari-hari: membuat repositori, commit, cabang fitur, menggabungkan, dan mengunggah.",
        "steps": [
            ("Buat repositori dan atur identitas",
             "Inisialisasi repositori di folder proyek dengan cabang utama bernama main, lalu isi nama dan email yang akan tercatat pada setiap commit. Pengaturan identitas cukup dilakukan sekali per komputer bila memakai opsi --global.",
             "bash", r'''git init -b main
git config user.name "Nama Anda"
git config user.email "nama@email.com"'''),
            ("Buat commit pertama",
             "Perintah git add menandai berkas yang akan disimpan, dan git commit merekamnya dengan pesan singkat yang menjelaskan perubahan. Gunakan git status kapan saja untuk melihat keadaan terkini.",
             "bash", r'''git add .
git commit -m "Tambah berkas awal proyek"
git status'''),
            ("Kerjakan fitur di cabang terpisah",
             "Cabang memungkinkan Anda bereksperimen tanpa mengganggu kode utama. Buat cabang baru, ubah berkas, lalu commit seperti biasa.",
             "bash", r'''git switch -c fitur-login
# ... ubah berkas, lalu:
git add .
git commit -m "Tambah halaman login"'''),
            ("Gabungkan cabang ke main",
             "Setelah fitur selesai, kembali ke main lalu gabungkan cabang fitur. Cabang yang sudah digabung dapat dihapus agar daftar cabang tetap rapi. Bila terjadi konflik, Git menandai bagian yang bentrok di berkas; selesaikan secara manual lalu commit.",
             "bash", r'''git switch main
git merge fitur-login
git branch -d fitur-login'''),
            ("Unggah ke repositori jarak jauh",
             "Hubungkan repositori lokal ke layanan seperti GitHub dengan git remote add, lalu kirim commit dengan git push. Ganti alamat contoh di bawah dengan alamat repositori Anda sendiri.",
             "bash", r'''git remote add origin https://github.com/username/proyek-saya.git
git push -u origin main'''),
        ],
    },
    {
        "slug": "query-sqlite-dengan-python",
        "title": "Mengelola Data SQLite dengan Modul sqlite3",
        "category": "python", "difficulty": "menengah", "minutes": 20, "days_ago": 26,
        "summary": "Buat tabel, simpan data dengan query berparameter, baca hasilnya per nama kolom, dan kelola transaksi.",
        "steps": [
            ("Buat koneksi dan tabel",
             "Modul sqlite3 sudah termasuk dalam Python sehingga tidak perlu dipasang. connect() membuat berkas basis data bila belum ada. Aktifkan foreign_keys karena SQLite mematikannya secara bawaan.",
             "python", r'''import sqlite3

conn = sqlite3.connect("catatan.db")
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("""
    CREATE TABLE IF NOT EXISTS catatan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        judul TEXT NOT NULL,
        isi TEXT
    )
""")
conn.commit()'''),
            ("Simpan data dengan query berparameter",
             "Selalu kirim nilai lewat tanda tanya (?) dan tuple parameter, jangan menyusun SQL dengan penggabungan string. Cara ini mencegah serangan SQL injection.",
             "python", r'''judul = "Belajar SQLite"
isi = "Gunakan tanda tanya agar aman dari SQL injection."
conn.execute("INSERT INTO catatan (judul, isi) VALUES (?, ?)", (judul, isi))
conn.commit()'''),
            ("Baca data berdasarkan nama kolom",
             "Atur row_factory ke sqlite3.Row supaya setiap baris dapat diakses lewat nama kolom, bukan nomor indeks. Kode menjadi lebih mudah dibaca dan tidak rusak bila urutan kolom berubah.",
             "python", r'''conn.row_factory = sqlite3.Row
for baris in conn.execute("SELECT id, judul FROM catatan ORDER BY id DESC"):
    print(baris["id"], baris["judul"])'''),
            ("Gunakan transaksi dan tutup koneksi",
             "Blok with conn menjalankan commit otomatis bila berhasil dan rollback bila terjadi kesalahan. Tutup koneksi di bagian finally agar sumber daya selalu dilepas.",
             "python", r'''try:
    with conn:   # commit otomatis, rollback bila ada error
        conn.execute("UPDATE catatan SET judul = ? WHERE id = ?", ("Judul baru", 1))
finally:
    conn.close()'''),
        ],
    },
    {
        "slug": "tata-letak-responsif-tailwind",
        "title": "Membuat Tata Letak Responsif dengan Tailwind CSS",
        "category": "web", "difficulty": "mudah", "minutes": 20, "days_ago": 22,
        "summary": "Susun grid kartu dan navigasi yang menyesuaikan ukuran layar, lengkap dengan mode gelap.",
        "steps": [
            ("Muat Tailwind lewat CDN",
             "Untuk belajar dan prototipe, Tailwind dapat dimuat lewat satu tag script tanpa instalasi. Letakkan di dalam head. Untuk produksi, hasilkan berkas CSS statis dengan Tailwind CLI.",
             "html", r'''<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="https://cdn.tailwindcss.com"></script>
  <title>Tailwind Responsif</title>
</head>'''),
            ("Susun grid kartu yang responsif",
             "Tailwind memakai pendekatan mobile-first: kelas tanpa awalan berlaku untuk semua layar, sedangkan awalan sm:, md:, dan lg: berlaku mulai lebar tertentu. Grid di bawah menampilkan 1 kolom di ponsel, 2 kolom di tablet, dan 3 kolom di layar lebar.",
             "html", r'''<div class="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
  <div class="rounded-lg border p-4">Kartu 1</div>
  <div class="rounded-lg border p-4">Kartu 2</div>
  <div class="rounded-lg border p-4">Kartu 3</div>
</div>'''),
            ("Buat navigasi yang menyesuaikan layar",
             "Sembunyikan menu mendatar di layar kecil dengan hidden lalu tampilkan mulai breakpoint md dengan md:flex. Di ponsel, tampilkan tombol menu sebagai gantinya.",
             "html", r'''<nav class="flex items-center justify-between p-4">
  <a href="/" class="font-bold">DKE</a>
  <ul class="hidden gap-6 md:flex">
    <li><a href="/portal/">Portal</a></li>
    <li><a href="/forum/">Forum</a></li>
  </ul>
  <button class="md:hidden" aria-label="Buka menu">Menu</button>
</nav>'''),
            ("Tambahkan mode gelap",
             "Atur darkMode ke 'class' agar tema ditentukan oleh kelas dark pada elemen html. Setelah itu, tambahkan varian dark: pada warna yang perlu berubah, dan buat tombol yang mengaktifkan atau mematikan kelas tersebut.",
             "javascript", r'''tailwind.config = { darkMode: 'class' };

// Pada elemen: class="bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100"
document.getElementById('tombol-tema').addEventListener('click', () => {
  document.documentElement.classList.toggle('dark');
});'''),
        ],
    },
]


# ---------------------------------------------------------------------------
# DATA: 10 artikel Portal (2 featured). Penulis: akun admin.
# (slug, judul, kategori, featured, menit_baca, views, hari_lalu, kutipan, isi)
# ---------------------------------------------------------------------------
ARTICLES = [
    ("belajar-mandiri-butuh-sistem", "Mengapa Belajar Mandiri Butuh Sistem, Bukan Sekadar Motivasi",
     "pendidikan", 1, 6, 1248, 3,
     "Semangat belajar mudah naik turun. Jadwal tetap, target kecil, dan evaluasi mingguan membuat belajar mandiri tetap berjalan.",
     """
Hampir semua orang pernah memulai belajar dengan semangat tinggi, lalu berhenti beberapa minggu kemudian. Penyebabnya jarang soal kemampuan. Motivasi memang kuat di awal, tetapi ia naik turun mengikuti suasana hati, beban kerja, dan kelelahan. Karena itu, belajar mandiri yang bertahan lama biasanya bertumpu pada sistem, bukan pada semangat semata.

Sistem yang sederhana pun sudah cukup. Tentukan jadwal tetap, misalnya satu jam setiap malam pukul delapan, sehingga belajar menjadi kebiasaan, bukan keputusan yang harus diambil ulang setiap hari. Pecah tujuan besar seperti "menguasai pemrograman web" menjadi target kecil yang bisa selesai dalam satu sesi, seperti "membuat satu formulir login yang berfungsi". Target kecil memberi rasa maju yang nyata dan mudah dicatat.

Terakhir, sisihkan lima belas menit setiap akhir pekan untuk mengevaluasi: apa yang sudah dipahami, apa yang masih membingungkan, dan apa yang akan dikerjakan pekan depan. Evaluasi singkat ini mencegah Anda berputar di topik yang sama dan membantu menyesuaikan rencana ketika ritme hidup berubah. Mulailah dari yang paling kecil, lalu pertahankan konsistensinya."""),

    ("lima-kebiasaan-developer-pemula", "Lima Kebiasaan Developer Pemula yang Mempercepat Belajar",
     "karier", 0, 5, 842, 6,
     "Bukan soal jumlah jam, melainkan cara belajarnya. Lima kebiasaan ini membuat kemajuan pemula terasa lebih cepat.",
     """
Banyak pemula mengira kemajuan datang dari menonton lebih banyak video. Pada praktiknya, orang yang cepat berkembang punya kebiasaan yang berbeda, dan kebiasaan itu bisa ditiru siapa saja.

Pertama, menulis kode sendiri, bukan hanya membaca atau menyalin. Setelah mengikuti contoh, tutup tutorialnya dan coba ulang dari nol. Kedua, membangun proyek mini di setiap topik baru, misalnya daftar tugas setelah belajar formulir. Ketiga, membaca pesan kesalahan sampai selesai; sebagian besar jawaban ada di baris terakhirnya. Keempat, memakai Git sejak proyek pertama sehingga setiap perubahan tercatat dan bisa dibatalkan. Kelima, menjelaskan apa yang dipelajari kepada orang lain atau menuliskannya sebagai catatan, karena kita baru benar-benar paham ketika bisa menjelaskannya.

Tidak perlu menerapkan kelimanya sekaligus. Pilih satu yang paling terasa kurang pada kebiasaan Anda sekarang, jalankan selama dua minggu, lalu tambahkan yang berikutnya."""),

    ("memahami-sqlite-basis-data-ringan", "Memahami SQLite: Basis Data Ringan untuk Proyek Kecil dan Menengah",
     "teknologi", 0, 6, 615, 9,
     "SQLite menyimpan seluruh basis data dalam satu berkas dan tidak memerlukan server. Kapan ia cocok dipakai, dan kapan tidak?",
     """
SQLite adalah mesin basis data relasional yang tertanam langsung di dalam aplikasi. Tidak ada server terpisah yang perlu dipasang atau dikonfigurasi; seluruh basis data tersimpan dalam satu berkas. Karena kesederhanaannya, SQLite banyak dipakai pada aplikasi ponsel, perangkat lunak desktop, dan prototipe aplikasi web.

Kelebihan utamanya adalah kemudahan: memindahkan basis data cukup dengan menyalin satu berkas, dan modul sqlite3 sudah tersedia bersama Python. Untuk proyek belajar, tugas kuliah, atau aplikasi dengan sedikit pengguna bersamaan, SQLite lebih dari memadai. Pastikan juga mengaktifkan PRAGMA foreign_keys = ON karena pemeriksaan kunci asing tidak menyala secara bawaan.

Keterbatasannya muncul ketika banyak pengguna menulis data secara bersamaan, karena SQLite mengunci basis data saat penulisan. Untuk layanan dengan lalu lintas tinggi atau kebutuhan hak akses yang rumit, basis data berbasis server seperti PostgreSQL atau MySQL lebih tepat. Kabar baiknya, bila dasar SQL Anda kuat, berpindah dari satu mesin ke mesin lain tidak terlalu sulit."""),

    ("teknik-pomodoro-dan-time-blocking", "Teknik Pomodoro dan Time Blocking untuk Mahasiswa",
     "produktivitas", 0, 4, 530, 12,
     "Dua teknik pengelolaan waktu yang sederhana: bekerja dalam interval pendek dan memberi jatah waktu khusus untuk tiap tugas.",
     """
Menunda tugas sering terjadi bukan karena malas, melainkan karena tugasnya terasa terlalu besar untuk dimulai. Teknik Pomodoro mengatasinya dengan memecah waktu menjadi interval pendek: bekerja fokus selama 25 menit, istirahat 5 menit, dan setelah empat putaran ambil istirahat lebih panjang. Karena komitmennya hanya 25 menit, hambatan untuk mulai menjadi jauh lebih kecil.

Time blocking melengkapinya dengan cara lain. Alih-alih membuat daftar tugas tanpa waktu, Anda memberi setiap tugas satu blok waktu di kalender, misalnya "Selasa 19.00 sampai 20.30: mengerjakan laporan basis data". Dengan begitu Anda tahu kapan tugas akan dikerjakan, dan bentrokan jadwal terlihat sejak awal.

Keduanya dapat digabung: tetapkan blok waktu di kalender, lalu isi blok itu dengan putaran Pomodoro. Matikan notifikasi selama putaran berlangsung dan catat apa yang selesai di akhir. Bila ternyata satu blok tidak cukup, itu informasi berharga untuk memperkirakan waktu secara lebih realistis di masa depan."""),

    ("antarmuka-ramah-pengguna-prinsip-imk", "Apa Itu Antarmuka yang Ramah Pengguna? Pengantar Prinsip IMK",
     "teknologi", 1, 7, 1102, 2,
     "Aplikasi yang lengkap fiturnya belum tentu mudah dipakai. Interaksi Manusia dan Komputer (IMK) memberi panduan merancang yang berpusat pada pengguna.",
     """
Pernahkah Anda meninggalkan sebuah situs karena bingung harus menekan tombol yang mana? Pengalaman seperti itu adalah masalah antarmuka, dan bidang yang mempelajarinya disebut Interaksi Manusia dan Komputer (IMK). Tujuannya sederhana: membuat sistem yang mudah dipelajari, efisien, dan menyenangkan dipakai.

Salah satu panduan yang paling sering dirujuk adalah Delapan Aturan Emas dari Ben Shneiderman. Di antaranya: konsisten dalam tampilan dan perilaku, memberi umpan balik yang jelas atas setiap tindakan, mencegah kesalahan sebelum terjadi, dan memudahkan pengguna membatalkan tindakan. Contoh nyatanya adalah dialog konfirmasi sebelum menghapus data, atau pesan kesalahan yang menyebutkan cara memperbaikinya, bukan sekadar kode galat.

IMK juga mengingatkan bahwa pengguna berbeda-beda: usia, pengalaman, perangkat, bahkan kondisi sekitar saat memakai aplikasi. Karena itu, rancangan sebaiknya diuji dengan pengguna sungguhan sejak dini. Cukup lima sampai delapan orang untuk menemukan sebagian besar masalah utama, dan perbaikan di tahap rancangan jauh lebih murah dibandingkan setelah aplikasi jadi."""),

    ("menyusun-portofolio-proyek-yang-dilirik-perekrut", "Cara Menyusun Portofolio Proyek yang Dilirik Perekrut",
     "karier", 0, 6, 977, 15,
     "Portofolio yang baik bukan tumpukan proyek, melainkan beberapa proyek yang dijelaskan dengan jelas: masalah, pendekatan, dan hasilnya.",
     """
Bagi pencari kerja di bidang teknologi, portofolio sering berbicara lebih banyak daripada daftar mata kuliah. Namun jumlah proyek bukan ukurannya. Tiga sampai lima proyek yang selesai dan dijelaskan dengan baik biasanya lebih meyakinkan daripada dua puluh repositori setengah jadi.

Untuk setiap proyek, tuliskan README yang menjawab empat hal: masalah apa yang diselesaikan, teknologi yang dipakai beserta alasannya, cara menjalankannya, dan apa yang Anda pelajari. Sertakan tangkapan layar atau tautan demo bila ada. Perekrut sering hanya punya beberapa menit, jadi buat bagian awal README cukup padat untuk dipahami sekilas.

Pilih proyek yang menunjukkan rentang kemampuan: satu yang melibatkan basis data dan autentikasi, satu yang menunjukkan perhatian pada tampilan dan kegunaan, dan satu yang dikerjakan bersama tim bila memungkinkan. Rapikan juga riwayat commit dan hapus data atau kunci rahasia dari repositori sebelum dipublikasikan."""),

    ("kecerdasan-buatan-di-kelas", "Kecerdasan Buatan di Kelas: Peluang dan Batasannya bagi Pelajar",
     "pendidikan", 0, 6, 756, 18,
     "Alat berbasis kecerdasan buatan dapat membantu belajar, asalkan dipakai sebagai pendamping berpikir, bukan pengganti.",
     """
Asisten berbasis kecerdasan buatan kini mudah diakses pelajar dan mahasiswa. Dipakai dengan tepat, alat ini dapat menjelaskan konsep dengan beberapa cara, membuat contoh soal latihan, atau memberi umpan balik cepat pada draf tulisan. Bagi pelajar mandiri yang tidak selalu punya tempat bertanya, ini bisa menjadi pendamping yang berguna.

Meski begitu, ada batasan yang perlu diingat. Jawaban yang terdengar meyakinkan belum tentu benar, sehingga hal penting perlu diperiksa ulang pada buku, dokumentasi resmi, atau dosen. Menyalin jawaban begitu saja juga menghilangkan proses berpikir yang justru membuat kita paham. Selain itu, ketentuan penggunaan alat ini dalam tugas berbeda-beda di tiap institusi; pastikan Anda mengetahui aturannya.

Cara pakai yang sehat adalah mencoba mengerjakan sendiri terlebih dahulu, lalu memakai alat itu untuk membandingkan, menanyakan bagian yang belum dipahami, dan menguji pemahaman. Dengan pola ini, teknologi memperkuat kemampuan belajar, bukan menggantikannya."""),

    ("tiga-kesalahan-keamanan-aplikasi-web", "Keamanan Dasar Aplikasi Web: Tiga Kesalahan yang Sering Terjadi",
     "teknologi", 0, 7, 689, 21,
     "Menyimpan kata sandi apa adanya, menyusun SQL dengan penggabungan string, dan menampilkan input tanpa disaring. Ketiganya mudah dicegah.",
     """
Keamanan sering terasa seperti urusan ahli, padahal banyak kebocoran berawal dari kesalahan dasar. Tiga di antaranya sangat umum pada aplikasi buatan pemula, dan ketiganya dapat dicegah dengan kebiasaan sederhana.

Kesalahan pertama adalah menyimpan kata sandi dalam bentuk asli. Simpanlah hanya hasil hash menggunakan fungsi yang disediakan kerangka kerja, misalnya generate_password_hash di Werkzeug, sehingga kata sandi asli tidak dapat dibaca meski basis data bocor. Kesalahan kedua adalah menyusun perintah SQL dengan penggabungan string. Gunakan query berparameter agar masukan pengguna selalu diperlakukan sebagai data, bukan sebagai bagian dari perintah.

Kesalahan ketiga adalah menampilkan masukan pengguna tanpa menyaringnya, yang membuka celah Cross-Site Scripting (XSS). Jinja2 pada Flask meng-escape isi variabel secara otomatis; jangan mematikannya kecuali benar-benar perlu. Tambahkan juga kebiasaan memeriksa kepemilikan data di setiap rute, supaya pengguna hanya dapat mengubah data miliknya sendiri."""),

    ("catatan-belajar-efektif-metode-cornell", "Menulis Catatan Belajar yang Efektif dengan Metode Cornell",
     "produktivitas", 0, 4, 412, 25,
     "Metode Cornell membagi halaman menjadi tiga bagian sehingga catatan sekaligus menjadi bahan mengulang.",
     """
Banyak catatan kuliah berakhir sebagai tumpukan tulisan yang jarang dibuka lagi. Metode Cornell membantu mengubah catatan menjadi alat belajar. Halaman dibagi menjadi tiga area: kolom catatan di sisi kanan, kolom isyarat yang lebih sempit di sisi kiri, dan ringkasan di bagian bawah.

Saat mendengarkan atau membaca, tulis poin-poin penting di kolom catatan dengan kalimat singkat. Setelah selesai, isi kolom isyarat dengan kata kunci atau pertanyaan yang dijawab oleh catatan itu, misalnya "Apa beda INNER JOIN dan LEFT JOIN?". Terakhir, tulis ringkasan satu sampai dua kalimat di bagian bawah dengan kata-kata Anda sendiri.

Keuntungannya muncul saat mengulang: tutup kolom catatan dan jawab pertanyaan di kolom isyarat dari ingatan, lalu cocokkan. Cara ini melatih pengambilan ingatan secara aktif, yang umumnya lebih efektif daripada membaca ulang. Metode ini dapat dikerjakan di kertas maupun aplikasi catatan digital."""),

    ("pembelajaran-daring-menjaga-fokus", "Pembelajaran Daring Efektif: Menjaga Fokus dan Konsistensi",
     "pendidikan", 0, 5, 534, 30,
     "Belajar daring fleksibel, tetapi mudah teralihkan. Atur ruang, waktu, dan target agar fokus tetap terjaga.",
     """
Belajar secara daring memberi kebebasan memilih waktu dan tempat, tetapi kebebasan itu menuntut pengaturan diri yang lebih ketat. Tanpa jadwal kelas, godaan untuk menunda dan teralihkan notifikasi menjadi lebih besar.

Mulailah dengan menyiapkan ruang yang konsisten. Tidak harus ruangan khusus; sudut meja yang selalu dipakai untuk belajar sudah cukup memberi isyarat kepada otak bahwa ini waktunya fokus. Tutup tab dan aplikasi yang tidak berkaitan, dan letakkan ponsel di luar jangkauan selama sesi belajar. Tentukan juga satu target jelas untuk setiap sesi, misalnya menyelesaikan satu pelajaran dan kuisnya.

Jangan lupa unsur sosial. Bergabung di forum atau kelompok belajar membuat Anda punya tempat bertanya dan alasan untuk tetap konsisten. Bila kemajuan terasa lambat, ingat bahwa konsistensi dalam porsi kecil biasanya mengalahkan sesi panjang yang jarang-jarang. Periksa progres secara berkala, dan rayakan capaian kecil agar semangat tetap terjaga."""),
]


# ---------------------------------------------------------------------------
# DATA: 5 thread forum beserta balasan
# posts: (label, email_penulis, label_induk atau None, jam_setelah_thread, isi)
# Balasan bersarang hanya 1 tingkat (induk selalu balasan tingkat atas).
# ---------------------------------------------------------------------------
THREADS = [
    {
        "title": "Error \"no such table: users\" saat membuka halaman login",
        "category": "tanya-jawab-teknis", "author": "budi@dke.test", "days_ago": 12, "views": 87,
        "accepted": "t1p1",
        "body": (
            "Halo semua, saya baru menjalankan proyek Flask dari repositori kelompok. Saat membuka "
            "/infosys/login muncul error sqlite3.OperationalError: no such table: users. Perintah "
            "python run.py berjalan tanpa masalah. Apa yang kurang?"),
        "posts": [
            ("t1p1", ADMIN_EMAIL, None, 2,
             "Kemungkinan besar databasenya belum dibuat. Tabel dibuat oleh seed.py, bukan oleh run.py. "
             "Jalankan python seed.py dari folder proyek (satu level dengan run.py), tunggu sampai muncul "
             "ringkasan jumlah baris, lalu jalankan ulang aplikasinya."),
            ("t1p2", "budi@dke.test", "t1p1", 3,
             "Sudah saya coba dan berhasil, terima kasih! Ternyata saya melewatkan langkah itu di README."),
            ("t1p3", "citra@dke.test", None, 5,
             "Tambahan: seed.py aman dijalankan ulang, jadi kalau datanya terasa berantakan, jalankan "
             "python seed.py --reset untuk membuat ulang database dari nol. Ingat, perintah itu menghapus semua data lama."),
        ],
    },
    {
        "title": "Bedanya INNER JOIN dan LEFT JOIN itu apa, ya?",
        "category": "tanya-jawab-teknis", "author": "dewi@dke.test", "days_ago": 9, "views": 112,
        "accepted": "t2p1",
        "body": (
            "Saya masih bingung kapan memakai INNER JOIN dan kapan LEFT JOIN. Di tugas basis data saya ada "
            "tabel mahasiswa dan tabel nilai, dan beberapa mahasiswa belum punya nilai. Kenapa hasil kueri "
            "saya tidak menampilkan mereka?"),
        "posts": [
            ("t2p1", "eko@dke.test", None, 3,
             "INNER JOIN hanya mengembalikan baris yang punya pasangan di kedua tabel, jadi mahasiswa tanpa "
             "nilai ikut tersaring. Pakai LEFT JOIN dari mahasiswa ke nilai: semua mahasiswa tetap muncul, "
             "dan kolom dari tabel nilai berisi NULL untuk yang belum punya nilai."),
            ("t2p2", "dewi@dke.test", "t2p1", 5,
             "Oh, jadi yang belum punya nilai muncul dengan kolom nilai kosong, ya? Berarti saya bisa mencari "
             "mereka saja dengan WHERE nilai.id IS NULL?"),
            ("t2p3", "eko@dke.test", "t2p1", 6,
             "@Dewi Anggraini betul, persis begitu. Pastikan kolom yang dicek berasal dari tabel sebelah kanan, "
             "dan tulis IS NULL, bukan = NULL (yang tidak pernah bernilai benar)."),
            ("t2p4", ADMIN_EMAIL, None, 9,
             "Pembahasan lengkapnya ada di pelajaran 3 kursus Dasar SQL dan Perancangan Basis Data, lengkap "
             "dengan contoh mencari data yang belum punya relasi."),
        ],
    },
    {
        "title": "Urutan belajar yang disarankan untuk menjadi web developer?",
        "category": "karier-belajar", "author": DEMO_EMAIL, "days_ago": 6, "views": 142,
        "accepted": None,
        "body": (
            "Saya mahasiswa semester 3 dan ingin fokus ke pengembangan web. Pilihannya banyak sekali: HTML, "
            "CSS, JavaScript, Python, berbagai kerangka kerja. Menurut kalian, urutan belajar yang masuk akal "
            "seperti apa supaya tidak lompat-lompat?"),
        "posts": [
            ("t3p1", "citra@dke.test", None, 4,
             "Saran saya: HTML dan CSS dulu (2 sampai 3 minggu), lalu dasar JavaScript. Setelah itu pilih satu "
             "bahasa backend saja, misalnya Python dengan Flask, dan selesaikan satu proyek kecil sebelum "
             "pindah ke hal lain."),
            ("t3p2", "budi@dke.test", None, 7,
             "Setuju. Satu hal yang menolong saya: setiap selesai satu topik, langsung buat proyek mini. "
             "Belajar dari tutorial saja membuat saya cepat lupa."),
            ("t3p3", ADMIN_EMAIL, None, 20,
             "Diskusi yang bagus. Di DKE ada kursus Dasar Pemrograman Python dan tutorial Membuat Aplikasi "
             "Flask Pertama yang bisa jadi titik awal. Padukan dengan tutorial Tailwind CSS untuk urusan tampilan."),
            ("t3p4", DEMO_EMAIL, "t3p1", 22,
             "Terima kasih, Citra! Saya akan coba pola proyek mini dulu. Kalau boleh tahu, proyek mini "
             "pertamamu dulu apa?"),
            ("t3p5", "citra@dke.test", "t3p1", 26,
             "@Pengguna Demo aplikasi daftar tugas sederhana. Fiturnya cuma tambah, centang selesai, dan hapus, "
             "tapi dari situ saya belajar formulir, basis data, dan validasi."),
        ],
    },
    {
        "title": "Berbagi: cara saya menjaga konsistensi belajar 1 jam per hari",
        "category": "diskusi-umum", "author": "eko@dke.test", "days_ago": 4, "views": 64,
        "accepted": None,
        "body": (
            "Sudah tiga bulan saya belajar 1 jam setiap hari sepulang kerja. Caranya sederhana: jadwal tetap "
            "pukul 20.00, ponsel mode senyap, dan satu target kecil tiap sesi. Setiap selesai saya beri tanda "
            "centang di kalender. Ada yang punya cara lain?"),
        "posts": [
            ("t4p1", "dewi@dke.test", None, 3,
             "Saya pakai Pomodoro 25 menit; dua putaran saja sudah terasa cukup. Tanda centang di kalender "
             "memang efektif, rasanya sayang kalau rantainya putus."),
            ("t4p2", "budi@dke.test", None, 6,
             "Kalau saya belajar pagi sebelum ngantuk. Tapi ritme tiap orang beda, yang penting waktunya tetap."),
            ("t4p3", ADMIN_EMAIL, None, 10,
             "Terima kasih sudah berbagi. Pengaturan target belajar harian (menit per hari) di tab Pengaturan "
             "E-Learning bisa membantu mencatat target ini."),
        ],
    },
    {
        "title": "Showcase: aplikasi pencatat keuangan sederhana dengan Flask",
        "category": "showcase-proyek", "author": "citra@dke.test", "days_ago": 2, "views": 103,
        "accepted": None,
        "body": (
            "Akhirnya selesai juga proyek pertama saya: aplikasi pencatat pemasukan dan pengeluaran dengan "
            "Flask dan SQLite. Fiturnya tambah transaksi, filter per bulan, dan ringkasan saldo. Tampilan "
            "mobilenya masih banyak kekurangan. Masukan sangat diterima!"),
        "posts": [
            ("t5p1", "eko@dke.test", None, 4,
             "Keren! Saran saya, validasi nominal juga di sisi server, jangan hanya di formulir HTML, karena "
             "data bisa saja dikirim langsung tanpa melewati formulir."),
            ("t5p2", ADMIN_EMAIL, None, 8,
             "Selamat atas proyek pertamanya. Untuk tampilan mobile, coba uji di lebar 360 px dan pastikan "
             "tabel yang lebar punya pembungkus overflow-x agar bisa digulir ke samping."),
            ("t5p3", "citra@dke.test", "t5p1", 9,
             "@Eko Prasetyo benar, terima kasih. Validasinya akan saya pindahkan ke fungsi tersendiri di sisi server."),
        ],
    },
]


# ---------------------------------------------------------------------------
# PENGISIAN DATA
# ---------------------------------------------------------------------------
def seed_users(conn):
    """Buat akun bila belum ada. Akun yang sudah ada tidak diubah (termasuk kata sandinya)."""
    ids, created = {}, set()
    for email, name, role, bio, days_ago, password in USERS:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            # Akun komunitas (password None) diberi hash acak yang tidak diketahui siapa pun,
            # sehingga tidak bisa dipakai login tetapi tetap valid sebagai baris users.
            pw_hash = generate_password_hash(password or secrets.token_urlsafe(24))
            cur = conn.execute(
                "INSERT INTO users (full_name, email, password_hash, role, bio, is_active, created_at, last_login_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (name, email, pw_hash, role, bio, ts(days_ago), ts(1) if password else ts(days_ago - 1)))
            ids[email] = cur.lastrowid
            created.add(email)
        else:
            ids[email] = row[0]
        insert_ignore(conn, "user_settings", {
            "user_id": ids[email], "theme": "light", "view_mode": "desktop",
            "landing_mode": "launcher", "updated_at": ts(days_ago)})
    return ids, created


def seed_categories(conn):
    cats = {}
    for module_key, name, slug in CATEGORIES:
        cats[(module_key, slug)] = ensure(
            conn, "categories", {"module_key": module_key, "slug": slug}, {"name": name})
    return cats


# Materi bertipe video (contoh): (slug kursus, nomor materi) -> tautan. Ganti dengan video Anda sendiri;
# tautan yang didukung: YouTube, Vimeo, atau berkas langsung .mp4/.webm/.ogg (https).
VIDEO_LESSONS = {
    ("dasar-pemrograman-python", 2): "https://www.youtube.com/watch?v=rfscVS0vtbw",
}


def seed_courses(conn, cats):
    """Kursus, pelajaran, kuis, dan soal. Mengembalikan peta slug -> info untuk tahap berikutnya."""
    info = {}
    for c in COURSES:
        course_id = ensure(conn, "courses", {"slug": c["slug"]}, {
            "category_id": cats[("elearning", c["category"])],
            "title": c["title"], "description": c["description"], "level": c["level"],
            "instructor_name": c["instructor"], "est_hours": c["hours"], "is_published": 1,
        }, fixed={"created_at": ts(c["days_ago"])})

        lesson_ids = []
        for order_no, (title, minutes, body) in enumerate(c["lessons"], start=1):
            video_url = VIDEO_LESSONS.get((c["slug"], order_no))
            lesson_ids.append(ensure(conn, "lessons", {"course_id": course_id, "order_no": order_no}, {
                "title": title, "content_type": "video" if video_url else "text",
                "content_body": body.strip(), "video_url": video_url, "duration_min": minutes}))

        quiz_id = ensure(conn, "quizzes", {"course_id": course_id, "title": c["quiz_title"]},
                         {"pass_score": c["pass_score"]})
        questions = []
        for q, a, b, opt_c, d, correct, expl in c["questions"]:
            qid = ensure(conn, "quiz_questions", {"quiz_id": quiz_id, "question": q}, {
                "option_a": a, "option_b": b, "option_c": opt_c, "option_d": d,
                "correct_option": correct, "explanation": expl})
            questions.append((qid, correct))
        info[c["slug"]] = {"id": course_id, "lessons": lesson_ids, "quiz_id": quiz_id,
                           "questions": questions, "pass_score": c["pass_score"], "title": c["title"]}
    return info


def seed_products(conn, cats, courses):
    ids = {}
    for slug, name, cat, ptype, price, course_slug, days_ago, desc in PRODUCTS:
        course_id = courses[course_slug]["id"] if course_slug else None
        if ptype == "course" and course_id is None:
            raise ValueError(f"Produk kursus '{slug}' harus punya course_slug")
        ids[slug] = ensure(conn, "products", {"slug": slug}, {
            "category_id": cats[("ecommerce", cat)], "course_id": course_id, "name": name,
            "description": desc, "price": price, "product_type": ptype, "is_active": 1,
        }, fixed={"created_at": ts(days_ago)})
    return ids


def seed_tutorials(conn, cats):
    ids = {}
    for t in TUTORIALS:
        tid = ensure(conn, "tutorials", {"slug": t["slug"]}, {
            "category_id": cats[("etutorial", t["category"])], "title": t["title"],
            "summary": t["summary"], "difficulty": t["difficulty"], "est_minutes": t["minutes"],
        }, fixed={"created_at": ts(t["days_ago"])})
        for step_no, (title, body, lang, code) in enumerate(t["steps"], start=1):
            ensure(conn, "tutorial_steps", {"tutorial_id": tid, "step_no": step_no}, {
                "title": title, "body": body, "code_snippet": code, "code_language": lang})
        ids[t["slug"]] = tid
    return ids


def seed_articles(conn, cats, admin_id):
    for slug, title, cat, featured, minutes, views, days_ago, excerpt, body in ARTICLES:
        ensure(conn, "articles", {"slug": slug}, {
            "category_id": cats[("portal", cat)], "author_id": admin_id, "title": title,
            "excerpt": excerpt, "body": body.strip(), "is_featured": featured, "read_minutes": minutes,
        }, fixed={"views": views, "published_at": ts(days_ago, hours=1)})


def seed_forum(conn, cats, users):
    """Thread + balasan + notifikasi 'seseorang membalas thread Anda' untuk penulis thread."""
    name_of = {email: name for email, name, *_ in USERS}
    thread_ids = {}
    for t in THREADS:
        author_id = users[t["author"]]
        last_hours = max(p[3] for p in t["posts"])
        thread_id = ensure(conn, "threads", {"user_id": author_id, "title": t["title"]}, {
            "category_id": cats[("forum", t["category"])], "body": t["body"],
            "updated_at": ts(t["days_ago"], hours=last_hours),
        }, fixed={"views": t["views"], "created_at": ts(t["days_ago"])})
        thread_ids[t["title"]] = thread_id

        post_ids = {}
        for label, email, parent, hours, body in t["posts"]:
            when = ts(t["days_ago"], hours=hours)
            post_ids[label] = ensure(conn, "posts", {
                "thread_id": thread_id, "user_id": users[email], "created_at": when,
            }, {"parent_post_id": post_ids[parent] if parent else None, "body": body})

        # Tandai solusi: thread selesai dan accepted_post_id menunjuk ke posts.id
        accepted = post_ids[t["accepted"]] if t["accepted"] else None
        conn.execute("UPDATE threads SET is_solved = ?, accepted_post_id = ? WHERE id = ?",
                     (1 if accepted else 0, accepted, thread_id))

        # Notifikasi balasan untuk penulis thread (balasan dari diri sendiri tidak dihitung)
        others = [p for p in t["posts"] if p[1] != t["author"]]
        for idx, (label, email, _parent, hours, _body) in enumerate(others):
            unread = t["author"] == DEMO_EMAIL and idx >= len(others) - 2  # 2 terakhir milik demo belum dibaca
            ensure(conn, "notifications", {
                "user_id": author_id,
                "message": f"{name_of[email]} membalas thread Anda: {t['title']}",
            }, {"module_key": "forum", "link_url": f"/forum/thread/{thread_id}"},
                fixed={"is_read": 0 if unread else 1, "created_at": ts(t["days_ago"], hours=hours)})
    return thread_ids


def make_answers(questions, n_correct):
    """Buat jawaban kuis: n_correct soal pertama benar, sisanya sengaja salah."""
    answers = {}
    for i, (qid, correct) in enumerate(questions):
        answers[str(qid)] = correct if i < n_correct else ("a" if correct != "a" else "b")
    return answers


def seed_activity(conn, users, courses, products, tutorials):
    """Data turunan pengguna: pengaturan modul, pesanan, pendaftaran kelas, progres, kuis, bookmark, log."""
    demo, budi, citra = users[DEMO_EMAIL], users["budi@dke.test"], users["citra@dke.test"]
    price = {r[0]: r[1] for r in conn.execute("SELECT id, price FROM products")}

    # --- pengaturan per modul (akun demo) ---
    demo_settings = [
        ("ecommerce", "shipping_address", "Jl. Dipatiukur No. 35, Bandung 40132"),
        ("ecommerce", "favorite_payment", "e-wallet"),
        ("elearning", "playback_speed", "1.25"),
        ("elearning", "daily_goal_min", "30"),
        ("etutorial", "font_size", "md"),
        ("portal", "preferred_categories", "teknologi,pendidikan"),
        ("forum", "profile_privacy", "public"),
        ("forum", "notify_reply", "1"),
    ]
    for module_key, key, value in demo_settings:
        ensure(conn, "module_settings",
               {"user_id": demo, "module_key": module_key, "setting_key": key}, {"setting_value": value})

    # --- pesanan (simulasi) + rincian ---
    def make_order(code, user_id, user_name, items, method, days_ago, address):
        total = sum(price[products[slug]] * qty for slug, qty in items)
        order_id = ensure(conn, "orders", {"order_code": code}, {
            "user_id": user_id, "total": total, "status": "paid", "payment_method": method,
            "recipient_name": user_name, "address": address}, fixed={"created_at": ts(days_ago)})
        for slug, qty in items:
            ensure(conn, "order_items", {"order_id": order_id, "product_id": products[slug]},
                   {"unit_price": price[products[slug]], "qty": qty})
        return order_id

    demo_order = make_order("DKE-20261105-0001", demo, "Pengguna Demo",
                            [("ebook-panduan-praktis-flask", 1)], "e-wallet", 8,
                            "Jl. Dipatiukur No. 35, Bandung 40132")
    budi_order = make_order("DKE-20261102-0001", budi, "Budi Santoso",
                            [("kursus-dasar-pemrograman-python", 1)], "transfer", 11,
                            "Jl. Setiabudi No. 12, Bandung 40154")

    py, ui = courses["dasar-pemrograman-python"], courses["prinsip-desain-antarmuka-pemula"]

    def enroll(user_id, course, source, order_id, days_ago, completed_at=None):
        ensure(conn, "enrollments", {"user_id": user_id, "course_id": course["id"]},
               {"source": source, "order_id": order_id},
               fixed={"enrolled_at": ts(days_ago), "completed_at": completed_at})

    def progress(user_id, course, upto, days_ago):
        for n, lesson_id in enumerate(course["lessons"][:upto]):
            ensure(conn, "lesson_progress", {"user_id": user_id, "lesson_id": lesson_id},
                   fixed={"completed_at": ts(days_ago - n * 0.5 if days_ago - n * 0.5 > 0 else 0)})

    # Demo: kursus gratis, baru 2 dari 5 pelajaran (kursus berbayar sengaja belum dibeli untuk demo checkout)
    enroll(demo, ui, "free", None, 9)
    progress(demo, ui, 2, 9)
    # Budi: kursus Python hasil pembelian -> pendaftaran source='order'
    enroll(budi, py, "order", budi_order, 11)
    progress(budi, py, 3, 10)
    # Citra: menyelesaikan kursus gratis; percobaan kuis pertama gagal, kedua lulus
    q = ui["questions"]
    passed_at = ts(15, hours=6)
    enroll(citra, ui, "free", None, 22, completed_at=passed_at)
    progress(citra, ui, 5, 21)
    for attempt_at, n_correct in ((ts(15), 3), (passed_at, 4)):
        score = round(100 * n_correct / len(q))
        ensure(conn, "quiz_attempts", {"user_id": citra, "quiz_id": ui["quiz_id"], "taken_at": attempt_at}, {
            "score": score, "passed": 1 if score >= ui["pass_score"] else 0,
            "answers_json": json.dumps(make_answers(q, n_correct))})

    # --- bookmark tutorial (akun demo) ---
    for slug, days_ago in (("membuat-aplikasi-flask-pertama", 7), ("tata-letak-responsif-tailwind", 5)):
        insert_ignore(conn, "tutorial_bookmarks",
                      {"user_id": demo, "tutorial_id": tutorials[slug], "created_at": ts(days_ago)})

    # --- notifikasi non-forum (akun demo) ---
    for module_key, msg, link, read, days_ago in (
        ("infosys", "Selamat datang di Digital Knowledge Ecosystem! Jelajahi enam modul dari Beranda.", "/", 1, 14),
        ("elearning", "Anda terdaftar di kursus Prinsip Desain Antarmuka untuk Pemula. Selamat belajar!", "/elearning/", 1, 9),
        ("ecommerce", "Pesanan DKE-20261105-0001 berhasil dibuat.", "/ecommerce/", 1, 8),
    ):
        ensure(conn, "notifications", {"user_id": demo, "message": msg},
               {"module_key": module_key, "link_url": link},
               fixed={"is_read": read, "created_at": ts(days_ago)})

    # --- log aktivitas lintas modul ---
    for user_id, module_key, action, detail, days_ago in (
        (demo, "infosys", "login", "Login berhasil", 14),
        (demo, "elearning", "enroll", "Mendaftar kursus gratis: prinsip-desain-antarmuka-pemula", 9),
        (demo, "ecommerce", "checkout", "Pesanan DKE-20261105-0001", 8),
        (demo, "forum", "create_thread", "Urutan belajar yang disarankan untuk menjadi web developer?", 6),
        (budi, "ecommerce", "checkout", "Pesanan DKE-20261102-0001", 11),
        (budi, "elearning", "enroll", "Kursus dari pesanan DKE-20261102-0001: dasar-pemrograman-python", 11),
        (citra, "elearning", "quiz_passed", "Kuis Prinsip Desain Antarmuka: skor 80", 15),
        (users[ADMIN_EMAIL], "infosys", "login", "Login admin", 1),
    ):
        ensure(conn, "activity_logs",
               {"user_id": user_id, "action": action, "detail": detail, "created_at": ts(days_ago)},
               {"module_key": module_key, "ip_address": "127.0.0.1"})


# ---------------------------------------------------------------------------
# VERIFIKASI
# ---------------------------------------------------------------------------
def scalar(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()[0]


def run_checks(conn):
    """Pemeriksaan kewajaran data. Mengembalikan jumlah pemeriksaan yang gagal."""
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
    checks = [
        ("23 tabel sesuai Blueprint 3.2", tables == set(EXPECTED_TABLES)),
        ("kategori ada untuk 5 modul berkonten",
         scalar(conn, "SELECT COUNT(DISTINCT module_key) FROM categories") == 5),
        ("6 produk, minimal 1 bertipe kursus dengan course_id valid",
         scalar(conn, "SELECT COUNT(*) FROM products") >= 6 and scalar(
             conn, "SELECT COUNT(*) FROM products p JOIN courses c ON c.id = p.course_id "
                   "WHERE p.product_type = 'course'") >= 1),
        ("produk non-kursus tidak punya course_id",
         scalar(conn, "SELECT COUNT(*) FROM products WHERE product_type <> 'course' AND course_id IS NOT NULL") == 0),
        ("3 kursus, masing-masing punya pelajaran, kuis, dan soal",
         scalar(conn, "SELECT COUNT(*) FROM courses") == 3 and scalar(
             conn, "SELECT COUNT(*) FROM courses c WHERE "
                   "NOT EXISTS (SELECT 1 FROM lessons l WHERE l.course_id = c.id) OR "
                   "NOT EXISTS (SELECT 1 FROM quizzes z JOIN quiz_questions q ON q.quiz_id = z.id "
                   "WHERE z.course_id = c.id)") == 0),
        ("5 tutorial, masing-masing punya langkah dan snippet kode",
         scalar(conn, "SELECT COUNT(*) FROM tutorials") == 5 and scalar(
             conn, "SELECT COUNT(*) FROM tutorials t WHERE NOT EXISTS (SELECT 1 FROM tutorial_steps s "
                   "WHERE s.tutorial_id = t.id AND s.code_snippet IS NOT NULL)") == 0),
        ("10 artikel, tepat 2 featured",
         scalar(conn, "SELECT COUNT(*) FROM articles") == 10
         and scalar(conn, "SELECT COUNT(*) FROM articles WHERE is_featured = 1") == 2),
        ("5 thread, masing-masing punya balasan",
         scalar(conn, "SELECT COUNT(*) FROM threads") == 5 and scalar(
             conn, "SELECT COUNT(*) FROM threads t WHERE NOT EXISTS "
                   "(SELECT 1 FROM posts p WHERE p.thread_id = t.id)") == 0),
        ("accepted_post_id menunjuk balasan di thread yang sama",
         scalar(conn, "SELECT COUNT(*) FROM threads t WHERE t.is_solved = 1 AND NOT EXISTS "
                      "(SELECT 1 FROM posts p WHERE p.id = t.accepted_post_id AND p.thread_id = t.id)") == 0),
        ("akun demo (member) dan admin ada, kata sandi ter-hash",
         scalar(conn, "SELECT COUNT(*) FROM users WHERE (email = ? AND role = 'member') OR (email = ? AND role = 'admin')",
                (DEMO_EMAIL, ADMIN_EMAIL)) == 2
         and scalar(conn, "SELECT COUNT(*) FROM users WHERE password_hash NOT LIKE 'scrypt:%' "
                          "AND password_hash NOT LIKE 'pbkdf2:%'") == 0),
        ("pendaftaran dari pesanan merujuk order yang valid",
         scalar(conn, "SELECT COUNT(*) FROM enrollments e WHERE e.source = 'order' AND "
                      "NOT EXISTS (SELECT 1 FROM orders o WHERE o.id = e.order_id)") == 0),
        ("PRAGMA foreign_key_check bersih", len(conn.execute("PRAGMA foreign_key_check").fetchall()) == 0),
        ("PRAGMA integrity_check = ok", scalar(conn, "PRAGMA integrity_check") == "ok"),
    ]
    failed = 0
    print("Pemeriksaan kewajaran data:")
    for label, ok in checks:
        print(f"  [{'OK' if ok else 'GAGAL'}] {label}")
        failed += 0 if ok else 1
    return failed


def print_row_counts(conn):
    """Kueri verifikasi akhir: jumlah baris tiap tabel (23 tabel)."""
    sql = " UNION ALL ".join(f"SELECT '{t}' AS tabel, COUNT(*) AS baris FROM {t}" for t in EXPECTED_TABLES)
    rows = conn.execute(sql).fetchall()
    width = max(len(r[0]) for r in rows)
    print("\nJumlah baris per tabel:")
    print(f"  {'tabel'.ljust(width)}  baris")
    print(f"  {'-' * width}  -----")
    for tabel, baris in rows:
        print(f"  {tabel.ljust(width)}  {baris:>5}")
    print(f"  {'-' * width}  -----")
    print(f"  {'TOTAL'.ljust(width)}  {sum(r[1] for r in rows):>5}   ({len(rows)} tabel)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(description="Buat dan isi database DKE (aman dijalankan ulang).")
    parser.add_argument("--db", default=DEFAULT_DB, help="jalur berkas SQLite (bawaan: instance/dke.db)")
    parser.add_argument("--reset", action="store_true",
                        help="hapus semua tabel lalu bangun ulang dari nol (SEMUA DATA LAMA HILANG)")
    args = parser.parse_args(argv)

    os.makedirs(os.path.dirname(os.path.abspath(args.db)), exist_ok=True)
    existed = os.path.exists(args.db)
    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if args.reset:
            print("Mode --reset: menghapus semua tabel lama ...")
            drop_all_tables(conn)
        apply_schema(conn)
        print(f"{'Memperbarui' if existed and not args.reset else 'Membuat'} database: {args.db}")

        users, created = seed_users(conn)
        cats = seed_categories(conn)
        courses = seed_courses(conn, cats)
        products = seed_products(conn, cats, courses)
        tutorials = seed_tutorials(conn, cats)
        seed_articles(conn, cats, users[ADMIN_EMAIL])
        seed_forum(conn, cats, users)
        seed_activity(conn, users, courses, products, tutorials)
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        print("Seed GAGAL; seluruh perubahan dibatalkan (ROLLBACK).", file=sys.stderr)
        raise

    print("\nAkun contoh:")
    for email, pw in ((DEMO_EMAIL, DEMO_PASSWORD), (ADMIN_EMAIL, ADMIN_PASSWORD)):
        if email in created:
            print(f"  {email:<16} kata sandi: {pw}   (akun baru dibuat)")
        else:
            print(f"  {email:<16} sudah ada; kata sandi tidak diubah")
    print("  Akun komunitas (budi/citra/dewi/eko@dke.test) hanya untuk konten forum dan tidak dapat dipakai login.")
    print()

    failed = run_checks(conn)
    print_row_counts(conn)
    conn.close()
    if failed:
        print(f"\n{failed} pemeriksaan GAGAL.", file=sys.stderr)
        return 1
    print("\nSeed selesai. Jalankan aplikasi dengan: python run.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
