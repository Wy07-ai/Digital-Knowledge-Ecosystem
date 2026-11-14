"""Tes kuis E-Learning (UC-EL-05/06): fungsi grade() dan alur kuis end-to-end."""
import json
import os
import re
import shutil
import sqlite3
import tempfile
import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from app.elearning.quiz import answers_from_json, answers_to_json, grade, question_options

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_questions(n=5, correct="b"):
    return [{"id": i, "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "D",
             "correct_option": correct} for i in range(1, n + 1)]


class GradeTests(unittest.TestCase):
    """grade() adalah fungsi murni: tanpa database dan tanpa Flask."""

    def test_all_correct_passes_with_score_100(self):
        qs = make_questions(5)
        r = grade(qs, {i: "b" for i in range(1, 6)}, 70)
        self.assertEqual((r["correct"], r["total"], r["score"], r["passed"]), (5, 5, 100, True))

    def test_all_wrong_fails_with_score_0(self):
        r = grade(make_questions(5), {i: "a" for i in range(1, 6)}, 70)
        self.assertEqual((r["correct"], r["score"], r["passed"]), (0, 0, False))

    def test_pass_boundary_is_inclusive(self):
        qs = make_questions(10)
        seven = {i: ("b" if i <= 7 else "a") for i in range(1, 11)}
        six = {i: ("b" if i <= 6 else "a") for i in range(1, 11)}
        self.assertTrue(grade(qs, seven, 70)["passed"])      # 70 >= 70
        self.assertFalse(grade(qs, six, 70)["passed"])       # 60 < 70

    def test_score_rounds_down_so_it_matches_pass_decision(self):
        # 139/200 = 69,5%: pembulatan biasa menghasilkan 70 (lulus) padahal belum mencapai 70%.
        qs = make_questions(200)
        answers = {i: ("b" if i <= 139 else "a") for i in range(1, 201)}
        r = grade(qs, answers, 70)
        self.assertEqual(r["score"], 69)
        self.assertFalse(r["passed"])
        # 2 dari 3 = 66,67% -> 66, dan tidak lulus pada batas 67 yang tak tercapai persis.
        r = grade(make_questions(3), {1: "b", 2: "b", 3: "a"}, 67)
        self.assertEqual(r["score"], 66)
        self.assertFalse(r["passed"])

    def test_unanswered_missing_and_invalid_answers_count_wrong(self):
        qs = make_questions(4)
        r = grade(qs, {1: "b", 2: "", 3: "z", 4: None}, 50)   # soal 4 tidak dikirim juga ok
        self.assertEqual(r["correct"], 1)
        self.assertEqual([x["answered"] for x in r["results"]], [True, False, False, False])
        self.assertIsNone(r["results"][2]["chosen"])
        r = grade(qs, {1: ["b"], 2: 5, 3: {"x": 1}}, 50)       # tipe aneh tidak membuat error
        self.assertEqual(r["correct"], 0)

    def test_answer_normalization_and_string_keys(self):
        r = grade(make_questions(2), {"1": " B ", "2": "b"}, 100)   # kunci str, huruf besar, spasi
        self.assertEqual(r["correct"], 2)
        self.assertTrue(r["passed"])

    def test_option_that_does_not_exist_is_invalid_even_if_it_is_the_key(self):
        qs = [{"id": 1, "option_a": "A", "option_b": "B", "option_c": None, "option_d": "",
               "correct_option": "c"}]   # data rusak: kunci menunjuk opsi kosong
        self.assertEqual(question_options(qs[0]), [("a", "A"), ("b", "B")])
        r = grade(qs, {1: "c"}, 70)
        self.assertEqual((r["correct"], r["results"][0]["chosen"]), (0, None))

    def test_empty_quiz_never_passes_even_with_zero_pass_score(self):
        r = grade([], {}, 0)
        self.assertEqual((r["total"], r["score"], r["passed"]), (0, 0, False))

    def test_pass_score_is_clamped_and_garbage_falls_back_to_default(self):
        qs = make_questions(2)
        both = {1: "b", 2: "b"}
        self.assertEqual(grade(qs, both, 150)["pass_score"], 100)
        self.assertTrue(grade(qs, both, 150)["passed"])         # 100% memenuhi batas yang dipotong ke 100
        self.assertFalse(grade(qs, {1: "b", 2: "a"}, 150)["passed"])
        self.assertEqual(grade(qs, both, -5)["pass_score"], 0)
        self.assertEqual(grade(qs, both, "abc")["pass_score"], 70)
        self.assertEqual(grade(qs, both, None)["pass_score"], 70)

    def test_non_dict_answers_are_treated_as_empty(self):
        for bad in (None, [], "b", 7):
            self.assertEqual(grade(make_questions(2), bad, 70)["correct"], 0)

    def test_accepts_sqlite_rows_and_does_not_mutate_input(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT 1 AS id, 'x' AS option_a, 'y' AS option_b, NULL AS option_c, "
                           "NULL AS option_d, 'a' AS correct_option").fetchone()
        answers = {1: "a"}
        r = grade([row], answers, 100)
        self.assertTrue(r["passed"])
        self.assertEqual(answers, {1: "a"})

    def test_answers_json_roundtrip_and_tolerance(self):
        r = grade(make_questions(3), {1: "b", 2: "a"}, 70)
        stored = answers_to_json(r["results"])
        self.assertEqual(json.loads(stored), {"1": "b", "2": "a"})   # soal 3 kosong tidak disimpan
        self.assertEqual(answers_from_json(stored), {"1": "b", "2": "a"})
        for bad in (None, "", "{rusak", "[1, 2]", "42"):
            self.assertEqual(answers_from_json(bad), {})


