import numpy as np

from image import *
# image to audio

def image_to_audio(image, sample_rate = 44100, hop = None, phase_seed = 0, window = None, phase_mode = 'fixed'):
    image = np.asarray(image, dtype= np.float64)
    n_rows, n_cols = image.shape
    frm_len = 2 * (n_cols -1)
    if hop is None:
        hop = frm_len
    rng = np.random.default_rng(phase_seed)
    total_len = hop* ( n_rows-1) + frm_len
    audio = np.zeros(total_len, dtype= np.float64)
    norm = np.zeros(total_len, dtype = np.float64)

    if window is None:
        window = np.ones(frm_len)

    fixed_phase = rng.uniform(-np.pi, np.pi, size = n_cols)

    for i in range(n_rows):
        magnitude = image[i]
        if phase_mode == 'fixed':
            phase = fixed_phase
        else :
            phase = rng.uniform(-np.pi, np.pi, size = n_cols)
        spectrum = magnitude * np.exp(1j*phase)
        frame = np.fft.irfft(spectrum, n= frm_len)
        frame = frame * window

        start = i * hop
        audio[start:start+frm_len] +=frame
        norm[start: start+frm_len] += window

    norm[norm == 0] = 1.0
    audio = audio/norm

    peak = np.max(np.abs(audio))
    if peak>0:
        audio = audio/peak

    return audio, frm_len

# audio to image
def audio_to_image(audio, frm_len, hop= None, n_rows = None):
    audio = np.asarray(audio, dtype = np.float64)
    if hop is None:
        hop = frm_len

    max_start = len(audio) - frm_len
    n_frames = max_start // hop + 1 if max_start>=0 else 0
    if n_rows is not None:
        n_frames = n_rows

    n_cols = frm_len//2 + 1
    image = np.zeros((n_frames, n_cols),dtype= np.float64)

    for i in range(n_frames):
        start = i* hop
        frame = audio[start: start+frm_len]
        if len(frame)<frm_len:
            frame = np.pad(frame, (0,frm_len-len(frame)))

        spectrum = np.fft.rfft(frame)
        image[i] = np.abs(spectrum)

    return image



#helpers

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