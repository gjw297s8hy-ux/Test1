#!/usr/bin/env python3
"""
Bande-son originale (générée, donc libre de droits) — 30 s, 120 BPM, 48 kHz stéréo.
Synchronisée sur les scènes : 4 s (stade), 9 s (concert), 14 s (spectacle), 18 s (billets), 24 s (marque).
Usage : python3 scripts/make_audio.py  → public/audio/soundtrack.wav
"""
import numpy as np, wave, os, subprocess
from scipy import signal

SR = 48000; DUR = 30.0; N = int(SR * DUR); BPM = 120; BEAT = 60 / BPM; BAR = 4 * BEAT
rng = np.random.default_rng(2024)
t_all = np.arange(N) / SR

def buf(): return np.zeros((N, 2))
def at(sec): return int(round(sec * SR))
def place(dst, x, sec, gain=1.0, pan=0.0):
    i = at(sec)
    if i >= N: return
    x = x[: N - i]
    if x.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        dst[i:i + len(x), 0] += x * gain * l * 1.414; dst[i:i + len(x), 1] += x * gain * r * 1.414
    else: dst[i:i + len(x)] += x * gain
def sos(kind, f, order=2):
    return signal.butter(order, np.clip(np.array(f) / (SR / 2), 1e-4, 0.999), btype=kind, output='sos')
def filt(x, kind, f, order=2): return signal.sosfilt(sos(kind, f, order), x, axis=0)
def sweep_lp(x, f0, f1, curve=2.0, block=512):
    out = np.zeros_like(x); zi = None; n = len(x)
    for s in range(0, n, block):
        k = (s / max(1, n - 1)) ** curve; f = f0 * (f1 / f0) ** k
        so = sos('lowpass', f); 
        if zi is None: zi = np.zeros((so.shape[0], 2))
        out[s:s + block], zi = signal.sosfilt(so, x[s:s + block], zi=zi)
    return out
def env(n, a=0.005, d=0.1, s=0.0, r=0.05, hold=0.0):
    a_, d_, h_, r_ = int(a * SR), int(d * SR), int(hold * SR), int(r * SR)
    e = np.concatenate([np.linspace(0, 1, max(1, a_)), np.linspace(1, s, max(1, d_)), np.full(h_, s), np.linspace(s, 0, max(1, r_))])
    return np.pad(e, (0, max(0, n - len(e))))[:n]
def saw(f, dur, detune=0.0):
    n = int(dur * SR); tt = np.arange(n) / SR
    ph = np.cumsum(np.full(n, f * (1 + detune)) / SR) + rng.random()
    return 2 * (ph % 1) - 1
def sine(f, dur, ph=0):
    n = int(dur * SR); return np.sin(2 * np.pi * np.cumsum(np.broadcast_to(f, (n,)) / SR) + ph)
def note(n): return 440 * 2 ** ((n - 69) / 12)

# ---------- instruments ----------
def kick(g=1.0):
    d = 0.5; n = int(d * SR); tt = np.arange(n) / SR
    f = 42 + 120 * np.exp(-tt * 30) + 40 * np.exp(-tt * 200)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 6.5)
    click = filt(rng.standard_normal(n), 'highpass', 2500) * np.exp(-tt * 300) * 0.3
    return np.tanh((x + click) * 1.6) * g
def clap():
    n = int(0.4 * SR); tt = np.arange(n) / SR
    x = rng.standard_normal(n); e = np.zeros(n)
    for o in (0, 0.011, 0.022): e += np.exp(-np.maximum(0, tt - o) * 60) * (tt >= o)
    e += np.exp(-tt * 14) * 0.5
    return filt(x * e, 'bandpass', [900, 6000]) * 0.5
def hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR); tt = np.arange(n) / SR
    return filt(rng.standard_normal(n), 'highpass', 8000) * np.exp(-tt * (12 if open_ else 70)) * 0.35
