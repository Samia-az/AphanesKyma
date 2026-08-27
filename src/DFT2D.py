import numpy as np
from image import Image

class DFT2D:
    def __init__(self, image:Image):
        self.I = image.image

    def transform(self):
        F = np.fft.fft2(self.I,axes=(0,1))
        F = np.fft.fftshift(F,axes=(0,1))
        return F.real, F.imag

class InverseDFT2D:
    def __init__(self,real, imag):
        self.F = real + 1j * imag

    def reconstruct(self):
        F = np.fft.ifftshift(self.F,axes=(0,1))
        img = np.fft.ifft2(F,axes=(0,1))
        return np.real(img)