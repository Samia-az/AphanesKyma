"""
noise_simulation.py
--------------------
Simulated channel noise for image<->audio pipeline.
"""

import numpy as np

NOISE_TYPES = ['none', 'awgn', 'clipping', 'dropout', 'bandlimit']


def add_none(audio, severity=0.5):
    """no corruption applied."""
    return audio.copy()


def add_awgn(audio, severity=0.5):
    """Additive white Gaussian noise, severity in [0, 1] maps to noise std in [0, 0.15]."""
    std = severity * 0.15
    rng = np.random.default_rng()
    return audio + rng.normal(0, std, size=audio.shape)


def add_clipping(audio, severity=0.5):
    """Hard-limits amplitude, simulating audio played too loud or
    through a low-quality device. Threshold is set as a percentile of
    the actual signal's amplitude distribution (rather than a fixed
    fraction of peak) so severity reliably controls what fraction of
    samples get clipped, regardless of how peaky a given signal is --
    a signal with a few rare loud outliers and mostly quiet samples
    (typical here) would barely be affected by a fixed-fraction-of-peak
    threshold otherwise."""
    if severity <= 0:
        return audio.copy()
    percentile = 100 * (1 - severity * 0.95)
    threshold = np.percentile(np.abs(audio), percentile)
    threshold = max(threshold, 1e-6)
    return np.clip(audio, -threshold, threshold)


def add_dropout(audio, severity=0.5):
    """Simulates brief signal loss / interference , severity in [0, 1] controls how much of the
    signal (by fraction of total samples, spread across several bursts)
    gets dropped."""
    out = audio.copy()
    n = len(out)
    frac_to_drop = severity * 0.4
    n_bursts = max(1, int(severity * 20))
    burst_len = max(1, int((frac_to_drop * n) / n_bursts))
    rng = np.random.default_rng()
    for _ in range(n_bursts):
        start = rng.integers(0, max(1, n - burst_len))
        out[start:start + burst_len] = 0.0
    return out


def add_bandlimit(audio, severity=0.5, sample_rate=44100):
    """Simulates a channel that doesn't pass all frequencies equally 
    """
    spec = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(len(audio), 1 / sample_rate)
    cutoff = sample_rate / 2 * (1 - severity * 0.9)  # shrinks toward low end
    rolloff_width = max(cutoff * 0.3, 1.0)
    gain = 1.0 / (1.0 + (freqs / cutoff) ** 4)  # smooth low-pass rolloff
    spec_filtered = spec * gain
    return np.fft.irfft(spec_filtered, n=len(audio))


_NOISE_FUNCS = {
    'none': add_none,
    'awgn': add_awgn,
    'clipping': add_clipping,
    'dropout': add_dropout,
    'bandlimit': add_bandlimit,
}


def apply_noise(audio, noise_type, severity=0.5):
    if noise_type not in _NOISE_FUNCS:
        raise ValueError(f"noise_type must be one of {NOISE_TYPES}, got {noise_type!r}")
    return _NOISE_FUNCS[noise_type](audio, severity)