def sub_boom(g=1.0, d=1.6):
    n = int(d * SR); tt = np.arange(n) / SR
    f = 36 + 60 * np.exp(-tt * 9)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2.2) * g
def impact(g=1.0):
    n = int(2.5 * SR); tt = np.arange(n) / SR
    body = sub_boom(1.0, 2.5)
    crash = filt(rng.standard_normal(n), 'bandpass', [300, 9000]) * np.exp(-tt * 3.5) * 0.45
    return np.tanh((body + crash) * 1.3) * g
def riser(d, f0=300, f1=9000):
    n = int(d * SR); x = rng.standard_normal(n)
    y = sweep_lp(x, f0, f1, 1.5) * np.linspace(0.05, 1, n) ** 2
    tone = sine(np.geomspace(110, 880, n), d) * np.linspace(0, 0.25, n) ** 2
    return (y * 0.45 + tone)
def whoosh(d=0.8, f0=400, f1=6000):
    n = int(d * SR); x = rng.standard_normal(n); k = np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return sweep_lp(x, f0, f1, 1.0) * k * 0.6
def zap():
    d = 0.18; n = int(d * SR); tt = np.arange(n) / SR
    return sine(1800 * np.exp(-tt * 22) + 120, d) * np.exp(-tt * 18) * 0.35
def blip(f):
    d = 0.22; n = int(d * SR); tt = np.arange(n) / SR
    return (sine(f, d) + 0.4 * sine(f * 2, d)) * np.exp(-tt * 14) * 0.35
def bell(f, d=2.5):
    n = int(d * SR); tt = np.arange(n) / SR
    return sum(sine(f * m, d) * np.exp(-tt * k) * a for m, k, a in [(1, 1.6, 1), (2.76, 3.2, 0.4), (5.4, 6, 0.2), (8.9, 9, 0.08)]) * 0.25
def pad(notes, start, dur, g=0.12, bright=1800, attack=0.6):
    x = np.zeros(int(dur * SR))
    for nn in notes:
        for dt in (-0.006, 0.0, 0.007): x += saw(note(nn), dur, dt)
    x = filt(x, 'lowpass', bright) * env(len(x), attack, 0.2, 0.85, 0.6, hold=dur - attack - 0.8)
    return x * g / len(notes)
def pluck(nn, d=0.22):
    x = saw(note(nn), d) + 0.5 * saw(note(nn + 12), d, 0.004)
    n = len(x); tt = np.arange(n) / SR
    return sweep_lp(x, 6000, 400, 0.6) * np.exp(-tt * 14) * 0.16
def bass(nn, d):
    x = sine(note(nn), d) * 0.8 + filt(saw(note(nn), d), 'lowpass', 380) * 0.45
    return x * env(len(x), 0.004, 0.08, 0.85, 0.06, hold=max(0, d - 0.2))
def crowd(d, swell=1.0):
    n = int(d * SR); x = filt(rng.standard_normal(n), 'bandpass', [250, 2800])
    am = 0.75 + 0.25 * np.sin(2 * np.pi * 0.7 * np.arange(n) / SR) + 0.1 * filt(rng.standard_normal(n), 'lowpass', 6)
    e = np.minimum(1, np.arange(n) / (0.4 * SR)) * np.minimum(1, (n - np.arange(n)) / (0.6 * SR))
    return x * am * e * 0.22 * swell

