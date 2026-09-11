import math
from pathlib import Path

from PIL import Image


def fit_cover_to_capacity(
    cover_path,
    required_bytes,
    block_size,
    bits_per_block
):

    cover_path = Path(cover_path)

    image = Image.open(cover_path).convert("L")

    width, height = image.size


    blocks_v = height // block_size

    blocks_h = width // block_size

    capacity_bytes = (
        blocks_v
        * blocks_h
        * bits_per_block
    ) // 8


    # Already big enough — use the original cover unchanged.

    if capacity_bytes >= required_bytes:

        return cover_path


    # ----------------------------------------------
    # Too small — work out the minimum size needed
    # and upscale, keeping the original aspect ratio.
    # ----------------------------------------------

    needed_bits = required_bytes * 8

    needed_blocks = math.ceil(
        needed_bits / bits_per_block
    )

    aspect = width / height

    blocks_h_needed = math.ceil(
        math.sqrt(needed_blocks * aspect)
    )

    blocks_v_needed = math.ceil(
        needed_blocks / blocks_h_needed
    )

    # +1 block safety margin so rounding never
    # lands just under the required capacity.

    new_width = (blocks_h_needed + 1) * block_size

    new_height = (blocks_v_needed + 1) * block_size

    resized = image.resize(
        (new_width, new_height),
        Image.LANCZOS
    )

    output_path = cover_path.with_name(
        cover_path.stem + "_fit.png"
    )

    resized.save(
        output_path,
        format="PNG"
    )

    print(
        f"\nCover image was too small "
        f"({width}x{height}, capacity "
        f"{capacity_bytes} bytes) for the "
        f"payload ({required_bytes} bytes).\n"
        f"Auto-resized cover to "
        f"{new_width}x{new_height} -> "
        f"{output_path}\n"
    )

    return output_path