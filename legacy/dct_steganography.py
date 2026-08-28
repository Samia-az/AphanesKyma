from pathlib import Path

import numpy as np
from PIL import Image
from scipy.fftpack import dct, idct


class DCTSteganographer:

    BLOCK_SIZE = 8

    # --------------------------------------------------
    # Mid-frequency coefficients
    #
    # We avoid:
    # (0,0) -> DC component
    #
    # We also avoid the highest frequencies because
    # they are more vulnerable to image distortion.
    # --------------------------------------------------

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

    # --------------------------------------------------
    # Larger value = stronger embedding
    # Smaller value = better visual quality
    #
    # Start with 16.
    # --------------------------------------------------

    QUANTIZATION_STEP = 16


    def __init__(
        self,
        quantization_step=None
    ):

        if quantization_step is None:
            quantization_step = self.QUANTIZATION_STEP

        self.quantization_step = (
            quantization_step
        )


    # ==================================================
    # LOAD IMAGE
    # ==================================================

    def load_image(
        self,
        image_path
    ):

        image_path = Path(
            image_path
        )

        if not image_path.exists():

            raise FileNotFoundError(
                f"Image not found:\n{image_path}"
            )


        image = Image.open(
            image_path
        )


        # Use grayscale for the DCT stage.

        return image.convert("L")


    # ==================================================
    # SAVE IMAGE
    # ==================================================

    def save_image(
        self,
        image_array,
        output_path
    ):

        output_path = Path(
            output_path
        )


        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        image_array = np.clip(
            image_array,
            0,
            255
        )


        image_array = np.rint(
            image_array
        ).astype(
            np.uint8
        )


        image = Image.fromarray(
            image_array
        )


        image.save(
            output_path,
            format="PNG"
        )


    # ==================================================
    # 2D DCT
    # ==================================================

    def apply_dct(
        self,
        block
    ):

        return dct(
            dct(
                block.T,
                norm="ortho"
            ).T,
            norm="ortho"
        )


    # ==================================================
    # 2D IDCT
    # ==================================================

    def apply_idct(
        self,
        coefficients
    ):

        return idct(
            idct(
                coefficients.T,
                norm="ortho"
            ).T,
            norm="ortho"
        )


    # ==================================================
    # QIM EMBEDDING
    # ==================================================

    def _embed_bit(
        self,
        coefficient,
        bit
    ):

        q = self.quantization_step

        sign = 1

        if coefficient < 0:
            sign = -1


        magnitude = abs(
            coefficient
        )


        # Find closest quantization index.

        index = int(
            round(
                magnitude / q
            )
        )


        # We want:
        #
        # even index -> bit 0
        # odd index  -> bit 1

        if index % 2 != bit:

            # Move to nearest index
            # having the required parity.

            lower = index - 1
            upper = index + 1


            if lower < 0:

                index = upper

            else:

                lower_distance = abs(
                    magnitude - lower * q
                )

                upper_distance = abs(
                    magnitude - upper * q
                )


                if lower_distance <= upper_distance:

                    index = lower

                else:

                    index = upper


        return (
            sign
            * index
            * q
        )


    # ==================================================
    # QIM EXTRACTION
    # ==================================================

    def _extract_bit(
        self,
        coefficient
    ):

        q = self.quantization_step


        magnitude = abs(
            coefficient
        )


        index = int(
            round(
                magnitude / q
            )
        )


        return index % 2


    # ==================================================
    # CAPACITY
    # ==================================================

    def calculate_capacity(
        self,
        image_array
    ):

        height, width = (
            image_array.shape
        )


        blocks_vertical = (
            height // self.BLOCK_SIZE
        )


        blocks_horizontal = (
            width // self.BLOCK_SIZE
        )


        total_blocks = (
            blocks_vertical
            * blocks_horizontal
        )


        bits_per_block = (
            len(self.EMBED_POSITIONS)
        )


        capacity_bits = (
            total_blocks
            * bits_per_block
        )


        capacity_bytes = (
            capacity_bits // 8
        )


        return {
            "blocks": total_blocks,
            "bits_per_block": bits_per_block,
            "bits": capacity_bits,
            "bytes": capacity_bytes
        }


    # ==================================================
    # EMBED
    # ==================================================

    def embed_bits(
        self,
        image_array,
        bits
    ):

        capacity = (
            self.calculate_capacity(
                image_array
            )
        )


        if len(bits) > capacity["bits"]:

            raise ValueError(
                "Payload is too large!\n"
                f"Required: {len(bits)} bits\n"
                f"Available: {capacity['bits']} bits"
            )


        image_array = (
            image_array.astype(
                float
            ).copy()
        )


        height, width = (
            image_array.shape
        )


        bit_index = 0


        # ------------------------------------------------
        # Process every 8×8 block
        # ------------------------------------------------

        for row in range(
            0,
            height - self.BLOCK_SIZE + 1,
            self.BLOCK_SIZE
        ):

            for col in range(
                0,
                width - self.BLOCK_SIZE + 1,
                self.BLOCK_SIZE
            ):

                if bit_index >= len(bits):

                    return image_array


                block = image_array[
                    row:row + self.BLOCK_SIZE,
                    col:col + self.BLOCK_SIZE
                ].copy()


                # ----------------------------------------
                # DCT
                # ----------------------------------------

                coefficients = (
                    self.apply_dct(
                        block
                    )
                )


                # ----------------------------------------
                # Embed bits
                # ----------------------------------------

                for position in (
                    self.EMBED_POSITIONS
                ):

                    if bit_index >= len(bits):

                        break


                    r, c = position


                    bit = int(
                        bits[bit_index]
                    )


                    coefficients[
                        r,
                        c
                    ] = self._embed_bit(
                        coefficients[
                            r,
                            c
                        ],
                        bit
                    )


                    bit_index += 1


                # ----------------------------------------
                # IDCT
                # ----------------------------------------

                modified_block = (
                    self.apply_idct(
                        coefficients
                    )
                )


                image_array[
                    row:row + self.BLOCK_SIZE,
                    col:col + self.BLOCK_SIZE
                ] = modified_block


        return image_array


    # ==================================================
    # EXTRACT
    # ==================================================

    def extract_bits(
        self,
        image_array,
        number_of_bits
    ):

        image_array = (
            image_array.astype(
                float
            )
        )


        height, width = (
            image_array.shape
        )


        bits = []


        for row in range(
            0,
            height - self.BLOCK_SIZE + 1,
            self.BLOCK_SIZE
        ):

            for col in range(
                0,
                width - self.BLOCK_SIZE + 1,
                self.BLOCK_SIZE
            ):

                if len(bits) >= number_of_bits:

                    return "".join(bits)[
                        :number_of_bits
                    ]


                block = image_array[
                    row:row + self.BLOCK_SIZE,
                    col:col + self.BLOCK_SIZE
                ]


                # ----------------------------------------
                # DCT
                # ----------------------------------------

                coefficients = (
                    self.apply_dct(
                        block
                    )
                )


                # ----------------------------------------
                # Extract bits
                # ----------------------------------------

                for position in (
                    self.EMBED_POSITIONS
                ):

                    if len(bits) >= number_of_bits:

                        return "".join(bits)[
                            :number_of_bits
                        ]


                    r, c = position


                    bit = (
                        self._extract_bit(
                            coefficients[
                                r,
                                c
                            ]
                        )
                    )


                    bits.append(
                        str(bit)
                    )


        result = "".join(bits)


        if len(result) < number_of_bits:

            raise ValueError(
                "Not enough data in the "
                "stego image."
            )


        return result[
            :number_of_bits
        ]


    # ==================================================
    # MSE
    # ==================================================

    def calculate_mse(
        self,
        original,
        modified
    ):

        difference = (
            original.astype(float)
            -
            modified.astype(float)
        )


        return np.mean(
            difference ** 2
        )


    # ==================================================
    # PSNR
    # ==================================================

    def calculate_psnr(
        self,
        original,
        modified
    ):

        mse = (
            self.calculate_mse(
                original,
                modified
            )
        )


        if mse == 0:

            return float("inf")


        return (
            10
            * np.log10(
                (255 ** 2) / mse
            )
        )