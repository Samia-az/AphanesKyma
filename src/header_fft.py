"""
header_fft.py
-------------
Self-describing header for the row-wise FFT image<->audio scheme.

Embeds n_rows / n_cols / audio_mode into a fixed-length header frame at
the start of the audio, protected with Hamming(7,4)
"""

import numpy as np
from image_audio_fft import image_to_audio, audio_to_image, SAMPLE_RATE

HEADER_FRAME_LEN = 512          # fixed & known 
HEADER_BITS_PER_VALUE = 16      # bits used to encode each of n_rows, n_cols
HEADER_MODE_BITS = 4            # bits used to encode the audio mode/preset id
HEADER_N_COLS = HEADER_FRAME_LEN // 2 + 1  # rFFT bins available in header frame
HEADER_REPEATS = 3              
HEADER_AMPLITUDE_SCALE = 0.35   

# --------------------------------------------------------------------------
# Hamming(7,4)
# --------------------------------------------------------------------------

_G = np.array([  # generator matrix (4 data bits -> 7 coded bits)
    [1,1,0,1],
    [1,0,1,1],
    [1,0,0,0],
    [0,1,1,1],
    [0,1,0,0],
    [0,0,1,0],
    [0,0,0,1],
]) % 2

_H = np.array([  # parity-check matrix
    [1,0,1,0,1,0,1],
    [0,1,1,0,0,1,1],
    [0,0,0,1,1,1,1],
]) % 2

_R = np.array([  # extracts the 4 data bits from a corrected 7-bit codeword
    [0,0,1,0,0,0,0],
    [0,0,0,0,1,0,0],
    [0,0,0,0,0,1,0],
    [0,0,0,0,0,0,1],
]) % 2


def hamming74_encode(bits4):
    """bits4: array of 4 bits -> returns array of 7 coded bits."""
    return (_G @ bits4) % 2


def hamming74_decode(bits7):
    """bits7: array of 7 (possibly noisy) bits -> corrects a single-bit
    error if present, returns the original 4 data bits."""
    bits7 = np.array(bits7, dtype=int) % 2
    syndrome = (_H @ bits7) % 2
    error_pos = syndrome[0] * 1 + syndrome[1] * 2 + syndrome[2] * 4
    if error_pos != 0:
        bits7 = bits7.copy()
        bits7[error_pos - 1] ^= 1  # flip the bad bit
    return (_R @ bits7) % 2


def bits_to_hamming_stream(bits):
    """Encode an arbitrary-length bit array in chunks of 4 -> 7-bit codewords."""
    pad = (-len(bits)) % 4
    bits = np.concatenate([bits, np.zeros(pad, dtype=int)])
    out = []
    for i in range(0, len(bits), 4):
        out.append(hamming74_encode(bits[i:i+4]))
    return np.concatenate(out)


def hamming_stream_to_bits(coded_bits, n_out_bits):
    """Decode a 7-bit-codeword stream back to data bits, trimmed to n_out_bits."""
    out = []
    for i in range(0, len(coded_bits), 7):
        chunk = coded_bits[i:i+7]
        if len(chunk) < 7:
            break
        out.append(hamming74_decode(chunk))
    bits = np.concatenate(out) if out else np.zeros(0, dtype=int)
    return bits[:n_out_bits]


def int_to_bits(value, n_bits):
    return np.array([(value >> (n_bits - 1 - i)) & 1 for i in range(n_bits)])


def bits_to_int(bits):
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return value


# --------------------------------------------------------------------------
# Header <-> audio frame
# --------------------------------------------------------------------------

def make_header_frame(n_rows, n_cols, mode_id=0, on_amplitude=40.0):
    """
    Build the time-domain header frame (length HEADER_FRAME_LEN) that
    encodes n_rows, n_cols, and mode_id, Hamming-protected, as an
    on/off pattern across frequency bins.
    """
    bits = np.concatenate([
        int_to_bits(n_rows, HEADER_BITS_PER_VALUE),
        int_to_bits(n_cols, HEADER_BITS_PER_VALUE),
        int_to_bits(mode_id, HEADER_MODE_BITS),
    ])
    coded = bits_to_hamming_stream(bits)

    if len(coded) > HEADER_N_COLS:
        raise ValueError("Header doesn't fit in HEADER_FRAME_LEN; increase it.")

    magnitude = np.zeros(HEADER_N_COLS)
    magnitude[:len(coded)] = coded * on_amplitude

    spectrum = magnitude.astype(np.complex128)
    frame = np.fft.irfft(spectrum, n=HEADER_FRAME_LEN)
    return frame