# ---------- arrangement ----------
drums, music, fx, sides = buf(), buf(), buf(), buf()
PROG = [[50, 53, 57], [46, 50, 53], [53, 57, 60], [48, 52, 55]]  # Dm Bb F C
ROOT = [38, 34, 41, 36]
chord_at = lambda sec: int(sec // BAR) % 4

# Intro 0-4 : pulsation + nappe + scintillements + montée
for b in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
    place(fx, sub_boom(0.38 if b % 1 == 0 else 0.18, 0.9), b)
place(music, pad([50, 57, 62, 65], 0.0, 4.1, g=0.08, bright=900, attack=1.5), 0.0)
for i in range(26):
    s = 0.3 + rng.random() * 3.2; place(fx, bell(note(74 + int(rng.choice([0, 3, 7, 10, 12, 15]))), 1.2) * 0.14, s, pan=rng.uniform(-0.8, 0.8))
place(fx, riser(1.6), 2.4, 0.55)

# Grille rythmique
def drum_section(a, b, half=False, hats=True, claps=True):
    s = a
    while s < b - 1e-6:
        beat_in_bar = round((s % BAR) / BEAT)
        if not half or beat_in_bar in (0, 2) and (beat_in_bar == 0 or not half): place(drums, kick(), s)
        if half and beat_in_bar == 2: place(drums, clap() * 1.1, s)
        if claps and not half and beat_in_bar in (1, 3): place(drums, clap(), s)
        if hats:
            for k in range(4): place(drums, hat(open_=(k == 2)), s + k * BEAT / 4, 0.8 if k % 2 else 0.5, pan=0.3 if k % 2 else -0.3)
        s += BEAT
drum_section(4.0, 8.0); drum_section(9.0, 13.0); drum_section(14.0, 17.0, half=True, hats=False); drum_section(18.0, 23.0)
for s in np.arange(24.5, 28.0, BEAT * 2): place(drums, kick(0.6), s)

# Basse + accords (stade / concert / billets)
def groove(a, b, stabs=True, arps=False):
    s = a
    while s < b - 1e-6:
        c = chord_at(s); r = ROOT[c]
        for k in range(4):  # basse en croches syncopées
            place(music, bass(r if k != 3 else r + 12, BEAT * 0.45), s + k * BEAT / 2 + BEAT / 2 * (k % 2 == 1) * 0)
        if stabs:
            for k in (0.5, 1.5, 2.5, 3.5):
                st = np.zeros(int(0.25 * SR))
                for nn in PROG[c]:
                    for dt in (-0.008, 0.008): st += saw(note(nn + 12), 0.25, dt)
                st = filt(st, 'lowpass', 2600) * env(len(st), 0.003, 0.18, 0.0, 0.04) * 0.06
                place(music, st, s + k * BEAT, pan=0.25 if k % 1 else -0.25)
        if arps:
            notes = [PROG[c][0] + 12, PROG[c][1] + 12, PROG[c][2] + 12, PROG[c][1] + 24]
            for k in range(8): place(music, pluck(notes[k % 4]), s + k * BEAT / 4, pan=np.sin(k) * 0.6)
        s += BEAT * 2
groove(4.0, 8.5); groove(9.0, 13.5, stabs=True, arps=True); groove(18.0, 23.5, stabs=True, arps=True)
place(music, pad([50, 53, 57, 62], 4.0, 5.0, g=0.08, bright=2200), 4.0)
place(music, pad([46, 50, 53, 58], 9.0, 5.0, g=0.08, bright=2600), 9.0)

# Stade : foule + cor
place(sides, crowd(5.0, 1.0), 4.0)
for s in (4.0, 6.0):
    horn = sum(saw(note(n), 0.9, d) for n in (50, 57) for d in (-0.004, 0.004))
    place(music, filt(horn, 'lowpass', 1500) * env(int(0.9 * SR), 0.06, 0.3, 0.6, 0.3, 0.3) * 0.07, s)
# Concert : zaps lasers + clameur
for s in np.arange(10.0, 13.0, BEAT * 2): place(fx, zap(), s, pan=rng.uniform(-0.6, 0.6))
place(sides, crowd(4.5, 1.3), 9.2)

# Spectacle 14-18 : cordes + timbales + rideau
strings = pad([50, 57, 62, 65, 69], 14.0, 4.2, g=0.16, bright=1600, attack=0.9)
place(music, strings, 14.0)
for s in (14.0, 16.0):
    n = int(1.4 * SR); tt = np.arange(n) / SR
    timp = sine(73 * (1 + 0.03 * np.exp(-tt * 8)), 1.4) * np.exp(-tt * 3) + filt(rng.standard_normal(n), 'lowpass', 400) * np.exp(-tt * 12) * 0.5
    place(fx, timp * 0.6, s)
place(fx, whoosh(1.4, 200, 3000), 14.25, 0.5)
for i, nn in enumerate([74, 77, 81, 86]): place(fx, bell(note(nn), 1.6) * 0.35, 15.0 + i * 0.25, pan=-0.4 + i * 0.25)

# Billets 18-24 : « prix qui diminue » (blips descendants synchronisés aux chevrons)
for k, s in enumerate((20.55, 20.95, 21.35)): place(fx, blip(note(84 - k * 5)), s)
place(fx, whoosh(0.8, 500, 7000), 18.1, 0.5)
place(music, pad([46, 53, 58, 62], 18.0, 6.0, g=0.07, bright=2400), 18.0)

# Montées + impacts aux raccords
for tr in (4.0, 9.0, 14.0, 18.0, 24.0):
    place(fx, riser(1.0 if tr != 4.0 else 0.6), tr - (1.0 if tr != 4.0 else 0.6), 0.45)
    place(fx, impact(0.9 if tr in (4.0, 24.0) else 0.7), tr)
    place(fx, whoosh(0.5, 800, 8000), tr - 0.25, 0.4)

# Marque 24-30 : carillon logo + nappe finale + bascule CTA
place(music, pad([50, 57, 62, 64, 69], 24.0, 6.0, g=0.15, bright=2000, attack=0.4), 24.0)
for i, nn in enumerate([62, 69, 74, 76, 81]): place(fx, bell(note(nn), 2.8) * 0.45, 24.35 + i * 0.12, pan=-0.5 + i * 0.25)
place(fx, whoosh(0.7, 600, 7000), 27.3, 0.45)
place(fx, bell(note(74), 2.5) * 0.5, 27.6); place(fx, bell(note(81), 2.5) * 0.35, 27.75)
place(fx, sub_boom(0.7, 2.0), 27.6)

# ---------- mixage ----------
def reverb(x, d=2.4, mix_=0.25):
    n = int(d * SR); tt = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-tt * 3.0)[:, None]
    ir = filt(ir, 'lowpass', 6000); ir /= np.sqrt((ir ** 2).sum(axis=0))
    wet = np.stack([signal.fftconvolve(x[:, c], ir[:, c])[:N] for c in range(2)], axis=1)
    return x + wet * mix_
