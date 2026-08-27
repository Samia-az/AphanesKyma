from pathlib import Path
from PIL import Image


# --------------------------------
# 1. Find project directory
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent

image_path = BASE_DIR / "image" / "babu.png"

print("Looking for image at:")
print(image_path)


# --------------------------------
# 2. Check whether image exists
# --------------------------------

if not image_path.exists():
    print("ERROR: Image not found!")
    print("Make sure babu.jpg is inside the image folder.")
    exit()


# --------------------------------
# 3. Load image
# --------------------------------

image = Image.open(image_path)
image = image.convert("RGB")

print("\nImage loaded successfully!")

print("Image size:", image.size)
print("Image mode:", image.mode)


# --------------------------------
# 4. Get one pixel
# --------------------------------

x = 10
y = 10

r, g, b = image.getpixel((x, y))

print("\nOriginal pixel:")
print("R =", r)
print("G =", g)
print("B =", b)


# --------------------------------
# 5. Show binary values
# --------------------------------

print("\nBinary values:")

print("R:", format(r, "08b"))
print("G:", format(g, "08b"))
print("B:", format(b, "08b"))


# --------------------------------
# 6. Change the LSB of Red
# --------------------------------

secret_bit = 1

new_r = (r & 0b11111110) | secret_bit

print("\nModified Red:")
print("Old R:", r)
print("New R:", new_r)

print("Old binary:", format(r, "08b"))
print("New binary:", format(new_r, "08b"))


# --------------------------------
# 7. Change the pixel
# --------------------------------

image.putpixel((x, y), (new_r, g, b))


# --------------------------------
# 8. Save modified image
# --------------------------------

output_path = BASE_DIR / "image" / "modified.png"

image.save(output_path)

print("\nModified image saved at:")
print(output_path)