def read_header_frame(frame, threshold_ratio=0.5):
    """
    Given the first HEADER_FRAME_LEN samples of audio, recover
    (n_rows, n_cols, mode_id), correcting up to 1 bit of noise per
    7-bit chunk.
    """
    spectrum = np.fft.rfft(frame, n=HEADER_FRAME_LEN)
    magnitude = np.abs(spectrum)

    total_data_bits = 2 * HEADER_BITS_PER_VALUE + HEADER_MODE_BITS
    n_chunks = -(-total_data_bits // 4)  
    n_coded_bits = n_chunks * 7
    coded_region = magnitude[:n_coded_bits]

    thresh = coded_region.max() * threshold_ratio if coded_region.max() > 0 else 0
    coded_bits = (coded_region > thresh).astype(int)

    bits = hamming_stream_to_bits(coded_bits, n_chunks * 4)
    n_rows = bits_to_int(bits[:HEADER_BITS_PER_VALUE])
    n_cols = bits_to_int(bits[HEADER_BITS_PER_VALUE:2 * HEADER_BITS_PER_VALUE])
    mode_id = bits_to_int(bits[2 * HEADER_BITS_PER_VALUE:2 * HEADER_BITS_PER_VALUE + HEADER_MODE_BITS])
    return n_rows, n_cols, mode_id


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

 


def image_to_audio_with_header(image, mode='listenable', phase_seed=0):
    """
    Encode image -> audio

    mode : str or int
        One of AUDIO_PRESETS' names ('fidelity', 'balanced',
        'listenable', 'very_listenable') or its integer id.
    """
    if isinstance(mode, str):
        mode_id = next(i for i, p in AUDIO_PRESETS.items() if p['name'] == mode)
    else:
        mode_id = mode

    n_rows, n_cols = image.shape
    processed_image, _weight = apply_preset(image, mode_id)

    header = make_header_frame(n_rows, n_cols, mode_id)
    data_audio, frame_len = image_to_audio(processed_image, phase_seed=phase_seed)

    # Rebalance the header's amplitude relative to the data audio's peak
    # (see HEADER_AMPLITUDE_SCALE above for why this specific value, and
    # why it can't simply be "as loud as possible" or "as quiet as
    # possible" -- it trades off AWGN robustness against clipping
    # robustness).
    header_peak = np.abs(header).max()
    data_peak = np.abs(data_audio).max()
    if header_peak > 0 and data_peak > 0:
        header = header * (data_peak / header_peak) * HEADER_AMPLITUDE_SCALE

    # Repeat the header HEADER_REPEATS times. Each copy is decoded
    # independently at read time and the results are majority-voted --
    # a second, independent layer of protection on top of Hamming(7,4),
    # since the header is still proportionally more exposed to
    # amplitude-based noise than the rest of the signal even after
    # rebalancing (a short, sparse pattern has more of its own samples
    # sitting near peak amplitude than the spread-out data audio does).
    full_audio = np.concatenate([header] * HEADER_REPEATS + [data_audio])

    peak = np.max(np.abs(full_audio))
    if peak > 0:
        full_audio = full_audio / peak
    return full_audio


def _is_valid_header_fields(n_rows, n_cols, mode_id, max_frame_len):
    """Shared sanity check for a decoded (n_rows, n_cols, mode_id) triple.
    Under noise (or, for captured audio, simple misalignment) the header
    can decode to nonsensical values -- e.g. because the Hamming code
    corrected the wrong bit for a multi-bit error it can't actually fix.
    Used both by the normal decode path (to fail clearly rather than try
    to process garbage dimensions) and by find_header_offset() in
    capture_decode.py (to tell a correctly-aligned header apart from
    noise/misalignment while searching)."""
    if n_cols < 2 or 2 * (n_cols - 1) > max_frame_len:
        return False
    if n_rows < 1 or n_rows > 100000:
        return False
    return True


def audio_with_header_to_image(audio):
    """
    Decode audio -> image using only what's embedded in the audio itself
    (no external knowledge of the original image's shape OR the encoding
    preset needed -- both are recovered from the header).

    Assumes the header starts at sample 0 of `audio` -- for audio that
    was captured live (mic recording, unknown start offset), locate the
    correct starting offset first with capture_decode.find_header_offset()
    and pass audio[offset:] in here instead.
    """
    n_rows, n_cols, mode_id = _read_header_majority_vote(audio)

    # Rather than attempt to process garbage dimensions (which can be
    # extremely slow or fail deep inside numpy), fail clearly here so
    # the caller knows this noise/misalignment exceeded what the
    # header's error correction could survive.
    if not _is_valid_header_fields(n_rows, n_cols, mode_id, len(audio)):
        raise ValueError(
            f"Header could not be reliably recovered (decoded n_rows={n_rows}, "
            f"n_cols={n_cols}) -- noise severity (or, for captured audio, "
            f"misalignment) likely exceeded what the header's error "
            f"correction can survive."
        )

    frame_len = 2 * (n_cols - 1)
    data_audio = audio[HEADER_FRAME_LEN * HEADER_REPEATS:]
    recovered = audio_to_image(data_audio, frame_len, n_rows=n_rows)
    image = invert_preset(recovered, mode_id)

    mode_name = AUDIO_PRESETS.get(mode_id, {}).get('name', f'unknown({mode_id})')
    return image, n_rows, n_cols, mode_name


def _read_header_copies(audio, offset=0):
    """Read all HEADER_REPEATS copies of the header starting at `offset`,
    WITHOUT voting them together -- returns the list of raw
    (n_rows, n_cols, mode_id) triples, one per copy. Used by
    capture_decode.find_header_offset(), which needs to check whether
    the copies genuinely agree with each other (a much stronger signal
    than any single copy merely passing the loose bounds check) rather
    than accepting whatever per-field majority voting produces -- voting
    always returns *some* value even when the three copies have nothing
    in common, which makes it unsuitable on its own for telling a real,
    aligned header apart from an arbitrary offset into ordinary audio."""
    out = []
    for i in range(HEADER_REPEATS):
        start = offset + i * HEADER_FRAME_LEN
        segment = audio[start:start + HEADER_FRAME_LEN]
        if len(segment) < HEADER_FRAME_LEN:
            out.append((-1, -1, -1))
            continue
        out.append(read_header_frame(segment))
    return out


def _read_header_majority_vote(audio, offset=0):
    """Read all HEADER_REPEATS copies of the header starting at `offset`
    samples into `audio`, decode each independently, and majority-vote
    each field. This survives noise that badly corrupts one or two
    copies (e.g. clipping, which hits the header harder than the data
    audio) as long as a majority of copies still decode correctly.

    `offset` defaults to 0 (the normal case: audio you encoded/wrote
    yourself, header at the very start). capture_decode.py's search
    passes different candidate offsets to find where a real mic
    recording's header actually begins."""
    from collections import Counter

    votes_rows, votes_cols, votes_mode = [], [], []
    for i in range(HEADER_REPEATS):
        start = offset + i * HEADER_FRAME_LEN
        segment = audio[start:start + HEADER_FRAME_LEN]
        if len(segment) < HEADER_FRAME_LEN:
            return -1, -1, -1  # not enough audio left at this offset
        n_rows, n_cols, mode_id = read_header_frame(segment)
        votes_rows.append(n_rows)
        votes_cols.append(n_cols)
        votes_mode.append(mode_id)

    n_rows = Counter(votes_rows).most_common(1)[0][0]
    n_cols = Counter(votes_cols).most_common(1)[0][0]
    mode_id = Counter(votes_mode).most_common(1)[0][0]
    return n_rows, n_cols, mode_id