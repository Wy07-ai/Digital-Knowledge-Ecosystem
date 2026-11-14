"""Logika kuis E-Learning (UC-EL-05 mengerjakan kuis, UC-EL-06 melihat hasil).

Modul ini sengaja TIDAK mengimpor routes.py: isinya fungsi murni (grade) dan akses data,
sehingga mudah diuji dan tidak membuat impor melingkar. View-nya ada di routes.py.

Aturan keamanan yang dijaga di sini:
  * Penilaian hanya terjadi di server lewat grade(). Server tidak pernah menerima skor dari klien;
    yang diterima hanya pilihan jawaban (a/b/c/d) per soal.
  * Kueri untuk halaman pengerjaan (get_public_questions) TIDAK mengambil correct_option dan
    explanation, jadi kunci jawaban tidak mungkin ikut ke HTML sebelum kuis dikumpulkan.
"""
import json

OPTION_KEYS = ("a", "b", "c", "d")
DEFAULT_PASS_SCORE = 70


# --------------------------------------------------------------------------
# Penilaian (fungsi murni)
# --------------------------------------------------------------------------
def _norm(value):
    """Pilihan jawaban -> huruf kecil tanpa spasi; bukan teks -> ''."""
    return value.strip().lower() if isinstance(value, str) else ""


def question_options(question):
    """[(kunci, teks), ...] untuk opsi yang terisi. Opsi a dan b wajib; c dan d boleh kosong."""
    q = dict(question)
    options = []
    for key in OPTION_KEYS:
        text = q.get(f"option_{key}")
        if text is not None and str(text).strip() != "":
            options.append((key, text))
    return options


def _clamp_pass_score(pass_score):
    try:
        value = int(pass_score)
    except (TypeError, ValueError):
        return DEFAULT_PASS_SCORE
    return max(0, min(100, value))


def grade(questions, answers, pass_score):
    """Nilai satu percobaan kuis. Fungsi murni: tanpa database, tanpa Flask.

    questions  : iterable soal (dict/Row) dengan kunci id, correct_option, option_a..option_d.
    answers    : mapping id soal -> pilihan peserta ('a'..'d'). Kunci boleh int atau str.
                 Soal tanpa jawaban, jawaban di luar opsi yang ada, atau bukan teks dihitung salah.
    pass_score : nilai minimal lulus (0-100); nilai di luar rentang dipotong ke rentang itu.

    score = persen benar dibulatkan KE BAWAH, supaya `score >= pass_score` selalu sama dengan
    "benar/total >= pass_score%". Pembulatan biasa bisa meluluskan 69,5% sebagai 70.
    Kuis tanpa soal tidak pernah lulus.

    Mengembalikan dict: total, correct, score, passed, pass_score, results. Setiap elemen results:
    question_id, chosen (None bila kosong/tidak valid), correct_option, answered, is_correct.
    """
    pass_score = _clamp_pass_score(pass_score)
    answers = answers if isinstance(answers, dict) else {}
    normalized = {str(k): v for k, v in answers.items()}

    results, correct = [], 0
    for question in questions:
        q = dict(question)
        qid = q["id"]
        allowed = {key for key, _text in question_options(q)}
        chosen = _norm(normalized.get(str(qid)))
        chosen = chosen if chosen in allowed else None
        right = _norm(q.get("correct_option"))
        is_correct = chosen is not None and chosen == right
        correct += is_correct
        results.append({
            "question_id": qid,
            "chosen": chosen,
            "correct_option": right,
            "answered": chosen is not None,
            "is_correct": is_correct,
        })

    total = len(results)
    score = (correct * 100) // total if total else 0
    passed = total > 0 and correct * 100 >= pass_score * total
    return {"total": total, "correct": correct, "score": score, "passed": passed,
            "pass_score": pass_score, "results": results}


def answers_to_json(results):
    """Jawaban tersimpan: {"<id soal>": "a"} hanya untuk soal yang dijawab (format sama dengan seed)."""
    return json.dumps({str(r["question_id"]): r["chosen"] for r in results if r["chosen"]},
                      ensure_ascii=False, sort_keys=True)


