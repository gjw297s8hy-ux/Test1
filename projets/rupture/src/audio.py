"""RUPTURE - habillage sonore original, synthetise (numpy), cale sur la timeline de sim.py.

Usage : python3 src/audio.py out.wav
Accents : impact 2.50 s, arret 7.00 s, reprise 10.00 s, revelation 14.00 s. Pulsation 120 BPM.
Les poses de blocs (sim.block_land_time) declenchent des chocs mineraux synchronises.
"""
import sys
import os
import wave
import math
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim  # noqa: E402

SR = 48000
DUR = sim.T_END
N = int(SR * DUR)
rng = np.random.RandomState(sim.SEED + 300)
T = np.arange(N) / SR


def buf():
    return np.zeros((N, 2))


def env_adsr(n, a, d, s_level, r):
    e = np.ones(n) * s_level
    ia, idd, ir = int(a * SR), int(d * SR), int(r * SR)
    if ia:
        e[:ia] = np.linspace(0, 1, ia)
    if idd:
        e[ia:ia + idd] = np.linspace(1, s_level, len(e[ia:ia + idd]))
    if ir:
        e[-ir:] *= np.linspace(1, 0, ir)
    return e


def place(dst, sig, t0, gain=1.0, pan=0.0):
    i0 = int(round(t0 * SR))
    if sig.ndim == 1:
        l = sig * math.cos((pan + 1) * math.pi / 4)
        r = sig * math.sin((pan + 1) * math.pi / 4)
        sig = np.stack([l, r], axis=1) * math.sqrt(2)
    i1 = min(N, i0 + len(sig))
    if i1 <= max(i0, 0):
        return
    s0 = max(0, -i0)
    dst[max(i0, 0):i1] += sig[s0:s0 + i1 - max(i0, 0)] * gain


def bandpass_fft(x, lo, hi, soft=0.15):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    m = 1 / (1 + np.exp(-(np.log(f + 1e-9) - math.log(lo)) / soft)) * (1 / (1 + np.exp((np.log(f + 1e-9) - math.log(hi)) / soft)))
    return np.fft.irfft(X * m, len(x))


def noise(n, seed=None):
    r = np.random.RandomState(seed) if seed is not None else rng
    return r.normal(0, 1, n)


def sat(x, drive=1.0):
    return np.tanh(x * drive) / math.tanh(drive)


# --------------------------------------------------------------------- elements


def wind():
    x = bandpass_fft(noise(N, 1), 250, 2200, 0.35)
    x /= np.abs(x).max()
    lfo = 0.55 + 0.45 * np.sin(2 * math.pi * 0.23 * T + 1.0) * np.sin(2 * math.pi * 0.071 * T)
    e = np.interp(T, [0, 0.4, 2.5, 6.0, 6.9, 7.0, 10.0, 10.3, 14.0, 17.0, 18.0], [0, 1, 1, 0.7, 0.6, 0.0, 0.0, 0.5, 0.5, 0.35, 0.0])
    y = x * lfo * e * 0.09
    st = np.stack([y, np.roll(y, 380)], axis=1)
    return st


def low_drone():
    """vibration grave qui monte jusqu'a l'impact (harmoniques pour les petits haut-parleurs)"""
    f = 41.2 + 3.0 * np.clip(T / 2.5, 0, 1)
    ph = 2 * math.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.5 * np.sin(2 * ph + 0.3) + 0.25 * np.sin(3 * ph)
    x = sat(x * 1.5, 1.8)
    e = np.clip(T / 2.5, 0, 1) ** 2.2 * (T < 2.5) + (T >= 2.5) * np.exp(-(T - 2.5) * 6)
    trem = 1 + 0.25 * np.sin(2 * math.pi * 7.5 * T) * np.clip((T - 1.4) / 1.1, 0, 1)
    y = x * e * trem * 0.16
    return np.stack([y, y], axis=1)


def metal_hit():
    """impact metallique sec : synthese modale (carte noire brossee)"""
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    base = 1730.0
    for ratio, dec, amp in [(1.0, 0.35, 1.0), (2.756, 0.22, 0.6), (5.404, 0.12, 0.45), (8.933, 0.07, 0.3),
                            (13.34, 0.04, 0.2), (0.503, 0.5, 0.35)]:
        y += amp * np.sin(2 * math.pi * base * ratio * t + rng.uniform(0, 6)) * np.exp(-t / dec)
    click = bandpass_fft(np.r_[noise(int(0.004 * SR), 7), np.zeros(n - int(0.004 * SR))], 2500, 12000, 0.3)
    y = y / np.abs(y).max() * 0.6 + click / (np.abs(click).max() + 1e-9) * 0.8
    return y


