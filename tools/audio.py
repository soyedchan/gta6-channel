"""Voz (Kokoro offline), música synthwave procedural y efectos. Todo original, sin licencias de terceros."""
import hashlib
import os

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

from config import SR, VOICE, VOICE_SPEED, tts_text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, ".models", "kokoro-v1.0.onnx")
VOICES = os.path.join(ROOT, ".models", "voices-v1.0.bin")
CACHE = os.path.join(ROOT, "build", "tts_cache")

_kokoro = None


def _engine():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(MODEL, VOICES)
    return _kokoro


def say(text: str) -> np.ndarray:
    """Sintetiza una frase y devuelve float32 mono a SR. Cacheado en disco."""
    spoken = tts_text(text)
    key = hashlib.sha1(f"{VOICE}|{VOICE_SPEED}|{spoken}".encode()).hexdigest()[:16]
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, key + ".wav")
    if os.path.exists(path):
        a, _ = sf.read(path, dtype="float32")
        return a
    samples, sr = _engine().create(spoken, voice=VOICE, speed=VOICE_SPEED, lang="es")
    assert sr == SR
    a = np.asarray(samples, dtype="float32")
    # recorta silencios de los extremos
    thr = 0.01
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx):
        a = a[max(0, idx[0] - 600): idx[-1] + 1200]
    sf.write(path, a, SR)
    return a


# ---------------------------------------------------------------- música

def _lp(x, f):
    return sosfilt(butter(2, f, "low", fs=SR, output="sos"), x)


def _hp(x, f):
    return sosfilt(butter(2, f, "high", fs=SR, output="sos"), x)


def _saw(freq, n, detune=0.0):
    t = np.arange(n) / SR
    out = np.zeros(n)
    for d in (-detune, 0.0, detune):
        ph = (t * freq * (1 + d)) % 1.0
        out += 2 * ph - 1
    return out / 3


def _env(n, a=0.01, r=0.2):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    na, nr = min(na, n), min(nr, n)
    e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def _hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _chord(root, minor):
    r = 48 + NOTE[root]
    return [r, r + (3 if minor else 4), r + 7]


PROGRESSIONS = [
    [("A", 1), ("F", 0), ("C", 0), ("G", 0)],
    [("D", 1), ("A#", 0), ("F", 0), ("C", 0)],
    [("E", 1), ("C", 0), ("G", 0), ("D", 0)],
    [("F#", 1), ("D", 0), ("A", 0), ("E", 0)],
    [("C", 1), ("G#", 0), ("D#", 0), ("A#", 0)],
]


