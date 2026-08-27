import numpy as np 
import matplotlib.pyplot as plt
import wave
from imageio.v2 import imread

from image import *
from DFT2D import *
from image_audio_fft import *

imagepath = 'D:/project/AphanesKyma/src/buet.jpg'
test = Image(imagepath)
print(test.x)
print('\n')
print(test.y)
test.show()
dft = DFT2D(test)
real, imag = dft.transform()
idft = InverseDFT2D(real, imag)
img = idft.reconstruct()
test.show()
test2 = ImageConstruct([[0,0.3,0.6,0.9],
                        [.15,0.3,0.6,0.9],
                        [.3,0.3,0.2,1],
                        [.5,0.2,0.6,0.8],
                        [.6,0.3,0.9,0]])
test2.show(cmap='plasma')

def load_wav(path):
    with wave.open(path, 'r') as wf:
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)
        audio_int16 = np.frombuffer(raw, dtype=np.int16)
        audio = audio_int16.astype(np.float64) / 32767.0
    return audio

audio = load_wav('D:/project/AphanesKyma/src/demo.wav')

frame_len = 256   
n_rows = 80        
recon = audio_to_image(audio, frame_len, n_rows=n_rows)
recon_img = magnitude_to_image_uint8(recon)

plt.imshow(recon_img, cmap='inferno', origin='lower', aspect='auto')
plt.title('Reconstructed image from audio')
plt.show()