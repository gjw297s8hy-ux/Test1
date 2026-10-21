#!/usr/bin/env node
// Headless render driver.
//   node scripts/render.mjs --q final --from 0 --to 30 --out renders/x.mov [--workers 2] [--codec prores|h264]
//   node scripts/render.mjs --q draft --stills 1.5,6,11 --outdir previews/draft
// Serves the project over HTTP, opens the engine in headless Chromium (SwiftShader WebGL2),
// renders frame-by-frame and pipes raw RGBA straight into ffmpeg.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright-core';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => {
  if (v.startsWith('--')) a.push([v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return a;
}, []));
const config = JSON.parse(fs.readFileSync(path.join(root, 'config/config.json'), 'utf8'));
const qname = args.q || 'draft';
const Q = { ...config.quality[qname] };
if (args.w) { Q.width = +args.w; Q.height = +args.h; }
if (args.fps) Q.fps = +args.fps;
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg' };

function scenesFor(t0, t1) {
  // scenes overlapping [t0, t1] including transition overlaps
  const pad = Math.max(...config.timing.transitions.map((t) => t.duration)) / 2 + 0.05;
  return config.timing.scenes.filter((s) => s.end + pad > t0 && s.start - pad < t1).map((s) => s.id).join(',');
}

function serve(onFrame, onStill) {
  const server = http.createServer((req, res) => {
    const u = new URL(req.url, 'http://x');
    if (req.method === 'POST') {
      const chunks = [];
      req.on('data', (c) => chunks.push(c));
      req.on('end', async () => {
        const body = Buffer.concat(chunks);
        try {
          if (u.pathname === '/frame') await onFrame(+u.searchParams.get('i'), body);
          else if (u.pathname === '/still') await onStill(u.searchParams.get('name'), body);
          res.end('ok');
        } catch (e) { res.statusCode = 500; res.end(String(e)); }
      });
      return;
    }
    const p = path.join(root, decodeURIComponent(u.pathname));
    if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.statusCode = 404; return res.end(); }
    res.setHeader('Content-Type', MIME[path.extname(p)] || 'application/octet-stream');
    fs.createReadStream(p).pipe(res);
  });
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r(server)));
}

async function openEngine(port, scenes) {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium',
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--disable-gpu-watchdog', '--js-flags=--max-old-space-size=8192'],
  });
  const page = await browser.newPage({ viewport: { width: 400, height: 400 } });
  page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[page]', m.text().slice(0, 400)); });
  page.on('pageerror', (e) => console.log('[pageerror]', e.message));
  const qs = new URLSearchParams({ q: qname, scenes, w: Q.width, h: Q.height, fps: Q.fps, ...(args.mb ? { mb: args.mb } : {}) });
  await page.goto(`http://127.0.0.1:${port}/src/engine/index.html?${qs}`);
  await page.waitForFunction(() => window.ENGINE && (window.ENGINE.ready || window.ENGINE.error), null, { timeout: 600000 });
  const err = await page.evaluate(() => window.ENGINE.error);
  if (err) { await browser.close(); throw new Error(err); }
  return { browser, page };
}

function ffmpegFor(out, codec) {
  const enc = codec === 'prores'
    ? ['-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le', '-vendor', 'apl0']
    : ['-c:v', 'libx264', '-preset', 'medium', '-crf', args.crf || '14', '-pix_fmt', 'yuv420p', '-movflags', '+faststart'];
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', `${Q.width}x${Q.height}`, '-r', String(Q.fps), '-i', '-', '-vf', 'vflip', ...enc, '-r', String(Q.fps), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const done = new Promise((r, j) => ff.on('close', (c) => (c === 0 ? r() : j(new Error('ffmpeg exit ' + c)))));
  return { ff, done };
}

async function renderRange(f0, f1, out, codec, tag) {
  let ffw;
  const server = await serve(async (i, body) => {
    if (!ffw.ff.stdin.write(body)) await new Promise((r) => ffw.ff.stdin.once('drain', r));
  }, async () => {});
  ffw = ffmpegFor(out, codec);
  const t0 = f0 / Q.fps, t1 = f1 / Q.fps;
  const { browser, page } = await openEngine(server.address().port, scenesFor(t0, t1));
  const start = Date.now();
  for (let i = f0; i < f1; i++) {
    await page.evaluate((i) => window.ENGINE.renderFrame(i), i);
    if ((i - f0) % 30 === 0 || i === f1 - 1) {
      const el = (Date.now() - start) / 1000, done = i - f0 + 1;
      console.log(`${tag} frame ${i} (${done}/${f1 - f0}) ${(el / done).toFixed(2)}s/f eta ${((f1 - f0 - done) * el / done / 60).toFixed(1)}min`);
    }
  }
  ffw.ff.stdin.end();
  await ffw.done;
  await browser.close();
  server.close();
}

async function main() {
  if (args.stills) {
    const outdir = path.join(root, args.outdir || `previews/${qname}`);
    fs.mkdirSync(outdir, { recursive: true });
    const times = String(args.stills).split(',').map(Number);
    const server = await serve(async () => {}, async (name, body) => fs.writeFileSync(path.join(outdir, name), body));
    const { browser, page } = await openEngine(server.address().port, scenesFor(Math.min(...times), Math.max(...times)));
    for (const t of times) {
      const s = Date.now();
      await page.evaluate(([t, n]) => window.ENGINE.still(t, n), [t, `t${t.toFixed(2).padStart(5, '0')}.png`]);
      console.log(`still t=${t} ${((Date.now() - s) / 1000).toFixed(2)}s`);
    }
    await browser.close(); server.close();
    return;
  }
  const from = Math.round((+args.from || 0) * Q.fps);
  const to = Math.round((args.to !== undefined ? +args.to : config.timing.duration) * Q.fps);
  const codec = args.codec || 'h264';
  const out = path.join(root, args.out || `renders/${qname}_${args.from || 0}-${args.to || config.timing.duration}.${codec === 'prores' ? 'mov' : 'mp4'}`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const workers = +(args.workers || 1);
  const t = Date.now();
  if (workers === 1) await renderRange(from, to, out, codec, 'w0');
  else {
    const tmp = path.join(root, 'renders/tmp'); fs.mkdirSync(tmp, { recursive: true });
    const step = Math.ceil((to - from) / workers);
    const parts = [];
    for (let w = 0; w < workers; w++) {
      const a = from + w * step, b = Math.min(to, a + step);
      if (a >= b) continue;
      parts.push({ a, b, file: path.join(tmp, `${path.basename(out)}.part${w}.${codec === 'prores' ? 'mov' : 'mp4'}`), w });
    }
    await Promise.all(parts.map((p) => renderRange(p.a, p.b, p.file, codec, 'w' + p.w)));
    const list = path.join(tmp, path.basename(out) + '.txt');
    fs.writeFileSync(list, parts.map((p) => `file '${p.file}'`).join('\n'));
    await new Promise((r, j) => spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', out], { stdio: 'inherit' }).on('close', (c) => (c ? j(new Error('concat')) : r())));
    parts.forEach((p) => fs.rmSync(p.file, { force: true }));
  }
  console.log(`done ${out} in ${((Date.now() - t) / 60000).toFixed(1)} min`);
}
main().catch((e) => { console.error(e); process.exit(1); });
