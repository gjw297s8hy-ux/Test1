#!/usr/bin/env python3
"""
Original, fully synthesized soundtrack for the WESTAFF PLACE spot (no samples, no third-party audio).
120 BPM, D minor (i - VI - III - VII), 48 kHz stereo, 30.000 s.

Beat-aligned edit plan (beat = 0.5 s):
  0.0  s1  darkness: sub pulses (heartbeat), gold-particle shimmer grains
  2.2      push through the ring: whoosh            3.0  IMPACT (title lands)       beat 6
  4.0  s2  stadium: half-time drums, bass, crowd bed; 6.0 ball whoosh + metallic spin
  9.0  s3  beam hit -> concert: four-on-the-floor, saw arp, sidechained bass, cheering
 14.0  s4  spotlight -> theatre: strings pad, harp plucks, timpani, curtain swoosh, portal shimmer
 18.0  s5  portal hit -> hero groove; ticket landings 19.95/20.15/20.35, TITLE IMPACT 20.0 (beat 40)
           holographic tag chime 20.5
 24.0  s6  tickets burn (crackle), particle swirl riser, FINAL IMPACT 27.0 (beat 54),
           glint chimes, sustained D chord to the end card.
"""
import json, os, sys, wave
import numpy as np
from scipy import signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'config', 'config.json')))
SR = 48000
DUR = float(CFG['timing']['duration'])
N = int(DUR * SR)
BEAT = 60.0 / CFG['timing']['bpm']
rng = np.random.default_rng(20261021)

L = np.zeros(N); R = np.zeros(N)            # dry bus
RVL = np.zeros(N); RVR = np.zeros(N)         # reverb send
KICKENV = np.zeros(N)                         # for sidechain


def t_(dur):
    return np.arange(int(dur * SR)) / SR


def add(sig, at, gain=1.0, pan=0.0, rev=0.0, bus=None):
    """Mix mono or stereo sig at time `at` (s). pan -1..1, rev = send amount."""
    i0 = int(round(at * SR))
    if i0 >= N:
        return
    if sig.ndim == 1:
        lg, rg = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        sl, sr_ = sig * lg * gain * 1.414, sig * rg * gain * 1.414
    else:
        sl, sr_ = sig[0] * gain, sig[1] * gain
    i1 = min(N, i0 + len(sl))
    s0 = max(0, -i0)
    i0c = max(0, i0)
    if i1 <= i0c:
        return
    L[i0c:i1] += sl[s0:s0 + i1 - i0c]; R[i0c:i1] += sr_[s0:s0 + i1 - i0c]
    if rev:
        RVL[i0c:i1] += sl[s0:s0 + i1 - i0c] * rev; RVR[i0c:i1] += sr_[s0:s0 + i1 - i0c] * rev


def lp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, min(fc, SR * 0.45), 'low', fs=SR, output='sos'), x)


def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, 'high', fs=SR, output='sos'), x)


def bp(x, f1, f2, order=2):
    return signal.sosfilt(signal.butter(order, [f1, min(f2, SR * 0.45)], 'band', fs=SR, output='sos'), x)


def sweep_lp(x, f_start, f_end, block=256):
    """Time-varying low-pass (exponential cutoff sweep), state carried between blocks."""
    out = np.zeros_like(x)
    nb = int(np.ceil(len(x) / block))
    zi = None
    for b in range(nb):
        fc = f_start * (f_end / f_start) ** (b / max(1, nb - 1))
        sos = signal.butter(2, min(fc, SR * 0.45), 'low', fs=SR, output='sos')
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        seg = x[b * block:(b + 1) * block]
        y, zi = signal.sosfilt(sos, seg, zi=zi)
        out[b * block:b * block + len(seg)] = y
    return out


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def pink(dur):
    w = rng.standard_normal(int(dur * SR))
    f = np.fft.rfft(w)
    k = np.arange(len(f)); k[0] = 1
    return np.fft.irfft(f / np.sqrt(k), len(w)) * 8


def env_ad(n, a, d, curve=4.0):
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-6), np.exp(-(t - a) * curve / max(d, 1e-6)))
    return e


