/** Konfigurasi Tailwind DKE (Blueprint 5.4 dan 6.7).
 *  Nilai warna sebenarnya ada di app/static/css/custom.css (variabel --c-*), sehingga satu kelas
 *  berlaku untuk Light dan Dark. Build: `npm run build:css` (lihat README). */
module.exports = {
  darkMode: 'class',
  content: [
    './app/templates/**/*.html',
    './app/static/js/**/*.js',
    // Kelas yang dirangkai di Python (mis. kelas badge/status yang dikirim ke templat)
    './app/**/*.py',
  ],
  // Kelas yang dibangun dinamis (string digabung di JS/Python) tidak terdeteksi pemindai; daftarkan di sini.
  safelist: [],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'] },
      colors: {
        page:    'rgb(var(--c-page) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        ink:     'rgb(var(--c-ink) / <alpha-value>)',
        muted:   'rgb(var(--c-muted) / <alpha-value>)',
        line:    'rgb(var(--c-border) / <alpha-value>)',
        primary: 'rgb(var(--c-primary) / <alpha-value>)',
        'on-primary':   'rgb(var(--c-on-primary) / <alpha-value>)',
        header:  'rgb(var(--c-header) / <alpha-value>)',
        success: 'rgb(var(--c-success) / <alpha-value>)',
        'success-fill': 'rgb(var(--c-success-fill) / <alpha-value>)',
      },
    },
  },
  plugins: [],
};
