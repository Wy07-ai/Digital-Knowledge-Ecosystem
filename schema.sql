-- =====================================================================
-- Digital Knowledge Ecosystem (DKE) - schema.sql
-- Sumber: Project Blueprint, bagian 3.3 (Skema SQL / dasar Kamus Data)
-- Total: 23 tabel dalam satu berkas SQLite (instance/dke.db)
--
-- Catatan:
--  * Seluruh CREATE memakai IF NOT EXISTS agar aman dijalankan ulang.
--  * courses dibuat SEBELUM products karena products.course_id merujuk
--    ke courses (lihat catatan "Urutan pembuatan tabel" di Blueprint).
--  * Harga = integer Rupiah; waktu = teks ISO-8601.
--  * threads.accepted_post_id sengaja tanpa FOREIGN KEY agar tidak
--    sirkular dengan posts.thread_id (sesuai Blueprint).
--  * Bagian INDEX di akhir berkas adalah tambahan (bukan tabel) untuk
--    mempercepat kueri yang paling sering dipakai.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ===== INTI / INFORMATION SYSTEM (6 tabel) =====
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  full_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'member',        -- member | admin
  avatar_url TEXT, bio TEXT,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS user_settings (      -- pengaturan GLOBAL (1 baris per user)
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  theme TEXT NOT NULL DEFAULT 'light',          -- light | dark | system
  view_mode TEXT NOT NULL DEFAULT 'desktop',    -- desktop | mobile
  landing_mode TEXT NOT NULL DEFAULT 'launcher',-- launcher | last_module
  last_module TEXT, last_path TEXT,             -- Smart Landing / Session Persistence
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS module_settings (    -- pengaturan per MODUL (key-value)
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module_key TEXT NOT NULL,                     -- infosys|ecommerce|elearning|etutorial|portal|forum
  setting_key TEXT NOT NULL,
  setting_value TEXT,
  UNIQUE (user_id, module_key, setting_key)
);

CREATE TABLE IF NOT EXISTS activity_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  module_key TEXT, action TEXT NOT NULL, detail TEXT, ip_address TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  module_key TEXT, message TEXT NOT NULL, link_url TEXT,
  is_read INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  module_key TEXT NOT NULL, name TEXT NOT NULL, slug TEXT NOT NULL,
  UNIQUE (module_key, slug)
);

-- ===== E-LEARNING (7 tabel) =====
-- (dibuat lebih dulu daripada E-Commerce karena products.course_id -> courses)
CREATE TABLE IF NOT EXISTS courses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER REFERENCES categories(id),
  title TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, description TEXT,
  level TEXT NOT NULL DEFAULT 'pemula',         -- pemula | menengah | lanjut
  thumbnail_url TEXT, instructor_name TEXT, est_hours REAL,
  is_published INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lessons (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  order_no INTEGER NOT NULL, title TEXT NOT NULL,
  content_type TEXT NOT NULL DEFAULT 'text',    -- text | video
  content_body TEXT, video_url TEXT, duration_min INTEGER,
  UNIQUE (course_id, order_no)
);

-- ===== E-COMMERCE (4 tabel) =====
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER REFERENCES categories(id),
  course_id INTEGER REFERENCES courses(id),     -- NULL jika bukan kursus
  name TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, description TEXT,
  price INTEGER NOT NULL DEFAULT 0,
  image_url TEXT,
  product_type TEXT NOT NULL DEFAULT 'course',  -- course | ebook | template
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cart_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  qty INTEGER NOT NULL DEFAULT 1,
  added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_code TEXT NOT NULL UNIQUE,              -- mis. DKE-20261112-0001
  user_id INTEGER NOT NULL REFERENCES users(id),
  total INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'paid',          -- pending | paid | cancelled (simulasi)
  payment_method TEXT,                          -- simulasi: transfer | e-wallet | kartu
  recipient_name TEXT, address TEXT,            -- salinan alamat saat checkout
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id),
  unit_price INTEGER NOT NULL, qty INTEGER NOT NULL DEFAULT 1
);

-- ===== E-LEARNING (lanjutan) =====
CREATE TABLE IF NOT EXISTS enrollments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  course_id INTEGER NOT NULL REFERENCES courses(id),
  source TEXT NOT NULL DEFAULT 'free',          -- free | order
  order_id INTEGER REFERENCES orders(id),
  enrolled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT,
  UNIQUE (user_id, course_id)
);

CREATE TABLE IF NOT EXISTS lesson_progress (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
  completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (user_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS quizzes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  title TEXT NOT NULL, pass_score INTEGER NOT NULL DEFAULT 70
);

CREATE TABLE IF NOT EXISTS quiz_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
  question TEXT NOT NULL,
  option_a TEXT NOT NULL, option_b TEXT NOT NULL, option_c TEXT, option_d TEXT,
  correct_option TEXT NOT NULL,                 -- 'a' | 'b' | 'c' | 'd'
  explanation TEXT
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  quiz_id INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
  score INTEGER NOT NULL, passed INTEGER NOT NULL,
  answers_json TEXT,
  taken_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== E-TUTORIAL (3 tabel) =====
CREATE TABLE IF NOT EXISTS tutorials (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER REFERENCES categories(id),
  title TEXT NOT NULL, slug TEXT NOT NULL UNIQUE, summary TEXT,
  difficulty TEXT NOT NULL DEFAULT 'mudah', est_minutes INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tutorial_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tutorial_id INTEGER NOT NULL REFERENCES tutorials(id) ON DELETE CASCADE,
  step_no INTEGER NOT NULL, title TEXT NOT NULL, body TEXT,
  code_snippet TEXT, code_language TEXT,
  UNIQUE (tutorial_id, step_no)
);

CREATE TABLE IF NOT EXISTS tutorial_bookmarks (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tutorial_id INTEGER NOT NULL REFERENCES tutorials(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id, tutorial_id)
);

-- ===== PORTAL (1 tabel) =====
CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER REFERENCES categories(id),
  author_id INTEGER REFERENCES users(id),
  title TEXT NOT NULL, slug TEXT NOT NULL UNIQUE,
  excerpt TEXT, body TEXT NOT NULL, cover_url TEXT,
  is_featured INTEGER NOT NULL DEFAULT 0,
  read_minutes INTEGER, views INTEGER NOT NULL DEFAULT 0,
  published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== FORUM (2 tabel) =====
CREATE TABLE IF NOT EXISTS threads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER REFERENCES categories(id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  title TEXT NOT NULL, body TEXT NOT NULL,
  is_solved INTEGER NOT NULL DEFAULT 0,
  accepted_post_id INTEGER,                     -- rujukan ke posts.id (tanpa FK agar tidak sirkular)
  views INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id),
  parent_post_id INTEGER REFERENCES posts(id),  -- balasan bersarang (1 level cukup)
  body TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ===== INDEKS TAMBAHAN (bukan tabel) =====
CREATE INDEX IF NOT EXISTS idx_activity_logs_user      ON activity_logs(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_user      ON notifications(user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_products_category       ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_course         ON products(course_id);
CREATE INDEX IF NOT EXISTS idx_orders_user             ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order       ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_courses_category        ON courses(category_id);
CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_quiz ON quiz_attempts(user_id, quiz_id);
CREATE INDEX IF NOT EXISTS idx_tutorials_category      ON tutorials(category_id);
CREATE INDEX IF NOT EXISTS idx_articles_category       ON articles(category_id, published_at);
CREATE INDEX IF NOT EXISTS idx_threads_category        ON threads(category_id, created_at);
CREATE INDEX IF NOT EXISTS idx_posts_thread            ON posts(thread_id, created_at);