# sidechain : la musique « respire » sur la grosse caisse
kenv = np.zeros(N)
for s in np.arange(0, 30, BEAT):
    if 4 <= s < 8.5 or 9 <= s < 13.5 or 18 <= s < 23.5:
        i = at(s); L_ = min(N - i, int(0.3 * SR)); kenv[i:i + L_] = np.maximum(kenv[i:i + L_], np.exp(-np.arange(L_) / SR * 12))
duck = 1 - 0.55 * kenv
music *= duck[:, None]; sides *= (1 - 0.3 * kenv)[:, None]
mix = drums * 0.9 + reverb(music, 2.6, 0.3) + reverb(fx, 2.2, 0.28) * 0.9 + reverb(sides, 1.5, 0.2)
mix = filt(mix, 'highpass', 28)
fade = np.ones(N); fl = int(0.5 * SR); fade[-fl:] = np.linspace(1, 0, fl) ** 1.5
mix *= fade[:, None]
mix = np.tanh(mix * 1.25) / np.tanh(1.25)
mix /= np.max(np.abs(mix)) / 0.89

os.makedirs('public/audio', exist_ok=True)
raw = 'public/audio/_raw.wav'
with wave.open(raw, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype('<i2').tobytes())
# normalisation loudness réseaux sociaux (-14 LUFS, true peak -1 dB)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-af', 'loudnorm=I=-14:TP=-1.0:LRA=11', '-ar', '48000', 'public/audio/soundtrack.wav'], check=True)
os.remove(raw)
print('OK → public/audio/soundtrack.wav')