class QuizFlowTests(unittest.TestCase):
    EXPLAIN = "PEMBAHASAN-RAHASIA-{n}"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        conn = sqlite3.connect(self.db_path)
        with open(os.path.join(ROOT, "schema.sql"), encoding="utf-8") as schema:
            conn.executescript(schema.read())
        conn.executemany(
            "INSERT INTO users (id, full_name, email, password_hash) VALUES (?, ?, ?, ?)",
            ((1, "Demo Pengguna", "demo@dke.test", generate_password_hash("Demo12345")),
             (2, "Orang Lain", "lain@dke.test", generate_password_hash("Lain12345"))))
        conn.execute("INSERT INTO categories (id, module_key, name, slug) VALUES (1, 'elearning', 'Pemrograman', 'pemrograman')")
        conn.executemany(
            "INSERT INTO courses (id, category_id, title, slug, level, instructor_name) VALUES (?, 1, ?, ?, 'pemula', 'Pengajar')",
            ((1, "Desain Dasar", "desain-dasar"), (2, "Tanpa Kuis", "tanpa-kuis"), (3, "Kuis Kosong", "kuis-kosong")))
        conn.executemany(
            "INSERT INTO lessons (id, course_id, order_no, title, content_type, content_body, duration_min) "
            "VALUES (?, ?, ?, ?, 'text', 'Isi.', 10)",
            ((1, 1, 1, "Materi satu"), (2, 1, 2, "Materi dua"), (3, 1, 3, "Materi tiga"),
             (4, 2, 1, "Materi lain"), (5, 3, 1, "Materi kosong")))
        conn.execute("INSERT INTO quizzes (id, course_id, title, pass_score) VALUES (1, 1, 'Kuis Desain', 70)")
        conn.execute("INSERT INTO quizzes (id, course_id, title, pass_score) VALUES (2, 3, 'Kuis Tanpa Soal', 70)")
        # 4 soal: kunci b, a, c, d. Soal 2 hanya punya opsi a dan b.
        conn.executemany(
            "INSERT INTO quiz_questions (id, quiz_id, question, option_a, option_b, option_c, option_d, correct_option, explanation) "
            "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)",
            ((1, "Soal pertama?", "p1a", "p1b", "p1c", "p1d", "b", self.EXPLAIN.format(n=1)),
             (2, "Soal kedua?", "p2a", "p2b", None, None, "a", self.EXPLAIN.format(n=2)),
             (3, "Soal ketiga?", "p3a", "p3b", "p3c", "p3d", "c", self.EXPLAIN.format(n=3)),
             (4, "Soal keempat?", "p4a", "p4b", "p4c", "p4d", "d", self.EXPLAIN.format(n=4))))
        conn.commit()
        conn.close()
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path, "SECRET_KEY": "test"})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- pembantu ----
    def sql(self, statement, params=()):
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(statement, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def login(self, user_id=1, client=None):
        with (client or self.client).session_transaction() as session:
            session["user_id"] = user_id

    def enroll(self, course_id=1, user_id=1):
        self.sql("INSERT INTO enrollments (user_id, course_id, source) VALUES (?, ?, 'free')", (user_id, course_id))

    def token(self, client=None):
        html = (client or self.client).get("/elearning/pengaturan").get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)

    def submit(self, answers, course_id=1, client=None, token=None, extra=None):
        client = client or self.client
        data = {"csrf_token": token if token is not None else self.token(client)}
        data.update({f"q_{qid}": v for qid, v in answers.items()})
        data.update(extra or {})
        return client.post(f"/elearning/kelas/{course_id}/kuis/kumpul", data=data)

    PERFECT = {1: "b", 2: "a", 3: "c", 4: "d"}
    ONE_RIGHT = {1: "b", 2: "b", 3: "a", 4: "a"}          # 1 dari 4 = 25%

    # ---- akses ----
    def test_guest_is_redirected_to_login(self):
        for method, url in (("get", "/elearning/kelas/1/kuis"), ("post", "/elearning/kelas/1/kuis/kumpul"),
                            ("get", "/elearning/kelas/1/kuis/hasil/1")):
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/infosys/login", response.headers["Location"])

    def test_not_enrolled_is_sent_back_to_course_detail(self):
        self.login()
        response = self.client.get("/elearning/kelas/1/kuis")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/elearning/kelas/1"))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM quiz_attempts")[0][0], 0)
        # POST langsung (tanpa enroll) juga tidak menyimpan apa pun.
        response = self.submit(self.PERFECT)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM quiz_attempts")[0][0], 0)

    def test_unknown_course_is_404_and_course_without_quiz_redirects(self):
        self.login()
        self.enroll(2)
        self.enroll(3)
        self.assertEqual(self.client.get("/elearning/kelas/999/kuis").status_code, 404)
        for course_id in (2, 3):   # tanpa kuis / kuis tanpa soal
            response = self.client.get(f"/elearning/kelas/{course_id}/kuis")
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith(f"/elearning/kelas/{course_id}"))

    # ---- UC-EL-05: halaman pengerjaan ----
    def test_quiz_page_shows_questions_and_options_one_form(self):
        self.login()
        self.enroll()
        response = self.client.get("/elearning/kelas/1/kuis")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Kuis Desain", html)
        for qid in (1, 2, 3, 4):
            self.assertIn(f'name="q_{qid}"', html)
        self.assertIn("Soal pertama?", html)
        self.assertIn("Soal 4 dari 4", html)
        self.assertEqual(html.count('name="q_2"'), 2)          # soal 2 hanya punya opsi a dan b
        self.assertEqual(html.count('data-goto='), 4)          # indikator nomor
        self.assertIn("quiz.js", html)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_quiz_page_never_leaks_answer_key_or_explanations(self):
        self.login()
        self.enroll()
        html = self.client.get("/elearning/kelas/1/kuis").get_data(as_text=True)
        self.assertNotIn("PEMBAHASAN-RAHASIA", html)
        self.assertNotIn("correct_option", html)
        radios = re.findall(r"<input[^>]*type=\"radio\"[^>]*>", html)
        self.assertEqual(len(radios), 14)                                  # 4 + 2 + 4 + 4 opsi
        self.assertFalse([r for r in radios if "checked" in r])            # tidak ada opsi yang sudah dicentang
        # Semua opsi berbentuk sama: hanya name/value yang berbeda, jadi tidak ada penanda kunci jawaban.
        shapes = {re.sub(r'name="q_\d+"|value="[a-d]"', "", r) for r in radios}
        self.assertEqual(len(shapes), 1)
        labels = re.findall(r'<label class="el-opt">', html)
        self.assertEqual(len(labels), 14)
        self.assertNotIn("data-correct", html)

    # ---- UC-EL-05/06: penilaian server ----
    def test_perfect_submission_passes_and_redirects_to_result(self):
        self.login()
        self.enroll()
        response = self.submit(self.PERFECT)
        self.assertEqual(response.status_code, 302)
        match = re.search(r"/elearning/kelas/1/kuis/hasil/(\d+)$", response.headers["Location"])
        self.assertIsNotNone(match)
        row = self.sql("SELECT user_id, quiz_id, score, passed, answers_json FROM quiz_attempts")[0]
        self.assertEqual(row[:4], (1, 1, 100, 1))
        self.assertEqual(json.loads(row[4]), {"1": "b", "2": "a", "3": "c", "4": "d"})

    def test_client_cannot_inject_score_or_pass(self):
        self.login()
        self.enroll()
        self.submit(self.ONE_RIGHT, extra={"score": "100", "passed": "1", "correct": "4", "pass_score": "0"})
        row = self.sql("SELECT score, passed FROM quiz_attempts")[0]
        self.assertEqual(row, (25, 0))
        self.assertIsNone(self.sql("SELECT completed_at FROM enrollments")[0][0])

    def test_unanswered_questions_are_graded_wrong_but_submission_is_accepted(self):
        self.login()
        self.enroll()
        self.submit({1: "b", 2: "a"})                        # soal 3 dan 4 kosong
        row = self.sql("SELECT score, passed, answers_json FROM quiz_attempts")[0]
        self.assertEqual((row[0], row[1]), (50, 0))
        self.assertEqual(json.loads(row[2]), {"1": "b", "2": "a"})

    def test_invalid_option_values_are_ignored(self):
        self.login()
        self.enroll()
        self.submit({1: "z", 2: "c", 3: "<script>", 4: "d"})   # soal 2 tidak punya opsi c
        row = self.sql("SELECT score, answers_json FROM quiz_attempts")[0]
        self.assertEqual(row[0], 25)
        self.assertEqual(json.loads(row[1]), {"4": "d"})

    def test_csrf_is_required(self):
        self.login()
        self.enroll()
        for bad in ("", "salah"):
            response = self.submit(self.PERFECT, token=bad)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.headers["Location"].endswith("/elearning/kelas/1/kuis"))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM quiz_attempts")[0][0], 0)

    # ---- kelulusan: completed_at dan progres 100% ----
    def test_pass_sets_completed_at_and_full_progress(self):
        self.login()
        self.enroll()
        self.sql("INSERT INTO lesson_progress (user_id, lesson_id, completed_at) VALUES (1, 1, '2026-01-01T00:00:00+00:00')")
        self.submit(self.PERFECT)
        completed = self.sql("SELECT completed_at FROM enrollments WHERE user_id = 1 AND course_id = 1")[0][0]
        self.assertIsNotNone(completed)
        done = self.sql("SELECT lesson_id FROM lesson_progress WHERE user_id = 1 ORDER BY lesson_id")
        self.assertEqual([r[0] for r in done], [1, 2, 3])
        # tanggal selesai materi yang sudah ada tidak ditimpa
        self.assertEqual(self.sql("SELECT completed_at FROM lesson_progress WHERE lesson_id = 1")[0][0],
                         "2026-01-01T00:00:00+00:00")
        page = self.client.get("/elearning/kelas/1").get_data(as_text=True)
        self.assertIn("3 dari 3 materi", page)
        self.assertIn("100%", page)

    def test_fail_keeps_course_incomplete_and_progress_untouched(self):
        self.login()
        self.enroll()
        self.submit(self.ONE_RIGHT)
        self.assertIsNone(self.sql("SELECT completed_at FROM enrollments")[0][0])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM lesson_progress")[0][0], 0)

    def test_second_pass_does_not_overwrite_first_completion_date(self):
        self.login()
        self.enroll()
        self.submit(self.PERFECT)
        self.sql("UPDATE enrollments SET completed_at = '2026-02-02T00:00:00+00:00'")
        self.submit(self.PERFECT)
        self.assertEqual(self.sql("SELECT completed_at FROM enrollments")[0][0], "2026-02-02T00:00:00+00:00")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM quiz_attempts")[0][0], 2)

    def test_fail_after_pass_does_not_undo_completion(self):
        self.login()
        self.enroll()
        self.submit(self.PERFECT)
        self.submit(self.ONE_RIGHT)
        self.assertIsNotNone(self.sql("SELECT completed_at FROM enrollments")[0][0])
        self.assertEqual(self.sql("SELECT passed FROM quiz_attempts ORDER BY id")[1][0], 0)

    def test_pass_notification_only_on_first_completion_and_activity_logged(self):
        self.login()
        self.enroll()
        self.submit(self.ONE_RIGHT)
        self.submit(self.PERFECT)
        self.submit(self.PERFECT)
        notes = self.sql("SELECT message FROM notifications WHERE user_id = 1")
        self.assertEqual(len(notes), 1)
        self.assertIn("Desain Dasar", notes[0][0])
        actions = [r[0] for r in self.sql("SELECT action FROM activity_logs WHERE user_id = 1 ORDER BY id")]
        self.assertEqual(actions, ["quiz_failed", "quiz_passed", "quiz_passed"])

    # ---- UC-EL-06: hasil dan pembahasan ----
    def test_result_page_shows_review_with_key_and_explanations(self):
        self.login()
        self.enroll()
        response = self.submit(self.ONE_RIGHT)
        result = self.client.get(response.headers["Location"])
        html = result.get_data(as_text=True)
        self.assertEqual(result.status_code, 200)
        self.assertIn("Belum lulus", html)
        self.assertIn("Benar 1 dari 4 soal", html)
        self.assertIn("Coba Lagi", html)
        self.assertIn("/elearning/kelas/1/kuis\"", html)
        for n in (1, 2, 3, 4):
            self.assertIn(self.EXPLAIN.format(n=n), html)
        self.assertEqual(html.count("Jawaban benar"), 4)
        self.assertEqual(html.count("Jawaban Anda"), 4)
        self.assertEqual(html.count("el-verdict is-right"), 1)
        self.assertEqual(html.count("el-verdict is-wrong"), 3)

    def test_result_page_marks_unanswered_and_pass_message(self):
        self.login()
        self.enroll()
        html = self.client.get(self.submit({1: "b"}).headers["Location"]).get_data(as_text=True)
        self.assertEqual(html.count("Tidak dijawab"), 3)
        html = self.client.get(self.submit(self.PERFECT).headers["Location"]).get_data(as_text=True)
        self.assertIn("Lulus", html)
        self.assertIn("progres belajar Anda menjadi 100%", html)
        self.assertIn("Coba Lagi", html)          # tombol tetap ada setelah lulus

    def test_result_belongs_to_owner_only(self):
        self.login()
        self.enroll()
        url = self.submit(self.PERFECT).headers["Location"]
        other = self.app.test_client()
        self.login(2, other)
        self.enroll(1, user_id=2)
        self.assertEqual(other.get(url).status_code, 404)           # sudah terdaftar, tetap tak boleh melihat
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get("/elearning/kelas/1/kuis/hasil/9999").status_code, 404)
        # id percobaan milik kelas lain tidak bisa dibuka lewat URL kelas ini
        self.sql("INSERT INTO enrollments (user_id, course_id, source) VALUES (1, 3, 'free')")
        self.assertEqual(self.client.get(url.replace("/kelas/1/", "/kelas/3/")).status_code, 302)

    def test_retry_creates_new_attempt_and_quiz_page_shows_history(self):
        self.login()
        self.enroll()
        self.submit(self.ONE_RIGHT)
        self.submit({1: "b", 2: "a", 3: "c", 4: "a"})               # 75% lulus
        self.assertEqual([r[0] for r in self.sql("SELECT score FROM quiz_attempts ORDER BY id")], [25, 75])
        html = self.client.get("/elearning/kelas/1/kuis").get_data(as_text=True)
        self.assertIn("percobaan sebelumnya: 2", html)
        self.assertIn("nilai terbaik 75", html)

    def test_result_survives_corrupt_answers_json(self):
        self.login()
        self.enroll()
        self.submit(self.PERFECT)
        self.sql("UPDATE quiz_attempts SET answers_json = '{rusak'")
        response = self.client.get("/elearning/kelas/1/kuis/hasil/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_data(as_text=True).count("Tidak dijawab"), 4)

    # ---- tautan dan navigasi ----
    def test_course_detail_and_lesson_link_to_quiz_only_for_enrolled(self):
        self.login()
        self.assertNotIn("/elearning/kelas/1/kuis", self.client.get("/elearning/kelas/1").get_data(as_text=True))
        self.enroll()
        detail = self.client.get("/elearning/kelas/1").get_data(as_text=True)
        self.assertIn("/elearning/kelas/1/kuis", detail)
        self.assertIn("Kerjakan kuis", detail)
        self.assertIn("/elearning/kelas/1/kuis", self.client.get("/elearning/kelas/1/materi/1").get_data(as_text=True))
        self.submit(self.PERFECT)
        self.assertIn("Coba kuis lagi", self.client.get("/elearning/kelas/1").get_data(as_text=True))

    def test_breadcrumb_on_quiz_pages(self):
        self.login()
        self.enroll()
        html = self.client.get("/elearning/kelas/1/kuis").get_data(as_text=True)
        self.assertIn("Desain Dasar", html)
        result = self.client.get(self.submit(self.PERFECT).headers["Location"]).get_data(as_text=True)
        self.assertIn("Hasil Kuis", result)
        self.assertIn('href="/elearning/kelas/1/kuis"', result)      # induk langsung: halaman kuis


if __name__ == "__main__":
    unittest.main()