def thump(f0=95.0, f1=36.0, dur=0.6, amp=1.0, drive=2.0):
    """impulsion sourde, avec harmoniques et attaque perceptibles sur telephone"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 14)
    ph = 2 * math.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t * (4.2 / dur))
    y = sat(y * 1.2, drive)
    knock = bandpass_fft(np.r_[noise(int(0.012 * SR), 3), np.zeros(n - int(0.012 * SR))], 180, 1800, 0.4)
    y += knock / (np.abs(knock).max() + 1e-9) * 0.35 * np.exp(-t * 30)
    return y * amp


def crackles(t0, t1, rate0, rate1, lo, hi, gain, seed):
    """craquements mineraux : grains de bruit filtre, densite croissante"""
    r = np.random.RandomState(seed)
    out = np.zeros((N, 2))
    t = t0
    while t < t1:
        u = (t - t0) / (t1 - t0)
        rate = rate0 + (rate1 - rate0) * u
        t += r.exponential(1.0 / rate)
        ln = int(r.uniform(0.003, 0.03) * SR)
        g = np.exp(-np.arange(ln) / (ln * 0.25)) * r.normal(0, 1, ln)
        place(out, g * r.uniform(0.3, 1.0), t, gain, pan=r.uniform(-0.8, 0.8))
    l = bandpass_fft(out[:, 0], lo, hi, 0.3)
    rr = bandpass_fft(out[:, 1], lo, hi, 0.3)
    return np.stack([l, rr], axis=1)


def rumble(t0, t1, gain):
    x = bandpass_fft(noise(N, 11), 30, 220, 0.3)
    x /= np.abs(x).max()
    e = np.clip((T - t0) / (t1 - t0), 0, 1) ** 1.5 * (T < t1) + (T >= t1) * np.exp(-(T - t1) * 8)
    e *= (T >= t0)
    y = sat(x * e * 2.0, 1.5) * gain
    return np.stack([y, np.roll(y, 120)], axis=1)


def cloth_whoosh(t_peak, dur, gain, lo=90, hi=900, seed=21, reverse=False):
    """souffle de tissu lourd : bruit grave module, enveloppe en cloche"""
    n = int(dur * SR)
    x = bandpass_fft(noise(n, seed), lo, hi, 0.35)
    x /= np.abs(x).max()
    t = np.linspace(0, 1, n)
    e = np.sin(np.pi * t) ** 2.2 if not reverse else t ** 3.0 * (t < 1)
    flap = 1 + 0.35 * np.sin(2 * math.pi * 6.5 * t * dur) * np.sin(np.pi * t)
    y = x * e * flap * gain
    return y, (t_peak - dur / 2) if not reverse else (t_peak - dur)


def riser(t0, t1, gain):
    """montee musicale : accord de dents de scie filtre qui s'ouvre"""
    n = int((t1 - t0) * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for fr in (73.42, 110.0, 146.83, 220.0):
        f = fr * (1 + 0.06 * (t / t[-1]) ** 2)
        ph = 2 * math.pi * np.cumsum(f) / SR
        saw = 2 * ((ph / (2 * math.pi)) % 1.0) - 1
        y += saw
    u = t / t[-1]
    # filtre passe-bas qui s'ouvre (approx. par melange de versions filtrees)
    lp1 = bandpass_fft(y, 40, 300, 0.4)
    lp2 = bandpass_fft(y, 40, 2400, 0.4)
    y = lp1 * (1 - u) + lp2 * u
    y = y / np.abs(y).max() * (u ** 1.8) * gain
    return y


def pulse_track(beats, gain, seed=5):
    out = np.zeros((N, 2))
    for i, b in enumerate(beats):
        k = thump(120.0, 48.0, 0.35, 1.0, 2.5)
        click = bandpass_fft(np.r_[noise(int(0.003 * SR), seed + i), np.zeros(len(k) - int(0.003 * SR))], 1800, 6000, 0.3)
        k = k + click / (np.abs(click).max() + 1e-9) * 0.25
        place(out, k, b, gain)
    return out


def stone_clack(seed, amp=1.0):
    r = np.random.RandomState(seed)
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for f, d in ((r.uniform(150, 230), 0.09), (r.uniform(420, 620), 0.05), (r.uniform(900, 1400), 0.025)):
        y += np.sin(2 * math.pi * f * t) * np.exp(-t / d)
    nz = bandpass_fft(r.normal(0, 1, n) * np.exp(-t / 0.02), 600, 5000, 0.3)
    y = y / np.abs(y).max() + nz / (np.abs(nz).max() + 1e-9) * 0.7
    grit = bandpass_fft(r.normal(0, 1, n) * np.exp(-t / 0.18) * (t > 0.02), 1500, 7000, 0.3)
    y += grit / (np.abs(grit).max() + 1e-9) * 0.15
    return y * amp


def inhale(t_end, dur, gain, seed):
    n = int(dur * SR)
    x = bandpass_fft(noise(n, seed), 500, 6000, 0.3)
    x /= np.abs(x).max()
    t = np.linspace(0, 1, n)
    e = t ** 3.2
    return x * e * gain, t_end - dur


def thin_resonance(t0, t1, gain):
    n = int((t1 - t0) * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * math.pi * 1318.5 * t) + 0.6 * np.sin(2 * math.pi * 1321.0 * t + 1)
         + 0.35 * np.sin(2 * math.pi * 1975.5 * t) + 0.5 * np.sin(2 * math.pi * 659.25 * t + 0.4))
    e = np.clip(t / 0.25, 0, 1) * np.clip((t[-1] - t) / 0.35, 0, 1)
    sub = np.sin(2 * math.pi * 55 * t) * 0.25
    return (y * 0.25 + sub) * e * gain


