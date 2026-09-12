"""
preprocessing.py
------------------
Image preprocessing for the pipeline.

"""

import numpy as np
from PIL import Image as PILImage

DEFAULT_MAX_DIMENSION = 512


def resize_for_audio(image_array, max_dimension=DEFAULT_MAX_DIMENSION):
    image_array = np.asarray(image_array)
    h, w = image_array.shape[:2]

    if max(h, w) <= max_dimension:
        return image_array

    scale = max_dimension / max(h, w)
    new_h = max(1, int(round(h * scale)))
    new_w = max(1, int(round(w * scale)))

    pil_img = PILImage.fromarray(image_array.astype(np.uint8))
    resized = pil_img.resize((new_w, new_h), PILImage.LANCZOS)
    return np.array(resized)


def estimate_audio_duration(n_rows, n_cols, sample_rate=44100):
    frame_len = 2 * (n_cols - 1)
    return n_rows * frame_len / sample_rate