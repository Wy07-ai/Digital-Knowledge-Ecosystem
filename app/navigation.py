"""Hierarki halaman DKE untuk navigasi 3 level (Blueprint 5.2).

Level 1  tombol "Kembali"  -> induk langsung halaman ini di hierarki (BUKAN riwayat browser)
Level 2  breadcrumb         -> seluruh rantai induk, setiap jenjang bisa diklik
Level 3  Top-Bar            -> App Switcher dan tombol DKE (Beranda), lihat templates/_components

Hierarki dideklarasikan SATU KALI di tabel NAV di bawah. Template tidak perlu memanggil
breadcrumb() atau back_link() sendiri: base.html menampilkannya otomatis lewat variabel `nav`
(lihat inject_globals di app/__init__.py).

Cara menambah halaman baru (misalnya detail kelas E-Learning):

    node("elearning.course_detail", _course_title, parent="elearning.index")
    node("elearning.lesson", _lesson_title, parent="elearning.course_detail")

  * label        : teks tetap, atau fungsi(view_args) -> teks (untuk judul dari database)
  * parent       : endpoint induk. Halaman utama modul (<modul>.index) otomatis menjadi akar.
  * parent_args  : fungsi(view_args) -> dict nilai URL induk; hanya perlu bila induk
                   membutuhkan argumen yang tidak sama namanya dengan argumen halaman ini.

Endpoint yang tidak terdaftar tidak mendapat breadcrumb dan tombol Kembali (mis. login).
"""
import sqlite3
from dataclasses import dataclass
from typing import Callable, Optional, Union
from urllib.parse import urlsplit

from flask import current_app, request, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.routing import BuildError, RequestRedirect

from .db import get_db

MAX_DEPTH = 6  # pagar pengaman terhadap hierarki yang salah (siklus)


@dataclass(frozen=True)
class Node:
    label: Union[str, Callable]
    parent: Optional[str] = None
    parent_args: Optional[Callable] = None


NAV = {}


def node(endpoint, label, parent=None, parent_args=None):
    """Daftarkan satu halaman ke hierarki."""
    NAV[endpoint] = Node(label=label, parent=parent, parent_args=parent_args)


# --------------------------------------------------------------------------
# Label dinamis (judul dari database; tetap aman bila data tidak ada)
# --------------------------------------------------------------------------
def _course_title(args):
    row = get_db().execute("SELECT title FROM courses WHERE id = ?", (args["course_id"],)).fetchone()
    return row["title"] if row else f"Kelas {args['course_id']}"


def _lesson_title(args):
    row = get_db().execute(
        "SELECT title FROM lessons WHERE course_id = ? AND order_no = ?",
        (args["course_id"], args["order_no"]),
    ).fetchone()
    base = f"Materi {args['order_no']}"
    return f"{base}: {row['title']}" if row else base


# --------------------------------------------------------------------------
# Tabel hierarki
# --------------------------------------------------------------------------
# Halaman yang sudah ada.
node("infosys.profile", "Profil & Pengaturan", parent="infosys.index")
node("infosys.activity", "Log Aktivitas", parent="infosys.index")
node("infosys.stats", "Statistik Lintas Modul", parent="infosys.index")
node("infosys.security", "Pengaturan Keamanan", parent="infosys.index")

# E-Learning: E-Learning > <judul kelas> > Materi N: <judul materi>
#             E-Learning > <judul kelas> > Kuis > Hasil Kuis
node("elearning.course_detail", _course_title, parent="elearning.index")
node("elearning.lesson", _lesson_title, parent="elearning.course_detail")
node("elearning.quiz", "Kuis", parent="elearning.course_detail")
node("elearning.quiz_result", "Hasil Kuis", parent="elearning.quiz")
node("elearning.my_courses", "Kelas Saya", parent="elearning.index")
node("elearning.settings", "Pengaturan", parent="elearning.index")

