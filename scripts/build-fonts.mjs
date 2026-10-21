// Converts the licensed (SIL OFL) @fontsource WOFF files into Three.js typeface JSON
// so headlines can be built as real extruded, bevelled geometry. Includes kerning pairs.
import fs from 'node:fs';
import path from 'node:path';
import opentype from 'opentype.js';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const FONTS = [
  ['cinzel-700', 'node_modules/@fontsource/cinzel/files/cinzel-latin-700-normal.woff'],
  ['cinzel-900', 'node_modules/@fontsource/cinzel/files/cinzel-latin-900-normal.woff'],
  ['montserrat-600', 'node_modules/@fontsource/montserrat/files/montserrat-latin-600-normal.woff'],
  ['montserrat-800', 'node_modules/@fontsource/montserrat/files/montserrat-latin-800-normal.woff'],
];
const CHARS = [];
for (let c = 0x20; c <= 0x7e; c++) CHARS.push(String.fromCharCode(c));
for (const c of 'ÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŒ•€’·') CHARS.push(c);

const r = (v) => Math.round(v * 10) / 10;
for (const [name, file] of FONTS) {
  const buf = fs.readFileSync(path.join(root, file));
  const font = opentype.parse(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
  const glyphs = {};
  const kerning = {};
  for (const ch of CHARS) {
    const g = font.charToGlyph(ch);
    if (!g || (g.index === 0 && ch !== ' ')) continue;
    let o = '';
    for (const c of g.path.commands) {
      if (c.type === 'M') o += `m ${r(c.x)} ${r(c.y)} `;
      else if (c.type === 'L') o += `l ${r(c.x)} ${r(c.y)} `;
      else if (c.type === 'Q') o += `q ${r(c.x)} ${r(c.y)} ${r(c.x1)} ${r(c.y1)} `;
      else if (c.type === 'C') o += `b ${r(c.x)} ${r(c.y)} ${r(c.x1)} ${r(c.y1)} ${r(c.x2)} ${r(c.y2)} `;
    }
    const bb = g.getBoundingBox();
    glyphs[ch] = { ha: g.advanceWidth, x_min: bb.x1, x_max: bb.x2, o: o.trim() };
  }
  const present = Object.keys(glyphs);
  for (const a of present) for (const b of present) {
    const k = font.getKerningValue(font.charToGlyph(a), font.charToGlyph(b));
    if (k) kerning[a + b] = k;
  }
  const out = {
    glyphs, kerning, familyName: font.names.fontFamily.en, resolution: font.unitsPerEm,
    ascender: font.ascender, descender: font.descender,
    underlinePosition: font.tables.post.underlinePosition, underlineThickness: font.tables.post.underlineThickness,
    boundingBox: { xMin: font.tables.head.xMin, yMin: font.tables.head.yMin, xMax: font.tables.head.xMax, yMax: font.tables.head.yMax },
    original_font_information: { license: 'SIL Open Font License 1.1', source: file },
  };
  fs.writeFileSync(path.join(root, 'assets/fonts', name + '.json'), JSON.stringify(out));
  console.log(name, Object.keys(glyphs).length, 'glyphs', Object.keys(kerning).length, 'kern pairs', 'missing:', CHARS.filter(c => !glyphs[c]).join(''));
}
