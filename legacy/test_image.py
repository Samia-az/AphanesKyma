from pathlib import Path

from steganography_engine import SteganographyEngine


# ==================================================
# PROJECT DIRECTORY
# ==================================================

# test_image.py is already inside:
#
# AphanesKyma/
#     legacy/
#         test_image.py
#
# Therefore .parent gives us the legacy folder.

BASE_DIR = Path(__file__).resolve().parent


# ==================================================
# FILE PATHS
# ==================================================

cover_path = BASE_DIR / "image" / "babu.png"

secret_path = BASE_DIR / "image" / "secret.png"

stego_path = BASE_DIR / "image" / "stego_secret.png"

recovered_path = BASE_DIR / "image" / "recovered_secret.png"


# ==================================================
# SHOW PATHS
# ==================================================

print()
print("==============================")
print("FILE PATHS")
print("==============================")

print("Cover:")
print(cover_path)

print()

print("Secret:")
print(secret_path)

print()

print("Stego:")
print(stego_path)

print()

print("Recovered:")
print(recovered_path)


# ==================================================
# CHECK FILES
# ==================================================

if not cover_path.exists():

    raise FileNotFoundError(
        f"\nCover image not found:\n{cover_path}"
    )


if not secret_path.exists():

    raise FileNotFoundError(
        f"\nSecret image not found:\n{secret_path}"
    )


print()
print("Cover image found.")
print("Secret image found.")


# ==================================================
# CREATE ENGINE
# ==================================================

engine = SteganographyEngine(
    quantization_step=8
)


password = "mypassword123"


# ==================================================
# ENCODE
# ==================================================

print()
print("==============================")
print("STARTING ENCODING")
print("==============================")


result = engine.encode_image(
    cover_path=cover_path,
    output_path=stego_path,
    secret_image_path=secret_path,
    password=password
)


print()
print("==============================")
print("ENCODING RESULT")
print("==============================")


print(
    "Payload size:",
    result["payload_size"],
    "bytes"
)


print(
    "Bits embedded:",
    result["bits"]
)


print(
    "MSE:",
    result["mse"]
)


print(
    "PSNR:",
    result["psnr"],
    "dB"
)


# ==================================================
# DECODE
# ==================================================

print()
print("==============================")
print("STARTING DECODING")
print("==============================")


recovered = engine.decode_image(
    stego_path=stego_path,
    output_path=recovered_path,
    password=password
)


print()
print("==============================")
print("DECODING SUCCESSFUL")
print("==============================")


print(
    "Recovered image:",
    recovered
)


# ==================================================
# FINAL CHECK
# ==================================================

if recovered_path.exists():

    print()
    print("==============================")
    print("FINAL RESULT")
    print("==============================")


    print(
        "Original secret:"
    )

    print(
        secret_path
    )


    print()

    print(
        "Recovered secret:"
    )

    print(
        recovered_path
    )


    print()

    print(
        "Secret image successfully "
        "embedded and recovered!"
    )