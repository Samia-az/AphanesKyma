"""
header_fft.py
-------------
Self-describing header for the row-wise FFT image<->audio scheme.

Embeds n_rows / n_cols / audio_mode / data_repeats into a fixed-length
header frame at the start of the audio, protected with Hamming(7,4).

Also wires in two extra robustness features on top of the original
header-only scheme:

  - data_repeats: each data row can be transmitted multiple times: the
    encoder repeats every row `data_repeats` times before handing the
    (expanded) image to image_to_audio(), and the decoder collapses
    each group of `data_repeats` decoded frames back into one row via a
    per-bin MEDIAN across the group -- the continuous-valued analogue
    of the header's own bit-level majority voting, since data rows
    carry real magnitude values rather than discrete bits. Raises the
    *typical* quality of a successful decode; see thumbnail_channel.py
    for the complementary guarantee.

  - thumbnail fallback: a small, independently-decodable, heavily
    protected preview (see thumbnail_channel.py) is transmitted right
    after the main header. If the main header can't be validated,
    audio_with_header_to_image() automatically falls back to that
    preview instead of raising -- a probability FLOOR on getting some
    recognizable image back, distinct from data_repeats' quality boost.
"""
HEADER_FRAME_LEN = 512          # fixed & known
HEADER_BITS_PER_VALUE = 16      # bits used to encode each of n_rows, n_cols
HEADER_MODE_BITS = 4            # bits used to encode the audio mode/preset id
HEADER_DATA_REPEATS_BITS = 4    # bits used to encode data_repeats (1-15)
HEADER_N_COLS = HEADER_FRAME_LEN // 2 + 1  # rFFT bins available in header frame
HEADER_REPEATS = 3
HEADER_AMPLITUDE_SCALE = 0.35
HEADER_BIN_OFFSET = 32   # ~3000 Hz -- empirically, bins below ~2.6kHz get
                          # destroyed by the acoustic path (speaker rolloff /
                          # mic rumble filter / room resonance), even though
                          # HEADER_N_COLS has plenty of unused headroom above
                          # where the header actually needs to live.
MAX_PLAUSIBLE_COLS = 256
MAX_PLAUSIBLE_ROWS = 256

import numpy as np
from collections import Counter
from image_audio_fft import image_to_audio, audio_to_image, SAMPLE_RATE
from marker import make_marker, MARKER_AMPLITUDE_SCALE, MARKER_LEN
from hamming_bits import (
    hamming74_encode, hamming74_decode,
    bits_to_hamming_stream, hamming_stream_to_bits,
    int_to_bits, bits_to_int,
)
from thumbnail_channel import (
    THUMBNAIL_DIM, THUMBNAIL_FRAME_LEN, THUMBNAIL_REPEATS,
    build_thumbnail_block, decode_thumbnail_block,
)



# Audio layout (sample offsets, all at SAMPLE_RATE):
#   [marker : MARKER_LEN] + [header × HEADER_REPEATS] + [thumbnail × THUMBNAIL_REPEATS] + [data]
MARKER_BLOCK_START    = 0
HEADER_BLOCK_START    = MARKER_LEN
THUMBNAIL_BLOCK_START = MARKER_LEN + HEADER_FRAME_LEN * HEADER_REPEATS
THUMBNAIL_BLOCK_LEN   = THUMBNAIL_FRAME_LEN * THUMBNAIL_REPEATS
DATA_BLOCK_START      = THUMBNAIL_BLOCK_START + THUMBNAIL_BLOCK_LEN

MAX_DATA_REPEATS = (1 << HEADER_DATA_REPEATS_BITS) - 1

_INTERLEAVE_PERM = np.array([
    0, 16, 32,  1, 17, 33,  2, 18, 34,  3, 19, 35,
    4, 20, 36,  5, 21, 37,  6, 22, 38,  7, 23, 39,
    8, 24,  9, 25, 10, 26, 11, 27, 12, 28, 13, 29,
    14, 30, 15, 31
])  # Scatters rows, cols, mode, and rep bits evenly


# --------------------------------------------------------------------------
# Header <-> audio frame
# --------------------------------------------------------------------------
def _interleave_bits(bits):
    return bits[_INTERLEAVE_PERM]

def _deinterleave_bits(bits):
    unshuffle = np.argsort(_INTERLEAVE_PERM)
    return bits[unshuffle]