def answers_from_json(text):
    """answers_json -> dict; data rusak/kosong menghasilkan {} (tidak membuat halaman hasil error)."""
    try:
        data = json.loads(text) if text else {}
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------
# Akses data
# --------------------------------------------------------------------------
def get_quiz(db, course_id):
    """Kuis kelas ini (satu kuis per kelas; bila ada beberapa, yang pertama dibuat)."""
    return db.execute(
        "SELECT id, course_id, title, pass_score FROM quizzes WHERE course_id = ? ORDER BY id ASC LIMIT 1",
        (course_id,),
    ).fetchone()


def get_public_questions(db, quiz_id):
    """Soal untuk halaman pengerjaan. Kolom correct_option dan explanation SENGAJA tidak dipilih."""
    return db.execute(
        "SELECT id, question, option_a, option_b, option_c, option_d "
        "FROM quiz_questions WHERE quiz_id = ? ORDER BY id ASC",
        (quiz_id,),
    ).fetchall()


def get_full_questions(db, quiz_id):
    """Soal lengkap beserta kunci dan pembahasan. Hanya untuk penilaian dan halaman hasil."""
    return db.execute(
        "SELECT id, question, option_a, option_b, option_c, option_d, correct_option, explanation "
        "FROM quiz_questions WHERE quiz_id = ? ORDER BY id ASC",
        (quiz_id,),
    ).fetchall()


def save_attempt(db, user_id, quiz_id, result, taken_at):
    """Simpan percobaan (tanpa commit; pemanggil yang mengatur transaksi). Mengembalikan id."""
    cur = db.execute(
        "INSERT INTO quiz_attempts (user_id, quiz_id, score, passed, answers_json, taken_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, quiz_id, result["score"], 1 if result["passed"] else 0,
         answers_to_json(result["results"]), taken_at),
    )
    return cur.lastrowid


def get_attempt(db, user_id, course_id, attempt_id):
    """Percobaan milik user_id untuk kuis kelas ini, atau None (tidak bisa mengintip milik orang lain)."""
    return db.execute(
        "SELECT a.*, q.title AS quiz_title, q.pass_score AS pass_score, q.id AS quiz_id "
        "FROM quiz_attempts a JOIN quizzes q ON q.id = a.quiz_id "
        "WHERE a.id = ? AND a.user_id = ? AND q.course_id = ?",
        (attempt_id, user_id, course_id),
    ).fetchone()


def quiz_summary(db, user_id, course_id):
    """Ringkasan kuis untuk tombol di detail kelas dan Ruang Belajar; None bila kelas tanpa soal."""
    quiz = get_quiz(db, course_id)
    if quiz is None:
        return None
    count = db.execute("SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = ?", (quiz["id"],)).fetchone()[0]
    if not count:
        return None
    row = db.execute(
        "SELECT COUNT(*) AS attempts, MAX(score) AS best, MAX(passed) AS passed "
        "FROM quiz_attempts WHERE user_id = ? AND quiz_id = ?",
        (user_id, quiz["id"]),
    ).fetchone()
    return {"title": quiz["title"], "pass_score": quiz["pass_score"], "question_count": count,
            "attempts": row["attempts"], "best_score": row["best"], "passed": bool(row["passed"])}


def complete_course(db, user_id, course_id, completed_at):
    """Tandai kelas selesai setelah lulus kuis (tanpa commit).

    * enrollments.completed_at diisi sekali; kelulusan berikutnya tidak menimpa tanggal pertama.
    * progress_percent tidak punya kolom sendiri (selalu dihitung dari lesson_progress), jadi progres
      100% dicapai dengan menandai semua materi selesai. INSERT OR IGNORE menjaga tanggal selesai
      materi yang sudah ada.
    Mengembalikan True bila ini kelulusan pertama yang menyelesaikan kelas.
    """
    cur = db.execute(
        "UPDATE enrollments SET completed_at = ? "
        "WHERE user_id = ? AND course_id = ? AND completed_at IS NULL",
        (completed_at, user_id, course_id),
    )
    db.execute(
        "INSERT OR IGNORE INTO lesson_progress (user_id, lesson_id, completed_at) "
        "SELECT ?, id, ? FROM lessons WHERE course_id = ?",
        (user_id, completed_at, course_id),
    )
    return cur.rowcount > 0
