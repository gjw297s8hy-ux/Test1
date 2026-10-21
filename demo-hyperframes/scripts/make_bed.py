"""Placeholder music bed: 120 BPM drums + bass + stabs, built to the film's sections.
Replace assets/bed.wav with a real track whenever you have one (same name, 30 s)."""
import numpy as np, wave, sys

SR = 48000
DUR = 30.0
BPM = 120
BEAT = 60 / BPM
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(3)

def add(sig, t, gain=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N: return
    s = sig[: N - i] * gain
    L[i:i + len(s)] += s * (1 - max(0, pan))
    R[i:i + len(s)] += s * (1 + min(0, pan))

def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))

def kick():
    n = int(0.42 * SR); t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * env_exp(n, 0.16)
    click = rng.normal(0, 1, n) * env_exp(n, 0.002) * 0.35
    return np.tanh((s + click) * 1.8) * 0.9

def hat(open_=False):
    n = int((0.22 if open_ else 0.05) * SR)
    x = rng.normal(0, 1, n)
    x = np.diff(np.concatenate([[0], x]))  # crude highpass
    x = np.diff(np.concatenate([[0], x]))
    return x * env_exp(n, 0.06 if open_ else 0.012) * 0.10

def clap():
    n = int(0.3 * SR)
    x = rng.normal(0, 1, n)
    x = np.diff(np.concatenate([[0], x]))
    e = np.zeros(n)
    for d in (0, 0.009, 0.018):
        i = int(d * SR); e[i:] += env_exp(n - i, 0.008 if d < 0.018 else 0.09)
    body = np.sin(2 * np.pi * 190 * np.arange(n) / SR) * env_exp(n, 0.04) * 0.4
    return (x * e * 0.33 + body * 0.3)

def lp(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc; y[i] = acc
    return y

def saw(freq, dur, det=0.0):
    t = np.arange(int(dur * SR)) / SR
    s = 2 * ((t * freq * (1 + det)) % 1) - 1
    return s

def bass_note(freq, dur):
    s = saw(freq, dur) + 0.5 * np.sin(2 * np.pi * freq * np.arange(int(dur * SR)) / SR)
    s = lp(s, 900)
    n = len(s)
    a = np.minimum(1, np.arange(n) / (0.004 * SR))
    return np.tanh(s * a * env_exp(n, 0.22) * 1.6) * 0.30

def stab(freqs, dur):
    s = sum(saw(f, dur, d) for f in freqs for d in (-0.004, 0.004))
    s = lp(s, 2400)
    n = len(s)
    return s * env_exp(n, 0.12) * 0.045

def pad(freqs, dur):
    t = np.arange(int(dur * SR)) / SR
    s = sum(saw(f, dur, d) for f in freqs for d in (-0.006, 0.0, 0.006))
    s = lp(s, 1100)
    n = len(s)
    a = np.minimum(1, t / 0.6) * np.minimum(1, (dur - t) / 0.4)
    return s * a * 0.035

# chords per bar: Am F C G (A1=55)
ROOT = [55.0, 43.65, 65.41, 49.0]
CHORD = [[220, 261.6, 329.6], [174.6, 220, 261.6], [196, 261.6, 329.6], [196, 246.9, 293.7]]

def groove(t0, t1, full=True):
    b = 0
    t = t0
    while t < t1 - 1e-6:
        bar = int(round((t - 4.0) / (4 * BEAT))) % 4
        beat_in_bar = b % 4
        add(kick(), t, 0.95)
        if beat_in_bar in (1, 3):
            add(clap(), t, 0.9)
        add(hat(), t + BEAT / 2, 1.0, 0.3)
        if full:
            add(hat(), t + BEAT / 4, 0.45, -0.3)
            add(hat(), t + 3 * BEAT / 4, 0.45, -0.3)
        # bass: root on the off-beats, octave on the last 16th
        r = ROOT[bar]
        add(bass_note(r, BEAT / 2 - 0.02), t + BEAT / 2)
        add(bass_note(r * 2, BEAT / 4 - 0.02), t + 3 * BEAT / 4, 0.7)
        if beat_in_bar == 0:
            add(stab(CHORD[bar], 0.5), t, 1.0, 0.15)
        b += 1
        t = t0 + b * BEAT

# 0-4 s: no bed (the words slam alone)
# 4-24 s: the groove
groove(4.0, 24.0)
# 24-26.5: drums drop, pad holds under « une phrase. un film. »
add(pad([220, 261.6, 329.6], 2.6), 24.0, 1.0)
add(bass_note(55, 2.4) , 24.0, 0.8)
# 26.5-30: back in for the lockup
groove(26.5, 30.0)

mix = np.stack([L, R], 1)
# fade out over the last 1.6 s
fo = int(1.6 * SR)
mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
mix = np.tanh(mix * 1.1)
mix /= np.abs(mix).max() / 0.89
out = (mix * 32767).astype(np.int16)
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(out.tobytes())
print("ok", sys.argv[1])
