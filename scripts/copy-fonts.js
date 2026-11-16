// Menyalin berkas font Inter (subset latin) dari @fontsource/inter ke app/static/fonts.
const fs = require('fs');
const path = require('path');
const src = path.join(__dirname, '..', 'node_modules', '@fontsource', 'inter', 'files');
const dst = path.join(__dirname, '..', 'app', 'static', 'fonts');
fs.mkdirSync(dst, { recursive: true });
for (const w of [400, 500, 600, 700]) {
  const f = `inter-latin-${w}-normal.woff2`;
  fs.copyFileSync(path.join(src, f), path.join(dst, f));
}
console.log('Font Inter disalin ke', dst);
