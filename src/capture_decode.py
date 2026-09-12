"""
capture_decode.py
-------------------
Decoding path for audio 
"""

import numpy as np

from image_audio_fft import SAMPLE_RATE
from header_fft import (
    HEADER_FRAME_LEN,
    HEADER_REPEATS,
    _read_header_majority_vote,
    _is_valid_header_fields,
    audio_with_header_to_image,
)


def resample_to_target_rate(audio, native_rate, target_rate=SAMPLE_RATE):
    """
    Resample captured audio from the rate it was actually recorded at
    (native_rate, read from the WAV file's own header -- see module
    docstring) to target_rate (SAMPLE_RATE, what the encoder assumed).

    If native_rate already equals target_rate this is a no-op copy.
    Uses scipy's polyphase resampler when available (much better
    preserved spectral content -- important here, since the decoded
    "image" *is* a spectrum); falls back to plain linear interpolation
    (via np.interp) if scipy isn't installed, which is lower quality but
    dependency-free.
    """
    audio = np.asarray(audio, dtype=np.float64)
    if native_rate == target_rate:
        return audio.copy()

    try:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(int(target_rate), int(native_rate))
        up, down = int(target_rate) // g, int(native_rate) // g
        return resample_poly(audio, up, down)
    except ImportError:
        n_out = int(round(len(audio) * target_rate / native_rate))
        old_idx = np.arange(len(audio))
        new_idx = np.linspace(0, len(audio) - 1, n_out)
        return np.interp(new_idx, old_idx, audio)


def find_header_offset(audio, search_seconds=2.0, coarse_stride=8,
                        min_correlation=0.9, target_rate=SAMPLE_RATE):
    """
    Search the first `search_seconds` of `audio` (already resampled to
    target_rate) for the exact sample offset where the repeated header
    starts.

    IMPORTANT: this does NOT work by checking whether the header decodes
    correctly at a candidate offset. It was tried and doesn't work: the
    header's Hamming(7,4) + HEADER_REPEATS-way redundancy makes field
    decoding deliberately tolerant of a fair amount of misalignment (a
    window a couple hundred samples off the true boundary, straddling
    silence and real header content, can still decode the right
    (n_rows, n_cols, mode_id) -- that's the whole point of that
    redundancy). But audio_with_header_to_image() then slices the data
    portion at a FIXED distance (HEADER_FRAME_LEN * HEADER_REPEATS) past
    whatever offset it's given -- so "the header decoded correctly here"
    is not enough; it has to be the exact true offset, or the data slice
    itself comes from the wrong place and the whole image scrambles even
    though the header fields looked fine.

    Instead this exploits the header block's own structure directly: it
    is HEADER_REPEATS *identical* 512-sample copies placed back-to-back.
    At the true start (and only there), audio[k:k+512] and
    audio[k+512:k+1024] are (near-)identical, and likewise
    audio[k+512:k+1024] vs audio[k+1024:k+1536] -- a normalized
    cross-correlation between consecutive windows peaks sharply and
    specifically at k = true offset, unlike header-field decoding, which
    stays "correct" across a range of nearby k. We require BOTH
    consecutive-pair correlations to be high, not just one, so a false
    peak from some other coincidentally-periodic stretch of audio (e.g.
    inside the data audio itself, which is not designed to be
    non-periodic) has to hold across two consecutive window-pairs rather
    than one.

    `min_correlation`: normalized correlation ([-1, 1], 1 = identical up
    to scale) required of both consecutive pairs for a candidate offset
    to be accepted at all. 0.9 leaves room for the small numerical noise
    introduced by resampling; a real, correctly-resampled header should
    score very close to 1.0.

    Returns the offset (int, samples) on success, or None if no
    sufficiently strong header alignment was found in the search window.
    """
    search_samples = int(search_seconds * target_rate)
    search_samples = min(search_samples, len(audio) - HEADER_FRAME_LEN * HEADER_REPEATS)
    if search_samples <= 0:
        return None

    def _ncc(x, y):
        denom = np.linalg.norm(x) * np.linalg.norm(y)
        if denom == 0:
            return 0.0
        return float(np.dot(x, y) / denom)

    def _score(offset):
        a = audio[offset:offset + HEADER_FRAME_LEN]
        b = audio[offset + HEADER_FRAME_LEN:offset + 2 * HEADER_FRAME_LEN]
        c = audio[offset + 2 * HEADER_FRAME_LEN:offset + 3 * HEADER_FRAME_LEN]
        if len(c) < HEADER_FRAME_LEN:
            return -2.0
        return min(_ncc(a, b), _ncc(b, c))

    def _best_in_range(offsets):
        best_offset, best_score = None, -2.0
        for offset in offsets:
            s = _score(offset)
            if s > best_score:
                best_offset, best_score = offset, s
        return best_offset, best_score

    coarse_best, coarse_score = _best_in_range(range(0, search_samples, coarse_stride))
    if coarse_best is None or coarse_score < min_correlation:
        return None

    # Fine refinement around the coarse peak, stride=1, to land on the
    # exact sample rather than within `coarse_stride` of it.
    lo = max(0, coarse_best - coarse_stride)
    hi = min(search_samples, coarse_best + coarse_stride)
    fine_best, fine_score = _best_in_range(range(lo, hi))

    if fine_best is None or fine_score < min_correlation:
        return None

    # Belt-and-suspenders: also confirm the header actually decodes to
    # sane values at the offset we landed on (cheap, and catches the
    # rare case of a strong correlation peak that isn't really a header).
    n_rows, n_cols, mode_id = _read_header_majority_vote(audio, offset=fine_best)
    if not _is_valid_header_fields(n_rows, n_cols, mode_id, len(audio) - fine_best):
        return None

    return fine_best


def decode_captured_audio(raw_audio, native_rate, search_seconds=2.0):
    """
    Full path for a live mic capture: resample to SAMPLE_RATE, locate
    the header, then decode exactly like audio_with_header_to_image()
    does for a clean round-trip.

    raw_audio    : 1D array of captured samples, as recorded.
    native_rate  : the mic's actual capture rate, read from the WAV file
                   you saved on the capturing device (wave.getframerate()) --
                   see module docstring for why this must come from the
                   file, not be assumed.
    search_seconds : how far into the recording to search for the header
                   start. Only needs to comfortably exceed the imprecision
                   of the user's manual front-trim in the webapp; the
                   default of 2s is generous for that.

    Raises ValueError if no valid header could be located.
    """
    resampled = resample_to_target_rate(raw_audio, native_rate, SAMPLE_RATE)
    offset = find_header_offset(resampled, search_seconds=search_seconds)
    if offset is None:
        raise ValueError(
            "Could not locate a valid header in the captured audio within "
            f"the first {search_seconds}s -- check that the recording "
            "actually contains the played signal (right device/mic, "
            "playback wasn't cut off, native_rate is correct)."
        )
    return audio_with_header_to_image(resampled[offset:])