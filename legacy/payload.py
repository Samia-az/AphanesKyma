import struct


class PayloadManager:

    MAGIC = b"APKY"

    VERSION = 1

    TYPE_TEXT = 1
    TYPE_IMAGE = 2

    HEADER_SIZE = 10


    # =========================================
    # Create payload
    # =========================================

    def create_payload(
        self,
        encrypted_data,
        data_type
    ):

        data_length = len(
            encrypted_data
        )

        header = (
            self.MAGIC
            + struct.pack(
                "B",
                self.VERSION
            )
            + struct.pack(
                "B",
                data_type
            )
            + struct.pack(
                ">I",
                data_length
            )
        )

        return header + encrypted_data


    # =========================================
    # Bytes → Bits
    # =========================================

    def to_bits(self, data):

        bits = ""

        for byte in data:

            bits += format(
                byte,
                "08b"
            )

        return bits


    # =========================================
    # Bits → Bytes
    # =========================================

    def from_bits(self, bits):

        data = bytearray()

        for i in range(
            0,
            len(bits),
            8
        ):

            byte_bits = bits[
                i:i + 8
            ]

            if len(byte_bits) < 8:

                break

            data.append(
                int(
                    byte_bits,
                    2
                )
            )

        return bytes(data)


    # =========================================
    # Read data length
    # =========================================

    def get_data_length(
        self,
        payload
    ):

        if len(payload) < self.HEADER_SIZE:

            raise ValueError(
                "Payload header is incomplete."
            )

        return struct.unpack(
            ">I",
            payload[6:10]
        )[0]


    # =========================================
    # Read data type
    # =========================================

    def get_data_type(
        self,
        payload
    ):

        if len(payload) < self.HEADER_SIZE:

            raise ValueError(
                "Payload header is incomplete."
            )

        return payload[5]


    # =========================================
    # Validate header
    # =========================================

    def validate_header(
        self,
        header
    ):

        if len(header) < self.HEADER_SIZE:

            raise ValueError(
                "Header is incomplete."
            )


        if header[:4] != self.MAGIC:

            raise ValueError(
                "This is not an AphanesKyma "
                "steganography image."
            )


        if header[4] != self.VERSION:

            raise ValueError(
                "Unsupported payload version."
            )


        data_type = self.get_data_type(
            header
        )


        if data_type not in (
            self.TYPE_TEXT,
            self.TYPE_IMAGE
        ):

            raise ValueError(
                "Unknown payload type."
            )


        return True


    # =========================================
    # Validate complete payload
    # =========================================

    def validate(
        self,
        payload
    ):

        self.validate_header(
            payload
        )

        data_length = (
            self.get_data_length(
                payload
            )
        )

        expected_size = (
            self.HEADER_SIZE
            + data_length
        )

        if len(payload) < expected_size:

            raise ValueError(
                "Payload is incomplete."
            )

        return True


    # =========================================
    # Extract encrypted data
    # =========================================

    def extract_data(
        self,
        payload
    ):

        data_length = (
            self.get_data_length(
                payload
            )
        )

        return payload[
            self.HEADER_SIZE:
            self.HEADER_SIZE + data_length
        ]