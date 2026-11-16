"""Tes efek transisi tema "circular reveal" (static/js/theme.js).

Jalankan dari akar proyek:   python -m unittest tests.test_theme_transition -v

Dua lapis:
1. Pemeriksaan teks berkas (selalu jalan): fallback, reduced-motion, CSS dasar, skrip anti-kedip utuh.
2. Eksekusi nyata theme.js di Node dengan DOM tiruan (dilewati bila Node tidak terpasang):
   fallback tanpa View Transitions, reduced-motion, lingkaran dari ikon, dan tombol terkunci.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class ThemeSourceTests(unittest.TestCase):
    def setUp(self):
        self.js = read("app", "static", "js", "theme.js")
        self.css = read("app", "static", "css", "custom.css")

    def test_has_fallback_without_view_transitions(self):
        self.assertIn("typeof document.startViewTransition !== 'function'", self.js)
        self.assertIn("prefers-reduced-motion: reduce", self.js)

    def test_circle_math_and_animation(self):
        for needle in ("Math.hypot", "getBoundingClientRect", "transition.ready",
                       "::view-transition-new(root)", "clipPath", "ease-in-out"):
            self.assertIn(needle, self.js)

    def test_base_css(self):
        self.assertIn("::view-transition-old(root)", self.css)
        self.assertIn("mix-blend-mode: normal", self.css)
        self.assertIn("html[data-theme-animating]", self.css)

    def test_storage_behaviour_untouched(self):
        self.assertIn("localStorage.setItem(LS[kind], value)", self.js)
        self.assertIn("/api/settings/global", self.js)

    def test_anti_flicker_script_untouched(self):
        base = read("app", "templates", "base.html")
        self.assertIn("d.classList.toggle('dark', dark);", base)
        self.assertNotIn("startViewTransition", base)

    def test_topbar_marks_toggle(self):
        self.assertIn("data-theme-toggle", read("app", "templates", "_components", "topbar.html"))


HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync(process.argv[2], 'utf8');
const scenario = JSON.parse(process.argv[3]);

function makeEnv() {
  const log = { animate: [], vtCalls: 0, fetches: [], ls: {} };
  const classes = new Set();
  const html = {
    dataset: { theme: 'light', view: 'desktop', member: scenario.member ? '1' : '0' },
    classList: { toggle(c, on) { on ? classes.add(c) : classes.delete(c); }, contains: c => classes.has(c) },
    attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    animate(kf, opt) { log.animate.push({ kf, opt }); }
  };
  const icon = { classList: { add() {}, remove() {} }, offsetWidth: 0,
                 getBoundingClientRect: () => ({ left: 900, top: 10, width: 20, height: 20 }) };
  const listeners = { true: [], false: [] };
  let pending = null;
  const document = {
    documentElement: html,
    querySelector: s => (s === '[data-theme-spin]' ? icon : null),
    querySelectorAll: () => [],
    addEventListener(t, fn, cap) { if (t === 'click') listeners[!!cap].push(fn); },
    dispatchEvent() {}
  };
  if (scenario.viewTransitions) {
    document.startViewTransition = function (cb) {
      log.vtCalls++;
      cb();
      let done; const finished = new Promise(r => { done = r; });
      pending = done;
      return { ready: Promise.resolve(), finished, updateCallbackDone: Promise.resolve() };
    };
  }
  const win = {
    document, innerWidth: 1000, innerHeight: 600,
    matchMedia: q => ({ matches: scenario.reduced && q.indexOf('reduced-motion') >= 0, addEventListener() {} }),
    addEventListener() {}, localStorage: { setItem(k, v) { log.ls[k] = v; } }, CustomEvent: function () {},
    fetch: (u, o) => { log.fetches.push({ u, body: o.body }); return Promise.resolve({ ok: true }); }
  };
  win.window = win; win.global = win;
  const ctx = vm.createContext(Object.assign(win, { localStorage: win.localStorage, CustomEvent: function () {}, fetch: win.fetch }));
  ctx.document = document;
  vm.runInContext(src, ctx);
  function click(opt) {
    const target = { closest: sel => (sel.indexOf('data-theme-option') >= 0 ? { dataset: { themeOption: opt } } : null) };
    let stopped = false;
    const ev = { target, preventDefault() {}, stopPropagation() { stopped = true; } };
    listeners[true].forEach(fn => fn(ev));
    if (!stopped) listeners[false].forEach(fn => fn(ev));
    return stopped;
  }
  return { log, html, classes, click, finish: () => pending && pending() };
}

(async () => {
  const env = makeEnv();
  const out = {};
  out.stopped1 = env.click('dark');
  out.darkImmediately = env.classes.has('dark');
  out.busyDuring = env.html.attrs['data-theme-animating'] === '1';
  out.stopped2 = scenario.single ? false : env.click('light');   // klik ganda saat transisi
  await Promise.resolve(); await Promise.resolve();
  out.animate = env.log.animate;
  out.vtCalls = env.log.vtCalls;
  out.stillDark = env.classes.has('dark');
  env.finish(); await new Promise(r => setTimeout(r, 0));
  out.busyAfter = env.html.attrs['data-theme-animating'] === '1';
  out.ls = env.log.ls;
  out.fetches = env.log.fetches;
  console.log(JSON.stringify(out));
})().catch(e => { console.error(e); process.exit(1); });
"""