def additive(freq, dur, harmonics=12, rolloff=1.0, detune=0.0, phase=0.0):
    """Band-limited saw-like tone (sum of harmonics) with optional slow detune."""
    t = t_(dur)
    out = np.zeros_like(t)
    for h in range(1, harmonics + 1):
        f = freq * h * (1 + detune)
        if f > SR * 0.45:
            break
        out += np.sin(2 * np.pi * f * t + phase * h) / h ** rolloff
    return out


NOTE = lambda n: 440.0 * 2 ** ((n - 69) / 12)
D2, F2, A2, C2, BB1, D3 = 38, 41, 45, 36, 34, 50
PROG = [  # (bass midi, chord midis) per 2 s bar
    (38, [62, 65, 69]),      # Dm
    (34, [58, 62, 65]),      # Bb
    (41, [60, 65, 69]),      # F
    (36, [60, 64, 67]),      # C
]


def bar_at(t):
    return PROG[int(t // (4 * BEAT)) % 4]


# ---------------------------------------------------------------- instruments
def kick(gain=1.0, at=0.0, big=False):
    d = 0.55 if big else 0.35
    t = t_(d)
    f = 45 + 110 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t * (6 if big else 9))
    s += lp(noise(d), 4000) * np.exp(-t * 160) * 0.35
    s = np.tanh(s * 1.6)
    add(s, at, gain)
    i0 = int(at * SR)
    e = np.exp(-t * 7)
    KICKENV[i0:i0 + len(e)] = np.maximum(KICKENV[i0:i0 + len(e)], e[:max(0, min(len(e), N - i0))])


def clap(at, gain=0.5):
    d = 0.4
    n = bp(noise(d), 900, 5000)
    t = t_(d)
    e = np.zeros_like(t)
    for o in (0, 0.011, 0.022, 0.034):
        e += np.where(t >= o, np.exp(-(t - o) * 60), 0) * 0.6
    e += np.where(t >= 0.034, np.exp(-(t - 0.034) * 14), 0)
    add(n * e, at, gain, pan=0.0, rev=0.5)


def hat(at, gain=0.12, open_=False, pan=0.15):
    d = 0.25 if open_ else 0.06
    s = hp(noise(d), 7000) * np.exp(-t_(d) * (12 if open_ else 70))
    add(s, at, gain, pan=pan, rev=0.05)


def tom(at, freq=80, gain=0.6):
    d = 1.2
    t = t_(d)
    f = freq * (1 + 0.5 * np.exp(-t * 20))
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2) + lp(noise(d), 800) * np.exp(-t * 18) * 0.3
    add(s, at, gain, rev=0.6)


def bass(at, midi, dur, gain=0.35):
    s = additive(NOTE(midi), dur, harmonics=10, rolloff=1.3)
    s = lp(s, 600) * env_ad(len(s), 0.005, dur, 2.5)
    s += np.sin(2 * np.pi * NOTE(midi) * t_(dur)) * env_ad(len(s), 0.005, dur, 2.0) * 0.8
    add(np.tanh(s * 1.3), at, gain)


def pad(at, midis, dur, gain=0.12, cutoff=1800, attack=0.6, rev=0.6):
    out = np.zeros((2, int(dur * SR)))
    for i, m in enumerate(midis):
        for k, det in enumerate((-0.004, 0.0, 0.0045)):
            s = additive(NOTE(m), dur, harmonics=16, rolloff=1.0, detune=det, phase=rng.uniform(0, 6))
            pan = (k - 1) * 0.6
            out[0] += s * np.cos((pan + 1) * np.pi / 4); out[1] += s * np.sin((pan + 1) * np.pi / 4)
    n = out.shape[1]
    e = np.minimum(1, np.arange(n) / (attack * SR)) * np.minimum(1, (n - np.arange(n)) / (0.4 * SR))
    out = np.stack([lp(out[0], cutoff), lp(out[1], cutoff)]) * e * gain / len(midis)
    add(out, at, 1.0, rev=rev)