def music(seconds: float, seed: int = 0) -> np.ndarray:
    """Pista synthwave original: pad + bajo arpegiado + batería. Bucle de 4 compases."""
    rng = np.random.default_rng(seed)
    bpm = [96, 100, 104, 92, 108][seed % 5]
    prog = PROGRESSIONS[seed % len(PROGRESSIONS)]
    beat = 60 / bpm
    bar = int(4 * beat * SR)
    loop_n = bar * 4
    pad = np.zeros(loop_n)
    bass = np.zeros(loop_n)
    arp = np.zeros(loop_n)
    for i, (root, minor) in enumerate(prog):
        notes = _chord(root, minor)
        seg = slice(i * bar, (i + 1) * bar)
        p = sum(_saw(_hz(m + 12), bar, 0.006) for m in notes) / 3
        pad[seg] += p * _env(bar, 0.4, 0.4)
        step = bar // 8
        for k in range(8):
            m = notes[0] - 12 if k % 2 == 0 else notes[0]
            b = _saw(_hz(m), step, 0.002) * _env(step, 0.005, 0.08)
            bass[i * bar + k * step: i * bar + (k + 1) * step] += b
        step16 = bar // 16
        pattern = [0, 1, 2, 1, 0, 2, 1, 2] * 2
        for k in range(16):
            m = notes[pattern[k]] + 24
            n = step16
            a_ = np.sin(2 * np.pi * _hz(m) * np.arange(n) / SR) * _env(n, 0.003, 0.09)
            arp[i * bar + k * n: i * bar + (k + 1) * n] += a_
    pad = _lp(pad, 1800)
    bass = _lp(bass, 600)
    # batería
    drums = np.zeros(loop_n)
    bn = int(beat * SR)
    kick_n = int(0.25 * SR)
    t = np.arange(kick_n) / SR
    kick = np.sin(2 * np.pi * (50 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 9)
    sn_n = int(0.2 * SR)
    snare = _hp(rng.standard_normal(sn_n), 1500) * np.exp(-np.arange(sn_n) / SR * 22) * 0.5
    hh_n = int(0.05 * SR)
    hat = _hp(rng.standard_normal(hh_n), 7000) * np.exp(-np.arange(hh_n) / SR * 80) * 0.25
    for b in range(16):
        s = b * bn
        drums[s:s + kick_n] += kick[: max(0, min(kick_n, loop_n - s))]
        if b % 2 == 1:
            drums[s:s + sn_n] += snare[: max(0, min(sn_n, loop_n - s))]
        for h in (0, bn // 2):
            hs = s + h
            drums[hs:hs + hh_n] += hat[: max(0, min(hh_n, loop_n - hs))]
    loop = 0.30 * pad + 0.38 * bass + 0.10 * arp + 0.45 * drums
    total = int(seconds * SR) + 1
    reps = total // loop_n + 1
    out = np.tile(loop, reps)[:total]
    # intro sin batería (primer compás) y fade out
    intro = min(bar, total)
    drum_full = np.tile(0.45 * drums, reps)[:total]
    out[:intro] -= drum_full[:intro] * np.linspace(1, 0, intro)
    fo = min(int(3 * SR), total)
    out[-fo:] *= np.linspace(1, 0, fo)
    out /= (np.abs(out).max() + 1e-9)
    return out.astype("float32")


# ---------------------------------------------------------------- efectos

def whoosh(seed=0):
    rng = np.random.default_rng(100 + seed)
    n = int(0.55 * SR)
    noise = rng.standard_normal(n)
    chunks = 20
    cs = n // chunks
    parts = []
    for i in range(chunks):
        f = 300 + 5000 * np.sin(np.pi * i / chunks) ** 2
        parts.append(_lp(_hp(noise[i * cs:(i + 1) * cs], max(80, f * 0.3)), f))
    out = np.concatenate(parts)
    n = len(out)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    out = out * env
    return (out / (np.abs(out).max() + 1e-9) * 0.5).astype("float32")


def pop():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * (900 + 700 * t / t[-1]) * t) * np.exp(-t * 45)
    return (s * 0.25).astype("float32")


def mix(total_s, voice_clips, sfx_clips, music_seed):
    """voice_clips / sfx_clips: lista de (inicio_s, array). Devuelve mezcla estéreo float32."""
    n = int(total_s * SR) + SR
    voice = np.zeros(n, dtype="float32")
    for t0, a in voice_clips:
        s = int(t0 * SR)
        voice[s:s + len(a)] += a[: n - s]
    sfx = np.zeros(n, dtype="float32")
    for t0, a in sfx_clips:
        s = max(0, int(t0 * SR))
        sfx[s:s + len(a)] += a[: n - s]
    mus = music(n / SR, music_seed)[:n]
    # ducking: envolvente de la voz suavizada
    env = np.abs(voice)
    k = int(0.25 * SR)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    duck = np.clip(env * 25, 0, 1)
    mus_gain = 0.20 - 0.13 * duck
    v = voice / (np.abs(voice).max() + 1e-9) * 0.92
    out = v + mus * mus_gain + sfx * 0.6
    out /= max(1.0, np.abs(out).max() / 0.98)
    return np.stack([out, out], axis=1).astype("float32")
