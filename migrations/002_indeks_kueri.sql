-- Versi 2: indeks untuk kueri yang sebelumnya SCAN tabel penuh (diukur dengan EXPLAIN QUERY PLAN).
-- IF NOT EXISTS: aman dijalankan pada database yang indeksnya sudah ada.
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz     ON quiz_questions(quiz_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_course          ON quizzes(course_id);
CREATE INDEX IF NOT EXISTS idx_posts_user              ON posts(user_id);
CREATE INDEX IF NOT EXISTS idx_posts_parent            ON posts(parent_post_id);
CREATE INDEX IF NOT EXISTS idx_threads_user            ON threads(user_id, created_at);
