from pathlib import Path

from steganography_engine import SteganographyEngine


# ==================================================
# PROJECT DIRECTORY
# ==================================================


BASE_DIR = Path(__file__).resolve().parent


# ==================================================
# FILE PATHS
# ==================================================

cover_path = BASE_DIR / "image" / "babu.png"

stego_path = BASE_DIR / "image" / "stego_message.png"


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

print("Stego:")
print(stego_path)


# ==================================================
# CHECK FILES
# ==================================================

if not cover_path.exists():

    raise FileNotFoundError(
        f"\nCover image not found:\n{cover_path}"
    )


print()
print("Cover image found.")


# ==================================================
# CREATE ENGINE
# ==================================================

engine = SteganographyEngine(
    quantization_step=8
)


password = "mypassword123"

secret_message = input("Enter the secret message to hide: ")


# ==================================================
# ENCODE
# ==================================================

print()
print("==============================")
print("STARTING ENCODING")
print("==============================")


print()
print("Original message:")
print(secret_message)


result = engine.encode_text(
    cover_path=cover_path,
    output_path=stego_path,
    message=secret_message,
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


recovered_message = engine.decode_text(
    stego_path=stego_path,
    password=password
)


print()
print("==============================")
print("DECODING SUCCESSFUL")
print("==============================")


print(
    "Recovered message:",
    recovered_message
)


# ==================================================
# FINAL CHECK
# ==================================================

print()
print("==============================")
print("FINAL RESULT")
print("==============================")


if recovered_message == secret_message:

    print(
        "Message matches exactly. "
        "Text steganography successful!"
    )

else:

    print(
        "MISMATCH: recovered message "
        "does not match the original."
    )

    print()

    print("Original: ", secret_message)
    print("Recovered:", recovered_message)