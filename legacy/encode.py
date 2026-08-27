from pathlib import Path
from PIL import Image

from crypto import encrypt_message


# --------------------------------
# 1. Project paths
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent

input_path = BASE_DIR / "image" / "babu.png"
output_path = BASE_DIR / "image" / "stego.png"


# --------------------------------
# 2. Get secret message
# --------------------------------

message = input("Enter secret message: ")

password = input("Enter password: ")


# --------------------------------
# 3. Encrypt message
# --------------------------------

encrypted_data = encrypt_message(
    message,
    password
)

print("\nMessage encrypted successfully!")

print("Encrypted data length:",
      len(encrypted_data),
      "bytes")


# --------------------------------
# 4. Convert encrypted data
#    to binary
# --------------------------------

binary_data = ""

for byte in encrypted_data:

    binary_data += format(byte, "08b")


print("Encrypted data bits:",
      len(binary_data))


# --------------------------------
# 5. Create MAGIC
# --------------------------------

magic = "APKY"

magic_bytes = magic.encode("ascii")

binary_magic = ""

for byte in magic_bytes:

    binary_magic += format(byte, "08b")


# --------------------------------
# 6. Store encrypted data length
# --------------------------------

data_length = len(encrypted_data)

binary_length = format(
    data_length,
    "032b"
)


# --------------------------------
# 7. Create payload
# --------------------------------

payload = (
    binary_magic
    + binary_length
    + binary_data
)


print("\nPayload information:")

print("MAGIC bits:", len(binary_magic))
print("Length bits:", len(binary_length))
print("Data bits:", len(binary_data))
print("Total bits:", len(payload))


# --------------------------------
# 8. Load image
# --------------------------------

image = Image.open(input_path).convert("RGB")

width, height = image.size


print("\nImage size:",
      width,
      "x",
      height)


# --------------------------------
# 9. Check image capacity
# --------------------------------

capacity = width * height * 3

print("Image capacity:",
      capacity,
      "bits")


if len(payload) > capacity:

    print("\nERROR:")
    print("Encrypted message is too large.")

    exit()


# --------------------------------
# 10. Embed payload
# --------------------------------

bit_index = 0


for y in range(height):

    for x in range(width):

        r, g, b = image.getpixel((x, y))


        # -------------------------
        # Red
        # -------------------------

        if bit_index < len(payload):

            bit = int(payload[bit_index])

            r = (r & 254) | bit

            bit_index += 1


        # -------------------------
        # Green
        # -------------------------

        if bit_index < len(payload):

            bit = int(payload[bit_index])

            g = (g & 254) | bit

            bit_index += 1


        # -------------------------
        # Blue
        # -------------------------

        if bit_index < len(payload):

            bit = int(payload[bit_index])

            b = (b & 254) | bit

            bit_index += 1


        image.putpixel(
            (x, y),
            (r, g, b)
        )


        if bit_index >= len(payload):

            break


    if bit_index >= len(payload):

        break


# --------------------------------
# 11. Save
# --------------------------------

image.save(output_path)


print("\n================================")
print("Message successfully hidden!")
print("================================")

print("Bits embedded:", bit_index)

print("Output:", output_path)