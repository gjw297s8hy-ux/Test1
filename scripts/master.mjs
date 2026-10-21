#!/usr/bin/env node
// Final delivery: mux the rendered master video with the 48 kHz mix into a platform-safe H.264/AAC MP4,
// then verify it (dimensions, fps, duration, streams, loudness) and write per-scene contact sheets.
//   node scripts/master.mjs --video renders/master_video.mov [--out renders/x.mp4] [--silent]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => { if (v.startsWith('--')) a.push([v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]); return a; }, []));
const cfg = JSON.parse(fs.readFileSync(path.join(root, 'config/config.json'), 'utf8'));
const video = path.join(root, args.video || 'renders/master_video.mov');
const out = path.join(root, args.out || cfg.output.master);
const audio = path.join(root, cfg.output.audio);
const ff = (a) => execFileSync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', ...a], { stdio: 'inherit' });

const enc = ['-c:v', 'libx264', '-preset', 'slow', '-profile:v', 'high', '-level', '5.1', '-pix_fmt', 'yuv420p', '-crf', String(args.crf || 17), '-maxrate', '24M', '-bufsize', '48M',
  '-g', '120', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-movflags', '+faststart'];
if (args.silent || !fs.existsSync(audio)) {
  ff(['-i', video, ...enc, '-an', out]);
} else {
  ff(['-i', video, '-i', audio, '-map', '0:v:0', '-map', '1:a:0', ...enc, '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-shortest', out]);
}
// silent alternate is always produced as well
const silentOut = out.replace(/\.mp4$/, '_silent.mp4');
ff(['-i', out, '-map', '0:v:0', '-c', 'copy', '-an', silentOut]);

const probe = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_streams', '-show_format', '-of', 'json', out]).toString());
const v = probe.streams.find((s) => s.codec_type === 'video'), a = probe.streams.find((s) => s.codec_type === 'audio');
let loud = null;
if (a) {
  const r = execFileSync('ffmpeg', ['-hide_banner', '-i', out, '-af', 'ebur128=peak=true', '-f', 'null', '-'], { stdio: ['ignore', 'pipe', 'pipe'] }).toString();
  loud = r;
}
const report = {
  file: path.relative(root, out),
  bytes: fs.statSync(out).size,
  video: { codec: v.codec_name, profile: v.profile, width: v.width, height: v.height, fps: v.r_frame_rate, frames: v.nb_frames, pix_fmt: v.pix_fmt, bit_rate: v.bit_rate },
  audio: a ? { codec: a.codec_name, sample_rate: a.sample_rate, channels: a.channels } : 'none (silent)',
  duration: probe.format.duration,
  silent_alternate: path.relative(root, silentOut),
};
console.log(JSON.stringify(report, null, 2));
fs.writeFileSync(out.replace(/\.mp4$/, '_report.json'), JSON.stringify(report, null, 2));

// contact sheets: 4 frames per scene
fs.mkdirSync(path.join(root, 'previews/final'), { recursive: true });
for (const s of cfg.timing.scenes) {
  const ts = [0.15, 0.4, 0.65, 0.9].map((k) => s.start + (s.end - s.start) * k);
  const sel = ts.map((t) => `eq(n\\,${Math.round(t * 60)})`).join('+');
  ff(['-i', out, '-vf', `select='${sel}',scale=360:640,tile=4x1:padding=6:color=0x111111`, '-frames:v', '1', path.join(root, `previews/final/${s.id}_sheet.jpg`)]);
}
console.log('contact sheets in previews/final/');
