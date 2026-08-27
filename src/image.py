import numpy as np
import matplotlib.pyplot as plt
from imageio.v2 import imread


class Image:
    def __init__(self, image_path, normalize=True, keep_alpha=False):
        img = imread(image_path)
        self.origdtype = img.dtype
        img = img.astype(np.float64)

        if img.ndim == 2:
            self.image = img

        elif img.ndim == 3:
            if img.shape[2] == 3:
                self.image = img

            elif img.shape[2] == 4:
                if keep_alpha:
                    self.image = img
                else:
                    # Ignore alpha channel
                    self.image = img[:, :, :3]

            else:
                raise ValueError(f"Unsupported number of channels: {img.shape[2]}")

        else:
            raise ValueError(f"Unsupported image dimensions: {img.shape}")

        if normalize:
            self._normalize()

        
        height, width = self.image.shape[:2]

        self.x = np.linspace(-1, 1, width)
        self.y = np.linspace(-1, 1, height)

    def _normalize(self):
        if np.issubdtype(self.origdtype, np.integer):
            info = np.iinfo(self.origdtype)
            self.image /= info.max

        else:
            min_val = np.min(self.image)
            max_val = np.max(self.image)

            if min_val >= 0 and max_val <= 1:
                # Already normalized
                return

            if max_val == min_val:
                self.image[:] = 0
            else:
                self.image = ((self.image - min_val)/ (max_val - min_val))

    def show(self, title="Image"):
        plt.figure()

        if self.image.ndim == 2:
            # Grayscale
            plt.imshow(
                self.image,
                cmap="gray",
                vmin=0,
                vmax=1
            )

        elif self.image.shape[2] == 3:
            # RGB
            plt.imshow(
                np.clip(self.image, 0, 1)
            )

        elif self.image.shape[2] == 4:
            # RGBA
            plt.imshow(
                np.clip(self.image, 0, 1)
            )

        plt.title(title)
        plt.axis("off")
        plt.show()


class ImageConstruct:
    def __init__(self, pix_val:np.ndarray):
        self.pix_val = pix_val

    def show(self, title="Image", cmap='gray', vmin = 0, vmax = 1):
        plt.imshow(np.clip(self.pix_val,vmin, vmax), cmap=cmap, vmin=vmin, vmax= vmax)
        plt.title(title)
        plt.axis("off")
        plt.show()