def arp(at, dur, gain=0.07):
    step = BEAT / 4
    t = at
    i = 0
    while t < at + dur - 1e-6:
        _, ch = bar_at(t)
        m = ch[i % 3] + (12 if (i // 3) % 2 else 0)
        s = additive(NOTE(m), step * 1.6, harmonics=14, rolloff=1.0)
        s = lp(s, 2600 + 1400 * np.sin(t * 1.3)) * env_ad(len(s), 0.003, step * 1.4, 3.5)
        add(s, t, gain, pan=0.4 * np.sin(i * 0.9), rev=0.25)
        t += step; i += 1


def pluck(at, midi, gain=0.18, pan=0.0):
    """Karplus-Strong harp-ish pluck."""
    f = NOTE(midi)
    p = int(SR / f)
    n = int(2.2 * SR)
    buf = rng.uniform(-1, 1, p)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.996 * 0.5 * (buf[i % p] + buf[(i + 1) % p])
    add(lp(out, 5000), at, gain, pan=pan, rev=0.5)


def bell(at, midi, gain=0.15, pan=0.0, dur=2.5):
    t = t_(dur)
    f = NOTE(midi)
    s = np.zeros_like(t)
    for ratio, amp, dec in ((1, 1, 2.2), (2.76, 0.5, 3.5), (5.4, 0.3, 6), (8.93, 0.18, 9), (2.0, 0.3, 2.8)):
        s += np.sin(2 * np.pi * f * ratio * t) * amp * np.exp(-t * dec)
    add(s * np.minimum(1, t / 0.002), at, gain, pan=pan, rev=0.6)


def shimmer(at, dur, density, gain=0.05, lo=72, hi=100):
    """Granular sparkle: many tiny high pings (the gold particles)."""
    count = int(dur * density)
    for _ in range(count):
        tt = at + rng.uniform(0, dur)
        m = rng.uniform(lo, hi)
        d = rng.uniform(0.05, 0.25)
        s = np.sin(2 * np.pi * NOTE(m) * t_(d)) * np.exp(-t_(d) * rng.uniform(15, 40))
        add(s, tt, gain * rng.uniform(0.3, 1), pan=rng.uniform(-0.9, 0.9), rev=0.7)


def whoosh(at, dur, gain=0.35, f0=300, f1=6000, pan_from=-0.6, pan_to=0.6, reverse=False):
    n = noise(dur)
    t = t_(dur)
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    if reverse:
        e = (t / dur) ** 3
    s = sweep_lp(n, f0, f1) * e
    s = hp(s, 120)
    pans = np.linspace(pan_from, pan_to, len(s))
    st = np.stack([s * np.cos((pans + 1) * np.pi / 4), s * np.sin((pans + 1) * np.pi / 4)]) * 1.414
    add(st, at, gain, rev=0.3)


def riser(at, dur, gain=0.25, f0=200, f1=1600):
    t = t_(dur)
    f = f0 * (f1 / f0) ** (t / dur)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    s = (tone * 0.25 + sweep_lp(noise(dur), 400, 9000) * 0.6) * (t / dur) ** 2
    add(s, at, gain, rev=0.4)


def impact(at, gain=1.0, size=1.0):
    """Cinematic hit: sub drop + noise body + metallic ring partials."""
    d = 3.5 * size
    t = t_(d)
    f = 30 + 60 * np.exp(-t * 6)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6 / size)
    body = lp(noise(d), 2500) * np.exp(-t * 9)
    crack = hp(noise(d), 3000) * np.exp(-t * 40) * 0.6
    metal = np.zeros_like(t)
    for ratio, amp in ((1.0, 1), (2.41, 0.6), (3.87, 0.4), (5.2, 0.25), (7.1, 0.15)):
        metal += np.sin(2 * np.pi * 146.8 * ratio * t) * amp * np.exp(-t * (1.4 + ratio * 0.5))
    s = np.tanh(sub * 1.4) * 0.9 + body * 0.5 + crack + metal * 0.12
    add(s, at, gain, rev=0.55)
    kick(0.6 * gain, at, big=True)


def crowd(at, dur, gain=0.1, roar=None):
    p = pink(dur)
    b = bp(p, 280, 2600)
    t = t_(dur)
    mod = 0.7 + 0.3 * lp(rng.standard_normal(len(t)), 3) * 30
    mod = np.clip(mod, 0.3, 1.4)
    if roar:
        for (rt, rd, ra) in roar:
            mod += ra * np.exp(-((t - rt) / rd) ** 2)
    s = b * mod * np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.5)
    sl = s; sr_ = np.roll(bp(pink(dur), 280, 2600) * mod * np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.5), 0)
    add(np.stack([sl, sr_]), at, gain, rev=0.2)
    # scattered claps / whistles in the crowd
    for _ in range(int(dur * 25)):
        tt = at + rng.uniform(0, dur)
        cl = bp(noise(0.03), 1200, 5000) * np.exp(-t_(0.03) * 120)
        add(cl, tt, gain * 0.25 * rng.uniform(0.2, 1), pan=rng.uniform(-1, 1), rev=0.3)


