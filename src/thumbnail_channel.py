"""
thumbnail_channel.py
---------------------
Self-contained, heavily-protected low-resolution fallback channel.

Encodes a small (THUMBNAIL_DIM x THUMBNAIL_DIM), heavily quantized
grayscale preview of the image using exactly the same scheme the main
header uses (on/off keyed bits across frequency bins, Hamming(7,4),
THUMBNAIL_REPEATS-way redundancy) -- just sized to carry real pixel
data instead of three integers.

Unlike the main data channel, this doesn't depend on the main header
succeeding at all: its size and position are fixed constants known
ahead of time by both sides, so it can be located and decoded
independently. header_fft.audio_with_header_to_image() falls back to
this when the main header/data path fails validation, so SOME
recognizable image comes back rather than nothing.

Important: this is a probability FLOOR, not a quality improvement --
different in kind from header_fft's data_repeats row-voting, which
raises the *typical* quality of a successful full-resolution decode.
This raises the odds you get *any* usable image at all.
"""

import numpy as np
from hamming_bits import (
    int_to_bits, bits_to_int, bits_to_hamming_stream, hamming_stream_to_bits,
)

THUMBNAIL_DIM = 16              # THUMBNAIL_DIM x THUMBNAIL_DIM grayscale preview
THUMBNAIL_BITS_PER_PIXEL = 6    # 64 quantization levels per pixel
THUMBNAIL_REPEATS = 3           # independent copies, bit-level majority-voted
THUMBNAIL_AMPLITUDE_SCALE = 0.35  # same deliberate trade-off as HEADER_AMPLITUDE_SCALE
                                   # in header_fft.py -- see that constant's
                                   # docstring for why (AWGN vs clipping robustness)

