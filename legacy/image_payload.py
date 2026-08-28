from pathlib import Path


class ImagePayloadManager:


    # =========================================
    # Read image
    # =========================================

    def read_image(
        self,
        image_path
    ):

        image_path = Path(
            image_path
        )

        if not image_path.exists():

            raise FileNotFoundError(
                f"Secret image not found:\n"
                f"{image_path}"
            )

        return image_path.read_bytes()


    # =========================================
    # Save recovered image
    # =========================================

    def save_image(
        self,
        image_data,
        output_path
    ):

        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        output_path.write_bytes(
            image_data
        )

        return output_path