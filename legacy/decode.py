from pathlib import Path
from PIL import Image

from crypto import decrypt_message


# --------------------------------
# 1. Project paths
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent

image_path = BASE_DIR / "image" / "stego.png"


# --------------------------------
# 2. Load image
# --------------------------------

image = Image.open(image_path).convert("RGB")

width, height = image.size

print("Image loaded successfully!")

print("Image size:",
      width,
      "x",
      height)


# --------------------------------
# Helper function
# --------------------------------

def extract_bits(image, number_of_bits):

    width, height = image.size

    bits = ""

    count = 0


    for y in range(height):

        for x in range(width):

            r, g, b = image.getpixel((x, y))


            # Red

            if count < number_of_bits:

                bits += str(r & 1)

                count += 1


            # Green

            if count < number_of_bits:

                bits += str(g & 1)

                count += 1


            # Blue

            if count < number_of_bits:

                bits += str(b & 1)

                count += 1


            if count >= number_of_bits:

                return bits


    return bits


# --------------------------------
# 3. Extract MAGIC
# --------------------------------

binary_magic = extract_bits(
    image,
    32
)


# --------------------------------
# 4. Binary → MAGIC
# --------------------------------

magic_bytes = bytearray()


for i in range(0, 32, 8):

    byte = binary_magic[i:i + 8]

    value = int(byte, 2)

    magic_bytes.append(value)


magic = magic_bytes.decode("ascii")


print("\nMAGIC:", magic)


# --------------------------------
# 5. Check MAGIC
# --------------------------------

if magic != "APKY":

    print("\nERROR:")
    print("This is not a valid stego image.")

    exit()


print("Valid AphanesKyma stego image!")


# --------------------------------
# 6. Extract header
# --------------------------------

header = extract_bits(
    image,
    64
)


# First 32 bits = MAGIC
# Next 32 bits = data length

binary_length = header[32:64]


# --------------------------------
# 7. Convert length
# --------------------------------

data_length = int(
    binary_length,
    2
)


print("\nEncrypted data length:",
      data_length,
      "bytes")


# --------------------------------
# 8. Calculate total bits
# --------------------------------

data_bits = data_length * 8

total_bits = 64 + data_bits


print("Total bits:",
      total_bits)


# --------------------------------
# 9. Extract all data
# --------------------------------

all_bits = extract_bits(
    image,
    total_bits
)


binary_data = all_bits[64:]


# --------------------------------
# 10. Binary → bytes
# --------------------------------

encrypted_data = bytearray()


for i in range(
    0,
    len(binary_data),
    8
):

    byte = binary_data[i:i + 8]

    value = int(byte, 2)

    encrypted_data.append(value)


# --------------------------------
# 11. Ask for password
# --------------------------------

password = input(
    "\nEnter password: "
)


# --------------------------------
# 12. Decrypt
# --------------------------------

try:

    message = decrypt_message(
        bytes(encrypted_data),
        password
    )

    print("\n================================")
    print("Decrypted message:")
    print(message)
    print("================================")


except Exception:

    print("\nERROR:")
    print("Wrong password or corrupted data.")