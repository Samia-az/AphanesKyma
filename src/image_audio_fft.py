import numpy as np
SAMPLE_RATE = 48000

# image to audio
#
# --------------------------------------------------------------------------
# Phase generators
# --------------------------------------------------------------------------

def _pin_dc_nyquist(phase, frm_len):
    """np.fft.irfft only uses the *real* part of bin 0 and the Nyquist
    bin (frm_len is always even here, so there always is one) -- any
    imaginary component placed there is silently dropped, which quietly
    attenuates those two columns on decode (recovered magnitude becomes
    magnitude*|cos(phase)| instead of magnitude). Pinning both to 0
    makes those two columns exact again, regardless of phase_mode."""
    phase = np.array(phase, dtype=np.float64, copy=True)
    phase[0] = 0.0
    phase[-1] = 0.0
    return phase


def phase_zero(n_cols, frm_len, **kwargs):
    """Every bin in phase. Turns each frame into a single sharp,
    symmetric pulse instead of hiss -- cheapest thing to try."""
    return _pin_dc_nyquist(np.zeros(n_cols), frm_len)


def phase_chirp(n_cols, frm_len, chirp_coeff=0.5, **kwargs):
    """Quadratic phase ramp -- spreads each frame's energy into a short
    sweep instead of a spike or hiss."""
    k = np.arange(n_cols)
    phase = chirp_coeff * (k ** 2) / max(n_cols, 1)
    return _pin_dc_nyquist(phase, frm_len)


def phase_random(n_cols, frm_len, rng, **kwargs):
    """Original behaviour: independent uniform-random phase per bin.
    This is what produces broadband-hiss-like audio. Kept so you can
    A/B directly against it."""
    phase = rng.uniform(-np.pi, np.pi, size=n_cols)
    return _pin_dc_nyquist(phase, frm_len)


def phase_minimum(magnitude, frm_len, **kwargs):
    """Minimum-phase reconstruction via the real cepstrum method: the
    standard vocoder trick for turning a magnitude-only spectral
    envelope into the most natural-sounding causal waveform with that
    envelope. Row-dependent (uses this row's own spectrum), usually
    the least noise-like of these options."""
    n_cols = len(magnitude)
    log_mag = np.log(np.maximum(magnitude, 1e-8))
    full_log_mag = np.concatenate([log_mag, log_mag[-2:0:-1]])  # length frm_len
    cepstrum = np.fft.ifft(full_log_mag).real
    half = frm_len // 2
    w = np.zeros(frm_len)
    w[0] = 1.0
    w[1:half] = 2.0
    w[half] = 1.0
    folded_cepstrum = cepstrum * w
    min_phase_spectrum = np.exp(np.fft.fft(folded_cepstrum))
    phase = np.angle(min_phase_spectrum[:n_cols])
    return _pin_dc_nyquist(phase, frm_len)


def phase_borrowed(n_cols, frm_len, reference_frame, **kwargs):
    """Lift the phase contour off a real reference waveform (resized to
    length frm_len) and reuse it for every row -- closest thing here to
    real phase-vocoder cross-synthesis."""
    reference_frame = np.asarray(reference_frame, dtype=np.float64)
    if len(reference_frame) != frm_len:
        reference_frame = np.resize(reference_frame, frm_len)
    spectrum = np.fft.rfft(reference_frame, n=frm_len)
    return _pin_dc_nyquist(np.angle(spectrum), frm_len)


_PHASE_MODES = {'fixed', 'random_per_row', 'zero', 'chirp', 'minphase', 'borrowed'}


def image_to_audio(image, sample_rate=SAMPLE_RATE, hop=None, phase_seed=0,
                    window=None, phase_mode='fixed', chirp_coeff=0.5,
                    reference_frame=None):
    """
    phase_mode:
      'fixed'          original behaviour -- one random phase drawn once,
                       reused for every row (unchanged default).
      'random_per_row' original 'else' behaviour -- fresh random phase
                       every row.
      'zero'           zero phase every row.
      'chirp'          quadratic phase ramp every row.
      'minphase'       row-dependent minimum-phase reconstruction from
                       that row's own magnitude spectrum.
      'borrowed'       phase lifted from `reference_frame`, reused for
                       every row.
    All modes recover the image identically (up to this mode's own global
    peak-normalization constant) -- see _pin_dc_nyquist's docstring for
    the one correctness fix bundled in here regardless of mode.
    """
    if phase_mode not in _PHASE_MODES:
        raise ValueError(f"phase_mode must be one of {_PHASE_MODES}, got {phase_mode!r}")

    image = np.asarray(image, dtype=np.float64)
    n_rows, n_cols = image.shape
    frm_len = 2 * (n_cols - 1)
    if hop is None:
        hop = frm_len
    rng = np.random.default_rng(phase_seed)
    total_len = hop * (n_rows - 1) + frm_len
    audio = np.zeros(total_len, dtype=np.float64)
    norm = np.zeros(total_len, dtype=np.float64)

    if window is None:
        window = np.ones(frm_len)

    fixed_phase = None
    if phase_mode == 'fixed':
        fixed_phase = _pin_dc_nyquist(rng.uniform(-np.pi, np.pi, size=n_cols), frm_len)
    elif phase_mode == 'zero':
        fixed_phase = phase_zero(n_cols, frm_len)
    elif phase_mode == 'chirp':
        fixed_phase = phase_chirp(n_cols, frm_len, chirp_coeff=chirp_coeff)
    elif phase_mode == 'borrowed':
        if reference_frame is None:
            raise ValueError("phase_mode='borrowed' requires reference_frame")
        fixed_phase = phase_borrowed(n_cols, frm_len, reference_frame)

    for i in range(n_rows):
        magnitude = image[i]

        if phase_mode == 'random_per_row':
            phase = _pin_dc_nyquist(rng.uniform(-np.pi, np.pi, size=n_cols), frm_len)
        elif phase_mode == 'minphase':
            phase = phase_minimum(magnitude, frm_len)
        else:
            phase = fixed_phase

        spectrum = magnitude * np.exp(1j * phase)
        frame = np.fft.irfft(spectrum, n=frm_len)
        frame = frame * window

        start = i * hop
        audio[start:start + frm_len] += frame
        norm[start:start + frm_len] += window

    norm[norm == 0] = 1.0
    audio = audio / norm

    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak

    return audio, frm_len


# audio to image
def audio_to_image(audio, frm_len, hop=None, n_rows=None):
    audio = np.asarray(audio, dtype=np.float64)
    if hop is None:
        hop = frm_len

    max_start = len(audio) - frm_len
    n_frames = max_start // hop + 1 if max_start >= 0 else 0
    if n_rows is not None:
        n_frames = n_rows

    n_cols = frm_len // 2 + 1
    image = np.zeros((n_frames, n_cols), dtype=np.float64)

    for i in range(n_frames):
        start = i * hop
        frame = audio[start:start + frm_len]
        if len(frame) < frm_len:
            frame = np.pad(frame, (0, frm_len - len(frame)))

        spectrum = np.fft.rfft(frame)
        image[i] = np.abs(spectrum)

    return image


# helpers

def normalize_image_to_magnitude(image, target_max=50.0):
    image = np.asarray(image, dtype=np.float64)
    img_max = image.max()
    if img_max == 0:
        return image
    return image / img_max * target_max


def magnitude_to_image_uint8(magnitude_image):
    m = np.asarray(magnitude_image, dtype=np.float64)
    m = m - m.min()
    if m.max() > 0:
        m = m / m.max()
    return (m * 255).astype(np.uint8)