# --- make_header_frame: add one always-on pilot bin per 7-bit chunk ---
def make_header_frame(n_rows, n_cols, mode_id=0, data_repeats=1, on_amplitude=40.0):
    bits = np.concatenate([
        int_to_bits(n_rows, HEADER_BITS_PER_VALUE),
        int_to_bits(n_cols, HEADER_BITS_PER_VALUE),
        int_to_bits(mode_id, HEADER_MODE_BITS),
        int_to_bits(data_repeats, HEADER_DATA_REPEATS_BITS),
    ])
    
    # Interleave bits across frequency bins
    bits = _interleave_bits(bits)
    
    coded = bits_to_hamming_stream(bits)          # length = n_chunks * 7
    n_chunks = len(coded) // 7

    # Lay out as [7 data bins, 1 pilot bin] per chunk, so every chunk
    # carries its own always-on amplitude reference right next to its
    # data -- a chunk whose real bits are all zero still has something
    # to threshold against, and the reference reflects THIS chunk's
    # frequency-local channel gain rather than some other chunk's.
    n_slots = n_chunks * 8
    if HEADER_BIN_OFFSET + n_slots > HEADER_N_COLS:
        raise ValueError("Header doesn't fit in HEADER_FRAME_LEN; increase it.")

    magnitude = np.zeros(HEADER_N_COLS)
    for c in range(n_chunks):
        data_slice = coded[c * 7:(c + 1) * 7]
        base = HEADER_BIN_OFFSET + c * 8
        magnitude[base:base + 7] = data_slice * on_amplitude
        magnitude[base + 7] = on_amplitude   # pilot, always on

    spectrum = magnitude.astype(np.complex128)
    frame = np.fft.irfft(spectrum, n=HEADER_FRAME_LEN)
    return frame


