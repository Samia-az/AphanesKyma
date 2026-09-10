import numpy as np 
import matplotlib.pyplot as plt
import wave
from imageio.v2 import imread

from image import *
from DFT2D import *
from image_audio_fft import *
from header_fft import *
from noise_simulation import *

imagepath = 'D:/project/AphanesKyma/src/buet.jpg'
# imagepath = 'D:/project/AphanesKyma/src/autumn-leaves.jpg'
# test = Image(imagepath)
# print(test.x)
# print('\n')
# print(test.y)
# test.show()
# dft = DFT2D(test)
# real, imag = dft.transform()
# idft = InverseDFT2D(real, imag)
# img = idft.reconstruct()
# test.show()
# test2 = ImageConstruct([[0,0.3,0.6,0.9],
#                         [.15,0.3,0.6,0.9],
#                         [.3,0.3,0.2,1],
#                         [.5,0.2,0.6,0.8],
#                         [.6,0.3,0.9,0]])
# test2.show(cmap='plasma')

def load_wav(path):
    with wave.open(path, 'r') as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        audio_int16 = np.frombuffer(raw, dtype=np.int16)
        audio = audio_int16.astype(np.float64) / 32767.0
    return audio

# audio = load_wav('D:/project/AphanesKyma/src/demo.wav')

# frame_len = 256   
# n_rows = 80        
# recon = audio_to_image(audio, frame_len, n_rows=n_rows)
# recon_img = magnitude_to_image_uint8(recon)

# plt.imshow(recon_img, cmap='inferno', origin='lower', aspect='auto')
# plt.title('Reconstructed image from audio')
# plt.show()


img_array = imread(imagepath)
print('raw image shape:', img_array.shape)
if img_array.ndim == 3:
    img_gray = img_array[:,:,0].astype(np.float64)
else:
    img_gray = img_array.astype(np.float64)

mag_img = normalize_image_to_magnitude(img_gray)

audio = image_to_audio_with_header(mag_img, mode = 'very_listenable')
# mode options: 'fidelity', 'balanced', 'listenable', 'very_listenable'

print('audio length: ',len(audio),'durtion sec: ',len(audio)/22000)


audio_int16 = (audio * 32767 * 0.9).astype(np.int16)
with wave.open('D:/project/AphanesKyma/src/buet_audio.wav', 'w') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(22000)
    wf.writeframes(audio_int16.tobytes())

# simulate noise using one from['none', 'awgn', 'clipping', 'dropout', 'bandlimit']
noisy_audio = apply_noise(audio, noise_type='clipping',severity= 0.5)
# reconstruct back from the freshly-generated audio to verify it round-trips
recon,nrows, ncols,mode_used = audio_with_header_to_image(noisy_audio)
recon_img = magnitude_to_image_uint8(recon)
print(f"reconstructed with ({nrows}, {ncols}) , mode = {mode_used}")
 
plt.imshow(recon_img, cmap='inferno', origin='lower', aspect='auto')
plt.title('Reconstructed image from generated audio')
plt.show()