def crackle(at, dur, gain=0.2):
    for _ in range(int(dur * 160)):
        tt = at + rng.uniform(0, dur) ** 1.2
        d = rng.uniform(0.002, 0.012)
        s = hp(noise(d), 2500) * np.exp(-t_(d) * 400)
        add(s, tt, gain * rng.uniform(0.2, 1), pan=rng.uniform(-0.8, 0.8), rev=0.2)


# ---------------------------------------------------------------- arrangement
# S1 - awakening (0-4)
for k, tt in enumerate((0.05, 1.0, 2.0)):
    d = 0.9
    tsub = t_(d)
    hb = np.sin(2 * np.pi * (38 + 25 * np.exp(-tsub * 18)) * tsub) * np.exp(-tsub * 5)
    add(hb, tt, 0.5 + 0.08 * k)
drone = np.sin(2 * np.pi * NOTE(26) * t_(4.0)) * np.minimum(1, t_(4.0) / 1.0) * np.exp(-np.maximum(0, t_(4.0) - 3.2) * 4)
add(drone, 0.0, 0.1)
shimmer(0.2, 1.8, 60, gain=0.04)
shimmer(1.4, 0.8, 120, gain=0.05)
riser(1.0, 1.3, 0.22)
whoosh(1.95, 0.75, gain=0.5, f0=200, f1=9000, pan_from=0.0, pan_to=0.0)
shimmer(2.2, 0.8, 50, gain=0.05, lo=84, hi=104)
impact(3.0, 0.95, 1.0)
pad(3.0, [62, 65, 69], 1.3, gain=0.1, cutoff=1400, attack=0.05)
whoosh(3.55, 0.7, gain=0.4, f0=300, f1=7000, reverse=True)

# S2 - football (4-9): half-time drums, bass, crowd
crowd(3.9, 5.4, gain=0.09, roar=[(2.6, 0.8, 0.9), (4.2, 0.6, 0.5)])
for b in range(10):  # 5 s = 10 beats
    tt = 4.0 + b * BEAT
    if b % 4 in (0,) or b % 8 == 3:
        kick(0.9, tt)
    if b % 4 == 2:
        clap(tt, 0.5)
    hat(tt, 0.08); hat(tt + BEAT / 2, 0.05)
for bar in range(3):
    tt = 4.0 + bar * 4 * BEAT
    root, ch = bar_at(tt)
    for e in range(8):
        bass(tt + e * BEAT / 2, root, BEAT / 2 * 0.9, gain=0.22)
    pad(tt, ch, 4 * BEAT, gain=0.08, cutoff=1200)
whoosh(5.95, 0.6, gain=0.45, f0=500, f1=8000, pan_from=0.8, pan_to=-0.1)
spin = np.sin(2 * np.pi * np.cumsum(900 + 400 * np.sin(np.linspace(0, 50, int(1.0 * SR)))) / SR) * np.exp(-t_(1.0) * 3) * 0.3
add(lp(spin, 4000), 6.05, 0.25, pan=0.3, rev=0.3)
add(np.sin(2 * np.pi * 1760 * t_(0.8)) * np.exp(-t_(0.8) * 6), 6.35, 0.06, rev=0.6)  # title shimmer
riser(8.0, 1.0, 0.25, 300, 3000)