THUMBNAIL_DATA_BITS = THUMBNAIL_DIM * THUMBNAIL_DIM * THUMBNAIL_BITS_PER_PIXEL
_THUMBNAIL_N_CHUNKS = -(-THUMBNAIL_DATA_BITS // 4)          # ceil div by 4
THUMBNAIL_CODED_BITS = _THUMBNAIL_N_CHUNKS * 7               # after Hamming(7,4)
# Frame long enough to give at least THUMBNAIL_CODED_BITS usable rFFT bins,
# with headroom (2x) the same way header_fft.HEADER_N_COLS has headroom
# over the main header's own coded-bit count.
THUMBNAIL_FRAME_LEN = 2 * THUMBNAIL_CODED_BITS
THUMBNAIL_N_COLS = THUMBNAIL_FRAME_LEN // 2 + 1


def _resize_to_thumbnail(image, dim=THUMBNAIL_DIM):
    """Crude, dependency-light nearest-neighbor downsample to a dim x dim
    grid. Doesn't need to be high quality -- this is a coarse fallback
    preview, not the main channel, and every bit of quality costs
    THUMBNAIL_BITS_PER_PIXEL more transmitted bits per pixel."""
    image = np.asarray(image, dtype=np.float64)
    h, w = image.shape
    row_idx = np.clip((np.arange(dim) * h / dim).astype(int), 0, h - 1)
    col_idx = np.clip((np.arange(dim) * w / dim).astype(int), 0, w - 1)
    return image[np.ix_(row_idx, col_idx)]


def quantize_thumbnail(image, dim=THUMBNAIL_DIM, bits=THUMBNAIL_BITS_PER_PIXEL):
    """Downsample + quantize to `bits`-bit levels, using the thumbnail's
    OWN min/max (not the original image's, and not passed separately at
    decode time -- there's nowhere to put it). This is fine because the
    final display step (magnitude_to_image_uint8 in image_audio_fft.py)
    does its own min-max rescale anyway, so only the thumbnail's
    relative structure needs to survive, not its absolute scale."""
    small = _resize_to_thumbnail(image, dim)
    lo, hi = small.min(), small.max()
    if hi <= lo:
        return np.zeros((dim, dim), dtype=int)
    levels = (2 ** bits) - 1
    q = np.round((small - lo) / (hi - lo) * levels).astype(int)
    return np.clip(q, 0, levels)


def dequantize_thumbnail(quantized, bits=THUMBNAIL_BITS_PER_PIXEL):
    """Inverse of quantize_thumbnail, up to the min/max discarded there
    (see that function's docstring -- doesn't matter for display)."""
    levels = (2 ** bits) - 1
    return quantized.astype(np.float64) / levels


def _quantized_to_bits(quantized, bits=THUMBNAIL_BITS_PER_PIXEL):
    flat = quantized.flatten()
    return np.concatenate([int_to_bits(int(v), bits) for v in flat])


def _bits_to_quantized(bit_array, dim=THUMBNAIL_DIM, bits=THUMBNAIL_BITS_PER_PIXEL):
    n_pixels = dim * dim
    out = np.zeros(n_pixels, dtype=int)
    for i in range(n_pixels):
        chunk = bit_array[i * bits:(i + 1) * bits]
        out[i] = bits_to_int(chunk)
    return out.reshape(dim, dim)


def make_thumbnail_frame(image, on_amplitude=40.0):
    """Build one THUMBNAIL_FRAME_LEN-sample time-domain frame encoding a
    quantized preview of `image`, Hamming-protected, on/off keyed --
    same construction as header_fft.make_header_frame, just carrying
    many more data bits."""
    quantized = quantize_thumbnail(image)
    bits = _quantized_to_bits(quantized)
    coded = bits_to_hamming_stream(bits)

    magnitude = np.zeros(THUMBNAIL_N_COLS)
    magnitude[:len(coded)] = coded * on_amplitude
    spectrum = magnitude.astype(np.complex128)
    frame = np.fft.irfft(spectrum, n=THUMBNAIL_FRAME_LEN)
    return frame


def build_thumbnail_block(image, data_peak_for_scaling=1.0):
    """Build the full THUMBNAIL_REPEATS-times-repeated, amplitude-scaled
    thumbnail block, ready to be concatenated into the full audio signal
    -- same idea as header_fft's header-repeat/rebalance step.

    data_peak_for_scaling: pass the main data audio's peak (same role
    HEADER_AMPLITUDE_SCALE * data_peak plays for the main header) so the
    thumbnail's loudness is set relative to it, not in isolation.
    """
    frame = make_thumbnail_frame(image)
    peak = np.abs(frame).max()
    if peak > 0:
        frame = frame * (data_peak_for_scaling / peak) * THUMBNAIL_AMPLITUDE_SCALE
    return np.concatenate([frame] * THUMBNAIL_REPEATS)


def decode_thumbnail_block(audio, offset=0, threshold_ratio=0.5):
    """Read all THUMBNAIL_REPEATS copies starting at `offset` samples
    into `audio`, and combine them with BIT-LEVEL majority voting (not
    per-field the way header_fft's main header does -- there's no small
    set of discrete fields here, just THUMBNAIL_DATA_BITS individual
    bits, so each bit position is voted on independently across the
    repeats). Returns the dequantized THUMBNAIL_DIM x THUMBNAIL_DIM
    preview image.

    Raises ValueError if there isn't even one full copy's worth of
    audio available at this offset.
    """
    bit_votes = []
    for i in range(THUMBNAIL_REPEATS):
        start = offset + i * THUMBNAIL_FRAME_LEN
        segment = audio[start:start + THUMBNAIL_FRAME_LEN]
        if len(segment) < THUMBNAIL_FRAME_LEN:
            continue
        spectrum = np.fft.rfft(segment, n=THUMBNAIL_FRAME_LEN)
        magnitude = np.abs(spectrum)
        coded_region = magnitude[:THUMBNAIL_CODED_BITS]
        thresh = coded_region.max() * threshold_ratio if coded_region.max() > 0 else 0
        coded_bits = (coded_region > thresh).astype(int)
        bits = hamming_stream_to_bits(coded_bits, THUMBNAIL_DATA_BITS)
        bit_votes.append(bits)

    if not bit_votes:
        raise ValueError(
            "No usable thumbnail copies found at this offset -- audio too "
            "short, or offset badly wrong."
        )

    stacked = np.stack(bit_votes, axis=0)
    # bit is "1" if at least half the available copies say so
    majority_bits = (stacked.sum(axis=0) * 2 >= stacked.shape[0]).astype(int)
    quantized = _bits_to_quantized(majority_bits)
    return dequantize_thumbnail(quantized)