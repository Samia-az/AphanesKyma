"""
denoise.py
-----------

Different noise types leave different characteristic artifacts (see
noise_simulation.py), so different denoising methods suit them best:
    - 'median'   : best against impulsive/salt-and-pepper-like noise
                   (clipping, dropout) -- isolated bad pixels get
                   replaced by their neighborhood's median.
    - 'blur'     : best against fine broadband speckle (AWGN) -- a
                   simple box blur averages out per-pixel noise.
    - 'spectral' : general-purpose -- natural images concentrate most
                   of their energy in low spatial frequencies, so a 2D
                   DFT low-pass keeps that structure while suppressing
                   broadband noise energy sitting in the high
                   frequencies.
    - 'none'     : passthrough, for A/B comparison.
"""

import numpy as np

DENOISE_METHODS = ['none', 'median', 'blur', 'spectral']


def denoise_none(image, **kwargs):
    return image.copy()


def denoise_median(image, kernel_size=3, **kwargs):
    """2D median filter, implemented with numpy only via a sliding
    window view (no scipy dependency)."""
    k = kernel_size
    pad = k // 2
    padded = np.pad(image, pad, mode='edge')
    windows = np.lib.stride_tricks.sliding_window_view(padded, (k, k))
    return np.median(windows, axis=(-2, -1))


def denoise_blur(image, kernel_size=3, **kwargs):
    """Simple separable box blur (two 1D convolutions), numpy only."""
    k = kernel_size
    kernel = np.ones(k) / k
    out = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode='same'), axis=1, arr=image)
    out = np.apply_along_axis(lambda col: np.convolve(col, kernel, mode='same'), axis=0, arr=out)
    return out


def denoise_spectral(image, keep_fraction=0.35, **kwargs):
    """2D DFT low-pass denoising: keep only the low spatial-frequency
    content (where a natural image's real structure lives) and discard
    the rest (where broadband noise energy tends to sit)."""
    spectrum = np.fft.fft2(image)
    spectrum_shifted = np.fft.fftshift(spectrum)

    rows, cols = image.shape
    cy, cx = rows // 2, cols // 2
    radius_y = int(rows * keep_fraction / 2)
    radius_x = int(cols * keep_fraction / 2)

    mask = np.zeros((rows, cols), dtype=bool)
    mask[max(0, cy - radius_y):cy + radius_y, max(0, cx - radius_x):cx + radius_x] = True

    spectrum_filtered = spectrum_shifted * mask
    spectrum_unshifted = np.fft.ifftshift(spectrum_filtered)
    denoised = np.fft.ifft2(spectrum_unshifted).real
    return denoised


_DENOISE_FUNCS = {
    'none': denoise_none,
    'median': denoise_median,
    'blur': denoise_blur,
    'spectral': denoise_spectral,
}


def denoise_image(image, method='median', **kwargs):
    """
    Apply a predefined, user-selected denoising method to a (possibly
    noisy) reconstructed image.

    Parameters
    ----------
    image : np.ndarray
        The image as recovered by audio_with_header_to_image().
    method : str
        One of DENOISE_METHODS: 'none', 'median', 'blur', 'spectral'.
    kwargs : passed through to the specific method
        - median/blur: kernel_size (default 3)
        - spectral: keep_fraction (default 0.35)
    """
    if method not in _DENOISE_FUNCS:
        raise ValueError(f"method must be one of {DENOISE_METHODS}, got {method!r}")
    return _DENOISE_FUNCS[method](image, **kwargs)


# --------------------------------------------------------------------------
# Recommended method per noise type
# --------------------------------------------------------------------------
# Determined empirically (see project notes): each noise type leaves a
# differently-shaped artifact, so no single method is best across all of
# them.
#   - awgn:      fine per-pixel speckle -> median wins clearly, and the
#                benefit grows with noise severity.
#   - clipping:  impulsive/extreme-value artifacts -> median helps most
#                at light severity, blur pulls ahead at heavier severity.
#                median is used as the single default since it is never
#                far behind blur and is cheaper to reason about.
#   - dropout:   short zeroed-out bursts/bands, not isolated speckle ->
#                median (which looks at a small local neighborhood)
#                barely helps; blur's wider averaging recovers more.
#   - bandlimit: this noise IS already a smoothing/blur operation on the
#                signal -- applying another blur or low-pass on top only
#                loses more real detail without removing anything
#                further, so the recommendation is to apply no
#                denoising at all.
RECOMMENDED_DENOISE = {
    'none': 'none',
    'awgn': 'median',
    'clipping': 'median',
    'dropout': 'blur',
    'bandlimit': 'none',
}


def recommend_denoise_method(noise_type):
    return RECOMMENDED_DENOISE.get(noise_type, 'median')