def _decode_from_magnitude(magnitude, threshold_ratio=0.5):
    total_data_bits = (
        2 * HEADER_BITS_PER_VALUE + HEADER_MODE_BITS + HEADER_DATA_REPEATS_BITS
    )
    n_chunks = -(-total_data_bits // 4)

    # 1. Calculate median pilot across all 10 chunks to resist narrow frequency nulls
    pilots = [
        magnitude[HEADER_BIN_OFFSET + c * 8 + 7] for c in range(n_chunks)
    ]
    median_pilot = np.median(pilots)

    # 2. Enforce a minimum pilot floor so acoustic nulls cannot collapse the threshold
    pilot_floor = max(median_pilot * 0.4, 1e-3)

    coded_bits = np.zeros(n_chunks * 7, dtype=int)
    for c in range(n_chunks):
        base = HEADER_BIN_OFFSET + c * 8
        data_slice = magnitude[base : base + 7]
        pilot = max(magnitude[base + 7], pilot_floor)
        local_thresh = pilot * threshold_ratio
        coded_bits[c * 7 : (c + 1) * 7] = (data_slice > local_thresh).astype(
            int
        )

    # Inside _decode_from_magnitude (header_fft.py)
    bits = hamming_stream_to_bits(coded_bits, n_chunks * 4)
    
    # Restore original bit order before parsing values
    bits = _deinterleave_bits(bits)
    
    n_rows = bits_to_int(bits[:HEADER_BITS_PER_VALUE])
    n_cols = bits_to_int(
        bits[HEADER_BITS_PER_VALUE : 2 * HEADER_BITS_PER_VALUE]
    )
    mode_id = bits_to_int(
        bits[
            2
            * HEADER_BITS_PER_VALUE : 2
            * HEADER_BITS_PER_VALUE
            + HEADER_MODE_BITS
        ]
    )
    data_repeats = bits_to_int(
        bits[
            2 * HEADER_BITS_PER_VALUE
            + HEADER_MODE_BITS : 2 * HEADER_BITS_PER_VALUE
            + HEADER_MODE_BITS
            + HEADER_DATA_REPEATS_BITS
        ]
    )
    return n_rows, n_cols, mode_id, data_repeats


def _read_header_majority_vote(audio, offset=0):
    rows_votes = []
    cols_votes = []
    mode_votes = []
    rep_votes = []

    for i in range(HEADER_REPEATS):
        start = offset + i * HEADER_FRAME_LEN
        segment = audio[start : start + HEADER_FRAME_LEN]
        if len(segment) < HEADER_FRAME_LEN:
            continue

        r_rows, r_cols, r_mode, r_rep = read_header_frame(segment)

        # Vote on valid individual fields rather than discarding the entire copy
        if 1 <= r_rows <= 256:
            rows_votes.append(r_rows)
        if 2 <= r_cols <= 256:
            cols_votes.append(r_cols)
        if r_mode in AUDIO_PRESETS:
            mode_votes.append(r_mode)
        if 1 <= r_rep <= MAX_DATA_REPEATS:
            rep_votes.append(r_rep)

    fallback_rows, fallback_cols, fallback_mode, fallback_rep = read_header_frame(
        audio[offset : offset + HEADER_FRAME_LEN]
    )

    final_rows = Counter(rows_votes).most_common(1)[0][0] if rows_votes else fallback_rows
    final_cols = Counter(cols_votes).most_common(1)[0][0] if cols_votes else fallback_cols
    final_mode = Counter(mode_votes).most_common(1)[0][0] if mode_votes else fallback_mode
    final_rep = Counter(rep_votes).most_common(1)[0][0] if rep_votes else fallback_rep

    return final_rows, final_cols, final_mode, final_rep
def read_header_frame(frame, threshold_ratio=0.5):
    spectrum = np.fft.rfft(frame, n=HEADER_FRAME_LEN)
    return _decode_from_magnitude(np.abs(spectrum), threshold_ratio)


# --------------------------------------------------------------------------
# Audio presets
# --------------------------------------------------------------------------
# Each preset is a FIXED, hardcoded recipe (not per-file data), so the
# decoder only needs to know which preset id was used (4 bits, embedded
# in the header above) to reconstruct the exact same weighting/sparsify
# behavior -- nothing about the preset itself needs to be stored anywhere.


AUDIO_PRESETS = {
    0: dict(name='fidelity',        strength=0.0, floor=1.00, blur_fraction=None),
    1: dict(name='balanced',        strength=0.6, floor=0.10, blur_fraction=0.05),
    2: dict(name='listenable',      strength=1.0, floor=0.03, blur_fraction=0.15),
    3: dict(name='very_listenable', strength=1.3, floor=0.02, blur_fraction=0.30),
}


def _a_weighting_gain_db(freq_hz):
    """Standard A-weighting curve (IEC 61672) -- approximates relative
    human hearing sensitivity across frequency. Higher = ear is more
    sensitive there (peaks around 2-5 kHz)."""
    f = np.maximum(freq_hz, 1e-6)
    f2 = f ** 2
    ra = (12194 ** 2 * f2 ** 2) / (
        (f2 + 20.6 ** 2) * np.sqrt((f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194 ** 2)
    )
    return 20 * np.log10(ra) + 2.00


def _make_weight_curve(n_cols, strength, floor, sample_rate=SAMPLE_RATE):
    """Build a per-bin attenuation curve that de-emphasizes frequencies
    the human ear is most sensitive to, rather than a blind rolloff.
    `strength` scales how aggressively sensitive frequencies are
    attenuated (0 = no weighting/flat, larger = stronger de-emphasis).
    `floor` sets a minimum gain so no bin is fully silenced (keeps the
    curve invertible without dividing by zero)."""
    if strength == 0.0 and floor == 1.00:
        return np.ones(n_cols)
    frame_len = 2 * (n_cols - 1)
    freqs = np.arange(n_cols) * sample_rate / frame_len
    a_db = _a_weighting_gain_db(freqs)
    sensitivity = 10 ** (a_db / 20)          # relative ear sensitivity
    curve = 1.0 / np.maximum(sensitivity, 1e-3) ** strength
    curve = curve / curve.max()              # normalize to a 0..1 range
    curve = curve * (1 - floor) + floor      # apply floor so nothing hits exactly 0
    return curve


def _blur_rows(image, blur_fraction):
    """Smooth each row with a moving-average filter (kernel width scales
    with n_cols) -- reduces fine detail/harsh column-to-column jumps
    while keeping every column populated (a real blur, not a crop)."""
    if blur_fraction is None:
        return image
    n_cols = image.shape[1]
    kernel_size = max(1, int(round(blur_fraction * n_cols)))
    if kernel_size <= 1:
        return image
    kernel = np.ones(kernel_size) / kernel_size
    out = np.zeros_like(image)
    for r in range(image.shape[0]):
        out[r] = np.convolve(image[r], kernel, mode='same')
    return out


def apply_preset(image, mode_id):
    """Apply a named preset's weighting + row-blur to an image, ready to
    be passed into image_to_audio(). Returns (processed_image,
    weight_curve) -- weight_curve is needed again at decode time to
    invert the weighting (the blur has no separate inverse; it's simply
    the accepted lossy trade-off of that preset)."""
    preset = AUDIO_PRESETS[mode_id]
    n_cols = image.shape[1]
    weight = _make_weight_curve(n_cols, preset['strength'], preset['floor'])
    blurred = _blur_rows(image, preset['blur_fraction'])
    weighted = blurred * weight[np.newaxis, :]
    return weighted, weight


def invert_preset(recovered_image, mode_id):
    """Undo a preset's weighting on a decoded image. n_cols is inferred
    from the recovered image's own shape (already known from the header
    by the time this is called)."""
    n_cols = recovered_image.shape[1]
    preset = AUDIO_PRESETS.get(mode_id, AUDIO_PRESETS[0])
    weight = _make_weight_curve(n_cols, preset['strength'], preset['floor'])
    return recovered_image / weight[np.newaxis, :]


# --------------------------------------------------------------------------
# Full pipeline
# --------------------------------------------------------------------------

def image_to_audio_with_header(image, mode='listenable', phase_seed=0, data_repeats=1):
    """
    Encode image -> audio.

    mode : str or int
        One of AUDIO_PRESETS' names ('fidelity', 'balanced',
        'listenable', 'very_listenable') or its integer id.
    data_repeats : int, 1..MAX_DATA_REPEATS
        How many times to transmit each data row. 1 = original
        behavior (no repetition). >1 repeats every row that many times
        before encoding; the decoder collapses each group of
        `data_repeats` decoded frames back into one row via a per-bin
        median, which is far more robust to localized corruption
        (dropout/clipping bursts, real acoustic noise) at the linear
        cost of `data_repeats`x longer audio. Stored in the header, so
        the decoder needs no external knowledge of it.

    Audio layout: [header x HEADER_REPEATS] + [thumbnail x THUMBNAIL_REPEATS]
    + [data audio, built from data_repeats-times-repeated rows].
    """
    if isinstance(mode, str):
        mode_id = next(i for i, p in AUDIO_PRESETS.items() if p['name'] == mode)
    else:
        mode_id = mode

    if not (1 <= data_repeats <= MAX_DATA_REPEATS):
        raise ValueError(f"data_repeats must be in [1, {MAX_DATA_REPEATS}], got {data_repeats}")

    n_rows, n_cols = image.shape
    processed_image, _weight = apply_preset(image, mode_id)

    # Repeat every row data_repeats times before encoding. audio_to_image
    # doesn't need to change at all -- it just sees a taller image with
    # data_repeats * n_rows frames; the decoder below groups them back.
    expanded_image = np.repeat(processed_image, data_repeats, axis=0)

    header = make_header_frame(n_rows, n_cols, mode_id, data_repeats)
    data_audio, frame_len = image_to_audio(expanded_image, phase_seed=phase_seed)

    # Rebalance the header's amplitude relative to the data audio's peak
    # (see HEADER_AMPLITUDE_SCALE above for why this specific value, and
    # why it can't simply be "as loud as possible" or "as quiet as
    # possible" -- it trades off AWGN robustness against clipping
    # robustness). The thumbnail block gets the same treatment, via
    # THUMBNAIL_AMPLITUDE_SCALE in thumbnail_channel.py.
    header_peak = np.abs(header).max()
    data_peak = np.abs(data_audio).max()
    marker = make_marker()
    marker_peak = np.abs(marker).max()
    if marker_peak > 0 and data_peak > 0:
        marker = marker * (data_peak / marker_peak) * MARKER_AMPLITUDE_SCALE
    if header_peak > 0 and data_peak > 0:
        header = header * (data_peak / header_peak) * HEADER_AMPLITUDE_SCALE

    thumbnail_block = build_thumbnail_block(image, data_peak_for_scaling=data_peak)

    # Repeat the header HEADER_REPEATS times. Each copy is decoded
    # independently at read time and the results are majority-voted --
    # a second, independent layer of protection on top of Hamming(7,4),
    # since the header is still proportionally more exposed to
    # amplitude-based noise than the rest of the signal even after
    # rebalancing (a short, sparse pattern has more of its own samples
    # sitting near peak amplitude than the spread-out data audio does).
    audio_layout = (
        "[marker:%d] + [header×%d] + [thumbnail×%d] + [data]"
        % (MARKER_LEN, HEADER_REPEATS, THUMBNAIL_REPEATS)
    )
    full_audio = np.concatenate(
        [marker] + [header] * HEADER_REPEATS + [thumbnail_block, data_audio]
    )

    peak = np.max(np.abs(full_audio))
    if peak > 0:
        full_audio = full_audio / peak
    return full_audio




def _is_valid_header_fields(n_rows, n_cols, mode_id, data_repeats, max_frame_len):
    if n_cols < 2 or n_cols > MAX_PLAUSIBLE_COLS or 2 * (n_cols - 1) > max_frame_len:
        return False
    if n_rows < 1 or n_rows > MAX_PLAUSIBLE_ROWS:
        return False
    if mode_id not in AUDIO_PRESETS:
        return False
    if not (1 <= data_repeats <= MAX_DATA_REPEATS):
        return False
    return True


def audio_with_header_to_image(audio):
    """
    Decode audio -> image, for audio that STILL HAS the marker preamble
    at sample 0 (the normal clean round-trip case: WAV samples read
    straight from a file you encoded).

    Expected audio layout (from sample 0 of the WAV):
      [marker : MARKER_LEN]
      [header frame × HEADER_REPEATS : HEADER_FRAME_LEN each]
      [thumbnail block : THUMBNAIL_BLOCK_LEN]
      [data audio]

    For captured audio -- where marker.find_marker_offset() has already
    been used to locate and logically strip the marker -- call
    _decode_body() directly with audio starting at the header (i.e.
    `resampled[offset:]` where offset is find_marker_offset()'s return
    value). Do NOT pass that here: this function strips another
    MARKER_LEN samples internally, which would skip straight past the
    real header into the thumbnail block. That mismatch was the actual
    bug behind the corrupted capture-decode header reads -- see
    capture_decode.py.

    Returns (image, n_rows, n_cols, mode_name, source).
      source='full'               -- full data channel decoded.
      source='thumbnail_fallback' -- fell back to thumbnail preview.
    """
    # Strip marker; everything below is in body-relative coordinates.
    return _decode_body(audio[MARKER_LEN:])


def _decode_body(body):
    """Decode audio -> image, for audio where the marker has ALREADY
    been stripped (sample 0 == start of the header). This is what
    audio_with_header_to_image() calls internally after its own strip,
    and what captured-audio callers (capture_decode.py) should call
    directly, since their `offset` from find_marker_offset() already
    points past the marker.

    Body layout:
      [0 .. HEADER_FRAME_LEN*HEADER_REPEATS)   -- header copies
      [HEADER_FRAME_LEN*HEADER_REPEATS ..)      -- thumbnail block
      [HEADER_FRAME_LEN*HEADER_REPEATS + THUMBNAIL_BLOCK_LEN ..) -- data
    """
    _BODY_THUMBNAIL_START = HEADER_FRAME_LEN * HEADER_REPEATS
    _BODY_DATA_START      = _BODY_THUMBNAIL_START + THUMBNAIL_BLOCK_LEN

    n_rows, n_cols, mode_id, data_repeats = _read_header_majority_vote(body)

    if _is_valid_header_fields(n_rows, n_cols, mode_id, data_repeats,
                               len(body) - _BODY_DATA_START):
        frame_len  = 2 * (n_cols - 1)
        data_audio = body[_BODY_DATA_START:]
        expanded   = audio_to_image(data_audio, frame_len, n_rows=n_rows * data_repeats)

        if data_repeats > 1:
            expanded  = expanded.reshape(n_rows, data_repeats, n_cols)
            recovered = np.median(expanded, axis=1)
        else:
            recovered = expanded

        image     = invert_preset(recovered, mode_id)
        mode_name = AUDIO_PRESETS.get(mode_id, {}).get('name', f'unknown({mode_id})')
        return image, n_rows, n_cols, mode_name, 'full'

    # Main header failed -- fall back to the thumbnail.
    thumbnail = decode_thumbnail_block(body, offset=_BODY_THUMBNAIL_START)
    return thumbnail, THUMBNAIL_DIM, THUMBNAIL_DIM, 'thumbnail_fallback', 'thumbnail_fallback'

# NOTE: a second _read_header_majority_vote used to be defined here, doing
# per-copy decode + per-field Counter-based majority voting. It silently
# shadowed the bin-averaging version above (see that function's docstring
# for why bin-averaging is the intended, more robust approach) and was
# actually the one running in production. Removed -- the bin-averaging
# version above is now the only definition.