# Contoh halaman bersarang 3 jenjang (halaman uji /dev/ui-test, hanya bila UI_TEST_PAGE aktif):
#   E-Learning > <judul kelas> > Materi N: <judul materi>
node("main.nav_demo_course", _course_title, parent="elearning.index")
node("main.nav_demo_lesson", _lesson_title, parent="main.nav_demo_course")


# --------------------------------------------------------------------------
# Penyelesaian hierarki
# --------------------------------------------------------------------------
def _node_for(endpoint):
    """Node terdaftar, atau akar modul otomatis untuk <modul>.index."""
    found = NAV.get(endpoint)
    if found is not None:
        return found
    from . import MODULE_BY_KEY  # impor tertunda: app/__init__.py mengimpor modul ini

    blueprint, _, view = endpoint.partition(".")
    if view == "index" and blueprint in MODULE_BY_KEY:
        return Node(label=MODULE_BY_KEY[blueprint]["name"])
    return None


def _label_of(found, args, endpoint):
    try:
        text = found.label(args) if callable(found.label) else found.label
    except (sqlite3.Error, KeyError, TypeError):
        current_app.logger.warning("Label navigasi gagal untuk %s", endpoint, exc_info=True)
        text = None
    return text or "Halaman"


def _url_of(endpoint, args):
    """URL endpoint dengan hanya argumen yang memang dipakai rutenya; None bila tak bisa dibuat."""
    wanted = set()
    for rule in current_app.url_map.iter_rules(endpoint):
        wanted |= rule.arguments
    try:
        return url_for(endpoint, **{k: v for k, v in args.items() if k in wanted})
    except BuildError:
        return None


def trail_for(endpoint, view_args=None):
    """Rantai halaman dari akar ke halaman ini: [(label, url, endpoint), ...]. Kosong bila tak terdaftar."""
    chain, args, seen = [], dict(view_args or {}), set()
    while endpoint and endpoint not in seen and len(chain) < MAX_DEPTH:
        found = _node_for(endpoint)
        if found is None:
            return [] if not chain else list(reversed(chain))
        seen.add(endpoint)
        chain.append((_label_of(found, args, endpoint), _url_of(endpoint, args), endpoint))
        args = found.parent_args(args) if found.parent_args else args
        endpoint = found.parent
    return list(reversed(chain))


def build_nav():
    """Konteks navigasi halaman saat ini, atau None bila halaman ini tidak punya hierarki.

    Hasil: {"trail": [(label, url), ...], "back": {"url", "label"} atau None}
    Segmen terakhir trail (halaman aktif) tidak punya url. Tombol Kembali hanya ada
    untuk halaman turunan (trail >= 2) dan menuju induk langsung di hierarki.
    """
    if not request.endpoint:
        return None
    chain = trail_for(request.endpoint, request.view_args)
    if not chain:
        return None
    trail = [(label, url) for label, url, _ep in chain[:-1]] + [(chain[-1][0], None)]
    back = None
    if len(chain) >= 2 and chain[-2][1]:
        back = {"url": chain[-2][1], "label": chain[-2][0]}
    return {"trail": trail, "back": back}


def describe_path(path):
    """Cocokkan jalur tersimpan (mis. user_settings.last_path) ke halaman nyata.

    Mengembalikan (endpoint, [label, ...]) atau None bila jalur tidak lagi menuju rute yang ada.
    Dipakai tombol "Lanjutkan" di Beranda.
    """
    path = (path or "").split("?", 1)[0].split("#", 1)[0]
    adapter = current_app.create_url_adapter(request)
    try:
        try:
            endpoint, args = adapter.match(path, method="GET")
        except RequestRedirect as redirect:  # mis. /forum -> /forum/ (garis miring penutup)
            endpoint, args = adapter.match(urlsplit(redirect.new_url).path, method="GET")
    except HTTPException:
        return None
    chain = trail_for(endpoint, args)
    return endpoint, [label for label, _url, _ep in chain]