@unittest.skipUnless(shutil.which("node"), "Node tidak terpasang")
class ThemeBehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.harness = os.path.join(cls.tmp, "harness.js")
        with open(cls.harness, "w", encoding="utf-8") as f:
            f.write(HARNESS)
        cls.theme = os.path.join(ROOT, "app", "static", "js", "theme.js")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_js(self, **scenario):
        res = subprocess.run(["node", self.harness, self.theme, json.dumps(scenario)],
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stderr)
        return json.loads(res.stdout.strip().splitlines()[-1])

    def test_fallback_without_view_transitions(self):
        r = self.run_js(viewTransitions=False, single=True)
        self.assertTrue(r["darkImmediately"])
        self.assertEqual(r["vtCalls"], 0)
        self.assertEqual(r["ls"].get("dke-theme"), "dark")      # Guest tetap ke localStorage

    def test_reduced_motion_skips_effect(self):
        r = self.run_js(viewTransitions=True, reduced=True)
        self.assertTrue(r["darkImmediately"])
        self.assertEqual(r["vtCalls"], 0)

    def test_circle_grows_from_icon(self):
        r = self.run_js(viewTransitions=True)
        self.assertEqual(r["vtCalls"], 1)
        self.assertTrue(r["darkImmediately"])
        anim = r["animate"][0]
        self.assertEqual(anim["opt"]["pseudoElement"], "::view-transition-new(root)")
        self.assertEqual(anim["opt"]["easing"], "ease-in-out")
        self.assertTrue(500 <= anim["opt"]["duration"] <= 600)
        # ikon di (910, 20); sudut terjauh = kiri-bawah: hypot(910, 580)
        start, end = anim["kf"]["clipPath"]
        self.assertEqual(start, "circle(0px at 910px 20px)")
        self.assertEqual(end, "circle(%spx at 910px 20px)" % ((910 ** 2 + 580 ** 2) ** 0.5))

    def test_no_double_press_during_transition(self):
        r = self.run_js(viewTransitions=True)
        self.assertTrue(r["busyDuring"])
        self.assertTrue(r["stopped2"])
        self.assertEqual(r["vtCalls"], 1)
        self.assertTrue(r["stillDark"])
        self.assertFalse(r["busyAfter"])

    def test_member_still_posts_to_server(self):
        r = self.run_js(viewTransitions=True, member=True, single=True)
        self.assertEqual(len(r["fetches"]), 1)
        self.assertEqual(json.loads(r["fetches"][0]["body"]), {"theme": "dark"})
        self.assertEqual(r["ls"], {})


if __name__ == "__main__":
    unittest.main()