# S3 - concert (9-14)
impact(9.0, 0.7, 0.7)
whoosh(8.7, 0.6, gain=0.3, reverse=True)
crowd(9.0, 5.2, gain=0.12, roar=[(0.3, 0.6, 1.0), (2.0, 1.2, 0.6)])
for b in range(10):
    tt = 9.0 + b * BEAT
    kick(1.0, tt)
    if b % 2 == 1:
        clap(tt, 0.45)
    for s16 in range(4):
        hat(tt + s16 * BEAT / 4, 0.05 if s16 % 2 else 0.07, open_=(s16 == 2), pan=0.25)
for bar in range(3):
    tt = 9.0 + bar * 4 * BEAT
    root, ch = bar_at(tt)
    for e in range(8):
        if tt + e * BEAT / 2 < 13.6:
            bass(tt + e * BEAT / 2, root, BEAT / 2 * 0.85, gain=0.24)
    pad(tt, [c + 12 for c in ch], min(4 * BEAT, 13.7 - tt), gain=0.06, cutoff=3000, attack=0.1)
arp(9.0, 4.6, gain=0.06)
for tz in (10.0, 11.0, 12.0, 13.0):  # laser zaps on the bar
    d = 0.25
    z = np.sin(2 * np.pi * np.cumsum(np.linspace(3000, 400, int(d * SR))) / SR) * np.exp(-t_(d) * 12)
    add(z, tz, 0.05, pan=rng.uniform(-0.6, 0.6), rev=0.4)
whoosh(13.3, 0.9, gain=0.4, f0=6000, f1=300)

# S4 - theatre (14-18)
tom(14.0, 70, 0.6); tom(16.0, 65, 0.5); tom(17.0, 70, 0.4); tom(17.5, 75, 0.45)
pad(13.9, [50, 57, 62, 65], 4.2, gain=0.16, cutoff=1600, attack=0.8, rev=0.8)   # strings-like
for i, (tt, m) in enumerate([(14.5, 62), (14.75, 65), (15.0, 69), (15.25, 74), (15.5, 77), (15.75, 74), (16.0, 69), (16.25, 72), (16.5, 76)]):
    pluck(tt, m, 0.12, pan=-0.5 + i * 0.12)
whoosh(15.7, 1.6, gain=0.35, f0=200, f1=2500, pan_from=-0.8, pan_to=0.8)
shimmer(16.0, 1.4, 70, gain=0.045, lo=86, hi=104)
riser(16.9, 1.1, 0.25, 250, 2400)

# S5 - tickets (18-24)
impact(18.0, 0.75, 0.8)
for b in range(11):
    tt = 18.5 + b * BEAT
    if b % 4 == 0 or b % 8 == 6:
        kick(0.9, tt)
    if b % 4 == 2:
        clap(tt, 0.45)
    hat(tt, 0.06); hat(tt + BEAT / 2, 0.04)
for tt, p in ((18.6, -0.6), (18.85, 0.0), (19.1, 0.6)):
    whoosh(tt, 0.7, gain=0.3, f0=400, f1=7000, pan_from=p * 1.5, pan_to=p)
for tt, p in ((19.95, 0.0), (20.15, -0.5), (20.35, 0.5)):  # metallic ticket landings
    d = 0.6
    s = sum(np.sin(2 * np.pi * 1200 * r * t_(d)) * a * np.exp(-t_(d) * (8 + r * 4)) for r, a in ((1, 1), (2.7, 0.5), (4.1, 0.3)))
    s = s + hp(noise(d), 3000) * np.exp(-t_(d) * 90) * 0.5
    add(s, tt, 0.12, pan=p, rev=0.4)
impact(20.0, 0.9, 1.0)
for bar in range(2):
    tt = 20.0 + bar * 4 * BEAT
    root, ch = bar_at(tt)
    for e in range(8):
        bass(tt + e * BEAT / 2, root, BEAT / 2 * 0.85, gain=0.22)
    pad(tt, ch + [ch[0] + 12], 4 * BEAT, gain=0.09, cutoff=2400, attack=0.05)
bell(20.5, 86, 0.12, pan=0.4); bell(20.75, 93, 0.09, pan=0.5)          # holographic tag chime
for k in range(4):
    add(np.sin(2 * np.pi * 2400 * t_(0.04)) * np.exp(-t_(0.04) * 80), 20.9 + k * 0.25, 0.04, pan=0.4)
