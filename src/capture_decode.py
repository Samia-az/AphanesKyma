"""
capture_decode.py
-------------------
Decoding path for audio that was actually played through a speaker and
picked up by a microphone, instead of the clean in-memory round-trip.

Two problems this solves that a controlled round-trip never has to:

    1. RATE MISMATCH -- the encoded WAV is written at SAMPLE_RATE and
       plays back at that real-time rate regardless of the capturing
       device's internal audio engine. The mic digitizes at *its own*
       native rate (commonly 44100 or 48000 Hz). The same real second
       of audio is represented by a different sample count at that rate,
       so frame_len-sized slices of the raw capture do not line up with
       the original frames until the capture is resampled back to
       SAMPLE_RATE. Read the true capture rate from the WAV file's own
       header (wave.getframerate()) -- do not hardcode or guess it.

    2. UNKNOWN START OFFSET -- the marker preamble (a broadband chirp
       500 Hz → 18 kHz, MARKER_LEN samples) is matched-filtered against
       the resampled capture by find_marker_offset() in marker.py. The
       matched filter compares the capture against the known clean
       template, so it stays robust under room reverb and mic
       frequency-response coloring -- unlike the old copy-vs-copy NCC
       approach, where each header copy picked up a *different* reverb
       tail depending on what preceded it, blunting the similarity peak.
       find_marker_offset() returns the sample where the marker ENDS,
       i.e. where the header block starts; that slice is passed to
       audio_with_header_to_image() for final decoding.
"""

from marker import _log
import numpy as np

from image_audio_fft import SAMPLE_RATE
from marker import find_marker_offset
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



def decode_captured_audio(raw_audio, native_rate, search_seconds=5.0):
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
                   start. Defaults to 5s to cover typical pre-roll
                   (silence between the user pressing Record and Play).
                   If the bounded search fails, a full-recording scan is
                   attempted automatically before giving up.

    Returns whatever audio_with_header_to_image() returns: (image,
    n_rows, n_cols, mode_name, source), where source is 'full' or
    'thumbnail_fallback' -- see that function's docstring in
    header_fft.py. Only raises if the header block itself couldn't even
    be LOCATED (see find_header_offset above); if it's located but its
    *contents* are too corrupted to trust, this falls back to the small
    protected thumbnail automatically rather than raising.

    Raises ValueError if no header alignment could be located at all.
    """
    import logging
    _log = logging.getLogger("aphaneskyma")

    _log.info(
        "capture_decode: native_rate=%d  target_rate=%d  raw_samples=%d  "
        "peak_abs=%.5f  search_seconds=%.1f",
        native_rate, SAMPLE_RATE, len(raw_audio),
        float(np.max(np.abs(raw_audio))) if len(raw_audio) else 0.0,
        search_seconds
    )

    resampled = resample_to_target_rate(raw_audio, native_rate, SAMPLE_RATE)
    _log.info(
        "capture_decode: resampled to %d samples at %d Hz  peak_abs=%.5f",
        len(resampled), SAMPLE_RATE,
        float(np.max(np.abs(resampled))) if len(resampled) else 0.0
    )

    # Bounded search (fast path: covers normal pre-roll up to search_seconds)
    offset = find_marker_offset(resampled, search_seconds=search_seconds)

    if offset is None:
        # Full-recording fallback: if the user had an unusually long pre-roll
        # (e.g. pressed Play well after Record), try scanning the whole file.
        full_seconds = len(resampled) / SAMPLE_RATE
        if full_seconds > search_seconds:
            _log.info(
                "capture_decode: bounded search failed; retrying with full scan (%.1fs)",
                full_seconds
            )
            offset = find_marker_offset(resampled, search_seconds=full_seconds)

    if offset is None:
        raise ValueError(
            "Could not locate a valid header in the captured audio "
            "(searched the entire %.1fs recording) -- check that the "
            "recording actually contains the played signal."
            % (len(resampled) / SAMPLE_RATE)
        )
    from header_fft import HEADER_FRAME_LEN, HEADER_REPEATS, read_header_frame, MARKER_LEN

    marker_start = offset - MARKER_LEN
    body_start = marker_start + MARKER_LEN  # == offset, just being explicit
    for i in range(HEADER_REPEATS):
        seg_start = body_start + i * HEADER_FRAME_LEN
        segment = resampled[seg_start:seg_start + HEADER_FRAME_LEN]
        spectrum = np.fft.rfft(segment, n=HEADER_FRAME_LEN)
        magnitude = np.abs(spectrum)
        n_rows, n_cols, mode_id, data_repeats = read_header_frame(segment)
        _log.info(
            "header copy %d: decoded=(rows=%d cols=%d mode=%d rep=%d)  "
            "coded_region max=%.4f mean=%.4f min=%.4f",
            i, n_rows, n_cols, mode_id, data_repeats,
            magnitude[:70].max(), magnitude[:70].mean(), magnitude[:70].min()
        )
    _log.info(
        "capture_decode: header confirmed at sample %d (%.3fs into recording)",
        offset, offset / SAMPLE_RATE
    )
    return audio_with_header_to_image(resampled[offset:])