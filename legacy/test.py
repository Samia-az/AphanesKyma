from pathlib import Path

from dct_steganography import DCTSteganographer
from crypto import CryptoManager
from payload import PayloadManager


# =========================================
# Paths
# =========================================

BASE_DIR = Path(__file__).resolve().parent

cover_path = (
    BASE_DIR
    / "image"
    / "babu.png"
)

stego_path = (
    BASE_DIR
    / "image"
    / "stego_secure.png"
)


# =========================================
# Create objects
# =========================================

crypto = CryptoManager()

payload_manager = PayloadManager()

stego = DCTSteganographer(
    quantization_step=10
)


# =========================================
# User input
# =========================================

message = input(
    "Enter secret message: "
)

password = input(
    "Enter password: "
)


# =========================================
# ENCRYPT
# =========================================

encrypted_data = crypto.encrypt(
    message,
    password
)


print(
    "\nEncrypted data:",
    len(encrypted_data),
    "bytes"
)


# =========================================
# CREATE PAYLOAD
# =========================================

payload = payload_manager.create_payload(
    encrypted_data
)


bits = payload_manager.to_bits(
    payload
)


print(
    "Payload size:",
    len(payload),
    "bytes"
)

print(
    "Payload bits:",
    len(bits)
)


# =========================================
# LOAD COVER IMAGE
# =========================================

image = stego.load_image(
    cover_path
)

image_array = (
    __import__("numpy")
    .array(
        image,
        dtype=float
    )
)


original = image_array.copy()


# =========================================
# EMBED
# =========================================

stego_image = stego.embed_bits(
    image_array,
    bits
)


# =========================================
# SAVE
# =========================================

stego.save_image(
    stego_image,
    stego_path
)


print(
    "\nStego image created:"
)

print(stego_path)


# =========================================
# QUALITY
# =========================================

mse = stego.calculate_mse(
    original,
    stego_image
)

psnr = stego.calculate_psnr(
    original,
    stego_image
)


print(
    "\nMSE:",
    mse
)

print(
    "PSNR:",
    psnr,
    "dB"
)


# =========================================
# DECODE
# =========================================

stego_loaded = stego.load_image(
    stego_path
)

stego_array = (
    __import__("numpy")
    .array(
        stego_loaded,
        dtype=float
    )
)


# -----------------------------------------
# First extract header
# -----------------------------------------

HEADER_BITS = 10 * 8


header_bits = stego.extract_bits(
    stego_array,
    HEADER_BITS
)


header = payload_manager.from_bits(
    header_bits
)


# -----------------------------------------
# Find encrypted data length
# -----------------------------------------

data_length = (
    payload_manager.get_data_length(
        header
    )
)


print(
    "\nEncrypted data length:",
    data_length,
    "bytes"
)


# -----------------------------------------
# Extract complete payload
# -----------------------------------------

total_payload_bits = (
    (10 + data_length) * 8
)


all_bits = stego.extract_bits(
    stego_array,
    total_payload_bits
)


complete_payload = (
    payload_manager.from_bits(
        all_bits
    )
)


# =========================================
# VALIDATE
# =========================================

payload_manager.validate(
    complete_payload
)


# =========================================
# GET ENCRYPTED DATA
# =========================================

encrypted_data = (
    payload_manager.extract_data(
        complete_payload
    )
)


# =========================================
# DECRYPT
# =========================================

try:

    decrypted_message = crypto.decrypt(
        encrypted_data,
        password
    )


    print(
        "\n=============================="
    )

    print(
        "Decrypted message:"
    )

    print(
        decrypted_message
    )

    print(
        "=============================="
    )


except Exception:

    print(
        "\nDecryption failed!"
    )

    print(
        "Wrong password or corrupted data."
    )