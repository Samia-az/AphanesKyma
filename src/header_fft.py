"""
header_fft.py
-------------
Self-describing header for the row-wise FFT image<->audio scheme.

Embeds n_rows / n_cols into a fixed-length header frame at the start of
the audio, protected with Hamming(7,4), so a decoder that only has the
.wav file (no access to the original image) can still figure out how
to parse the rest of the audio -- and can survive some bit noise while
doing so.
"""

import numpy as np

HEADER_FRAME_LEN = 512          # fixed , known
HEADER_BITS_PER_VALUE = 16      # bits used to encode each of n_rows, n_cols
HEADER_N_COLS = HEADER_FRAME_LEN // 2 + 1  # rFFT bins available in header frame

# --------------------------------------------------------------------------
# Hamming(7,4): protects 4 data bits with 3 parity bits, corrects 1-bit errors
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

def make_header_frame(n_rows, n_cols, on_amplitude=40.0):
    """
    Build the time-domain header frame (length HEADER_FRAME_LEN) that
    encodes n_rows and n_cols, Hamming-protected, as an on/off pattern
    across frequency bins.
    """
    bits = np.concatenate([
        int_to_bits(n_rows, HEADER_BITS_PER_VALUE),
        int_to_bits(n_cols, HEADER_BITS_PER_VALUE),
    ])
    coded = bits_to_hamming_stream(bits)  # 32 bits -> 56 coded bits

    if len(coded) > HEADER_N_COLS:
        raise ValueError("Header doesn't fit in HEADER_FRAME_LEN; increase it.")

    magnitude = np.zeros(HEADER_N_COLS)
    magnitude[:len(coded)] = coded * on_amplitude
    # zero phase for the header keeps it simple/deterministic
    spectrum = magnitude.astype(np.complex128)
    frame = np.fft.irfft(spectrum, n=HEADER_FRAME_LEN)
    return frame


def read_header_frame(frame, threshold_ratio=0.5):
    """
    Given the first HEADER_FRAME_LEN samples of audio, recover
    (n_rows, n_cols), correcting up to 1 bit of noise per 7-bit chunk.
    """
    spectrum = np.fft.rfft(frame, n=HEADER_FRAME_LEN)
    magnitude = np.abs(spectrum)

    n_coded_bits = 2 * ((HEADER_BITS_PER_VALUE + 3) // 4) * 7  # bits per value padded to x4, *7 for hamming
    coded_region = magnitude[:n_coded_bits]

    thresh = coded_region.max() * threshold_ratio if coded_region.max() > 0 else 0
    coded_bits = (coded_region > thresh).astype(int)

    bits = hamming_stream_to_bits(coded_bits, 2 * HEADER_BITS_PER_VALUE)
    n_rows = bits_to_int(bits[:HEADER_BITS_PER_VALUE])
    n_cols = bits_to_int(bits[HEADER_BITS_PER_VALUE:])
    return n_rows, n_cols


# --------------------------------------------------------------------------
# Full pipeline: image -> self-describing audio -> image
# --------------------------------------------------------------------------

from image_audio_fft import image_to_audio, audio_to_image  # noqa: E402


def image_to_audio_with_header(image, phase_seed=0):
    """
    Encode image -> audio, prepending a Hamming-protected header frame
    that records (n_rows, n_cols) so the audio is fully self-describing.
    """
    n_rows, n_cols = image.shape
    header = make_header_frame(n_rows, n_cols)
    data_audio, frame_len = image_to_audio(image, phase_seed=phase_seed)
    full_audio = np.concatenate([header, data_audio])

    peak = np.max(np.abs(full_audio))
    if peak > 0:
        full_audio = full_audio / peak
    return full_audio


def audio_with_header_to_image(audio):
    """
    Decode audio -> image using only what's embedded in the audio itself
    (no external knowledge of the original image's shape needed).
    """
    header_frame = audio[:HEADER_FRAME_LEN]
    n_rows, n_cols = read_header_frame(header_frame)
    frame_len = 2 * (n_cols - 1)

    data_audio = audio[HEADER_FRAME_LEN:]
    image = audio_to_image(data_audio, frame_len, n_rows=n_rows)
    return image, n_rows, n_cols