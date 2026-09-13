"""
hamming_bits.py
-----------------
Hamming(7,4) single-bit-error-correcting code, plus small bit-packing
helpers, shared by header_fft.py (the main header) and
thumbnail_channel.py (the low-res fallback channel). Split out into its
own module purely so those two can both use it without importing each
other.
"""

import numpy as np

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