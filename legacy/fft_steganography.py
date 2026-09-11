from pathlib import Path

import numpy as np
from PIL import Image


class FFTSteganographer:
    

    BLOCK_SIZE = 8

    EMBED_POSITIONS = [
        (1, 2),
        (1, 3),
        (2, 1),
        (2, 2),
        (2, 3),
        (3, 1),
        (3, 2),
        (3, 3),
    ]

    QUANTIZATION_STEP = 8

    def __init__(self, quantization_step=None):
        if quantization_step is None:
            quantization_step = self.QUANTIZATION_STEP

        self.quantization_step = quantization_step

    # ==================================================
    # LOAD / SAVE (same as DCTSteganographer)
    # ==================================================

    def load_image(self, image_path):
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image not found:\n{image_path}")

        image = Image.open(image_path)

        return image.convert("L")

    def save_image(self, image_array, output_path):
        output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        image_array = np.clip(image_array, 0, 255)
        image_array = np.rint(image_array).astype(np.uint8)

        image = Image.fromarray(image_array)

        image.save(output_path, format="PNG")

    # ==================================================
    # 2D FFT / IFFT
    # ==================================================

    def apply_fft(self, block):
        return np.fft.fft2(block, norm="ortho")     # add norm="ortho"

    def apply_ifft(self, coefficients):
        return np.fft.ifft2(coefficients, norm="ortho").real   # add norm="ortho"

    # ==================================================
    # QIM ON MAGNITUDE
    # ==================================================

    def _embed_magnitude(self, coefficient, bit):
        q = self.quantization_step

        magnitude = np.abs(coefficient)
        phase = np.angle(coefficient)

        index = int(round(magnitude / q))

        if index % 2 != bit:
            lower = index - 1
            upper = index + 1

            if lower < 0:
                index = upper
            else:
                lower_distance = abs(magnitude - lower * q)
                upper_distance = abs(magnitude - upper * q)

                index = lower if lower_distance <= upper_distance else upper

        new_magnitude = index * q

        return new_magnitude * np.exp(1j * phase)

    def _extract_magnitude(self, coefficient):
        q = self.quantization_step

        magnitude = np.abs(coefficient)
        index = int(round(magnitude / q))

        return index % 2

    # ==================================================
    # CAPACITY (identical formula to DCTSteganographer)
    # ==================================================

    def calculate_capacity(self, image_array):
        height, width = image_array.shape

        blocks_vertical = height // self.BLOCK_SIZE
        blocks_horizontal = width // self.BLOCK_SIZE
        total_blocks = blocks_vertical * blocks_horizontal

        bits_per_block = len(self.EMBED_POSITIONS)
        capacity_bits = total_blocks * bits_per_block
        capacity_bytes = capacity_bits // 8

        return {
            "blocks": total_blocks,
            "bits_per_block": bits_per_block,
            "bits": capacity_bits,
            "bytes": capacity_bytes,
        }

    # ==================================================
    # EMBED
    # ==================================================

    def embed_bits(self, image_array, bits):
        capacity = self.calculate_capacity(image_array)

        if len(bits) > capacity["bits"]:
            raise ValueError(
                "Payload is too large!\n"
                f"Required: {len(bits)} bits\n"
                f"Available: {capacity['bits']} bits"
            )

        image_array = image_array.astype(float).copy()
        height, width = image_array.shape

        bit_index = 0
        N = self.BLOCK_SIZE

        for row in range(0, height - N + 1, N):
            for col in range(0, width - N + 1, N):
                if bit_index >= len(bits):
                    return image_array

                block = image_array[row:row + N, col:col + N].copy()
                coefficients = self.apply_fft(block)

                for position in self.EMBED_POSITIONS:
                    if bit_index >= len(bits):
                        break

                    r, c = position
                    bit = int(bits[bit_index])

                    new_value = self._embed_magnitude(coefficients[r, c], bit)
                    coefficients[r, c] = new_value

                    # Enforce conjugate symmetry so the block stays
                    # real after ifft2.
                    mirror_r = (-r) % N
                    mirror_c = (-c) % N
                    coefficients[mirror_r, mirror_c] = np.conj(new_value)

                    bit_index += 1

                modified_block = self.apply_ifft(coefficients)
                image_array[row:row + N, col:col + N] = modified_block

        return image_array

    # ==================================================
    # EXTRACT
    # ==================================================

    def extract_bits(self, image_array, number_of_bits):
        image_array = image_array.astype(float)
        height, width = image_array.shape

        bits = []
        N = self.BLOCK_SIZE

        for row in range(0, height - N + 1, N):
            for col in range(0, width - N + 1, N):
                if len(bits) >= number_of_bits:
                    return "".join(bits)[:number_of_bits]

                block = image_array[row:row + N, col:col + N]
                coefficients = self.apply_fft(block)

                for position in self.EMBED_POSITIONS:
                    if len(bits) >= number_of_bits:
                        return "".join(bits)[:number_of_bits]

                    r, c = position
                    bit = self._extract_magnitude(coefficients[r, c])
                    bits.append(str(bit))

        result = "".join(bits)

        if len(result) < number_of_bits:
            raise ValueError("Not enough data in the stego image.")

        return result[:number_of_bits]

    # ==================================================
    # MSE / PSNR (identical formulas to DCTSteganographer)
    # ==================================================

    def calculate_mse(self, original, modified):
        difference = original.astype(float) - modified.astype(float)
        return np.mean(difference ** 2)

    def calculate_psnr(self, original, modified):
        mse = self.calculate_mse(original, modified)

        if mse == 0:
            return float("inf")

        return 10 * np.log10((255 ** 2) / mse)
