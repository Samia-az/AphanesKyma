import numpy as np

from crypto import CryptoManager
from payload import PayloadManager
from image_payload import ImagePayloadManager
from dct_steganography import DCTSteganographer


class SteganographyEngine:


    def __init__(
        self,
        quantization_step=8
    ):

        self.crypto = (
            CryptoManager()
        )

        self.payload = (
            PayloadManager()
        )

        self.image_payload = (
            ImagePayloadManager()
        )

        self.dct = (
            DCTSteganographer(
                quantization_step
            )
        )


    # ==================================================
    # ENCODE TEXT
    # ==================================================

    def encode_text(
        self,
        cover_path,
        output_path,
        message,
        password
    ):

        encrypted_data = (
            self.crypto.encrypt_text(
                message,
                password
            )
        )


        payload = (
            self.payload.create_payload(
                encrypted_data,
                self.payload.TYPE_TEXT
            )
        )


        return self._encode_payload(
            cover_path,
            output_path,
            payload
        )


    # ==================================================
    # DECODE TEXT
    # ==================================================

    def decode_text(
        self,
        stego_path,
        password
    ):

        payload = (
            self._extract_payload(
                stego_path
            )
        )


        data_type = (
            self.payload.get_data_type(
                payload
            )
        )


        if data_type != (
            self.payload.TYPE_TEXT
        ):

            raise ValueError(
                "The stego image does not "
                "contain a text message."
            )


        encrypted_data = (
            self.payload.extract_data(
                payload
            )
        )


        return self.crypto.decrypt_text(
            encrypted_data,
            password
        )


    # ==================================================
    # ENCODE IMAGE
    # ==================================================

    def encode_image(
        self,
        cover_path,
        output_path,
        secret_image_path,
        password
    ):

        print()
        print("==============================")
        print("Reading Secret Image")
        print("==============================")


        secret_data = (
            self.image_payload.read_image(
                secret_image_path
            )
        )


        print(
            "Secret image size:",
            len(secret_data),
            "bytes"
        )


        # ----------------------------------------------
        # Encrypt secret image
        # ----------------------------------------------

        encrypted_data = (
            self.crypto.encrypt_bytes(
                secret_data,
                password
            )
        )


        print(
            "Encrypted data size:",
            len(encrypted_data),
            "bytes"
        )


        # ----------------------------------------------
        # Create payload
        # ----------------------------------------------

        payload = (
            self.payload.create_payload(
                encrypted_data,
                self.payload.TYPE_IMAGE
            )
        )


        print(
            "Complete payload:",
            len(payload),
            "bytes"
        )


        # ----------------------------------------------
        # Embed
        # ----------------------------------------------

        return self._encode_payload(
            cover_path,
            output_path,
            payload
        )


    # ==================================================
    # DECODE IMAGE
    # ==================================================

    def decode_image(
        self,
        stego_path,
        output_path,
        password
    ):

        print()
        print("==============================")
        print("Extracting Secret Image")
        print("==============================")


        payload = (
            self._extract_payload(
                stego_path
            )
        )


        data_type = (
            self.payload.get_data_type(
                payload
            )
        )


        if data_type != (
            self.payload.TYPE_IMAGE
        ):

            raise ValueError(
                "The stego image does not "
                "contain a secret image."
            )


        encrypted_data = (
            self.payload.extract_data(
                payload
            )
        )


        print(
            "Encrypted data:",
            len(encrypted_data),
            "bytes"
        )


        # ----------------------------------------------
        # Decrypt
        # ----------------------------------------------

        secret_data = (
            self.crypto.decrypt_bytes(
                encrypted_data,
                password
            )
        )


        print(
            "Recovered image data:",
            len(secret_data),
            "bytes"
        )


        # ----------------------------------------------
        # Save
        # ----------------------------------------------

        output = (
            self.image_payload.save_image(
                secret_data,
                output_path
            )
        )


        return output


    # ==================================================
    # COMMON ENCODING
    # ==================================================

    def _encode_payload(
        self,
        cover_path,
        output_path,
        payload
    ):

        # ----------------------------------------------
        # Load cover
        # ----------------------------------------------

        image = self.dct.load_image(
            cover_path
        )


        image_array = np.array(
            image,
            dtype=float
        )


        original = (
            image_array.copy()
        )


        # ----------------------------------------------
        # Calculate capacity
        # ----------------------------------------------

        capacity = (
            self.dct.calculate_capacity(
                image_array
            )
        )


        required_bits = (
            len(payload) * 8
        )


        print()
        print("==============================")
        print("DCT Capacity")
        print("==============================")


        print(
            "Number of blocks:",
            capacity["blocks"]
        )


        print(
            "Bits per block:",
            capacity["bits_per_block"]
        )


        print(
            "Available bits:",
            capacity["bits"]
        )


        print(
            "Available bytes:",
            capacity["bytes"]
        )


        print(
            "Required bits:",
            required_bits
        )


        print(
            "Required bytes:",
            len(payload)
        )


        # ----------------------------------------------
        # Capacity check
        # ----------------------------------------------

        if required_bits > capacity["bits"]:

            raise ValueError(
                "\nSecret data is too large!\n\n"
                f"Required: "
                f"{required_bits} bits "
                f"({len(payload)} bytes)\n"
                f"Available: "
                f"{capacity['bits']} bits "
                f"({capacity['bytes']} bytes)\n\n"
                "Use a larger cover image "
                "or a smaller secret."
            )


        # ----------------------------------------------
        # Convert payload → bits
        # ----------------------------------------------

        bits = (
            self.payload.to_bits(
                payload
            )
        )


        # ----------------------------------------------
        # Embed using DCT
        # ----------------------------------------------

        stego_array = (
            self.dct.embed_bits(
                image_array,
                bits
            )
        )


        # ----------------------------------------------
        # Save
        # ----------------------------------------------

        self.dct.save_image(
            stego_array,
            output_path
        )


        # ----------------------------------------------
        # Quality
        # ----------------------------------------------

        mse = (
            self.dct.calculate_mse(
                original,
                stego_array
            )
        )


        psnr = (
            self.dct.calculate_psnr(
                original,
                stego_array
            )
        )


        print()
        print("==============================")
        print("Embedding Successful")
        print("==============================")


        print(
            "Payload:",
            len(payload),
            "bytes"
        )


        print(
            "Bits embedded:",
            len(bits)
        )


        print(
            "MSE:",
            mse
        )


        print(
            "PSNR:",
            psnr,
            "dB"
        )


        print()
        print(
            "Stego image:",
            output_path
        )


        return {
            "payload_size": len(payload),
            "bits": len(bits),
            "capacity": capacity,
            "mse": mse,
            "psnr": psnr
        }


    # ==================================================
    # COMMON EXTRACTION
    # ==================================================

    def _extract_payload(
        self,
        stego_path
    ):

        image = (
            self.dct.load_image(
                stego_path
            )
        )


        image_array = np.array(
            image,
            dtype=float
        )


        # ----------------------------------------------
        # Extract header first
        # ----------------------------------------------

        header_bits = (
            self.dct.extract_bits(
                image_array,
                self.payload.HEADER_SIZE * 8
            )
        )


        header = (
            self.payload.from_bits(
                header_bits
            )
        )


        # ----------------------------------------------
        # Validate header
        # ----------------------------------------------

        self.payload.validate_header(
            header
        )


        # ----------------------------------------------
        # Find payload size
        # ----------------------------------------------

        data_length = (
            self.payload.get_data_length(
                header
            )
        )


        total_bytes = (
            self.payload.HEADER_SIZE
            + data_length
        )


        total_bits = (
            total_bytes * 8
        )


        print(
            "Payload detected:",
            total_bytes,
            "bytes"
        )


        # ----------------------------------------------
        # Extract complete payload
        # ----------------------------------------------

        bits = (
            self.dct.extract_bits(
                image_array,
                total_bits
            )
        )


        payload = (
            self.payload.from_bits(
                bits
            )
        )


        # ----------------------------------------------
        # Validate
        # ----------------------------------------------

        self.payload.validate(
            payload
        )


        return payload