def chord_final(t0, gain):
    """accord grave final, longue queue"""
    n = N - int(t0 * SR)
    t = np.arange(n) / SR
    y = np.zeros(n)
    for fr, a in ((36.71, 1.0), (73.42, 0.9), (110.0, 0.55), (146.83, 0.45), (174.61, 0.35), (220.0, 0.3), (293.66, 0.15)):
        for det in (-0.12, 0.12):
            ph = 2 * math.pi * fr * (1 + det / 100) * t
            y += a * (np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph))
    y /= np.abs(y).max()
    e = np.exp(-t / 1.25) * np.clip(t / 0.01, 0, 1)
    shimmer = bandpass_fft(noise(n, 77), 3000, 9000, 0.4) * np.exp(-t / 0.5)
    shimmer /= np.abs(shimmer).max() + 1e-9
    return (y * e + shimmer * 0.15) * gain


def amber_tone(f, gain):
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    y = (np.sin(2 * math.pi * f * t) + 0.3 * np.sin(4 * math.pi * f * t)) * np.exp(-t / 0.45) * np.clip(t / 0.01, 0, 1)
    return y * gain


def reverb(x, seconds=2.6, mix=0.25, seed=99):
    r = np.random.RandomState(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    out = np.zeros_like(x)
    for ch in range(2):
        ir = r.normal(0, 1, n) * np.exp(-t / (seconds / 6.9)) * (t > 0.012)
        ir = bandpass_fft(ir, 120, 7000, 0.5)
        ir /= np.sqrt(np.sum(ir ** 2))
        L = len(x) + n
        y = np.fft.irfft(np.fft.rfft(x[:, ch], L) * np.fft.rfft(ir, L), L)[:len(x)]
        out[:, ch] = y
    return x * (1 - mix) + out * mix * 2.2


# --------------------------------------------------------------------- montage


def mix():
    master = buf()
    master += wind()
    master += low_drone()
    # 2.50 : impact
    place(master, metal_hit(), sim.T_IMPACT, 0.55, pan=-0.05)
    place(master, thump(110, 34, 0.9, 1.0, 2.2), sim.T_IMPACT + 0.03, 0.55)
    # 2.6 - 6 : arrachement mineral, souffle du tissu, montee
    master += crackles(2.62, 6.0, 25, 220, 900, 7000, 0.18, 31)
    master += crackles(2.8, 6.0, 6, 40, 150, 1200, 0.25, 32)
    master += rumble(2.6, 6.0, 0.22)
    for tp, dur, g in ((4.3, 1.4, 0.22), (5.35, 1.3, 0.3), (5.95, 0.6, 0.38)):
        y, st = cloth_whoosh(tp, dur, g, seed=int(tp * 10))
        place(master, y, st, 1.0, pan=0.2)
    place(master, riser(3.0, 7.0, 0.20), 3.0, 1.0)
    beats_a = [2.5 + 0.5 * i for i in range(1, 9)]          # 3.0 ... 6.5
    master += pulse_track(beats_a, 0.30)
    # 6 - 7 : blocs qui montent (chocs mineraux epars)
    master += crackles(6.0, 6.95, 30, 10, 400, 5000, 0.16, 33)
    y, st = cloth_whoosh(6.35, 0.9, 0.25, seed=63)
    place(master, y, st, 1.0, pan=-0.3)
    # 7.00 : aspiration puis quasi-silence
    y, st = inhale(7.0, 0.45, 0.22, 70)
    place(master, y, st, 1.0)
    cut = np.ones(N)
    i7 = int(7.0 * SR)
    i10 = int(10.0 * SR)
    fade = int(0.012 * SR)
    cut[i7:i7 + fade] = np.linspace(1, 0, fade)
    cut[i7 + fade:i10] = 0.0
    master *= cut[:, None]
    # 9.6 - 10 : souffle inverse, 10.00 : reprise
    y, st = cloth_whoosh(10.0, 0.62, 0.32, 120, 2400, seed=91, reverse=True)
    place(master, y, st, 1.0)
    place(master, thump(100, 40, 0.6, 1.0, 2.2), 10.0, 0.5)
    place(master, stone_clack(400, 1.0), 10.0, 0.35)
    # 10 - 14 : reconstruction (pulsation reprise + poses de blocs synchronisees)
    beats_b = [10.0 + 0.5 * i for i in range(1, 8)]         # 10.5 ... 13.5
    master += pulse_track(beats_b, 0.26, seed=50)
    for i, b in enumerate(sim.block_layout()):
        tl = sim.block_land_time(b)
        if tl < 14.2:
            pan = float(np.clip(b["F"][0] / 11.0, -0.9, 0.9))
            place(master, stone_clack(500 + i, 1.0), tl, 0.13 + 0.05 * (b["cell"]["tier"] == 0), pan=pan)
    for tp, dur, g in ((11.0, 1.4, 0.2), (12.3, 1.5, 0.24), (13.4, 1.2, 0.2)):
        y, st = cloth_whoosh(tp, dur, g, seed=int(tp * 10) + 1)
        place(master, y, st, 1.0, pan=-0.25)
    place(master, riser(11.0, 14.0, 0.17), 11.0, 1.0)
    for k, (tk, f) in enumerate(zip((13.25, 13.5, 13.75), (440.0, 523.25, 659.25))):
        place(master, amber_tone(f, 0.05), tk, 1.0, pan=(k - 1) * 0.35)
    # 14.00 : impact musical et accord grave
    place(master, thump(90, 30, 1.6, 1.0, 2.0), 14.0, 0.62)
    place(master, stone_clack(900, 1.2), 14.0, 0.3)
    place(master, chord_final(14.0, 0.42), 14.0, 1.0)
    master = reverb(master, 2.8, 0.22)
    # arret du temps : la queue de reverb est coupee aussi, puis resonance tenue
    gate = np.ones(N)
    a, b, c = int(7.0 * SR), int(7.02 * SR), int(9.35 * SR)
    gate[a:b] = np.linspace(1, 0.03, b - a)
    gate[b:c] = 0.03
    gate[c:int(9.6 * SR)] = np.linspace(0.03, 1, int(9.6 * SR) - c)
    master *= gate[:, None]
    res = np.zeros((N, 2))
    place(res, thin_resonance(7.04, 9.95, 0.028), 7.04, 1.0)
    master += reverb(res, 1.5, 0.3, seed=7)
    # fin propre : extinction douce sur les 1.2 dernieres secondes
    tail = np.clip((DUR - T) / 1.2, 0, 1) ** 1.5
    master *= tail[:, None]
    # marge avant saturation : limiteur doux puis normalisation -1.5 dBFS crete
    master = np.tanh(master * 1.1) / 1.1
    peak = np.abs(master).max()
    master *= (10 ** (-1.5 / 20)) / peak
    return master


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "rupture_audio.wav"
    m = mix()
    write_wav(out, m)
    rms = np.sqrt(np.mean(m ** 2))
    print(f"ecrit {out} : {len(m) / SR:.3f} s, crete {20 * np.log10(np.abs(m).max()):.2f} dBFS, RMS {20 * np.log10(rms):.1f} dBFS")