whoosh(20.9, 0.5, gain=0.2, f0=800, f1=6000)
pad(22.0, [62, 65, 69, 74], 2.0, gain=0.08, cutoff=2000)
whoosh(23.2, 0.9, gain=0.35, reverse=True, f0=500, f1=9000)

# S6 - finale (24-30)
crackle(24.1, 1.3, gain=0.05)
shimmer(24.2, 2.4, 140, gain=0.04, lo=80, hi=104)
whoosh(24.4, 2.5, gain=0.35, f0=150, f1=7000, pan_from=-0.7, pan_to=0.7)
riser(25.4, 1.6, 0.3, 150, 2200)
pad(24.0, [50, 57, 62], 3.0, gain=0.1, cutoff=900, attack=1.0)
impact(27.0, 1.0, 1.3)
pad(27.0, [38, 50, 57, 62, 65, 69, 76], 3.0, gain=0.22, cutoff=2800, attack=0.02, rev=0.9)  # final Dm(add9) stack
bell(27.15, 86, 0.1, pan=-0.4); bell(27.6, 93, 0.08, pan=0.4); bell(28.6, 98, 0.06, pan=0.1)
whoosh(27.3, 0.5, gain=0.15, f0=1000, f1=6000)
whoosh(27.85, 0.5, gain=0.12, f0=1000, f1=6000)

# ---------------------------------------------------------------- mix & master
# sidechain: duck pads/bass bed during the concert section via kick envelope (applied to whole mix lightly)
duck = 1 - 0.25 * lp(KICKENV, 40)
sec = (np.arange(N) / SR >= 9.0) & (np.arange(N) / SR < 14.0)
g = np.where(sec, duck, 1.0)
L *= g; R *= g

# reverb: synthesized stereo hall IR (2.4 s RT60), FFT convolution
ir_len = int(2.6 * SR)
tt = np.arange(ir_len) / SR
decay = np.exp(-6.9 * tt / 2.4)
irL = lp(rng.standard_normal(ir_len), 6000) * decay
irR = lp(rng.standard_normal(ir_len), 6000) * decay
irL[: int(0.012 * SR)] = 0; irR[: int(0.017 * SR)] = 0
irL /= np.sqrt(np.sum(irL ** 2)); irR /= np.sqrt(np.sum(irR ** 2))
wetL = signal.fftconvolve(RVL, irL)[:N] * 0.5
wetR = signal.fftconvolve(RVR, irR)[:N] * 0.5
L += wetL; R += wetR

# master: HP at 25 Hz, gentle glue compression, soft clip, peak normalise to -1 dBFS
L = hp(L, 32); R = hp(R, 32)
mix = np.stack([L, R])
peak_env = lp(np.max(np.abs(mix), axis=0), 8)
thr = np.percentile(peak_env, 99.0) * 0.6
gain = np.where(peak_env > thr, (thr + (peak_env - thr) / 3.0) / np.maximum(peak_env, 1e-9), 1.0)
mix *= lp(gain, 10)
mix = np.tanh(mix / np.max(np.abs(mix)) * 2.6) / np.tanh(2.6)
# fade: 5 ms in, 300 ms out
fade = np.ones(N); fade[: int(0.005 * SR)] = np.linspace(0, 1, int(0.005 * SR)); fade[-int(0.3 * SR):] = np.linspace(1, 0, int(0.3 * SR))
mix *= fade
mix *= 10 ** (-1.0 / 20) / np.max(np.abs(mix))
# true-peak safety: measure inter-sample peaks at 4x and scale to -1.0 dBTP
tp = np.max(np.abs(signal.resample_poly(mix, 4, 1, axis=1)))
mix *= 10 ** (-1.0 / 20) / tp

out = os.path.join(ROOT, CFG['output']['audio'])
os.makedirs(os.path.dirname(out), exist_ok=True)
pcm = (np.clip(mix.T, -1, 1) * 32767).astype('<i2')
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('wrote', out, f'{N / SR:.3f}s', 'peak dBFS', round(20 * np.log10(np.max(np.abs(mix))), 2))
