"""
marker.py
---------
Fixed chirp preamble used ONLY to locate where the header block starts.
Replaces find_header_offset's copy-vs-copy correlation, which degrades
under real room reverb (each header copy picks up a different
reverb tail depending on what preceded it, blunting the NCC peak).
A matched filter against a known, clean broadband sweep doesn't have
that problem -- it's comparing against a template, not two live,
independently-degraded copies of each other.
"""

import logging
import numpy as np
from image_audio_fft import SAMPLE_RATE

_log = logging.getLogger("aphaneskyma")

MARKER_LEN = 4096
MARKER_F0 = 500.0
MARKER_F1 = 18000.0
MARKER_AMPLITUDE_SCALE = 0.5


def make_marker(sample_rate=SAMPLE_RATE, length=MARKER_LEN, f0=MARKER_F0, f1=MARKER_F1):
    t = np.arange(length) / sample_rate
    k = (f1 - f0) / (length / sample_rate)
    phase = 2 * np.pi * (f0 * t + 0.5 * k * t ** 2)
    chirp = np.sin(phase)

    taper_len = length // 20
    window = np.ones(length)
    ramp = 0.5 * (1 - np.cos(np.linspace(0, np.pi, taper_len)))
    window[:taper_len] = ramp
    window[-taper_len:] = ramp[::-1]
    return chirp * window


def find_marker_offset(audio,marker=None,search_seconds=5.0,target_rate=SAMPLE_RATE,min_score=0.40,):
    """Returns the offset where the marker ENDS (i.e. where the header
    begins), or None if no sufficiently strong match was found."""
    if marker is None:
        marker = make_marker(target_rate)
    marker = np.asarray(marker, dtype=np.float64)
    m_len = len(marker)
    m_norm = np.linalg.norm(marker)

    search_samples = int(search_seconds * target_rate)
    search_samples = min(search_samples, max(0, len(audio) - m_len))
    if search_samples <= 0 or m_norm == 0:
        _log.warning("find_marker_offset: audio too short to contain marker")
        return None

    window = audio[:search_samples + m_len]
    raw_corr = np.correlate(window, marker, mode='valid')

    sq = window ** 2
    cumsum = np.concatenate([[0.0], np.cumsum(sq)])
    window_energy = cumsum[m_len:] - cumsum[:-m_len]
    window_norm = np.sqrt(np.maximum(window_energy, 1e-12))

    scores = raw_corr / (window_norm * m_norm)
    best_offset = int(np.argmax(scores))
    best_score = float(scores[best_offset])

    _log.info("find_marker_offset: best_score=%.4f @ raw_offset=%d threshold=%.2f",
               best_score, best_offset, min_score)

    if best_score < min_score:
        _log.warning("find_marker_offset: below threshold -- marker not found")
        return None

    return best_offset + m_len