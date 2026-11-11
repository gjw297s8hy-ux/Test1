#!/usr/bin/env python3
"""Bande-son du teaser NPNG : extrait du morceau (issu du clip fourni) + effets calés sur les plans + queue de fin."""
import numpy as np, wave, subprocess, os
from scipy import signal
SR = 48000; DUR = 15.0; N = int(SR * DUR)
rng = np.random.default_rng(7)
BEAT, B0 = 0.508, 0.396
beat = lambda k: B0 + BEAT * k
def load(p):
    with wave.open(p) as w: x = np.frombuffer(w.readframes(w.getnframes()), '<i2').reshape(-1, w.getnchannels()).astype(float) / 32768
    return x if x.shape[1] == 2 else np.repeat(x, 2, 1)
def place(dst, x, sec, g=1.0):
    i = int(sec * SR); x = x[: N - i]
    if x.ndim == 1: x = np.stack([x, x], 1)
    dst[i:i + len(x)] += x * g
def filt(x, kind, f): return signal.sosfilt(signal.butter(2, np.array(f) / (SR / 2), btype=kind, output='sos'), x, axis=0)
def whoosh(d, f0=400, f1=7000):
    n = int(d * SR); x = rng.standard_normal(n); out = np.zeros(n); zi = None
    for s in range(0, n, 512):
        f = f0 * (f1 / f0) ** (s / n); so = signal.butter(2, f / (SR / 2), output='sos')
        if zi is None: zi = np.zeros((so.shape[0], 2))
        out[s:s + 512], zi = signal.sosfilt(so, x[s:s + 512], zi=zi)
    return out * np.sin(np.pi * np.linspace(0, 1, n)) ** 2 * 0.5
def impact(g=1.0):
    n = int(1.8 * SR); tt = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(38 + 70 * np.exp(-tt * 10)) / SR) * np.exp(-tt * 2.5)
    crash = filt(rng.standard_normal(n), 'bandpass', [300, 8000]) * np.exp(-tt * 5) * 0.35
    return np.tanh((sub + crash) * 1.3) * g
def fire(d):
    n = int(d * SR); x = filt(rng.standard_normal(n), 'bandpass', [300, 3000])
    crack = np.zeros(n)
    for _ in range(int(d * 40)): i = rng.integers(0, n - 400); crack[i:i + 400] += rng.standard_normal(400) * np.exp(-np.arange(400) / 60)
    return (x * 0.15 + crack * 0.25) * np.minimum(1, np.arange(n) / (0.3 * SR))
song = load(os.path.join(os.path.dirname(__file__), '..', 'assets_src', 'npng', 'clip_audio.wav'))
mix = np.zeros((N, 2)); fx = np.zeros((N, 2))
place(mix, song, 0.0)
# queue : la fin du morceau s'étire en écho pendant le carton final
tail = song[-int(0.6 * SR):]
echo = np.zeros((int(1.6 * SR), 2))
for k in range(5): i = int(k * 0.254 * SR); seg = tail[: len(echo) - i]; echo[i:i + len(seg)] += seg * (0.55 ** (k + 1))
place(mix, filt(echo, 'lowpass', 2500), len(song) / SR)
# effets
for c in (beat(4), beat(8), beat(11), beat(22)): place(fx, whoosh(0.45), c - 0.35, 0.5)
place(fx, impact(0.8), beat(4)); place(fx, impact(0.6), beat(5)); place(fx, impact(1.0), beat(8) + 0.28); place(fx, impact(0.7), beat(22))
place(fx, fire(2.5), beat(6) - 0.3, 0.6); place(fx, fire(2.0), 0.6, 0.35)
out = mix + fx * 0.8
fade = np.ones(N); fl = int(0.6 * SR); fade[-fl:] = np.linspace(1, 0, fl); out *= fade[:, None]
out = np.tanh(out * 1.1) / np.tanh(1.1); out /= np.abs(out).max() / 0.9
os.makedirs('public/npng', exist_ok=True)
with wave.open('public/npng/_raw.wav', 'wb') as w: w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype('<i2').tobytes())
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', 'public/npng/_raw.wav', '-af', 'loudnorm=I=-14:TP=-1.0:LRA=11', '-ar', '48000', 'public/npng/soundtrack.wav'], check=True)
os.remove('public/npng/_raw.wav'); print('OK → public/npng/soundtrack.wav')
